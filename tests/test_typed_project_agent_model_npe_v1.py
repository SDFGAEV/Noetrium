from __future__ import annotations

import ast
from dataclasses import dataclass

import pytest

from research_platform.model.api import (
    ModelBindingDiagnosticCode,
    ModelCapabilityRequirement,
    ModelProjectBindingError,
    ModelProviderProfile,
    ProjectModelClientPort,
    ProjectModelProviderPort,
    ProjectModelRequest,
)
from research_platform.model.providers import QualifiedModelProjectProvider
from research_platform.model.request.api import ContentRef, ModelRequestEnvelope
from research_platform.model.serving.endpoint.api import (
    ModelEndpointRequest,
    ModelEndpointResponse,
    ModelEndpointRoute,
    QualifiedModelEndpointBinding,
)
from research_platform.participant.api import (
    AgentIdentity,
    AgentProjectDefinition,
    ParticipantBindingDiagnosticCode,
    ParticipantProjectBindingError,
    ParticipantProviderProfile,
    ParticipantRequirement,
    ProjectParticipantProviderPort,
)
from research_platform.participant.core.api.contracts import (
    ParticipantRuntimeBinding,
    ParticipantSessionRuntimeIdentity,
)
from research_platform.participant.core.api.runtime import ParticipantRuntimeHandle
from research_platform.participant.providers import RuntimeParticipantProjectProvider
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity


D = {
    "prompt": "1" * 64,
    "tool": "2" * 64,
    "generation": "3" * 64,
    "stack": "4" * 64,
    "certificate": "5" * 64,
    "runtime": "6" * 64,
    "host": "7" * 64,
    "canary": "8" * 64,
}


def _model(name: str = "model-a") -> ImmutableModelIdentity:
    return ImmutableModelIdentity(
        logical_name=name,
        model_id=name,
        revision="rev-1",
        engine="engine",
        engine_version="1",
        dtype="bf16",
        quantization=None,
        context_length=8192,
        tokenizer_revision="tok-1",
    )


def _requirement(**changes: object) -> ModelCapabilityRequirement:
    values: dict[str, object] = {
        "role": "planner",
        "prompt_generation_id": "prompt-generation-v1",
        "prompt_id": "planner.v1",
        "prompt_digest": D["prompt"],
        "required_capabilities": ("chat", "tools"),
        "minimum_context_tokens": 4096,
        "tool_schema_sha256": D["tool"],
    }
    values.update(changes)
    return ModelCapabilityRequirement(**values)  # type: ignore[arg-type]


def _qualified_binding(
    *, deployment_id: str = "dep-a", model: ImmutableModelIdentity | None = None,
    prompt_generation: str = "prompt-generation-v1",
) -> QualifiedModelEndpointBinding:
    return QualifiedModelEndpointBinding(
        role="planner",
        deployment_id=deployment_id,
        deployment_generation=D["generation"],
        base_url="http://127.0.0.1:8000",
        model=_model() if model is None else model,
        model_stack_digest=D["stack"],
        qualification_certificate_digest=D["certificate"],
        runtime_qualification_digest=D["runtime"],
        host_identity_digest=D["host"],
        prompt_generation=prompt_generation,
        max_admitted_concurrency=2,
        runtime_canary_evidence_digests=(D["canary"],),
    )


class _BindingPort:
    def __init__(self, binding: QualifiedModelEndpointBinding) -> None:
        self.binding = binding

    def binding_for(self, *, role: str, prompt_generation: str) -> QualifiedModelEndpointBinding:
        return self.binding


@dataclass
class _Endpoint:
    route: ModelEndpointRoute
    calls: list[ModelEndpointRequest]

    def complete(self, request: ModelEndpointRequest) -> ModelEndpointResponse:
        self.calls.append(request)
        return ModelEndpointResponse(
            request_id=request.request.request_id,
            deployment_id=request.deployment_id,
            text="ok",
            finish_reason="stop",
            input_tokens=3,
            output_tokens=1,
        )


def _endpoint_factory(binding: QualifiedModelEndpointBinding) -> _Endpoint:
    return _Endpoint(
        ModelEndpointRoute(
            binding.deployment_id,
            binding.deployment_generation,
            binding.base_url,
            binding.completion_path,
            binding.timeout_s,
        ),
        [],
    )


def _envelope(
    model: ImmutableModelIdentity,
    *, prompt_digest: str = D["prompt"],
    prompt_generation: str = "prompt-generation-v1",
    tool_digest: str = D["tool"],
) -> ModelRequestEnvelope:
    return ModelRequestEnvelope(
        schema_version="model-request.v1",
        request_id="request-1",
        context=ExecutionContext("run-1", "trace-1", "span-1"),
        role="planner",
        model=model,
        prompt_generation_id=prompt_generation,
        prompt_id="planner.v1",
        prompt_digest=prompt_digest,
        request_body=ContentRef("9" * 64, 2, "application/json"),
        tool_schema_bundle=ContentRef(tool_digest, 2, "application/json"),
    )


def _provider(binding: QualifiedModelEndpointBinding) -> QualifiedModelProjectProvider:
    return QualifiedModelProjectProvider(
        ModelProviderProfile("qualified-local", ("chat", "tools")),
        _BindingPort(binding),
        _endpoint_factory,
    )


def test_common_project_source_uses_only_role04_public_api() -> None:
    source = """
from research_platform.model.api import ModelCapabilityRequirement
from research_platform.participant.api import (
    AgentIdentity, AgentProjectDefinition, AgentSession, AgentTurnResult,
)

AGENT = AgentProjectDefinition(
    role='worker',
    identity=AgentIdentity('agent', '1', '1', '1', 'artifact'),
    required_capabilities=('observe',),
)
MODEL = ModelCapabilityRequirement(
    role='planner', prompt_generation_id='gen', prompt_id='prompt',
    prompt_digest='1' * 64, required_capabilities=('chat',),
)
class DemoSession:
    def run_turn(self, request, capabilities): return AgentTurnResult({'ok': True})
    def checkpoint(self): return None
    def restore(self, snapshot): return None
    def diagnostics(self): return {}
    def close(self): return None
DEMO_SESSION = DemoSession()
"""
    tree = ast.parse(source)
    modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert modules == {
        "research_platform.model.api",
        "research_platform.participant.api",
    }
    namespace: dict[str, object] = {}
    exec(compile(tree, "project.py", "exec"), namespace)
    assert isinstance(namespace["AGENT"], AgentProjectDefinition)
    assert isinstance(namespace["MODEL"], ModelCapabilityRequirement)
    assert isinstance(namespace["DEMO_SESSION"], namespace["AgentSession"])


def test_model_provider_conformance_and_binding_hide_route_process_details() -> None:
    requirement = _requirement()
    provider = _provider(_qualified_binding())
    assert isinstance(provider, ProjectModelProviderPort)
    client = provider.bind(requirement)
    assert isinstance(client, ProjectModelClientPort)
    assert client.binding.requirement_digest == requirement.digest()
    assert client.binding.prompt_digest == requirement.prompt_digest
    assert client.binding.runtime_canary_evidence_digests == (D["canary"],)
    assert not hasattr(client.binding, "base_url")
    assert not hasattr(client.binding, "completion_path")
    assert not hasattr(client.binding, "pid")
    assert not hasattr(client.binding, "process_start_marker")


def test_model_request_binds_exact_prompt_tool_and_deployment_provenance() -> None:
    requirement = _requirement()
    client = _provider(_qualified_binding()).bind(requirement)
    envelope = _envelope(client.binding.model)
    body = {"messages": [{"role": "user", "content": "hello"}]}
    request = ProjectModelRequest(requirement.digest(), envelope, body)
    body["messages"][0]["content"] = "mutated"
    response = client.complete(request)
    assert response.request_digest == request.request_digest
    assert response.binding_digest == client.binding.digest()
    assert request.body["messages"][0]["content"] == "hello"


@pytest.mark.parametrize(
    ("envelope", "match"),
    [
        (_envelope(_model(), prompt_digest="a" * 64), "prompt provenance"),
        (_envelope(_model(), prompt_generation="other"), "prompt provenance"),
        (_envelope(_model(), tool_digest="b" * 64), "tool schema provenance"),
    ],
)
def test_model_request_provenance_drift_fails_closed(
    envelope: ModelRequestEnvelope, match: str
) -> None:
    requirement = _requirement()
    client = _provider(_qualified_binding()).bind(requirement)
    request = ProjectModelRequest(requirement.digest(), envelope, {"messages": []})
    with pytest.raises(ValueError, match=match):
        client.complete(request)


def test_model_provider_rejects_binding_role_or_prompt_generation_drift() -> None:
    requirement = _requirement()
    drifted = _qualified_binding(prompt_generation="wrong-generation")
    provider = _provider(drifted)
    diagnostics = provider.diagnose(requirement)
    assert diagnostics[0].code is ModelBindingDiagnosticCode.BINDING_PROVENANCE_DRIFT
    with pytest.raises(ModelProjectBindingError):
        provider.bind(requirement)


def test_model_provider_swap_preserves_project_requirement_and_logic() -> None:
    requirement = _requirement()
    first = _provider(_qualified_binding(deployment_id="dep-a", model=_model("model-a"))).bind(requirement)
    second = _provider(_qualified_binding(deployment_id="dep-b", model=_model("model-b"))).bind(requirement)

    def project_logic(client: ProjectModelClientPort) -> str:
        request = ProjectModelRequest(
            requirement.digest(),
            _envelope(client.binding.model),
            {"messages": [{"role": "user", "content": "plan"}]},
        )
        return client.complete(request).response.text

    assert project_logic(first) == "ok"
    assert project_logic(second) == "ok"
    assert first.binding.requirement_digest == second.binding.requirement_digest
    assert first.binding.deployment_id != second.binding.deployment_id
    assert first.binding.model != second.binding.model


class _FailingBindingPort:
    def binding_for(self, *, role: str, prompt_generation: str) -> QualifiedModelEndpointBinding:
        raise RuntimeError("https://secret.invalid?token=do-not-leak")


def test_model_doctor_diagnostics_are_typed_and_do_not_echo_provider_secrets() -> None:
    requirement = _requirement()
    provider = QualifiedModelProjectProvider(
        ModelProviderProfile("qualified-local", ("chat", "tools")),
        _FailingBindingPort(),
        _endpoint_factory,
    )
    diagnostics = provider.diagnose(requirement)
    assert diagnostics[0].code is ModelBindingDiagnosticCode.QUALIFIED_BINDING_UNAVAILABLE
    assert diagnostics[0].requirement_digest == requirement.digest()
    assert "secret.invalid" not in diagnostics[0].message
    assert "token=" not in diagnostics[0].message


def test_model_doctor_reports_capability_and_context_failures_without_endpoint_materialization() -> None:
    missing = QualifiedModelProjectProvider(
        ModelProviderProfile("small", ("chat",)),
        _BindingPort(_qualified_binding()),
        lambda binding: (_ for _ in ()).throw(AssertionError("must not materialize")),
    )
    assert missing.diagnose(_requirement())[0].code is ModelBindingDiagnosticCode.CAPABILITY_MISSING
    short = _provider(_qualified_binding(model=ImmutableModelIdentity(
        "short", "short", "rev", "engine", "1", "bf16", None, 1024, None
    )))
    assert short.diagnose(_requirement())[0].code is ModelBindingDiagnosticCode.CONTEXT_INSUFFICIENT


def _participant_requirement() -> ParticipantRequirement:
    definition = AgentProjectDefinition(
        role="worker",
        identity=AgentIdentity("agent", "1", "1", "1", "artifact"),
        configuration_digest="config-v1",
        required_capabilities=("observe", "act"),
    )
    return definition.requirement()


def _runtime(runtime_id: str = "local-agent-runtime") -> ParticipantSessionRuntimeIdentity:
    return ParticipantSessionRuntimeIdentity(
        runtime_id=runtime_id,
        runtime_version="1",
        abi_version="1",
        artifact_digest=f"artifact-{runtime_id}",
    )


class _ParticipantResolver:
    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle:
        return ParticipantRuntimeHandle(binding, object())  # type: ignore[arg-type]


def _participant_provider(runtime_id: str = "local-agent-runtime") -> RuntimeParticipantProjectProvider:
    return RuntimeParticipantProjectProvider(
        ParticipantProviderProfile("participant-local", ("agent",), ("observe", "act")),
        _ParticipantResolver(),
        lambda requirement: _runtime(runtime_id),
    )


def test_participant_provider_conformance_binds_agent_without_runtime_imports_in_project() -> None:
    requirement = _participant_requirement()
    provider = _participant_provider()
    assert isinstance(provider, ProjectParticipantProviderPort)
    binding = provider.bind(requirement)
    assert binding.requirement_digest == requirement.digest()
    assert binding.binding.role == "worker"
    assert binding.binding.implementation == requirement.implementation
    assert binding.binding.configuration_digest == requirement.configuration_digest


def test_participant_provider_swap_preserves_project_requirement_identity() -> None:
    requirement = _participant_requirement()
    local = _participant_provider("local").bind(requirement)
    server = _participant_provider("server").bind(requirement)
    assert local.requirement_digest == server.requirement_digest == requirement.digest()
    assert local.binding.implementation == server.binding.implementation
    assert local.binding.runtime != server.binding.runtime


def test_participant_doctor_reports_missing_capability_as_typed_failure() -> None:
    provider = RuntimeParticipantProjectProvider(
        ParticipantProviderProfile("participant-small", ("agent",), ("observe",)),
        _ParticipantResolver(),
        lambda requirement: _runtime(),
    )
    diagnostics = provider.diagnose(_participant_requirement())
    assert diagnostics[0].code is ParticipantBindingDiagnosticCode.CAPABILITY_MISSING
    with pytest.raises(ParticipantProjectBindingError):
        provider.bind(_participant_requirement())


class _FailingParticipantResolver:
    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle:
        raise RuntimeError("C:/secret/provider/path token=do-not-leak")


def test_participant_doctor_does_not_echo_provider_secrets() -> None:
    requirement = _participant_requirement()
    provider = RuntimeParticipantProjectProvider(
        ParticipantProviderProfile("participant-local", ("agent",), ("observe", "act")),
        _FailingParticipantResolver(),
        lambda req: _runtime(),
    )
    diagnostics = provider.diagnose(requirement)
    assert diagnostics[0].code is ParticipantBindingDiagnosticCode.RUNTIME_UNAVAILABLE
    assert diagnostics[0].requirement_digest == requirement.digest()
    assert "secret/provider" not in diagnostics[0].message
    assert "token=" not in diagnostics[0].message


class _DriftingParticipantResolver:
    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle:
        drifted = ParticipantRuntimeBinding(
            role="other",
            implementation=binding.implementation,
            runtime=binding.runtime,
            configuration_digest=binding.configuration_digest,
        )
        return ParticipantRuntimeHandle(drifted, object())  # type: ignore[arg-type]


def test_participant_provider_detects_resolver_binding_drift() -> None:
    requirement = _participant_requirement()
    provider = RuntimeParticipantProjectProvider(
        ParticipantProviderProfile("participant-local", ("agent",), ("observe", "act")),
        _DriftingParticipantResolver(),
        lambda req: _runtime(),
    )
    diagnostics = provider.diagnose(requirement)
    assert diagnostics[0].code is ParticipantBindingDiagnosticCode.BINDING_PROVENANCE_DRIFT
    with pytest.raises(ParticipantProjectBindingError):
        provider.bind(requirement)


def test_role04_public_exports_are_reflection_safe_strings() -> None:
    import research_platform.model.api as model_api
    import research_platform.participant.api as participant_api

    assert model_api.__all__
    assert participant_api.__all__
    assert all(type(name) is str for name in model_api.__all__)
    assert all(type(name) is str for name in participant_api.__all__)


def test_provider_ports_fail_closed_on_untyped_requirements() -> None:
    with pytest.raises(TypeError, match="typed"):
        _provider(_qualified_binding()).diagnose(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="typed"):
        _participant_provider().diagnose(object())  # type: ignore[arg-type]
