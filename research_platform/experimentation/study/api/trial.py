"""Neutral trial lifecycle shared by arbitrary paper-general loops."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from research_platform.experimentation.experiment.api import ExperimentTrialProtocolIdentity
from research_platform.experimentation.identity import OptionalIdentityFacet
from research_platform.artifact.reference.api import ArtifactReference
from research_platform.platform.kernel import canonical_digest

from .contracts import StudyAssignment
from .measurement import MeasurementProtocol, MeasurementRecord
from .plan import VariantBinding

_HEX = frozenset("0123456789abcdef")


def _text(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _sha(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(ch not in _HEX for ch in text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text

@dataclass(frozen=True, slots=True)
class TrialExecutionRequest:
    project_id: str
    run_id: str
    research_plan_digest: str
    revision: OptionalIdentityFacet
    participant_schedule: OptionalIdentityFacet
    intervention: OptionalIdentityFacet
    assignment: StudyAssignment
    binding: VariantBinding
    measurement_protocol: MeasurementProtocol
    protocol_identity: ExperimentTrialProtocolIdentity
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.project_id, "trial request project_id")
        _text(self.run_id, "trial request run_id")
        _sha(self.research_plan_digest, "trial request research_plan_digest")
        if type(self.revision) is not OptionalIdentityFacet:
            raise TypeError("trial request revision must be OptionalIdentityFacet")
        if type(self.participant_schedule) is not OptionalIdentityFacet:
            raise TypeError("trial request participant_schedule must be OptionalIdentityFacet")
        if type(self.intervention) is not OptionalIdentityFacet:
            raise TypeError("trial request intervention must be OptionalIdentityFacet")
        if type(self.assignment) is not StudyAssignment:
            raise TypeError("trial request assignment must be StudyAssignment")
        if type(self.binding) is not VariantBinding:
            raise TypeError("trial request binding must be VariantBinding")
        if self.assignment.variant_id != self.binding.variant.variant_id:
            raise ValueError("trial request binding does not match assignment")
        if type(self.measurement_protocol) is not MeasurementProtocol:
            raise TypeError("trial request measurement_protocol must be MeasurementProtocol")
        if type(self.protocol_identity) is not ExperimentTrialProtocolIdentity:
            raise TypeError("trial request protocol_identity must be ExperimentTrialProtocolIdentity")
        object.__setattr__(self, "request_digest", canonical_digest({
            "project_id": self.project_id,
            "run_id": self.run_id,
            "research_plan_digest": self.research_plan_digest,
            "revision": self.revision,
            "participant_schedule": self.participant_schedule,
            "intervention": self.intervention,
            "assignment_digest": self.assignment.assignment_digest,
            "binding_digest": self.binding.binding_digest,
            "measurement_protocol_digest": self.measurement_protocol.protocol_digest,
            "protocol_identity_digest": self.protocol_identity.digest(),
        }))


@dataclass(frozen=True, slots=True)
class TrialExecutionReceipt:
    request_digest: str
    assignment_digest: str
    measurements: tuple[MeasurementRecord, ...]
    evidence_refs: tuple[ArtifactReference, ...] = ()
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.request_digest, "trial receipt request_digest")
        _sha(self.assignment_digest, "trial receipt assignment_digest")
        if type(self.measurements) is not tuple:
            raise TypeError("trial receipt measurements must be a tuple")
        if any(type(row) is not MeasurementRecord for row in self.measurements):
            raise TypeError("trial receipt measurements must contain MeasurementRecord")
        if type(self.evidence_refs) is not tuple or any(type(row) is not ArtifactReference for row in self.evidence_refs):
            raise TypeError("trial receipt evidence_refs must contain ArtifactReference")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("trial receipt evidence_refs must be unique")
        object.__setattr__(self, "receipt_digest", canonical_digest({
            "request_digest": self.request_digest,
            "assignment_digest": self.assignment_digest,
            "measurements": tuple(row.record_digest for row in self.measurements),
            "evidence_refs": self.evidence_refs,
        }))


class TrialProviderPort(Protocol):
    protocol_identity: ExperimentTrialProtocolIdentity

    def run_trial(self, request: TrialExecutionRequest) -> TrialExecutionReceipt: ...


@dataclass(frozen=True, slots=True)
class TrialMatrixExecutionReport:
    project_id: str
    run_id: str
    research_plan_digest: str
    records: tuple[MeasurementRecord, ...]
    trial_receipt_digests: tuple[str, ...]
    report_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.project_id, "trial report project_id")
        _text(self.run_id, "trial report run_id")
        _sha(self.research_plan_digest, "trial report research_plan_digest")
        if type(self.records) is not tuple or any(type(row) is not MeasurementRecord for row in self.records):
            raise TypeError("trial report records must contain MeasurementRecord")
        if type(self.trial_receipt_digests) is not tuple or any(type(row) is not str for row in self.trial_receipt_digests):
            raise TypeError("trial report receipt digests must be strings")
        for digest in self.trial_receipt_digests:
            _sha(digest, "trial report receipt digest")
        object.__setattr__(self, "report_digest", canonical_digest({
            "project_id": self.project_id,
            "run_id": self.run_id,
            "research_plan_digest": self.research_plan_digest,
            "records": tuple(row.record_digest for row in self.records),
            "receipts": self.trial_receipt_digests,
        }))


__all__ = [
    "TrialExecutionReceipt",
    "TrialExecutionRequest",
    "TrialMatrixExecutionReport",
    "TrialProviderPort",
]