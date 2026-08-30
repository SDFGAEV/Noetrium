from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from research_platform.governance.api import RepositorySourceIndexPort
from research_platform.platform.kernel import canonical_digest

from .audit import AuditViolation
from .budget import (
    ArchitectureBudgetViolation,
    ArchitectureComplexity,
    ArchitectureComplexityBudget,
    ArchitectureMigrationApprovalSet,
    ArchitectureMigrationObservation,
    audit_architecture_complexity_budget,
    import_projection_digest,
    load_architecture_migration_approval_set,
    source_catalog_complexity,
    source_scope_digest,
)
from .hotspots import ModuleHotspot
from .import_graph import (
    ImportViolation,
    LayerViolation,
    architecture_import_rules,
    audit_import_rules,
    audit_layer_dag,
    package_cycles,
)
from .optimization import ModuleOptimizationProfile
from .platform_policy import build_platform_audit
from .seam_graphs import SeamEdge, declared_capability_graph, partition_seam_graphs
from .source_authority import architecture_source_authority_rules
from .source_authority_contracts import SourceAuthorityViolation
from .source_index import architecture_source_index
from .source_invariants import audit_source_invariants
from .source_profile import scan_architecture_source_profile
from .source_scan import SourceInvariantViolation
from .system_graphs import (
    SubsystemGraphEdge,
    SystemGraphEdge,
    declared_subsystem_graph,
    declared_system_graph,
)


@dataclass(frozen=True, slots=True)
class ImportViolationRecord:
    source: str
    target: str
    path: str
    line: int
    reason: str

    @classmethod
    def from_violation(cls, violation: ImportViolation) -> "ImportViolationRecord":
        return cls(
            source=violation.edge.source_module,
            target=violation.edge.target_module,
            path=violation.edge.path,
            line=violation.edge.line,
            reason=violation.reason,
        )


@dataclass(frozen=True, slots=True)
class LayerViolationRecord:
    source: str
    target: str
    path: str
    line: int
    source_layer: str
    target_layer: str
    reason: str

    @classmethod
    def from_violation(cls, violation: LayerViolation) -> "LayerViolationRecord":
        return cls(
            source=violation.edge.source_module,
            target=violation.edge.target_module,
            path=violation.edge.path,
            line=violation.edge.line,
            source_layer=violation.source_layer,
            target_layer=violation.target_layer,
            reason=violation.reason,
        )


@dataclass(frozen=True, slots=True)
class ArchitectureReport:
    source_root: str
    source_digest: str
    import_edges: int
    import_violations: tuple[ImportViolationRecord, ...]
    layer_violations: tuple[LayerViolationRecord, ...]
    package_cycles: tuple[tuple[str, ...], ...]
    declared_authority_violations: tuple[AuditViolation, ...]
    source_invariant_violations: tuple[SourceInvariantViolation, ...]
    source_authority_violations: tuple[SourceAuthorityViolation, ...]
    architecture_complexity: ArchitectureComplexity
    architecture_complexity_budget: ArchitectureComplexityBudget | None
    architecture_budget_violations: tuple[ArchitectureBudgetViolation, ...]
    top_hotspots: tuple[ModuleHotspot, ...]
    top_optimization_risks: tuple[ModuleOptimizationProfile, ...]
    capability_graph: tuple[SeamEdge, ...]
    operation_graph: tuple[SeamEdge, ...]
    event_graph: tuple[SeamEdge, ...]
    system_graph: tuple[SystemGraphEdge, ...]
    subsystem_graph: tuple[SubsystemGraphEdge, ...]
    report_sha256: str

    @property
    def clean(self) -> bool:
        return not (
            self.import_violations
            or self.layer_violations
            or self.package_cycles
            or self.declared_authority_violations
            or self.source_invariant_violations
            or self.source_authority_violations
            or self.architecture_budget_violations
        )


def build_architecture_report(
    root: Path,
    *,
    hotspot_limit: int = 20,
    source_index: RepositorySourceIndexPort | None = None,
    historical_source_index_factory: Callable[[str], RepositorySourceIndexPort] | None = None,
    migration_approval_set: ArchitectureMigrationApprovalSet | None = None,
) -> ArchitectureReport:
    root = Path(root).resolve()
    if source_index is None:
        from .composition.report import build_architecture_report as compose_architecture_report

        return compose_architecture_report(root, hotspot_limit=hotspot_limit)
    authority_rules = architecture_source_authority_rules(root)
    profile = scan_architecture_source_profile(
        root, source_index=source_index, authority_rules=authority_rules
    )
    with architecture_source_index(
        root, max_entries=128, repository_index=source_index
    ) as architecture_index:
        architecture_index.seed_imports(
            (root / fact.path, fact.imports) for fact in profile.import_facts
        )
        architecture_index.seed_import_edges(("research_platform", "projects"), profile.import_edges)
        architecture_index.seed_import_edges(
            ("research_platform",),
            (
                edge
                for edge in profile.import_edges
                if edge.source_module.startswith("research_platform")
            ),
        )
        source_invariant_violations = audit_source_invariants(root)

    edges = profile.import_edges
    import_violations = tuple(
        ImportViolationRecord.from_violation(item)
        for item in audit_import_rules(edges, architecture_import_rules(root))
    )
    layer_violations = tuple(
        LayerViolationRecord.from_violation(item)
        for item in audit_layer_dag(root, edges)
    )
    cycles = package_cycles(edges)
    declared_authority_violations = build_platform_audit().run()
    hotspots = profile.hotspots[:hotspot_limit]
    risks = profile.optimization_risks[:hotspot_limit]
    source_authority_violations = profile.authority_violations
    historical_observation_resolver = None
    if historical_source_index_factory is not None:
        def historical_observation_resolver(
            git_sha: str, module_prefixes: tuple[str, ...]
        ) -> tuple[str, ArchitectureMigrationObservation]:
            historical_index = historical_source_index_factory(git_sha)
            historical_profile = scan_architecture_source_profile(
                root, source_index=historical_index
            )
            historical_pairs = tuple(
                (edge.source_module, edge.target_module)
                for edge in historical_profile.import_edges
            )
            projection = (
                import_projection_digest(historical_pairs, module_prefixes)
                if module_prefixes else None
            )
            return historical_index.source_digest, ArchitectureMigrationObservation(
                complexity=source_catalog_complexity(
                    historical_index, import_edges=len(historical_profile.import_edges)
                ),
                import_projection_sha256=projection,
                owner_source_sha256=(
                    source_scope_digest(historical_index, module_prefixes)
                    if module_prefixes else None
                ),
            )

    architecture_complexity, architecture_complexity_budget, architecture_budget_violations = (
        audit_architecture_complexity_budget(
            root,
            import_edges=len(edges),
            import_edge_pairs=tuple(
                (edge.source_module, edge.target_module) for edge in edges
            ),
            source_index=source_index,
            approval_set=migration_approval_set,
            historical_observation_resolver=historical_observation_resolver,
        )
    )
    declared_audit = build_platform_audit()
    capability_graph, operation_graph, event_graph = partition_seam_graphs(
        profile.seam_edges,
        declared_capabilities=declared_capability_graph(declared_audit),
    )
    system_graph = declared_system_graph()
    subsystem_graph = declared_subsystem_graph()

    payload = {
        "source_root": str(root),
        "source_digest": source_index.source_digest,
        "import_edges": len(edges),
        "import_violations": [asdict(item) for item in import_violations],
        "layer_violations": [asdict(item) for item in layer_violations],
        "package_cycles": [list(item) for item in cycles],
        "declared_authority_violations": [asdict(item) for item in declared_authority_violations],
        "source_invariant_violations": [asdict(item) for item in source_invariant_violations],
        "source_authority_violations": [asdict(item) for item in source_authority_violations],
        "architecture_complexity": asdict(architecture_complexity),
        "architecture_complexity_budget": (
            asdict(architecture_complexity_budget)
            if architecture_complexity_budget is not None
            else None
        ),
        "architecture_budget_violations": [asdict(item) for item in architecture_budget_violations],
        "top_hotspots": [asdict(item) for item in hotspots],
        "top_optimization_risks": [asdict(item) for item in risks],
        "capability_graph": [asdict(item) for item in capability_graph],
        "operation_graph": [asdict(item) for item in operation_graph],
        "event_graph": [asdict(item) for item in event_graph],
        "system_graph": [asdict(item) for item in system_graph],
        "subsystem_graph": [asdict(item) for item in subsystem_graph],
    }
    identity = {key: value for key, value in payload.items() if key != "source_root"}
    digest = canonical_digest(identity)

    return ArchitectureReport(
        source_root=payload["source_root"],
        source_digest=payload["source_digest"],
        import_edges=len(edges),
        import_violations=import_violations,
        layer_violations=layer_violations,
        package_cycles=cycles,
        declared_authority_violations=declared_authority_violations,
        source_invariant_violations=source_invariant_violations,
        source_authority_violations=source_authority_violations,
        architecture_complexity=architecture_complexity,
        architecture_complexity_budget=architecture_complexity_budget,
        architecture_budget_violations=architecture_budget_violations,
        top_hotspots=hotspots,
        top_optimization_risks=risks,
        capability_graph=capability_graph,
        operation_graph=operation_graph,
        event_graph=event_graph,
        system_graph=system_graph,
        subsystem_graph=subsystem_graph,
        report_sha256=digest,
    )
