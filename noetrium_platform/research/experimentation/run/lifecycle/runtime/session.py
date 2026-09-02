from __future__ import annotations

from noetrium_platform.foundation.kernel.kernel import ExecutionContext, JsonValue, OperationResult

from ..api.contracts import RunCleanupReport
from noetrium_platform.research.execution.decision.cycle_identity import DecisionCycleIdentity
from noetrium_platform.research.execution.decision.cycle_result import DecisionCycleResult
from .closer import RunCloser
from ..api import RunCycleExecutorPort
from ...identity.api import RunIdentity
from .state import RunState
from noetrium_platform.research.experimentation.experiment.api import ExperimentSpec


class RunSession:
    """Long-lived run façade over cycle execution, run state, and cleanup authorities."""

    def __init__(
        self,
        *,
        spec: ExperimentSpec,
        identity: RunIdentity,
        cycle_executor: RunCycleExecutorPort,
        closer: RunCloser,
        open_operations: tuple[OperationResult[JsonValue], ...],
        initial_context: ExecutionContext,
    ) -> None:
        self.spec = spec
        self.identity = identity
        self.open_operations = open_operations
        self.state = RunState(last_context=initial_context)
        self._cycle_executor = cycle_executor
        self._closer = closer

    @property
    def latest_checkpoint_id(self) -> str | None:
        return self.state.latest_checkpoint_id

    @property
    def requires_recovery(self) -> bool:
        return self.state.requires_recovery

    def execute(
        self,
        *,
        task: object,
        input_kind: str = "input",
        input_payload: object = None,
        cycle_identity: DecisionCycleIdentity,
    ) -> DecisionCycleResult:
        self.state.require_runnable()
        try:
            execution = self._cycle_executor.execute(
                task=task,
                input_kind=input_kind,
                input_payload=input_payload,
                cycle_identity=cycle_identity,
                previous_context=self.state.last_context,
            )
        except BaseException:
            self.state.mark_failed()
            raise
        self.state.mark_cycle_complete(
            execution.final_context,
            execution.checkpoint_id,
        )
        return execution.result

    def close(self) -> RunCleanupReport:
        if self.state.closed:
            return RunCleanupReport(())
        try:
            return self._closer.close(
                self.state.last_context,
                trial_completed=self.state.completed_cycles > 0,
            )
        finally:
            self.state.mark_closed()

    def __enter__(self) -> "RunSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.close()
        except BaseException as cleanup_exc:
            if exc is not None:
                try:
                    exc.add_note(f"study run close failure: {cleanup_exc}")
                except AttributeError:
                    pass
                return False
            raise
        return False


__all__ = ["RunSession"]
