from __future__ import annotations

from dataclasses import replace

import pytest

from research_platform.experimentation.experiment.api import (
    ExperimentSpec,
    ExperimentTrialProtocol,
    ExperimentTrialProtocolIdentityMismatch,
)
from research_platform.experimentation.experiment.runtime import (
    trial_protocol_identity,
    verify_trial_protocol_identity,
)


class _OfflineTrialProtocol:
    protocol_id = "offline-score.v1"
    configuration_digest = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    surface_id = "offline.score.surface.v1"

    def run(self, surface, context, *, task, input_kind, input_payload):
        del surface, context, task, input_kind, input_payload
        return object()


def _spec() -> ExperimentSpec:
    return ExperimentSpec(
        "experiment-1", "study-1", "project-1", (),
        "1" * 64, "prompt", "2" * 64, "3" * 64, 1,
        "offline-score.v1", "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    )


def test_trial_protocol_identity_is_public_and_exact() -> None:
    protocol = _OfflineTrialProtocol()
    assert isinstance(protocol, ExperimentTrialProtocol)
    identity = trial_protocol_identity(protocol)
    assert identity.protocol_id == "offline-score.v1"
    assert identity.configuration_digest == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    verify_trial_protocol_identity(_spec(), identity)


def test_trial_protocol_identity_drift_fails_closed() -> None:
    identity = trial_protocol_identity(_OfflineTrialProtocol())
    with pytest.raises(ExperimentTrialProtocolIdentityMismatch, match="identity mismatch"):
        verify_trial_protocol_identity(
            replace(_spec(), trial_protocol_id="custom-state-machine.v2"),
            identity,
        )
