from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract
import time

from .contracts import ServicePhase, ServiceReadyEvidence
from .service_state_contracts import ServiceSupervisorState
from .start_intent_contracts import ServiceStartIntent
from .state_transition import ServiceStateTransitionWriter
from .supervision_contracts import ServiceProcessAdapter


def service_start_intent_refs(intent: ServiceStartIntent) -> tuple[str, ...]:
    refs = [f"service-start-intent:{intent.intent_id}"]
    handle = intent.recovery_handle
    if handle is not None:
        refs.append(f"service-start-recovery:{handle.provider_schema}:{handle.payload_sha256}")
    return tuple(refs)


class ServiceReadinessCommitter:
    """Owns readiness observation -> RUNNING state publication only."""

    def __init__(
        self,
        adapter: ServiceProcessAdapter,
        transitions: ServiceStateTransitionWriter,
    ) -> None:
        self._adapter = adapter
        self._transitions = transitions

    def commit(
        self,
        contract: ServiceLaunchContract,
        state: ServiceSupervisorState,
        process,
    ) -> tuple[ServiceSupervisorState, tuple[str, str, str]]:
        ready_ref, stdout_ref, stderr_ref = self._adapter.wait_ready(process, contract)
        ready = ServiceReadyEvidence(
            contract.digest(), process, ready_ref, stdout_ref, stderr_ref, time.time()
        )
        state = self._transitions.persist(
            state,
            ServicePhase.RUNNING,
            process=process,
            ready_evidence_ref=ready_ref,
            ready_at=ready.ready_at,
            stdout_capture_ref=stdout_ref,
            stderr_capture_ref=stderr_ref,
            last_heartbeat_at=ready.ready_at,
            last_failure_id=None,
            last_exit_class=None,
        )
        return state, (ready_ref, stdout_ref, stderr_ref)


__all__ = ["ServiceReadinessCommitter", "service_start_intent_refs"]
