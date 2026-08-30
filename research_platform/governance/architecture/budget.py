from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping

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
_SCHEMA_VERSION = "architecture-complexity-budget.v3"
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ROLE_RE = re.compile(r"ROLE[0-9]{2}")
_MIGRATION_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
_MODULE_PREFIX_RE = re.compile(r"research_platform(?:\.[a-z_][a-z0-9_]*)+")

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
    approval_status: str
    approval_authority: str
    approval_evidence_ref: str
    module_prefixes: tuple[str, ...]
    import_projection_sha256: str | None

    @property
    def approved(self) -> bool:
        return self.approval_status == "approved"


@dataclass(frozen=True, slots=True)
class ArchitectureMigrationObservation:
    complexity: ArchitectureComplexity
    import_projection_sha256: str | None


@dataclass(frozen=True, slots=True)
class ArchitectureComplexityBudget:
    schema_version: str
    baseline: ArchitectureBaselineAuthority
    migrations: tuple[ArchitectureMigrationAllowance, ...]
    effective_limits: ArchitectureComplexity
    applicable_migration_ids: tuple[str, ...]

    @property
    def limits(self) -> ArchitectureComplexity:
        return self.effective_limits


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


def import_projection_digest(
    import_edge_pairs: Iterable[tuple[str, str]],
    module_prefixes: Iterable[str],
) -> str:
    prefixes = tuple(module_prefixes)
    pairs = sorted(
        (str(source), str(target))
        for source, target in import_edge_pairs
        if any(source == prefix or source.startswith(prefix + ".") for prefix in prefixes)
    )
    raw = json.dumps(pairs, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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

def _decode_approval(value: object, *, index: int) -> tuple[str, str, str]:
    expected = {"status", "authority", "evidence_ref"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"migrations[{index}].approval has unexpected fields")
    status = str(value["status"])
    if status not in {"approved", "proposed"}:
        raise ValueError(f"migrations[{index}].approval.status must be approved or proposed")
    authority = str(value["authority"])
    if authority != "ROLE00":
        raise ValueError(f"migrations[{index}].approval.authority must be ROLE00")
    evidence_ref = str(value["evidence_ref"]).strip()
    if len(evidence_ref) < 16:
        raise ValueError(f"migrations[{index}].approval.evidence_ref is too weak")
    return status, authority, evidence_ref


def _decode_applicability(
    value: object,
    *,
    index: int,
    approved: bool,
) -> tuple[tuple[str, ...], str | None]:
    if value is None:
        if approved:
            raise ValueError(f"migrations[{index}] approved allowance requires applicability binding")
        return (), None
    expected = {"module_prefixes", "import_projection_sha256"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"migrations[{index}].applicability has unexpected fields")
    raw_prefixes = value["module_prefixes"]
    if not isinstance(raw_prefixes, list) or not raw_prefixes:
        raise ValueError(f"migrations[{index}].applicability.module_prefixes must be non-empty")
    prefixes = tuple(str(item) for item in raw_prefixes)
    if len(prefixes) != len(set(prefixes)):
        raise ValueError(f"migrations[{index}].applicability.module_prefixes must be unique")
    if any(_MODULE_PREFIX_RE.fullmatch(prefix) is None for prefix in prefixes):
        raise ValueError(f"migrations[{index}].applicability.module_prefixes are not canonical")
    projection = _canonical_sha256(
        value["import_projection_sha256"],
        field=f"migrations[{index}].applicability.import_projection_sha256",
    )
    return prefixes, projection


def _decode_migration(value: object, *, index: int) -> ArchitectureMigrationAllowance:
    expected = {
        "migration_id", "owner_role", "source_git_sha", "delta", "justification",
        "approval", "applicability",
    }
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
    approval_status, approval_authority, approval_evidence_ref = _decode_approval(
        value["approval"], index=index
    )
    module_prefixes, projection = _decode_applicability(
        value["applicability"], index=index, approved=approval_status == "approved"
    )
    return ArchitectureMigrationAllowance(
        migration_id=migration_id,
        owner_role=owner_role,
        source_git_sha=_canonical_git_sha(
            value["source_git_sha"], field=f"migrations[{index}].source_git_sha"
        ),
        delta=delta,
        justification=justification,
        approval_status=approval_status,
        approval_authority=approval_authority,
        approval_evidence_ref=approval_evidence_ref,
        module_prefixes=module_prefixes,
        import_projection_sha256=projection,
    )


def _read_budget_document(
    root: Path,
    *,
    source_index: RepositorySourceIndexPort | None,
) -> tuple[Path, dict[str, object]]:
    path = Path(root).resolve() / _BUDGET_PATH
    try:
        raw = source_index.text(_BUDGET_PATH.as_posix()) if source_index is not None else path.read_text(encoding="utf-8")
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
    expected_authority_sha256: str | None = None,
) -> ArchitectureComplexityBudget:
    _path, document = _read_budget_document(root, source_index=source_index)
    if expected_authority_sha256 is not None:
        expected = _canonical_sha256(expected_authority_sha256, field="review authority")
        observed = architecture_budget_authority_digest(document)
        if observed != expected:
            raise ArchitectureBudgetProvenanceError(
                f"architecture budget document digest mismatch: observed={observed} expected={expected}"
            )
    if set(document) != {"schema_version", "baseline", "migrations"}:
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
    return ArchitectureComplexityBudget(
        schema_version=_SCHEMA_VERSION,
        baseline=baseline,
        migrations=migrations,
        effective_limits=baseline.complexity,
        applicable_migration_ids=(),
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
        mismatches.append(f"git_sha observed={canonical_git_sha} expected={budget.baseline.git_sha}")
    if canonical_source_digest != budget.baseline.source_digest:
        mismatches.append(
            f"source_digest observed={canonical_source_digest} expected={budget.baseline.source_digest}"
        )
    if complexity != budget.baseline.complexity:
        mismatches.append(f"complexity observed={complexity!r} expected={budget.baseline.complexity!r}")
    if mismatches:
        raise ArchitectureBudgetProvenanceError(
            "architecture baseline authority mismatch: " + "; ".join(mismatches)
        )


def verify_architecture_migration_sources(
    budget: ArchitectureComplexityBudget,
    observed_by_git_sha: Mapping[str, ArchitectureMigrationObservation],
) -> None:
    for migration in budget.migrations:
        if not migration.approved:
            continue
        observed = observed_by_git_sha.get(migration.source_git_sha)
        if observed is None:
            raise ArchitectureBudgetProvenanceError(
                f"approved migration source unavailable: {migration.migration_id} {migration.source_git_sha}"
            )
        expected_values = {
            field: getattr(budget.baseline.complexity, field) + getattr(migration.delta, field)
            for field in _BUDGET_FIELDS
        }
        expected = ArchitectureComplexity(**expected_values)
        if observed.complexity != expected:
            raise ArchitectureBudgetProvenanceError(
                f"migration source delta mismatch: {migration.migration_id} "
                f"observed={observed.complexity!r} expected={expected!r}"
            )
        if observed.import_projection_sha256 != migration.import_projection_sha256:
            raise ArchitectureBudgetProvenanceError(
                f"migration import projection mismatch: {migration.migration_id} "
                f"observed={observed.import_projection_sha256} "
                f"expected={migration.import_projection_sha256}"
            )


def source_catalog_complexity(source_index: RepositorySourceIndexPort, *, import_edges: int) -> ArchitectureComplexity:
    document = json.loads(
        source_index.text("research_platform/governance/system_registry/catalog.json")
    )
    if not isinstance(document, dict):
        raise ArchitectureBudgetProvenanceError("historical system catalog is not an object")
    rows = tuple(document.values())
    if any(not isinstance(row, dict) for row in rows):
        raise ArchitectureBudgetProvenanceError("historical system catalog contains non-object rows")
    return ArchitectureComplexity(
        top_level_systems=sum(row.get("parent") is None for row in rows),
        subsystems=sum(row.get("parent") is not None for row in rows),
        contract_declarations=sum(
            len(row.get("requires", ())) + len(row.get("provides", ())) for row in rows
        ),
        authorities=sum(bool(row.get("authority")) for row in rows),
        import_edges=int(import_edges),
    )


def _verify_budget_provenance(
    budget: ArchitectureComplexityBudget,
    *,
    historical_observation_resolver: Callable[[str, tuple[str, ...]], tuple[str, ArchitectureMigrationObservation]] | None,
) -> None:
    if historical_observation_resolver is None:
        raise ArchitectureBudgetProvenanceError(
            "formal architecture budget verification requires immutable historical observations"
        )
    baseline_digest, baseline_observation = historical_observation_resolver(
        budget.baseline.git_sha,
        (),
    )
    verify_architecture_baseline_authority(
        budget,
        git_sha=budget.baseline.git_sha,
        source_digest=baseline_digest,
        complexity=baseline_observation.complexity,
    )
    observations: dict[str, ArchitectureMigrationObservation] = {}
    for migration in budget.migrations:
        if not migration.approved:
            continue
        _digest, observation = historical_observation_resolver(
            migration.source_git_sha,
            migration.module_prefixes,
        )
        observations[migration.source_git_sha] = observation
    verify_architecture_migration_sources(budget, observations)

def _effective_budget(
    budget: ArchitectureComplexityBudget,
    *,
    import_edge_pairs: Iterable[tuple[str, str]],
) -> ArchitectureComplexityBudget:
    pairs = tuple(import_edge_pairs)
    values = {field: getattr(budget.baseline.complexity, field) for field in _BUDGET_FIELDS}
    applicable: list[str] = []
    for migration in budget.migrations:
        if not migration.approved:
            continue
        if not migration.module_prefixes or migration.import_projection_sha256 is None:
            raise ArchitectureBudgetProvenanceError(
                f"approved migration has no applicability binding: {migration.migration_id}"
            )
        observed_projection = import_projection_digest(pairs, migration.module_prefixes)
        if observed_projection != migration.import_projection_sha256:
            continue
        applicable.append(migration.migration_id)
        for field in _BUDGET_FIELDS:
            values[field] += getattr(migration.delta, field)
    return replace(
        budget,
        effective_limits=ArchitectureComplexity(**values),
        applicable_migration_ids=tuple(applicable),
    )


def audit_architecture_complexity_budget(
    root: Path,
    *,
    import_edges: int,
    import_edge_pairs: Iterable[tuple[str, str]] = (),
    source_index: RepositorySourceIndexPort | None = None,
    historical_observation_resolver: Callable[[str, tuple[str, ...]], tuple[str, ArchitectureMigrationObservation]] | None = None,
    verify_provenance: bool | None = None,
    expected_authority_sha256: str | None = None,
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
    formal = (
        source_index is not None and source_index.source_authority == "git"
        if verify_provenance is None
        else bool(verify_provenance)
    )
    if formal:
        if source_index is None or source_index.source_authority != "git":
            raise ArchitectureBudgetProvenanceError(
                "formal architecture budget verification requires Git source authority"
            )
        _verify_budget_provenance(budget, historical_observation_resolver=historical_observation_resolver)
    evaluated = _effective_budget(budget, import_edge_pairs=import_edge_pairs)
    limits = evaluated.limits
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
    return current, evaluated, tuple(violations)

__all__ = [
    "ArchitectureBaselineAuthority",
    "ArchitectureBudgetProvenanceError",
    "ArchitectureBudgetViolation",
    "ArchitectureComplexity",
    "ArchitectureComplexityBudget",
    "ArchitectureMigrationAllowance",
    "ArchitectureMigrationObservation",
    "architecture_budget_authority_digest",
    "audit_architecture_complexity_budget",
    "current_architecture_complexity",
    "import_projection_digest",
    "load_architecture_complexity_budget",
    "import_projection_digest",
    "source_catalog_complexity",
    "verify_architecture_baseline_authority",
    "verify_architecture_migration_sources",
]
