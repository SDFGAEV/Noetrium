"""Generic trial executor over compiled research plans."""

from __future__ import annotations

from noetrium_platform.research.experimentation.identity import OptionalIdentityFacet
from noetrium_platform.research.experimentation.study.api import (
    MeasurementRecord,
    TrialExecutionReceipt,
    TrialExecutionRequest,
    TrialMatrixExecutionReport,
    TrialProviderPort,
)

from noetrium_platform.research.experimentation.api.research_compiler import CompiledResearchPlan


def _require_measurements(
    plan: CompiledResearchPlan,
    request: TrialExecutionRequest,
    receipt: TrialExecutionReceipt,
) -> tuple[MeasurementRecord, ...]:
    if receipt.request_digest != request.request_digest:
        raise ValueError("trial receipt does not bind the execution request")
    if receipt.assignment_digest != request.assignment.assignment_digest:
        raise ValueError("trial receipt does not bind the assignment")
    expected_ids = {row.measurement_id for row in plan.measurement_protocol.definitions}
    actual_ids = tuple(row.measurement_id for row in receipt.measurements)
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids:
        raise ValueError("trial receipt does not exactly cover the measurement protocol")

    for record in receipt.measurements:
        record.validate_against(plan.measurement_protocol)
        if record.project_id != request.project_id or record.study_id != request.assignment.study_id:
            raise ValueError("trial measurement belongs to another project or study")
        if record.run_id != request.run_id:
            raise ValueError("trial measurement belongs to another run")
        if record.assignment_digest != request.assignment.assignment_digest:
            raise ValueError("trial measurement does not bind the assignment")
        if record.variant_id != request.assignment.variant_id:
            raise ValueError("trial measurement variant does not match assignment")
        if record.intervention != request.intervention:
            raise ValueError("trial measurement intervention does not match request")
        if record.revision != request.revision:
            raise ValueError("trial measurement revision does not match request")
    return receipt.measurements


class TrialMatrixExecutor:
    def execute(
        self,
        plan: CompiledResearchPlan,
        *,
        run_id: str,
        provider: TrialProviderPort,
    ) -> TrialMatrixExecutionReport:
        """Execute each compiled assignment and emit each measurement once.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: N is total emitted trial measurements plus assignments; each receipt and measurement is validated exactly once.
        """
        if type(plan) is not CompiledResearchPlan:
            raise TypeError("trial executor requires CompiledResearchPlan")

        if type(run_id) is not str or not run_id.strip():
            raise ValueError("trial executor run_id must be non-empty")
        protocol_identity = getattr(provider, "protocol_identity", None)
        expected_protocol = plan.trial_protocol_identity
        if protocol_identity != expected_protocol:
            raise ValueError("trial provider protocol identity does not match compiled plan")
        binding_by_variant = {
            row.variant.variant_id: row for row in plan.experiment_plan.bindings
        }
        records: list[MeasurementRecord] = []
        receipts: list[str] = []
        for assignment in plan.experiment_plan.assignments:
            request = TrialExecutionRequest(
                plan.experiment.project_id,
                run_id,
                plan.research_plan_digest,
                plan.research_semantics.revision,
                plan.research_semantics.participant_schedule,
                OptionalIdentityFacet(binding_by_variant[assignment.variant_id].intervention_digest),
                assignment,
                binding_by_variant[assignment.variant_id],
                plan.measurement_protocol,
                protocol_identity,
            )
            receipt = provider.run_trial(request)
            if type(receipt) is not TrialExecutionReceipt:
                raise TypeError("trial provider must return TrialExecutionReceipt")
            records.extend(_require_measurements(plan, request, receipt))
            receipts.append(receipt.receipt_digest)

        return TrialMatrixExecutionReport(
            plan.experiment.project_id,
            run_id,
            plan.research_plan_digest,
            tuple(records),
            tuple(receipts),
        )


__all__ = ["TrialMatrixExecutor"]
