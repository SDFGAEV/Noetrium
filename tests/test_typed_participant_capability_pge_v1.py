from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from research_platform.platform.kernel import EffectClass, ExecutionContext, canonical_digest
from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityInputCarrier,
    CapabilityOutputCarrier,
    CapabilityProviderIdentity,
    TypedCapabilityPort,
    TypedCapabilityRequest,
)
from research_platform.participant.capability.providers import FunctionalTypedCapabilityProvider


def _identity() -> CapabilityProviderIdentity:
    return CapabilityProviderIdentity(
        provider_id="novel-provider",
        implementation_version="1",
        abi_version="1",
        schema_version="1",
        artifact_digest="a" * 64,
    )


def _context(trace: str = "trace") -> ExecutionContext:
    return ExecutionContext("run", trace, "span")


@dataclass(frozen=True, slots=True)
class NovelComponentInput:
    values: tuple[float, ...]
    schema_id: str = field(init=False, default="paper.novel.input.v1")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class NovelComponentOutput:
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


def _descriptor(effect_class: EffectClass = EffectClass.PURE) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "paper.novel", "v1", "paper.novel.input.v1", "paper.novel.output.v1",
        effect_class=effect_class, deterministic=True,
    )


def test_novel_component_uses_public_typed_capability_without_platform_registration() -> None:
    provider = FunctionalTypedCapabilityProvider[
        NovelComponentInput, NovelComponentOutput
    ](
        identity=_identity(),
        descriptor=_descriptor(),
        handler=lambda payload, _context: NovelComponentOutput(sum(payload.values)),
    )
    request = TypedCapabilityRequest(
        _descriptor(), NovelComponentInput((1.5, 2.5)), _context()
    )

    result = provider.invoke_typed(request)

    assert isinstance(provider, TypedCapabilityPort)
    assert isinstance(request.payload, CapabilityInputCarrier)
    assert isinstance(result.payload, CapabilityOutputCarrier)
    assert result.payload.score == 4.0
    assert result.provider_identity == _identity()
    assert result.request_digest == request.digest()


def test_typed_request_rejects_schema_drift_before_provider() -> None:
    descriptor = CapabilityDescriptor(
        "paper.novel", "v1", "paper.other.input.v1", "paper.novel.output.v1"
    )
    with pytest.raises(ValueError, match="request schema"):
        TypedCapabilityRequest(descriptor, NovelComponentInput((1.0,)), _context())


def test_provider_rejects_descriptor_drift_before_handler() -> None:
    called: list[int] = []
    provider = FunctionalTypedCapabilityProvider[
        NovelComponentInput, NovelComponentOutput
    ](
        identity=_identity(),
        descriptor=_descriptor(),
        handler=lambda payload, _context: (called.append(1), NovelComponentOutput(0.0))[1],
    )
    other = CapabilityDescriptor(
        "paper.other", "v1", "paper.novel.input.v1", "paper.novel.output.v1"
    )
    request = TypedCapabilityRequest(other, NovelComponentInput((1.0,)), _context())

    with pytest.raises(ValueError, match="provider descriptor"):
        provider.invoke_typed(request)
    assert called == []


def test_provider_rejects_output_schema_drift() -> None:
    provider = FunctionalTypedCapabilityProvider[
        NovelComponentInput, WrongOutput
    ](
        identity=_identity(), descriptor=_descriptor(),
        handler=lambda _payload, _context: WrongOutput(1.0),
    )
    request = TypedCapabilityRequest(
        _descriptor(), NovelComponentInput((1.0,)), _context()
    )
    with pytest.raises(ValueError, match="result schema"):
        provider.invoke_typed(request)


def test_direct_typed_provider_rejects_effectful_descriptor() -> None:
    with pytest.raises(ValueError, match="limited to pure"):
        FunctionalTypedCapabilityProvider[
            NovelComponentInput, NovelComponentOutput
        ](
            identity=_identity(),
            descriptor=_descriptor(EffectClass.RECONCILABLE),
            handler=lambda _payload, _context: NovelComponentOutput(0.0),
        )


def test_typed_request_digest_excludes_trace_only_context() -> None:
    left = TypedCapabilityRequest(
        _descriptor(), NovelComponentInput((1.0, 2.0)), _context("trace-a")
    )
    right = TypedCapabilityRequest(
        _descriptor(), NovelComponentInput((1.0, 2.0)), _context("trace-b")
    )

    assert left.digest() == right.digest()


class MutableNovelInput:
    schema_id = "paper.novel.input.v1"

    def __init__(self, values: list[float]) -> None:
        self.values = values

    def digest(self) -> str:
        return canonical_digest({"values": self.values})


class MutableNovelOutput:
    schema_id = "paper.novel.output.v1"

    def __init__(self, score: float) -> None:
        self.score = score

    def digest(self) -> str:
        return canonical_digest({"score": self.score})


def test_mutated_input_carrier_is_rejected_before_handler() -> None:
    called: list[int] = []
    provider = FunctionalTypedCapabilityProvider[
        MutableNovelInput, NovelComponentOutput
    ](
        identity=_identity(), descriptor=_descriptor(),
        handler=lambda _payload, _context: (called.append(1), NovelComponentOutput(1.0))[1],
    )
    payload = MutableNovelInput([1.0])
    request = TypedCapabilityRequest(_descriptor(), payload, _context())
    payload.values.append(2.0)

    with pytest.raises(ValueError, match="payload drifted"):
        provider.invoke_typed(request)
    assert called == []


def test_handler_cannot_mutate_input_carrier_and_publish_result() -> None:
    payload = MutableNovelInput([1.0])

    def mutate(value: MutableNovelInput, _context: ExecutionContext) -> NovelComponentOutput:
        value.values.append(2.0)
        return NovelComponentOutput(3.0)

    provider = FunctionalTypedCapabilityProvider[MutableNovelInput, NovelComponentOutput](
        identity=_identity(), descriptor=_descriptor(), handler=mutate,
    )
    request = TypedCapabilityRequest(_descriptor(), payload, _context())
    with pytest.raises(ValueError, match="payload drifted"):
        provider.invoke_typed(request)


def test_mutated_output_carrier_is_detectable_from_published_result() -> None:
    payload = MutableNovelOutput(1.0)
    provider = FunctionalTypedCapabilityProvider[
        NovelComponentInput, MutableNovelOutput
    ](
        identity=_identity(), descriptor=_descriptor(),
        handler=lambda _payload, _context: payload,
    )
    result = provider.invoke_typed(
        TypedCapabilityRequest(_descriptor(), NovelComponentInput((1.0,)), _context())
    )
    payload.score = 2.0

    with pytest.raises(ValueError, match="payload drifted"):
        result.verify_payload_integrity()


def test_provider_implementation_identity_changes_typed_result_digest() -> None:
    request = TypedCapabilityRequest(
        _descriptor(), NovelComponentInput((1.0,)), _context()
    )
    first = FunctionalTypedCapabilityProvider[
        NovelComponentInput, NovelComponentOutput
    ](
        identity=_identity(), descriptor=_descriptor(),
        handler=lambda _payload, _context: NovelComponentOutput(1.0),
    ).invoke_typed(request)
    second_identity = CapabilityProviderIdentity(
        provider_id="novel-provider", implementation_version="1",
        abi_version="1", schema_version="1", artifact_digest="b" * 64,
    )
    second = FunctionalTypedCapabilityProvider[
        NovelComponentInput, NovelComponentOutput
    ](
        identity=second_identity, descriptor=_descriptor(),
        handler=lambda _payload, _context: NovelComponentOutput(1.0),
    ).invoke_typed(request)

    assert first.provider_identity.provider_id == second.provider_identity.provider_id
    assert first.digest() != second.digest()
