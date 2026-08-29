from .audit import ArchitectureAudit, AuditViolation, ComponentDescriptor
from .dataflow import DataflowAudit, DataflowEdge
from .import_graph import DEFAULT_IMPORT_RULES, ImportEdge, ImportRule, ImportViolation, LayerViolation, audit_import_rules, audit_layer_dag, package_cycles, scan_imports
from .hotspots import ModuleHotspot, analyze_hotspots
from .report import ArchitectureReport
from .composition import build_architecture_report
__all__=["ArchitectureAudit","AuditViolation","ComponentDescriptor","DataflowAudit","DataflowEdge","DEFAULT_IMPORT_RULES","ImportEdge","ImportRule","ImportViolation","LayerViolation","audit_import_rules","audit_layer_dag","package_cycles","scan_imports","ModuleHotspot","analyze_hotspots","ArchitectureReport","build_architecture_report"]
from .optimization import ModuleOptimizationProfile, OptimizationReport, analyze_optimization_risks, build_optimization_report
__all__ = tuple(globals().get("__all__", ())) + ("ModuleOptimizationProfile","OptimizationReport","analyze_optimization_risks","build_optimization_report")

from .source_invariants import SourceInvariantViolation, audit_source_invariants
__all__ = tuple(__all__) + ("SourceInvariantViolation","audit_source_invariants")

from .source_authority import SourceAuthorityViolation, audit_source_authorities
__all__ = tuple(__all__) + ("SourceAuthorityViolation","audit_source_authorities")

from .platform_policy import build_platform_audit
__all__ = tuple(__all__) + ("build_platform_audit",)
