from __future__ import annotations

from noetrium_platform.capabilities.environment.runtime.api import ActionRecoveryRequired
from noetrium_platform.foundation.kernel.kernel import ExecutionContext

from .action_commit_tracker import ActionCommitTracker
from .action_contracts import SafeActionExecution
from .action_preparation import ActionPreparationCoordinator
from .committed_action_recovery import CommittedActionRecovery


class ActionCommittedRecoveryCoordinator:
    """Recovers committed actions exclusively from durable provider recovery handles."""

    def __init__(
        self,
        preparation: ActionPreparationCoordinator,
        recovery: CommittedActionRecovery | None,
        commit_tracker: ActionCommitTracker,
    ) -> None:
        self._preparation = preparation
        self._recovery = recovery
        self._commit_tracker = commit_tracker

    def recover(
        self,
        *,
        action_type: str,
        action_payload: object,
        context: ExecutionContext,
    ) -> SafeActionExecution:
        existing = self._preparation.nonterminal_candidate
        if existing is None or self._recovery is None:
            raise ActionRecoveryRequired(
                "committed-method recovery requires a non-terminal action intent"
            )
        if existing.intent.recovery_handle is None:
            raise ActionRecoveryRequired(
                "committed-method recovery requires a durable provider recovery handle"
            )
        execution = self._recovery.recover_durable(existing, context)
        self._commit_tracker.activate(existing.intent)
        return execution


__all__ = ["ActionCommittedRecoveryCoordinator"]
