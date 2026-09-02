from __future__ import annotations

from noetrium_platform.research.experimentation.experiment.api import ExperimentSpec
from noetrium_platform.research.experimentation.run.identity.api import RunIdentity
from noetrium_platform.research.experimentation.study import StudySpec
from noetrium_platform.foundation.scope.api import ScopeIdentity, ScopeKind, ScopeRegistryPort


class ExperimentationCatalogConflict(RuntimeError):
    pass


class ExperimentationCatalogNotFound(KeyError):
    pass


class InMemoryExperimentationCatalog:
    """Study/Experiment/Run hierarchy authority backed by Scope System."""

    def __init__(self, scopes: ScopeRegistryPort) -> None:
        self._scopes = scopes
        self._studies: dict[str, StudySpec] = {}
        self._experiments: dict[str, ExperimentSpec] = {}
        self._runs: dict[str, tuple[str, RunIdentity]] = {}

    @staticmethod
    def _put(store: dict[str, object], key: str, value: object) -> None:
        current = store.get(key)
        if current is not None and current != value:
            raise ExperimentationCatalogConflict(key)
        store[key] = value

    def register_study(self, spec: StudySpec) -> None:
        parent = ScopeIdentity(ScopeKind.PROJECT, spec.project_id)
        if not self._scopes.contains(parent):
            raise ExperimentationCatalogNotFound(parent.key)
        self._put(self._studies, spec.study_id, spec)
        self._scopes.register(spec.scope, parent)

    def register_experiment(self, spec: ExperimentSpec) -> None:
        try:
            study = self._studies[spec.study_id]
        except KeyError as exc:
            raise ExperimentationCatalogNotFound(spec.study_id) from exc
        if study.project_id != spec.project_id:
            raise ExperimentationCatalogConflict("experiment project_id does not match its Study")
        if spec.experiment_id not in study.experiment_ids:
            raise ExperimentationCatalogConflict("experiment is not declared by its Study")
        self._put(self._experiments, spec.experiment_id, spec)
        self._scopes.register(spec.scope, study.scope)

    def register_run(self, experiment_id: str, identity: RunIdentity) -> None:
        try:
            experiment = self._experiments[experiment_id]
        except KeyError as exc:
            raise ExperimentationCatalogNotFound(experiment_id) from exc
        value = (experiment_id, identity)
        self._put(self._runs, identity.run_id, value)
        self._scopes.register(identity.scope, experiment.scope)

    def study(self, study_id: str) -> StudySpec:
        try:
            return self._studies[study_id]
        except KeyError as exc:
            raise ExperimentationCatalogNotFound(study_id) from exc

    def experiment(self, experiment_id: str) -> ExperimentSpec:
        try:
            return self._experiments[experiment_id]
        except KeyError as exc:
            raise ExperimentationCatalogNotFound(experiment_id) from exc

    def experiments(self, *, study_id: str | None = None) -> tuple[ExperimentSpec, ...]:
        rows = self._experiments.values()
        if study_id is not None:
            rows = (row for row in rows if row.study_id == study_id)
        return tuple(sorted(rows, key=lambda row: row.experiment_id))


__all__ = ["ExperimentationCatalogConflict", "ExperimentationCatalogNotFound", "InMemoryExperimentationCatalog"]
