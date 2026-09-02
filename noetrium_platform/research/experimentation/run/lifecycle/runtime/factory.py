from __future__ import annotations

from noetrium_platform.research.experimentation.experiment.api import ExperimentSpec
from noetrium_platform.research.experimentation.run.identity.api import RunIdentity
from noetrium_platform.capabilities.participant.core.api import ParticipantSessionBinding
from noetrium_platform.capabilities.participant.core.api.runtime_ports import ParticipantSessionLifecyclePort
from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonValue, OperationResult

from ..api import RunCycleExecutorPort, RunSessionPort
from .closer import RunCloser
from .session import RunSession


class DefaultRunSessionFactory:
    """Default Lifecycle implementation for constructing an open run session."""

    def create(
        self,
        *,
        spec: ExperimentSpec,
        identity: RunIdentity,
        cycle_executor: RunCycleExecutorPort,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        participant_lifecycle: ParticipantSessionLifecyclePort,
        open_operations: tuple[OperationResult[JsonValue], ...],
        initial_context: ExecutionContext,
    ) -> RunSessionPort:
        closer = RunCloser(
            spec=spec,
            identity=identity,
            participant_sessions=participant_sessions,
            lifecycle=participant_lifecycle,
        )
        return RunSession(
            spec=spec,
            identity=identity,
            cycle_executor=cycle_executor,
            closer=closer,
            open_operations=open_operations,
            initial_context=initial_context,
        )


__all__ = ["DefaultRunSessionFactory"]
