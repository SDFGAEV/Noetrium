from __future__ import annotations

from noetrium_platform.foundation.kernel.kernel import (
    ExecutionContext,
    JsonValue,
    OperationResult,
    canonical_digest,
)

from noetrium_platform.research.execution.workflow.api import TrialCycleExecution
from .contracts import ContextActionOperationPort


class ContextActionTrialProtocol:
    """Default context-action workflow; preserves the original Study trial semantics."""

    protocol_id = "context_action.v2"
    surface_id = "context_action.operations.v1"
    configuration_digest = canonical_digest({})

    def run(
        self,
        operations: ContextActionOperationPort,
        context: ExecutionContext,
        *,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> TrialCycleExecution:
        rows: list[OperationResult[JsonValue]] = list(
            operations.preflight_action(input_kind, input_payload, context)
        )
        recovered = operations.try_recover_committed_cycle(
            input_kind, input_payload, context
        )
        if recovered is not None:
            return TrialCycleExecution(
                "",
                recovered.action_result,
                recovered.final_context,
                tuple(rows) + recovered.operation_results,
            )

        observation, operation = operations.observe(context)
        rows.append(operation)
        context = context.with_generation("environment", observation.generation)

        rows.append(operations.ingest(observation, context))

        recall, operation = operations.recall(str(task), context)
        rows.append(operation)
        context = context.with_generation("method", recall.method_generation)

        action_result, action_operations = operations.act(input_kind, input_payload, context)
        rows.extend(action_operations)
        if action_result.observation is not None:
            context = context.with_generation("environment", action_result.observation.generation)

        completion = operations.task_completed(action_result, context)
        rows.extend(completion.operation_results)
        if completion.receipt is not None and completion.receipt.method_generation is not None:
            context = context.with_generation("method", completion.receipt.method_generation)

        return TrialCycleExecution(
            recall.context_text,
            action_result,
            context,
            tuple(rows),
        )
