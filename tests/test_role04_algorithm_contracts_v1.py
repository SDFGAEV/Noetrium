from __future__ import annotations

import pytest

from research_platform.model.qualification.api import (
    DeploymentQualificationApplicationReceipt,
    DeploymentQualificationRuntimeReceipt,
    DeploymentRuntimeQualificationStatus,
    InstallPackage,
    QualificationCommandReceipt,
    QualificationMaterializationStatus,
    RuntimeCheckReceipt,
)
from research_platform.model.serving.endpoint.api import QualifiedModelEndpointBinding
from research_platform.participant.agent.api.cognition import AgentObservation
from research_platform.participant.agent.runtime.conversation import ConversationMessage
from research_platform.platform.kernel import ImmutableModelIdentity


_SHA = "a" * 64


def _command() -> QualificationCommandReceipt:
    return QualificationCommandReceipt("install", _SHA, 0, "b" * 64, "c" * 64)


def _check() -> RuntimeCheckReceipt:
    return RuntimeCheckReceipt("check", _SHA, 0, "b" * 64, "c" * 64)


def _model() -> ImmutableModelIdentity:
    return ImmutableModelIdentity("m", "repo/m", "rev", "vllm", "1.0", "bf16", None, 4096)


def test_application_receipt_checks_last_variable_length_element() -> None:
    packages = (
        InstallPackage("a", "1", "https://example.invalid/simple"),
        InstallPackage("b", "1", "https://example.invalid/simple"),
        object(),
    )
    with pytest.raises(ValueError, match="packages must be typed"):
        DeploymentQualificationApplicationReceipt(
            _SHA, "env", "vllm", packages, (_command(),), _command(),
            QualificationMaterializationStatus.SUCCEEDED,
        )


def test_runtime_receipt_checks_last_variable_length_element() -> None:
    with pytest.raises(ValueError, match="checks must be typed"):
        DeploymentQualificationRuntimeReceipt(
            _SHA, _SHA, "env", "vllm", (_check(), _check(), object()),
            DeploymentRuntimeQualificationStatus.PASSED,
        )


def test_qualified_binding_checks_last_canary_digest() -> None:
    with pytest.raises(ValueError, match="runtime_canary_evidence_digests"):
        QualifiedModelEndpointBinding(
            role="planner", deployment_id="dep", deployment_generation="1" * 64,
            base_url="http://127.0.0.1:30000", model=_model(),
            model_stack_digest="2" * 64, qualification_certificate_digest="3" * 64,
            runtime_qualification_digest="4" * 64, host_identity_digest="5" * 64,
            prompt_generation="prompt-v1", max_admitted_concurrency=1,
            runtime_canary_evidence_digests=("6" * 64, "7" * 64, "bad"),
        )


def test_agent_observation_checks_last_artifact_reference() -> None:
    with pytest.raises(TypeError, match="artifact_refs"):
        AgentObservation(
            "obs", "generation", {"ok": True},
            artifact_refs=("artifact:a", "artifact:b", ""),
        )


def test_conversation_message_checks_last_metadata_value() -> None:
    with pytest.raises(TypeError, match="metadata"):
        ConversationMessage(
            "m", "peer", "sender", "text", 1,
            metadata={"a": "1", "b": "2", "tail": 3},
        )
