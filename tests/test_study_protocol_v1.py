from __future__ import annotations

from research_platform.experimentation.study.api import (
    StudyConcurrencyPolicy,
    StudyAssignment,
    StudyMetricAggregate,
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantExecutionReceipt,
    VariantKind,
)
from research_platform.experimentation.study.runtime import BasicStudyMetricAggregator, DeterministicStudyAssignment
import pytest


def _protocol() -> StudyProtocol:
    return StudyProtocol(
        "study-1",
        "workload-1",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "memory.fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "memory.evolving", "b" * 64),
        ),
        2,
        "c" * 64,
        ("success_rate", "utility"),
        "d" * 64,
    )


def test_study_protocol_expands_full_variant_repetition_matrix_and_aggregates():
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    assert len(assignments) == 4
    observations = tuple(
        StudyMetricObservation(assignment, (("success_rate", 1.0), ("utility", 2.0)))
        for assignment in assignments
    )
    aggregates = BasicStudyMetricAggregator().aggregate(protocol, observations, assignments)
    assert {(item.variant_id, item.metric_name, item.count) for item in aggregates} == {
        ("control", "success_rate", 2),
        ("control", "utility", 2),
        ("treatment", "success_rate", 2),
        ("treatment", "utility", 2),
    }


def test_study_aggregation_rejects_incomplete_matrix() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    observations = tuple(
        StudyMetricObservation(assignments[0], (("success_rate", 1.0), ("utility", 2.0)))
        for _ in (0,)
    )
    with pytest.raises(ValueError, match="matrix is incomplete"):
        BasicStudyMetricAggregator().aggregate(protocol, observations, assignments)


def test_study_aggregation_rejects_incomplete_metric_schema() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    observations = tuple(
        StudyMetricObservation(assignment, (("success_rate", 1.0),))
        for assignment in assignments
    )
    with pytest.raises(ValueError, match="metric schema is incomplete"):
        BasicStudyMetricAggregator().aggregate(protocol, observations, assignments)


def test_study_contracts_reject_bool_as_integer_identity() -> None:
    with pytest.raises(TypeError, match="repetitions must be an integer"):
        StudyProtocol(
            "study", "workload",
            (StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),),
            True, "b" * 64, ("score",), "c" * 64,
        )
    with pytest.raises(TypeError, match="repetition must be an integer"):
        StudyAssignment("study", "control", True, "seed")
    with pytest.raises(TypeError, match="max_parallel_repetitions must be an integer"):
        StudyConcurrencyPolicy(max_parallel_repetitions=True)


def test_study_contracts_reject_implicit_scalar_coercion() -> None:
    assignment = StudyAssignment("study", "control", 0, "seed")
    with pytest.raises(TypeError, match="must be numeric"):
        StudyMetricObservation(assignment, (("score", "1.0"),))
    with pytest.raises(TypeError, match="count must be an integer"):
        StudyMetricAggregate("study", "control", "score", True, 1.0, 0.0, 0.0)
    with pytest.raises(TypeError, match="kind must be VariantKind"):
        StudyVariantSpec("control", "control", "fixed", "a" * 64)


def test_study_aggregate_rejects_impossible_uncertainty_statistics() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        StudyMetricAggregate("study", "control", "score", 2, 1.0, -1.0, 0.0)

def test_variant_execution_receipt_validates_provider_output_immediately() -> None:
    assignment = StudyAssignment("study", "control", 0, "seed")
    receipt = VariantExecutionReceipt(assignment, (("score", 1.0),))
    assert receipt.as_observation() == StudyMetricObservation(assignment, (("score", 1.0),))
    with pytest.raises(TypeError, match="assignment must be StudyAssignment"):
        VariantExecutionReceipt(object(), (("score", 1.0),))
    with pytest.raises(TypeError, match="metrics must be a tuple"):
        VariantExecutionReceipt(assignment, [("score", 1.0)])
    with pytest.raises(ValueError, match="unique metrics"):
        VariantExecutionReceipt(assignment, (("score", 1.0), ("score", 2.0)))
