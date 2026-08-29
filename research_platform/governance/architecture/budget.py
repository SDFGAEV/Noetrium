from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

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


@dataclass(frozen=True, slots=True)
class ArchitectureComplexity:
    top_level_systems: int
    subsystems: int
    contract_declarations: int
    authorities: int
    import_edges: int


@dataclass(frozen=True, slots=True)
class ArchitectureComplexityBudget:
    schema_version: str
    baseline_git_sha: str
    baseline: ArchitectureComplexity
    limits: ArchitectureComplexity
    migration_id: str
    growth_justification: str


@dataclass(frozen=True, slots=True)
class ArchitectureBudgetViolation:
    dimension: str
    observed: int
    limit: int
    detail: str


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


def load_architecture_complexity_budget(
    root: Path,
    *,
    source_index: RepositorySourceIndexPort | None = None,
) -> ArchitectureComplexityBudget:
    path = Path(root).resolve() / _BUDGET_PATH
    try:
        raw = (
            source_index.text(_BUDGET_PATH.as_posix())
            if source_index is not None
            else path.read_text(encoding="utf-8")
        )
        document = json.loads(raw)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"architecture complexity budget unavailable: {path}") from exc
    expected = {
        "schema_version", "baseline_git_sha", "baseline", "limits",
        "migration_id", "growth_justification",
    }
    if not isinstance(document, dict) or set(document) != expected:
        raise ValueError("architecture complexity budget has unexpected fields")
    if document["schema_version"] != "architecture-complexity-budget.v1":
        raise ValueError("unsupported architecture complexity budget schema")
    baseline_git_sha = str(document["baseline_git_sha"])
    if len(baseline_git_sha) != 40:
        raise ValueError("baseline_git_sha must be an exact 40-character Git SHA")
    baseline = _decode_complexity(document["baseline"], field="baseline")
    limits = _decode_complexity(document["limits"], field="limits")
    migration_id = str(document["migration_id"]).strip()
    justification = str(document["growth_justification"]).strip()
    raised = tuple(
        field for field in _BUDGET_FIELDS if getattr(limits, field) > getattr(baseline, field)
    )
    if raised and (not migration_id or len(justification) < 24):
        raise ValueError(
            "architecture budget growth requires migration_id and substantive authority/lifecycle justification"
        )
    return ArchitectureComplexityBudget(
        schema_version=document["schema_version"],
        baseline_git_sha=baseline_git_sha,
        baseline=baseline,
        limits=limits,
        migration_id=migration_id,
        growth_justification=justification,
    )


def audit_architecture_complexity_budget(
    root: Path,
    *,
    import_edges: int,
    source_index: RepositorySourceIndexPort | None = None,
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
    budget = load_architecture_complexity_budget(root, source_index=source_index)
    violations: list[ArchitectureBudgetViolation] = []
    for field in _BUDGET_FIELDS:
        observed = getattr(current, field)
        limit = getattr(budget.limits, field)
        if observed > limit:
            violations.append(ArchitectureBudgetViolation(
                dimension=field,
                observed=observed,
                limit=limit,
                detail=f"{field} complexity budget exceeded: observed={observed} limit={limit}",
            ))
    return current, budget, tuple(violations)


__all__ = [
    "ArchitectureBudgetViolation",
    "ArchitectureComplexity",
    "ArchitectureComplexityBudget",
    "audit_architecture_complexity_budget",
    "current_architecture_complexity",
    "load_architecture_complexity_budget",
]
