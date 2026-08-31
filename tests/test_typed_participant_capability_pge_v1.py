from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

import pytest

from research_platform.execution.capability.runtime import (
    CapabilityInvocationPipeline,
    ScopedRegistrationRuntime,
)
from research_platform.execution.workflow.implementations.agent_turn.capability_operations import (
    CapabilityOperationAdapter,
)
from research_platform.execution.workflow.implementations.agent_turn.capability_routing import (
    CapabilitySessionBinding,
    StudyCapabilityRouter,
)
from research_platform.execution.workflow.runtime import KernelOperationDispatcher
from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityExportSession,
    CapabilityPolicySet,
    CapabilityProviderIdentity,
    CapabilityProviderSession,
    CapabilityRequest,
    GuardDecision,
    GuardVerdict,
    capability_request_digest,
    decode_typed_capability_result,
    make_typed_capability_request,
)
from research_platform.participant.capability.providers import FunctionalTypedCapabilityProvider
from research_platform.platform.kernel import (
    ComponentIdentity,
    EffectClass,
    ExecutionContext,
    OperationExecutor,
    canonical_digest,
)


def _d(char: str) -> str:
    return char * 64


def _identity(char: str = "a") -> CapabilityProviderIdentity:
    return CapabilityProviderIdentity(
        "novel-provider", "1", "1", "1", _d(char)
    )


def _descriptor(effect_class: EffectClass = EffectClass.PURE) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "paper.novel", "v1", "paper.novel.input.v1", "paper.novel.output.v1",
        effect_class=effect_class, deterministic=True,
    )


def _context(trace: str = "trace", generation: str = "planner-r7") -> ExecutionContext:
    return ExecutionContext(
        "run", trace, "span", decision_cycle_id="dc",
        participant_generations=(("planner", generation),),
    )


@dataclass(frozen=True, slots=True)
class NovelInput:
    values: tuple[float, ...]
    schema_id: str = field(init=False, default="paper.novel.input.v1")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class NovelOutput:
    score: float
    schema_id: str = field(init=False, default="paper.novel.output.v1")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class WrongOutput:
    score: float
    schema_id: str = field(init=False, default="paper.wrong.output.v1")

    def digest(self) -> str:
        return canonical_digest(self)


class MemoryTransport:
    def __init__(self) -> None:
        self.payloads: dict[str, bytes] = {}

    def publish(self, reference, payload: bytes) -> None:
        if hashlib.sha256(payload).hexdigest() != reference.content_digest:
            raise ValueError("test transport publish digest mismatch")
        self.payloads[reference.content_digest] = payload

    def load(self, reference) -> bytes:
        return self.payloads[reference.content_digest]


class NovelCodec:
    input_schema_id = "paper.novel.input.v1"
    output_schema_id = "paper.novel.output.v1"
    codec_id = "paper.novel.json.v1"
    implementation_digest = _d("c")
    media_type = "application/vnd.paper.novel+json"

    def encode_input(self, value: NovelInput) -> bytes:
        return json.dumps(
            {"values": value.values}, separators=(",", ":")
        ).encode("utf-8")

    def decode_input(self, payload: bytes) -> NovelInput:
        row = json.loads(payload.decode("utf-8"))
        return NovelInput(tuple(float(value) for value in row["values"]))
    def encode_output(self, value: NovelOutput) -> bytes:
        return json.dumps(
            {"score": value.score}, separators=(",", ":")
        ).encode("utf-8")

    def decode_output(self, payload: bytes) -> NovelOutput:
        row = json.loads(payload.decode("utf-8"))
        return NovelOutput(float(row["score"]))


class CountingGuard:
    guard_id = "typed-policy"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, descriptor, request):
        self.calls += 1
        assert descriptor == _descriptor()
        assert request.capability_id == descriptor.capability_id
        return GuardDecision(self.guard_id, GuardVerdict.ALLOW)


def _provider(
    transport: MemoryTransport,
    *,
    identity: CapabilityProviderIdentity | None = None,
    codec: NovelCodec | None = None,
    handler=None,
):
    return FunctionalTypedCapabilityProvider(
        identity=identity or _identity(),
        descriptor=_descriptor(),
        codec=codec or NovelCodec(),
        transport=transport,
        participant_role="planner",
        handler=handler or (lambda payload, _context: NovelOutput(sum(payload.values))),
    )


def _request(
    transport: MemoryTransport,
    *,
    payload: NovelInput | None = None,
    context: ExecutionContext | None = None,
    codec: NovelCodec | None = None,
) -> CapabilityRequest:
    return make_typed_capability_request(
        descriptor=_descriptor(),
        payload=payload or NovelInput((1.5, 2.5)),
        context=context or _context(),
        codec=codec or NovelCodec(),
        transport=transport,
    )


def _router(provider, guard: CountingGuard):
    dispatcher = KernelOperationDispatcher(OperationExecutor())
    adapter = CapabilityOperationAdapter(dispatcher)
    component = ComponentIdentity("participant.typed", "typed", "1", "1", "cfg")
    return StudyCapabilityRouter(
        adapter,
        (CapabilitySessionBinding(component, provider, "planner"),),
        pipeline=CapabilityInvocationPipeline(CapabilityPolicySet(guards=(guard,))),
        scope=ScopedRegistrationRuntime("typed-capability-test"),
    )


def test_typed_component_runs_through_canonical_session_policy_and_operation_path() -> None:
    transport = MemoryTransport()
    provider = _provider(transport)
    guard = CountingGuard()
    router = _router(provider, guard)
    request = _request(transport)

    result = router.invoke(request)
    decoded = decode_typed_capability_result(
        result,
        request=request,
        descriptor=_descriptor(),
        codec=NovelCodec(),
        transport=transport,
        expected_provider_identity=_identity(),
    )

    assert isinstance(provider, CapabilityExportSession)
    assert isinstance(provider, CapabilityProviderSession)
    assert decoded == NovelOutput(4.0)
    assert guard.calls == 1
    assert result.request_digest == capability_request_digest(request)
    assert result.generation == "planner-r7"
    operations = router.drain_operations()
    assert len(operations) == 1
    assert operations[0].operation_id == "dc:capability.invoke:paper.novel"


def test_large_high_dimensional_carrier_stays_out_of_canonical_json_payload() -> None:
    transport = MemoryTransport()
    values = tuple(float(index) for index in range(120_000))
    request = _request(transport, payload=NovelInput(values))

    assert set(request.payload) == {
        "descriptor_digest", "schema_id", "semantic_digest", "content_digest",
        "content_size", "media_type", "codec_id", "codec_implementation_digest",
    }
    assert request.payload["content_size"] > 700_000
    assert len(json.dumps(dict(request.payload))) < 1_000
    result = _provider(transport).invoke(request)
    decoded = decode_typed_capability_result(
        result, request=request, descriptor=_descriptor(), codec=NovelCodec(), transport=transport,
        expected_provider_identity=_identity(),
    )
    assert decoded.score == pytest.approx(sum(values))


def test_equivalent_codec_instance_can_substitute_across_transport_boundary() -> None:
    transport = MemoryTransport()
    client_codec = NovelCodec()
    provider_codec = NovelCodec()
    request = _request(transport, codec=client_codec)
    result = _provider(transport, codec=provider_codec).invoke(request)
    decoded = decode_typed_capability_result(
        result, request=request, descriptor=_descriptor(), codec=NovelCodec(), transport=transport,
        expected_provider_identity=_identity(),
    )
    assert decoded == NovelOutput(4.0)


def test_canonical_request_digest_excludes_trace_only_context() -> None:
    transport = MemoryTransport()
    left = _request(transport, context=_context("trace-a"))
    right = _request(transport, context=_context("trace-b"))
    assert capability_request_digest(left) == capability_request_digest(right)


def test_wrong_provider_descriptor_is_rejected_before_handler() -> None:
    transport = MemoryTransport()
    called: list[int] = []
    other = CapabilityDescriptor(
        "paper.other", "v1", "paper.novel.input.v1", "paper.novel.output.v1",
        deterministic=True,
    )
    request = make_typed_capability_request(
        descriptor=other,
        payload=NovelInput((1.0,)),
        context=_context(),
        codec=NovelCodec(),
        transport=transport,
    )
    provider = _provider(
        transport,
        handler=lambda payload, _context: (called.append(1), NovelOutput(sum(payload.values)))[1],
    )
    with pytest.raises(ValueError, match="provider descriptor"):
        provider.invoke(request)
    assert called == []


def test_provider_revision_drift_is_detected_when_decoding_result() -> None:
    transport = MemoryTransport()
    request = _request(transport)
    result = _provider(transport, identity=_identity("a")).invoke(request)
    with pytest.raises(ValueError, match="provider identity"):
        decode_typed_capability_result(
            result,
            request=request,
            descriptor=_descriptor(),
            codec=NovelCodec(),
            transport=transport,
            expected_provider_identity=_identity("b"),
        )


def test_codec_implementation_drift_is_rejected_before_handler() -> None:
    transport = MemoryTransport()
    request = _request(transport, codec=NovelCodec())

    class DriftedCodec(NovelCodec):
        implementation_digest = _d("d")

    called: list[int] = []
    provider = _provider(
        transport,
        codec=DriftedCodec(),
        handler=lambda payload, _context: (called.append(1), NovelOutput(sum(payload.values)))[1],
    )
    with pytest.raises(ValueError, match="codec implementation"):
        provider.invoke(request)
    assert called == []


def test_corrupted_transport_bytes_fail_closed_before_handler() -> None:
    transport = MemoryTransport()
    request = _request(transport)
    digest = request.payload["content_digest"]
    raw = bytearray(transport.payloads[digest])
    raw[0] ^= 1
    transport.payloads[digest] = bytes(raw)
    called: list[int] = []
    provider = _provider(
        transport,
        handler=lambda payload, _context: (called.append(1), NovelOutput(sum(payload.values)))[1],
    )
    with pytest.raises(ValueError, match="wrong digest"):
        provider.invoke(request)
    assert called == []


def test_wrong_output_schema_is_rejected_before_publication() -> None:
    transport = MemoryTransport()
    provider = _provider(
        transport,
        handler=lambda _payload, _context: WrongOutput(1.0),
    )
    with pytest.raises(ValueError, match="output schema"):
        provider.invoke(_request(transport))


def test_effectful_typed_provider_has_no_parallel_direct_execution_path() -> None:
    with pytest.raises(ValueError, match="DurablePreparedCapabilitySession"):
        FunctionalTypedCapabilityProvider(
            identity=_identity(),
            descriptor=_descriptor(EffectClass.NON_IDEMPOTENT),
            codec=NovelCodec(),
            transport=MemoryTransport(),
            participant_role="planner",
            handler=lambda payload, _context: NovelOutput(sum(payload.values)),
        )



def test_canonical_policy_can_deny_typed_provider_before_handler() -> None:
    transport = MemoryTransport()
    called: list[int] = []
    provider = _provider(
        transport,
        handler=lambda payload, _context: (called.append(1), NovelOutput(sum(payload.values)))[1],
    )

    class DenyGuard:
        guard_id = "deny-typed"

        def evaluate(self, descriptor, request):
            del descriptor, request
            return GuardDecision(self.guard_id, GuardVerdict.DENY, "TEST_DENY")

    dispatcher = KernelOperationDispatcher(OperationExecutor())
    router = StudyCapabilityRouter(
        CapabilityOperationAdapter(dispatcher),
        (CapabilitySessionBinding(
            ComponentIdentity("participant.typed", "typed", "1", "1", "cfg"),
            provider,
            "planner",
        ),),
        pipeline=CapabilityInvocationPipeline(CapabilityPolicySet(guards=(DenyGuard(),))),
        scope=ScopedRegistrationRuntime("typed-capability-deny-test"),
    )
    with pytest.raises(PermissionError, match="TEST_DENY"):
        router.invoke(_request(transport))
    assert called == []


def test_provider_identity_is_part_of_canonical_result_provenance_digest() -> None:
    first_transport = MemoryTransport()
    first_request = _request(first_transport)
    first = _provider(first_transport, identity=_identity("a")).invoke(first_request)

    second_transport = MemoryTransport()
    second_request = _request(second_transport)
    second = _provider(second_transport, identity=_identity("b")).invoke(second_request)

    assert first.payload == second.payload
    assert first.request_digest == second.request_digest
    assert first.provider_identity != second.provider_identity
    assert first.digest() != second.digest()


def test_result_decode_rejects_wrong_canonical_request_provenance() -> None:
    transport = MemoryTransport()
    request = _request(transport, payload=NovelInput((1.0, 2.0)))
    result = _provider(transport).invoke(request)
    other_request = _request(transport, payload=NovelInput((9.0,)))
    with pytest.raises(ValueError, match="canonical request provenance"):
        decode_typed_capability_result(
            result,
            request=other_request,
            descriptor=_descriptor(),
            codec=NovelCodec(),
            transport=transport,
            expected_provider_identity=_identity(),
        )


def test_provider_requires_runtime_participant_generation() -> None:
    transport = MemoryTransport()
    context = ExecutionContext("run", "trace", "span", decision_cycle_id="dc")
    request = _request(transport, context=context)
    with pytest.raises(ValueError, match="missing participant generation"):
        _provider(transport).invoke(request)
