from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Mapping

from research_platform.governance.api import RepositorySourceIndexPort
from research_platform.governance.system_registry.api import system_catalog


_BUDGET_FIELDS = (
    "top_level_systems",
    "subsystems",
    "contract_declarations",
    "authorities",
    "import_edges",
)
_BUDGET_PATH = Path("research_platform/governance/architecture/ARCHITECTURE_BUDGET.json")
_SCHEMA_VERSION = "architecture-complexity-budget.v2"
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ROLE_RE = re.compile(r"ROLE[0-9]{2}")
_MIGRATION_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
_REVIEWED_BUDGET_AUTHORITY_SHA256 = "4d11c3d4cab9f496e2f6365a65b69aeeea0c51dfae8ffd5a0b5b1d4a837bab42"

@dataclass(frozen=True, slots=True)
class ArchitectureComplexity:
    top_level_systems: int
    subsystems: int
    contract_declarations: int
    authorities: int
    import_edges: int


@dataclass(frozen=True, slots=True)
class ArchitectureBaselineAuthority:
    git_sha: str
    source_digest: str
    complexity: ArchitectureComplexity


@dataclass(frozen=True, slots=True)
class ArchitectureMigrationAllowance:
    migration_id: str
    owner_role: str
    source_git_sha: str
    delta: ArchitectureComplexity
    justification: str


@dataclass(frozen=True, slots=True)
class ArchitectureComplexityBudget:
    schema_version: str
    baseline: ArchitectureBaselineAuthority
    migrations: tuple[ArchitectureMigrationAllowance, ...]

    @property
    def limits(self) -> ArchitectureComplexity:
        values = {field: getattr(self.baseline.complexity, field) for field in _BUDGET_FIELDS}
        for migration in self.migrations:
            for field in _BUDGET_FIELDS:
                values[field] += getattr(migration.delta, field)
        return ArchitectureComplexity(**values)


@dataclass(frozen=True, slots=True)
class ArchitectureBudgetViolation:
    dimension: str
    observed: int
    limit: int
    detail: str


class ArchitectureBudgetProvenanceError(RuntimeError):
    pass


def architecture_budget_authority_digest(document: Mapping[str, object]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_architecture_complexity(*, import_edges: int) -> ArchitectureComplexity:
    descriptors = system_catalog()
    return ArchitectureComplexity(
        top_level_systems=sum(row.identity.is_system for row in descriptors),
        subsystems=sum(not row.identity.is_system for row in descriptors),
        contract_declarations=sum(len(row.requires) + len(row.provides) for row in descriptors),
        authorities=sum(len(row.authorities) for row in descriptors),
        import_edges=int(import_edges),
    )


def _decode_complexity(value: object, *, field: str) -> ArchitectureComplexity:
    if not isinstance(value, dict) or set(value) != set(_BUDGET_FIELDS):
        raise ValueError(f"{field} must define exactly {', '.join(_BUDGET_FIELDS)}")
    decoded: dict[str, int] = {}
    for key in _BUDGET_FIELDS:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise ValueError(f"{field}.{key} must be a non-negative integer")
        decoded[key] = raw
    return ArchitectureComplexity(**decoded)


def _canonical_git_sha(value: object, *, field: str) -> str:
    text = str(value)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ValueError(f"{field} must be an exact lowercase 40-character Git SHA")
    return text


def _canonical_sha256(value: object, *, field: str) -> str:
    text = str(value)
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{field} must be an exact lowercase SHA-256 digest")
    return text


def _decode_baseline(value: object) -> ArchitectureBaselineAuthority:
    expected = {"git_sha", "source_digest", "complexity"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("baseline must define exactly git_sha, source_digest and complexity")
    return ArchitectureBaselineAuthority(
        git_sha=_canonical_git_sha(value["git_sha"], field="baseline.git_sha"),
        source_digest=_canonical_sha256(value["source_digest"], field="baseline.source_digest"),
        complexity=_decode_complexity(value["complexity"], field="baseline.complexity"),
    )


def _decode_migration(value: object, *, index: int) -> ArchitectureMigrationAllowance:
    expected = {"migration_id", "owner_role", "source_git_sha", "delta", "justification"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"migrations[{index}] has unexpected fields")
    migration_id = str(value["migration_id"])
    if _MIGRATION_ID_RE.fullmatch(migration_id) is None:
        raise ValueError(f"migrations[{index}].migration_id is not canonical")
    owner_role = str(value["owner_role"])
    if _ROLE_RE.fullmatch(owner_role) is None:
        raise ValueError(f"migrations[{index}].owner_role must use ROLE## identity")
    justification = str(value["justification"]).strip()
    if len(justification) < 48:
        raise ValueError(f"migrations[{index}].justification must be substantive")
    delta = _decode_complexity(value["delta"], field=f"migrations[{index}].delta")
    if all(getattr(delta, field) == 0 for field in _BUDGET_FIELDS):
        raise ValueError(f"migrations[{index}].delta must contain reviewed growth")
    return ArchitectureMigrationAllowance(
        migration_id=migration_id,
        owner_role=owner_role,
        source_git_sha=_canonical_git_sha(
            value["source_git_sha"], field=f"migrations[{index}].source_git_sha"
        ),
        delta=delta,
        justification=justification,
    )


def _read_budget_document(
    root: Path,
    *,
    source_index: RepositorySourceIndexPort | None,
) -> tuple[Path, dict[str, object]]:
    path = Path(root).resolve() / _BUDGET_PATH
    try:
        raw = (
            source_index.text(_BUDGET_PATH.as_posix())
            if source_index is not None
            else path.read_text(encoding="utf-8")
        )
        document = json.loads(raw)
    except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"architecture complexity budget unavailable: {path}") from exc
    if not isinstance(document, dict):
        raise ValueError("architecture complexity budget must be a JSON object")
    return path, document


def load_architecture_complexity_budget(
    root: Path,
    *,
    source_index: RepositorySourceIndexPort | None = None,
    expected_authority_sha256: str | None = _REVIEWED_BUDGET_AUTHORITY_SHA256,
) -> ArchitectureComplexityBudget:
    _path, document = _read_budget_document(root, source_index=source_index)
    if expected_authority_sha256 is not None:
        expected = _canonical_sha256(expected_authority_sha256, field="review authority")
        observed = architecture_budget_authority_digest(document)
        if observed != expected:
            raise ArchitectureBudgetProvenanceError(
                f"architecture budget review authority mismatch: observed={observed} expected={expected}"
            )
    expected_fields = {"schema_version", "baseline", "migrations"}
    if set(document) != expected_fields:
        raise ValueError("architecture complexity budget has unexpected fields")
    if document["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("unsupported architecture complexity budget schema")
    baseline = _decode_baseline(document["baseline"])
    raw_migrations = document["migrations"]
    if not isinstance(raw_migrations, list):
        raise ValueError("migrations must be a JSON array")
    migrations = tuple(
        _decode_migration(value, index=index)
        for index, value in enumerate(raw_migrations)
    )
    migration_ids = tuple(item.migration_id for item in migrations)
    if len(migration_ids) != len(set(migration_ids)):
        raise ValueError("migration_id values must be unique")
    source_bindings = tuple((item.owner_role, item.source_git_sha) for item in migrations)
    if len(source_bindings) != len(set(source_bindings)):
        raise ValueError("migration source bindings must be unique per owner role")
    return ArchitectureComplexityBudget(
        schema_version=_SCHEMA_VERSION,
        baseline=baseline,
        migrations=migrations,
    )


def verify_architecture_baseline_authority(
    budget: ArchitectureComplexityBudget,
    *,
    git_sha: str,
    source_digest: str,
    complexity: ArchitectureComplexity,
) -> None:
    canonical_git_sha = _canonical_git_sha(git_sha, field="observed baseline git_sha")
    canonical_source_digest = _canonical_sha256(
        source_digest, field="observed baseline source_digest"
    )
    mismatches: list[str] = []
    if canonical_git_sha != budget.baseline.git_sha:
        mismatches.append(
            f"git_sha observed={canonical_git_sha} expected={budget.baseline.git_sha}"
        )
    if canonical_source_digest != budget.baseline.source_digest:
        mismatches.append(
            "source_digest observed="
            f"{canonical_source_digest} expected={budget.baseline.source_digest}"
        )
    if complexity != budget.baseline.complexity:
        mismatches.append(
            f"complexity observed={complexity!r} expected={budget.baseline.complexity!r}"
        )
    if mismatches:
        raise ArchitectureBudgetProvenanceError(
            "architecture baseline authority mismatch: " + "; ".join(mismatches)
        )


def verify_architecture_migration_sources(
    budget: ArchitectureComplexityBudget,
    observed_by_git_sha: Mapping[str, ArchitectureComplexity],
) -> None:
    for migration in budget.migrations:
        observed = observed_by_git_sha.get(migration.source_git_sha)
        if observed is None:
            raise ArchitectureBudgetProvenanceError(
                f"migration source unavailable: {migration.migration_id} {migration.source_git_sha}"
            )
        expected_values = {
            field: getattr(budget.baseline.complexity, field) + getattr(migration.delta, field)
            for field in _BUDGET_FIELDS
        }
        expected = ArchitectureComplexity(**expected_values)
        if observed != expected:
            raise ArchitectureBudgetProvenanceError(
                f"migration source delta mismatch: {migration.migration_id} "
                f"observed={observed!r} expected={expected!r}"
            )


def audit_architecture_complexity_budget(
    root: Path,
    *,
    import_edges: int,
    source_index: RepositorySourceIndexPort | None = None,
    expected_authority_sha256: str | None = _REVIEWED_BUDGET_AUTHORITY_SHA256,
) -> tuple[
    ArchitectureComplexity,
    ArchitectureComplexityBudget | None,
    tuple[ArchitectureBudgetViolation, ...],
]:
    current = current_architecture_complexity(import_edges=import_edges)
    if source_index is not None:
        architecture_marker = "research_platform/governance/architecture/report.py"
        if not any(
            blob.relative_path == architecture_marker
            for blob in source_index.documents(suffixes={".py"})
        ):
            return current, None, ()
    budget = load_architecture_complexity_budget(
        root,
        source_index=source_index,
        expected_authority_sha256=expected_authority_sha256,
    )
    limits = budget.limits
    violations: list[ArchitectureBudgetViolation] = []
    for field in _BUDGET_FIELDS:
        observed = getattr(current, field)
        limit = getattr(limits, field)
        if observed > limit:
            violations.append(ArchitectureBudgetViolation(
                dimension=field,
                observed=observed,
                limit=limit,
                detail=f"{field} complexity budget exceeded: observed={observed} limit={limit}",
            ))
    return current, budget, tuple(violations)


__all__ = [
    "ArchitectureBaselineAuthority",
    "ArchitectureBudgetProvenanceError",
    "ArchitectureBudgetViolation",
    "ArchitectureComplexity",
    "ArchitectureComplexityBudget",
    "ArchitectureMigrationAllowance",
    "architecture_budget_authority_digest",
    "audit_architecture_complexity_budget",
    "current_architecture_complexity",
    "load_architecture_complexity_budget",
    "verify_architecture_baseline_authority",
    "verify_architecture_migration_sources",
]
