from __future__ import annotations

from dataclasses import dataclass
import hashlib
from collections.abc import Mapping

from research_platform.platform.kernel import JsonInput, canonical_bytes
from research_platform.platform.kernel.identity import ImmutableModelIdentity
from .runtime_contracts import PromptResolution


@dataclass(frozen=True, slots=True)
class PromptRequestContract:
    request_id: str
    generation_id: str
    prompt_id: str
    prompt_digest: str
    role: str
    model_resume_key: tuple[object, ...]
    body_sha256: str
    temperature: float
    top_p: float
    max_output_tokens: int


def build_prompt_request_contract(
    *,
    request_id: str,
    resolution: PromptResolution,
    model: ImmutableModelIdentity,
    request_body: Mapping[str, JsonInput],
) -> PromptRequestContract:
    bundle = resolution.bundle
    encoded = canonical_bytes(request_body)
    return PromptRequestContract(
        request_id=request_id,
        generation_id=resolution.generation_id,
        prompt_id=bundle.prompt_id,
        prompt_digest=bundle.digest,
        role=bundle.role,
        model_resume_key=model.resume_key(),
        body_sha256=hashlib.sha256(encoded).hexdigest(),
        temperature=bundle.temperature,
        top_p=bundle.top_p,
        max_output_tokens=bundle.max_output_tokens,
    )


def verify_prompt_request_contract(
    contract: PromptRequestContract,
    *,
    resolution: PromptResolution,
    model: ImmutableModelIdentity,
    request_body: Mapping[str, JsonInput],
) -> None:
    actual = build_prompt_request_contract(
        request_id=contract.request_id,
        resolution=resolution,
        model=model,
        request_body=request_body,
    )
    if actual != contract:
        raise ValueError("prompt request contract drift")
