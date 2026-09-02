from __future__ import annotations

from noetrium_platform.foundation.kernel.kernel import canonical_digest

from noetrium_platform.research.execution.workflow.api import TrialCycleExecution
from .contracts import AgentTurnOperationPort


class AgentTurnTrialProtocol:
    """Generic Agent workflow with no Environment or Method assumptions."""

    protocol_id = "agent_turn.v1"
    surface_id = "agent_turn.operations.v1"
    configuration_digest = canonical_digest({})

    def run(
        self,
        operations: AgentTurnOperationPort,
        context,
        *,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> TrialCycleExecution:
        result, rows = operations.agent_turn(
            task,
            {"input_kind": input_kind, "payload": input_payload},
            context,
        )
        final_context = (
            context.with_generation("agent", result.agent_generation)
            if result.agent_generation is not None
            else context
        )
        return TrialCycleExecution(
            context_text=str(result.output),
            primary_result=result,
            final_context=final_context,
            operation_results=rows,
        )


__all__ = ["AgentTurnTrialProtocol"]
