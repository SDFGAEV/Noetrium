from __future__ import annotations

import ast
import inspect
from pathlib import Path

from research_platform.reliability.recovery.api import (
    RecoveryActionCode,
    RecoveryAutomation,
    RecoveryDecisionReport,
    RecoveryRecommendation,
)
from research_platform.resource.compute.api import (
    ComputeCandidatePort,
    ComputeGPU,
    ComputeHost,
    ComputeRequirement,
)
from research_platform.runtime.server.health.api import (
    ServerDiagnosticIssue,
    ServerDiagnosticReport,
    ServerDiagnosticSeverity,
    ServerDiagnosticStatus,
    ServerHealthReport,
)
from research_platform.runtime.server.identity.api import ServerCommandResult
from research_platform.scope.api import ScopeIdentity, ScopeKind


def _candidate_hosts(requirement: ComputeRequirement, hosts: tuple[ComputeHost, ...]) -> tuple[str, ...]:
    required_labels = dict(requirement.required_labels)
    return tuple(
        host.host_id for host in hosts
        if host.enabled
        and host.cpu_cores >= requirement.cpu_cores
        and host.memory_bytes >= requirement.memory_bytes
        and sum(gpu.memory_bytes >= requirement.minimum_gpu_memory_bytes for gpu in host.gpus) >= requirement.gpu_count
        and all(dict(host.labels).get(key) == value for key, value in required_labels.items())
    )


def _server(status: ServerDiagnosticStatus) -> ServerDiagnosticReport:
    command = ServerCommandResult("server-2", "health", 0, "ok", "")
    health = ServerHealthReport("server-2", True, "host", "3.12", "2.55", "3.4", command, True)
    issues = () if status is ServerDiagnosticStatus.READY else (
        ServerDiagnosticIssue(
            "runtime:not-ready",
            ServerDiagnosticSeverity.ERROR,
            "runtime is not ready",
            evidence_refs=("server:server-2",),
            recommended_action="inspect_health_checks",
        ),
    )
    return ServerDiagnosticReport(
        "server-2", "p" * 64, "ops.log", health, (), (), None, issues, status
    )


def _recovery(blocked: bool) -> RecoveryDecisionReport:
    if not blocked:
        return RecoveryDecisionReport(())
    return RecoveryDecisionReport((RecoveryRecommendation(
        "runtime", RecoveryActionCode.BLOCK_IDENTITY_DRIFT,
        RecoveryAutomation.FORBIDDEN, ("identity_drift",),
    ),))


def test_public_runtime_resource_recovery_facts_are_sufficient_for_read_only_preflight() -> None:
    scope = ScopeIdentity(ScopeKind.RUN, "run-1")
    requirement = ComputeRequirement(
        cpu_cores=4, memory_bytes=8 * 1024, gpu_count=1,
        minimum_gpu_memory_bytes=16 * 1024, required_labels=(("os", "linux"),),
    )
    hosts = (
        ComputeHost("local", scope, 8, 32 * 1024, (ComputeGPU("g0", 8 * 1024),), (("os", "windows"),)),
        ComputeHost("server-2", scope, 8, 32 * 1024, (ComputeGPU("g1", 24 * 1024),), (("os", "linux"),)),
    )

    candidates = _candidate_hosts(requirement, hosts)
    server = _server(ServerDiagnosticStatus.READY)
    recovery = _recovery(False)

    assert candidates == ("server-2",)
    assert server.status is ServerDiagnosticStatus.READY
    assert recovery.blocked == ()
    assert not server.issues


def test_public_facts_fail_closed_without_mutating_domain_authorities() -> None:
    requirement = ComputeRequirement(cpu_cores=64, memory_bytes=1024)
    scope = ScopeIdentity(ScopeKind.RUN, "run-2")
    hosts = (ComputeHost("small", scope, 4, 4096),)
    assert _candidate_hosts(requirement, hosts) == ()
    assert _server(ServerDiagnosticStatus.REMOTE_NOT_READY).issues
    assert _recovery(True).blocked


def test_reference_consumer_uses_public_api_modules_only() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imports = tuple(
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("research_platform.")
    )
    assert imports
    assert all(".api" in module for module in imports)
    assert all(".providers" not in module and ".composition" not in module for module in imports)


def test_compute_candidate_port_is_a_read_only_preflight_surface() -> None:
    public_methods = {
        name
        for name, member in ComputeCandidatePort.__dict__.items()
        if not name.startswith("_") and callable(member)
    }
    assert public_methods == {"candidates"}

    signature = inspect.signature(ComputeCandidatePort.candidates)
    assert tuple(signature.parameters) == ("self", "requirement", "scope")
    assert "allocate" not in public_methods
    assert "release" not in public_methods
