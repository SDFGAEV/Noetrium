from __future__ import annotations

from pathlib import Path

from .source_index import source_text
from .source_scan import SourceInvariantViolation, imports, violation


def _require_tokens(root: Path, path: Path, invariant: str, tokens: tuple[str, ...]) -> list[SourceInvariantViolation]:
    if not path.parent.exists():
        return []
    if not path.exists():
        return [violation(root, path, invariant, 1, "required module missing")]
    text = source_text(path)
    return [
        violation(root, path, invariant, 1, f"missing required boundary token: {token}")
        for token in tokens
        if token not in text
    ]


def _audit_api_dependency_direction(root: Path) -> list[SourceInvariantViolation]:
    rows: list[SourceInvariantViolation] = []
    rules = (
        (root / "research_platform" / "model" / "request" / "api", ("research_platform.model.request.runtime", "research_platform.model.request.prompt.runtime", "research_platform.model.serving")),
        (root / "research_platform" / "execution" / "capability" / "api", ("research_platform.execution.capability.runtime", "research_platform.execution.workflow.implementations", "research_platform.experimentation")),
        (root / "research_platform" / "data" / "projection" / "api", ("research_platform.data.projection.runtime", "research_platform.reliability.forensics")),
        (root / "research_platform" / "data" / "fact" / "api", ("research_platform.data.fact.runtime",)),
        (root / "research_platform" / "participant" / "capability" / "api", ("research_platform.execution.capability.runtime",)),
        (root / "research_platform" / "data" / "record" / "api", ("research_platform.data.fact.api", "research_platform.observability.api", "research_platform.participant.capability.api")),
    )
    for base, forbidden in rules:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            for module, line in imports(path):
                if module.startswith(forbidden):
                    rows.append(violation(root, path, "harness_api_dependency_direction", line, f"API package {base.relative_to(root)} imports runtime/upper implementation {module}"))
    return rows


def audit_harness_pattern_invariants(root: Path) -> list[SourceInvariantViolation]:
    rows = _audit_api_dependency_direction(root)
    rows += _require_tokens(
        root,
        root / "research_platform" / "model" / "request" / "prompt" / "runtime" / "request_build.py",
        "model_visible_request_reconstructability",
        ("ModelRequestRecorderPort", "model_requests.record", "model_requests.verify_visible_request"),
    )
    rows += _require_tokens(
        root,
        root / "research_platform" / "execution" / "workflow" / "implementations" / "agent_turn" / "capability_routing.py",
        "scoped_capability_pipeline",
        ("RegistrationScopePort", "CapabilityInvocationPipelinePort", "self._scope.acquire", "self._scope.dispose"),
    )
    rows += _require_tokens(
        root,
        root / "research_platform" / "execution" / "workflow" / "implementations" / "agent_turn" / "agent_turn_operations.py",
        "scoped_capability_lifecycle",
        ("finally:", "router.close()"),
    )
    rows += _require_tokens(
        root,
        root / "research_platform" / "data" / "record" / "api" / "contracts.py",
        "execution_record_planes",
        ("DURABLE_FACT", "LIVE_INTERCEPTION", "SIDE_PLANE_OBSERVATION"),
    )
    rows += _require_tokens(
        root,
        root / "research_platform" / "data" / "fact" / "runtime" / "decoder_registry.py",
        "unknown_required_fact_fail_closed",
        ("FactCriticality.IGNORABLE", "raise UnknownRequiredFact"),
    )
    return rows


__all__ = ["audit_harness_pattern_invariants"]
