from __future__ import annotations

from dataclasses import dataclass

from research_platform.experimentation.run.api import DecisionCycleCoordinatorPort, RunCoordinatorPort
from research_platform.experimentation.experiment.api import ExperimentTrialProtocolIdentity


@dataclass(frozen=True, slots=True)
class ExperimentRuntimeComponents:
    trial_protocol_identity: ExperimentTrialProtocolIdentity
    cycle_coordinator: DecisionCycleCoordinatorPort
    run_coordinator: RunCoordinatorPort


__all__ = ["ExperimentRuntimeComponents"]
