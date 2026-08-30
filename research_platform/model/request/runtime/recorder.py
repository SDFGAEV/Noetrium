from __future__ import annotations


from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity, canonical_bytes
from research_platform.model.request._immutable_json import FrozenJsonObject, freeze_json_object, freeze_json_value
from research_platform.model.request.api import (
    ContentAddressedStorePort,
    ModelRequestEnvelope,
    ModelRequestLedgerPort,
    ReconstructedModelRequest,
)


def _canonical_json(value: object) -> bytes:
    return canonical_bytes(value)


class ReconstructableModelRequestRecorder:
    """Makes model-visible request bytes durable before returning the envelope to the caller."""

    def __init__(self, content: ContentAddressedStorePort, ledger: ModelRequestLedgerPort) -> None:
        self._content = content
        self._ledger = ledger

    def record(
        self,
        *,
        request_id: str,
        context: ExecutionContext,
        role: str,
        model: ImmutableModelIdentity,
        prompt_generation_id: str,
        prompt_id: str,
        prompt_digest: str,
        request_body: dict[str, object],
        compiled_prompt_text: str | None = None,
        tool_schema_bundle: object | None = None,
        source_artifact_refs: tuple[str, ...] = (),
        source_state_refs: tuple[str, ...] = (),
    ) -> ModelRequestEnvelope:
        frozen_body = freeze_json_object(request_body, field="model-visible request body")
        frozen_tools = None if tool_schema_bundle is None else freeze_json_value(
            tool_schema_bundle, field="model-visible tool schema bundle"
        )
        body_ref = self._content.put(_canonical_json(frozen_body), media_type="application/json")
        prompt_ref = None if compiled_prompt_text is None else self._content.put(
            compiled_prompt_text.encode("utf-8"), media_type="text/plain; charset=utf-8"
        )
        tool_ref = None if frozen_tools is None else self._content.put(
            _canonical_json(frozen_tools), media_type="application/json"
        )
        envelope = ModelRequestEnvelope(
            schema_version="model-request.v1",
            request_id=request_id,
            context=context,
            role=role,
            model=model,
            prompt_generation_id=prompt_generation_id,
            prompt_id=prompt_id,
            prompt_digest=prompt_digest,
            request_body=body_ref,
            compiled_prompt=prompt_ref,
            tool_schema_bundle=tool_ref,
            source_artifact_refs=source_artifact_refs,
            source_state_refs=source_state_refs,
        )
        self._ledger.append(envelope)
        return envelope

    def reconstruct(self, envelope: ModelRequestEnvelope) -> ReconstructedModelRequest:
        payload = self._content.get(envelope.request_body)
        body = json.loads(payload)
        if not isinstance(body, dict):
            raise RuntimeError("reconstructed model request body is not an object")
        compiled = None
        if envelope.compiled_prompt is not None:
            compiled = self._content.get(envelope.compiled_prompt).decode("utf-8")
        tools = None
        if envelope.tool_schema_bundle is not None:
            tools = json.loads(self._content.get(envelope.tool_schema_bundle))
        return ReconstructedModelRequest(body, compiled, tools)

    def reconstruct_request_body(self, envelope: ModelRequestEnvelope) -> FrozenJsonObject:
        return self.reconstruct(envelope).request_body

    def verify_visible_request(self, envelope: ModelRequestEnvelope, actual_body: dict[str, object]) -> None:
        if _canonical_json(actual_body) != self._content.get(envelope.request_body):
            raise RuntimeError("model-visible request drift: actual bytes are not durably referenced")


__all__ = ["ReconstructableModelRequestRecorder"]
