from __future__ import annotations

import json
import math

import pytest

from research_platform.model.api import (
    EmbeddingInput,
    EmbeddingOutput,
    EmbeddingVector,
    ModelCapabilityInvocation,
    ModelCapabilityRequirement,
    ModelProviderProfile,
    MultimodalInferenceOutput,
    MultimodalInferenceInput,
    MultimodalContent,
    NamedScalar,
    ProjectModelBinding,
    ProjectModelCapabilityClientPort,
    PolicyActionProbability,
    PolicyInferenceInput,
    PolicyInferenceOutput,
    RankedCandidate,
    RankingCandidate,
    RankingInput,
    RankingOutput,
    ProjectModelCapabilityProviderPort,
    ProjectModelResponse,
    ScoredCandidate,
    ScoringCandidate,
    ScoringInput,
    ScoringOutput,
    StructuredGenerationOutput,
    StructuredGenerationInput,
    ValueInferenceInput,
    ValueInferenceOutput,
)
from research_platform.model.providers import (
    FunctionalModelCapabilityProvider, QualifiedStructuredGenerationCapabilityProvider,
)
from research_platform.model.request.api import ContentRef, ModelRequestEnvelope
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity


D = {name: char * 64 for name, char in {
    "profile": "1", "generation": "2", "stack": "3", "certificate": "4",
    "runtime": "5", "host": "6", "canary": "7",
}.items()}

def _model() -> ImmutableModelIdentity:
    return ImmutableModelIdentity(
        logical_name="model-a",
        model_id="model-a",
        revision="rev-1",
        engine="engine",
        engine_version="1",
        dtype="bf16",
        quantization=None,
        context_length=8192,
        tokenizer_revision="tok-1",
    )


def _requirement(capability_id: str, input_schema_id: str, output_schema_id: str) -> ModelCapabilityRequirement:
    return ModelCapabilityRequirement(
        role="scientist",
        prompt_generation_id=None,
        prompt_id=None,
        prompt_digest=None,
        required_capabilities=(capability_id,),
        capability_id=capability_id,
        input_schema_id=input_schema_id,
        output_schema_id=output_schema_id,
    )


def _binding(requirement: ModelCapabilityRequirement) -> ProjectModelBinding:
    profile = ModelProviderProfile("functional-model", (requirement.capability_id,))
    return ProjectModelBinding(
        requirement_digest=requirement.digest(),
        provider_id=profile.provider_id,
        provider_profile_digest=profile.digest(),
        role=requirement.role,
        model=_model(),
        deployment_id="deployment-a",
        deployment_generation=D["generation"],
        model_stack_digest=D["stack"],
        qualification_certificate_digest=D["certificate"],
        runtime_qualification_digest=D["runtime"],
        host_identity_digest=D["host"],
        prompt_generation_id=None,
        prompt_id=None,
        prompt_digest=None,
        capabilities=profile.capabilities,
        runtime_canary_evidence_digests=(D["canary"],),
        capability_id=requirement.capability_id,
        input_schema_id=requirement.input_schema_id,
        output_schema_id=requirement.output_schema_id,
    )


def test_generation_requirement_retains_small_prompt_api() -> None:
    requirement = ModelCapabilityRequirement(
        role="agent",
        prompt_generation_id="generation-1",
        prompt_id="default",
        prompt_digest="a" * 64,
    )
    assert requirement.is_generation
    assert requirement.capability_id == "generation"
    assert requirement.input_schema_id == "model.generation.request.v1"


def test_non_generation_requirement_uses_schema_identity_without_fake_prompt() -> None:
    requirement = _requirement(
        "embedding", "model.embedding.input.v1", "model.embedding.output.v1"
    )
    assert not requirement.is_generation
    assert requirement.prompt_generation_id is None
    with pytest.raises(ValueError, match="must not fabricate prompt identity"):
        ModelCapabilityRequirement(
            role="scientist",
            prompt_generation_id="fake",
            prompt_id="fake",
            prompt_digest="a" * 64,
            capability_id="embedding",
            input_schema_id="model.embedding.input.v1",
            output_schema_id="model.embedding.output.v1",
        )

def test_embedding_invocation_and_response_bind_exact_schema_and_digests() -> None:
    requirement = _requirement(
        "embedding", "model.embedding.input.v1", "model.embedding.output.v1"
    )
    payload = EmbeddingInput(("alpha", "beta"), normalize=True)
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "embed-1", payload)
    output = EmbeddingOutput(
        (EmbeddingVector((1.0, 2.0)), EmbeddingVector((3.0, 4.0))),
        model_revision="rev-1",
    )
    response = FunctionalModelCapabilityProvider(
        "embedding", _binding, lambda request: output
    ).bind_capability(requirement).invoke(invocation)
    assert response.request_digest == invocation.request_digest
    assert response.output is output
    assert response.output_schema_id == requirement.output_schema_id
    assert len(response.response_digest) == 64


def test_embedding_rejects_non_finite_or_dimension_drift() -> None:
    with pytest.raises(ValueError, match="finite"):
        EmbeddingVector((1.0, math.nan))
    with pytest.raises(ValueError, match="one dimension"):
        EmbeddingOutput(
            (EmbeddingVector((1.0,)), EmbeddingVector((1.0, 2.0))),
            model_revision="rev-1",
        )


def test_scoring_is_typed_and_rejects_duplicate_candidate_identity() -> None:
    requirement = _requirement(
        "scoring", "model.scoring.input.v1", "model.scoring.output.v1"
    )
    request = ScoringInput(
        "query",
        (ScoringCandidate("a", "A"), ScoringCandidate("b", "B")),
    )
    output = ScoringOutput(
        (ScoredCandidate("a", 0.2), ScoredCandidate("b", 0.8)),
        model_revision="rev-1",
    )
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "score-1", request)
    client = FunctionalModelCapabilityProvider(
        "scoring", _binding, lambda payload: output
    ).bind_capability(requirement)
    assert isinstance(client, ProjectModelCapabilityClientPort)
    assert isinstance(
        FunctionalModelCapabilityProvider("scoring", _binding, lambda payload: output),
        ProjectModelCapabilityProviderPort,
    )
    response = client.invoke(invocation)
    assert tuple(item.candidate_id for item in response.output.scores) == ("a", "b")
    with pytest.raises(ValueError, match="unique"):
        ScoringInput(
            "query",
            (ScoringCandidate("a", "A"), ScoringCandidate("a", "B")),
        )


def test_value_inference_has_typed_non_text_output() -> None:
    request = ValueInferenceInput((NamedScalar("x", 1.0), NamedScalar("y", -2.0)))
    output = ValueInferenceOutput(0.75, model_revision="rev-2", uncertainty=0.1)
    assert request.schema_id == "model.value.input.v1"
    assert output.schema_id == "model.value.output.v1"
    assert output.value == 0.75
    with pytest.raises(ValueError, match="finite"):
        ValueInferenceOutput(float("inf"), model_revision="rev-2")


def test_schema_drift_fails_before_handler_execution() -> None:
    requirement = _requirement(
        "embedding", "model.embedding.input.v1", "model.embedding.output.v1"
    )
    invoked = False

    def handler(payload: EmbeddingInput) -> EmbeddingOutput:
        nonlocal invoked
        invoked = True
        return EmbeddingOutput((EmbeddingVector((1.0,)),), model_revision="rev-1")

    client = FunctionalModelCapabilityProvider("embedding", _binding, handler).bind_capability(requirement)
    with pytest.raises(ValueError, match="schema"):
        ModelCapabilityInvocation(
            requirement.digest(), "embedding", "wrong.schema", "embed-drift", EmbeddingInput(("x",))
        )
    assert not invoked


def test_non_generation_requirement_has_small_level_zero_constructor() -> None:
    requirement = ModelCapabilityRequirement(
        role="scientist",
        capability_id="embedding",
        input_schema_id="model.embedding.input.v1",
        output_schema_id="model.embedding.output.v1",
    )
    assert requirement.prompt_generation_id is None
    assert requirement.prompt_id is None
    assert requirement.prompt_digest is None


def test_binding_capability_or_schema_drift_fails_before_handler() -> None:
    from dataclasses import replace

    requirement = _requirement(
        "embedding", "model.embedding.input.v1", "model.embedding.output.v1"
    )
    invoked = False

    def handler(payload: EmbeddingInput) -> EmbeddingOutput:
        nonlocal invoked
        invoked = True
        return EmbeddingOutput((EmbeddingVector((1.0,)),), model_revision="rev-1")

    for field_name, replacement in (
        ("capability_id", "scoring"),
        ("input_schema_id", "wrong.input.v1"),
        ("output_schema_id", "wrong.output.v1"),
    ):
        def drift_factory(req: ModelCapabilityRequirement) -> ProjectModelBinding:
            return replace(_binding(req), **{field_name: replacement})

        with pytest.raises(ValueError, match="drift"):
            FunctionalModelCapabilityProvider(
                "embedding", drift_factory, handler
            ).bind_capability(requirement)
    assert not invoked


def test_generation_provider_rejects_non_generation_before_binding_lookup() -> None:
    from research_platform.model.api import ModelBindingDiagnosticCode
    from research_platform.model.providers import QualifiedModelProjectProvider

    class ForbiddenBindingLookup:
        def binding_for(self, **kwargs):
            raise AssertionError("non-generation requirement reached generation binding lookup")

    requirement = ModelCapabilityRequirement(
        role="scientist",
        capability_id="embedding",
        input_schema_id="model.embedding.input.v1",
        output_schema_id="model.embedding.output.v1",
    )
    provider = QualifiedModelProjectProvider(
        profile=ModelProviderProfile("generation-only", ("chat",)),
        bindings=ForbiddenBindingLookup(),  # type: ignore[arg-type]
        endpoint_factory=lambda binding: (_ for _ in ()).throw(AssertionError("endpoint touched")),
        model_requests=object(),  # type: ignore[arg-type]
    )
    diagnostics = provider.diagnose(requirement)
    assert len(diagnostics) == 1
    assert diagnostics[0].code is ModelBindingDiagnosticCode.CAPABILITY_PROTOCOL_UNSUPPORTED



def test_ranking_capability_preserves_ordered_semantics_without_prompt_identity() -> None:
    requirement = _requirement(
        "ranking", "model.ranking.input.v1", "model.ranking.output.v1"
    )
    request = RankingInput(
        "best candidate",
        (
            RankingCandidate("a", "candidate A"),
            RankingCandidate("b", "candidate B"),
            RankingCandidate("c", "candidate C"),
        ),
        top_k=2,
    )
    output = RankingOutput(
        (RankedCandidate("b", 1, 0.9), RankedCandidate("a", 2, 0.7)),
        model_revision="ranker-r1",
    )
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "rank-1", request)
    response = FunctionalModelCapabilityProvider(
        "ranking", _binding, lambda payload: output
    ).bind_capability(requirement).invoke(invocation)
    assert response.output == output
    assert tuple(item.candidate_id for item in response.output.ranking) == ("b", "a")
    assert requirement.prompt_id is None
    with pytest.raises(ValueError, match="contiguous"):
        RankingOutput((RankedCandidate("a", 2),), model_revision="ranker-r1")
    with pytest.raises(ValueError, match="top_k"):
        RankingInput("q", (RankingCandidate("a", "A"),), top_k=2)


def test_policy_inference_capability_returns_typed_normalized_action_distribution() -> None:
    requirement = _requirement(
        "policy-inference", "model.policy.input.v1", "model.policy.output.v1"
    )
    request = PolicyInferenceInput(
        (NamedScalar("health", 0.8), NamedScalar("risk", 0.2)),
        ("advance", "wait"),
    )
    output = PolicyInferenceOutput(
        (
            PolicyActionProbability("advance", 0.75),
            PolicyActionProbability("wait", 0.25),
        ),
        model_revision="policy-r3",
        selected_action_id="advance",
    )
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "policy-1", request)
    response = FunctionalModelCapabilityProvider(
        "policy-inference", _binding, lambda payload: output
    ).bind_capability(requirement).invoke(invocation)
    assert response.output.selected_action_id == "advance"
    assert response.output.probabilities[0].probability == 0.75
    assert requirement.prompt_generation_id is None
    with pytest.raises(ValueError, match="sum to one"):
        PolicyInferenceOutput(
            (PolicyActionProbability("advance", 0.7), PolicyActionProbability("wait", 0.2)),
            model_revision="policy-r3",
        )
    with pytest.raises(ValueError, match="selected action"):
        PolicyInferenceOutput(
            (PolicyActionProbability("advance", 1.0),),
            model_revision="policy-r3",
            selected_action_id="wait",
        )



class _StructuredTextClient:
    def __init__(self, binding: ProjectModelBinding) -> None:
        self.binding = binding
        self.last_request = None

    def complete(self, request):
        self.last_request = request
        return ProjectModelResponse(
            request_digest=request.request_digest,
            binding_digest=self.binding.digest(),
            response_digest="f" * 64,
            text='{"answer": 42, "ok": true}',
            finish_reason="stop",
        )


class _StructuredTextProvider:
    def __init__(self, client: _StructuredTextClient) -> None:
        self.client = client

    def bind(self, requirement):
        assert requirement.capability_id == "structured-generation"
        return self.client


class _JsonSchemaDecoder:
    def __init__(self) -> None:
        self.schemas = []

    def decode_and_validate(self, text: str, *, schema_sha256: str):
        self.schemas.append(schema_sha256)
        assert schema_sha256 == "9" * 64
        document = json.loads(text)
        assert set(document) == {"answer", "ok"}
        return document


def _structured_requirement() -> ModelCapabilityRequirement:
    return ModelCapabilityRequirement(
        role="scientist",
        prompt_generation_id="prompt-generation-7",
        prompt_id="structured-answer",
        prompt_digest="8" * 64,
        capability_id="structured-generation",
        input_schema_id="model.structured-generation.input.v1",
        output_schema_id="model.structured-generation.output.v1",
    )


def _structured_binding(requirement: ModelCapabilityRequirement) -> ProjectModelBinding:
    profile = ModelProviderProfile("qualified-text", ("structured-generation",))
    return ProjectModelBinding(
        requirement_digest=requirement.digest(), provider_id=profile.provider_id,
        provider_profile_digest=profile.digest(), role=requirement.role, model=_model(),
        deployment_id="deployment-a", deployment_generation=D["generation"],
        model_stack_digest=D["stack"], qualification_certificate_digest=D["certificate"],
        runtime_qualification_digest=D["runtime"], host_identity_digest=D["host"],
        prompt_generation_id=requirement.prompt_generation_id, prompt_id=requirement.prompt_id,
        prompt_digest=requirement.prompt_digest, capabilities=profile.capabilities,
        runtime_canary_evidence_digests=(D["canary"],), capability_id=requirement.capability_id,
        input_schema_id=requirement.input_schema_id, output_schema_id=requirement.output_schema_id,
    )


def test_structured_generation_adapts_qualified_text_generation_without_new_prompt_or_endpoint_authority() -> None:
    requirement = _structured_requirement()
    binding = _structured_binding(requirement)
    text_client = _StructuredTextClient(binding)
    decoder = _JsonSchemaDecoder()
    provider = QualifiedStructuredGenerationCapabilityProvider(_StructuredTextProvider(text_client), decoder)
    envelope = ModelRequestEnvelope(
        "model-request.v1", "structured-request-1",
        ExecutionContext("run-s", "trace-s", "span-s"), requirement.role, _model(),
        requirement.prompt_generation_id, requirement.prompt_id, requirement.prompt_digest,
        ContentRef("7" * 64, 2, "application/json"),
    )
    payload = StructuredGenerationInput(
        envelope, {"messages": ({"role": "user", "content": "return json"},)}, "9" * 64
    )
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "structured-1", payload)
    response = provider.bind_capability(requirement).invoke(invocation)
    assert response.output.document["answer"] == 42
    assert response.output.output_schema_sha256 == "9" * 64
    assert response.output.source_response_digest == "f" * 64
    assert response.output.model_revision == _model().revision
    assert decoder.schemas == ["9" * 64]
    assert text_client.last_request.envelope is envelope
    assert text_client.last_request.requirement_digest == requirement.digest()


def test_structured_generation_rejects_noncanonical_output_schema_before_text_provider() -> None:
    requirement = _structured_requirement()
    with pytest.raises(ValueError, match="output_schema_sha256"):
        StructuredGenerationInput(
            ModelRequestEnvelope(
                "model-request.v1", "structured-request-bad",
                ExecutionContext("run-s", "trace-s", "span-s"), requirement.role, _model(),
                requirement.prompt_generation_id, requirement.prompt_id, requirement.prompt_digest,
                ContentRef("7" * 64, 2, "application/json"),
            ),
            {"messages": ()},
            "not-a-digest",
        )



def test_multimodal_inference_uses_content_addressed_refs_not_inline_media_or_paths() -> None:
    requirement = _requirement(
        "multimodal-inference", "model.multimodal.input.v1", "model.multimodal.output.v1"
    )
    image = ContentRef("a" * 64, 4096, "image/png")
    audio = ContentRef("b" * 64, 8192, "audio/wav")
    request = MultimodalInferenceInput(
        (MultimodalContent("observation-image", image), MultimodalContent("observation-audio", audio)),
        instruction="identify the event",
    )
    evidence = ContentRef("c" * 64, 1024, "application/json")
    output = MultimodalInferenceOutput(
        model_revision="multimodal-r4",
        text="event detected",
        content=(MultimodalContent("derived-evidence", evidence),),
    )
    invocation = ModelCapabilityInvocation.from_requirement(requirement, "multimodal-1", request)
    response = FunctionalModelCapabilityProvider(
        "multimodal-inference", _binding, lambda payload: output
    ).bind_capability(requirement).invoke(invocation)
    assert response.output.text == "event detected"
    assert response.output.content[0].content.sha256 == "c" * 64
    assert request.content[0].content.media_type == "image/png"
    assert request.content[1].content.media_type == "audio/wav"
    assert requirement.prompt_id is None


def test_multimodal_identity_changes_with_content_digest_and_empty_output_fails_closed() -> None:
    left = MultimodalInferenceInput(
        (MultimodalContent("image", ContentRef("d" * 64, 5, "image/png")),),
        instruction="inspect",
    )
    right = MultimodalInferenceInput(
        (MultimodalContent("image", ContentRef("e" * 64, 5, "image/png")),),
        instruction="inspect",
    )
    assert left.digest() != right.digest()
    with pytest.raises(ValueError, match="text or content"):
        MultimodalInferenceOutput(model_revision="multimodal-r4")
    with pytest.raises(TypeError, match="ContentRef"):
        MultimodalContent("image", b"raw-bytes")  # type: ignore[arg-type]
