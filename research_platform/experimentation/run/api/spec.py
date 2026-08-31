from __future__ import annotations

from dataclasses import dataclass
import re

from research_platform.platform.kernel import canonical_digest


@dataclass(frozen=True, slots=True)
class ExperimentRunSpec:
    """Immutable, environment-neutral identity of one experiment run.

    The specification deliberately contains no server, model-client, process
    or filesystem-provider object. Those are selected by an outer composition
    root and are represented here only by frozen identities/digests. MC and
    non-MC adapters therefore consume the same run identity without sharing
    provider details.
    """

    run_id: str
    project_id: str
    experiment_id: str
    study_id: str
    execution_profile: str
    task_manifest_digest: str
    seed_schedule_digest: str
    repetitions: int
    artifact_root: str
    environment_identity_digest: str
    model_binding_digest: str | None = None
    prompt_generation: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.run_id,
            self.project_id,
            self.experiment_id,
            self.study_id,
            self.execution_profile,
            self.task_manifest_digest,
            self.seed_schedule_digest,
            self.artifact_root,
            self.environment_identity_digest,
        )
        if any(not value.strip() for value in required):
            raise ValueError("experiment run specification contains an empty identity")
        if re.fullmatch(r"[A-Za-z0-9_.:-]+", self.execution_profile) is None:
            raise ValueError("experiment run execution_profile is not a safe identity")
        if self.repetitions <= 0:
            raise ValueError("experiment run repetitions must be positive")
        if self.model_binding_digest is not None and not self.model_binding_digest.strip():
            raise ValueError("experiment run model_binding_digest cannot be empty")
        if self.prompt_generation is not None and not self.prompt_generation.strip():
            raise ValueError("experiment run prompt_generation cannot be empty")

    def scientific_identity_digest(self) -> str:
        return canonical_digest({
            "run_id": self.run_id, "project_id": self.project_id,
            "experiment_id": self.experiment_id, "study_id": self.study_id,
            "task_manifest_digest": self.task_manifest_digest,
            "seed_schedule_digest": self.seed_schedule_digest,
            "repetitions": self.repetitions,
            "model_binding_digest": self.model_binding_digest,
            "prompt_generation": self.prompt_generation,
        })

    def execution_placement_digest(self) -> str:
        return canonical_digest({
            "execution_profile": self.execution_profile,
            "artifact_root": self.artifact_root,
            "environment_identity_digest": self.environment_identity_digest,
        })

    def identity_digest(self) -> str:
        return canonical_digest({
            "scientific_identity_digest": self.scientific_identity_digest(),
            "execution_placement_digest": self.execution_placement_digest(),
        })


__all__ = ["ExperimentRunSpec"]
