from __future__ import annotations

from typing import Callable

from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from ..api.cognition import AgentCognitionError, AgentObservation
from ..api.cognition_ports import AgentEvidencePort, AgentObservationPort


EventSink = Callable[..., None]
FailureSink = Callable[..., None]


class CognitionObservationPhase:
    """Own observation acquisition, validation and evidence ingestion."""

    def __init__(
        self,
        *,
        observation: AgentObservationPort,
        evidence: AgentEvidencePort,
        event: EventSink,
        failure: FailureSink,
    ) -> None:
        self._observation = observation
        self._evidence = evidence
        self._event = event
        self._failure = failure

    def accept(
        self,
        value: AgentObservation,
        context: ExecutionContext,
        *,
        phase: str,
    ) -> AgentObservation:
        try:
            if not isinstance(value, AgentObservation):
                raise TypeError("agent observation port returned an invalid observation")
            self._evidence.ingest(value, context)
            self._event(
                "AGENT_OBSERVATION",
                phase=phase,
                observation_id=value.observation_id,
                state_digest=value.state_digest,
                modality=value.modality,
            )
            return value
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_OBSERVATION_FAILED", str(exc), phase=phase)
            raise AgentCognitionError(
                phase,
                "AGENT_OBSERVATION_FAILED",
                str(exc),
                cause=exc,
            ) from exc

    def observe(self, context: ExecutionContext, *, phase: str) -> AgentObservation:
        try:
            value = self._observation.observe(context)
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_OBSERVATION_FAILED", str(exc), phase=phase)
            raise AgentCognitionError(
                phase,
                "AGENT_OBSERVATION_FAILED",
                str(exc),
                cause=exc,
            ) from exc
        return self.accept(value, context, phase=phase)


__all__ = ["CognitionObservationPhase"]