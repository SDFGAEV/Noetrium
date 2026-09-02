from __future__ import annotations

from typing import TypeVar

from noetrium_platform.foundation.kernel.kernel import canonical_digest
from noetrium_platform.capabilities.environment.catalog.api import (
    EnvironmentAssignment,
    EnvironmentBinding,
    EnvironmentInstance,
    EnvironmentOverlay,
    EnvironmentSpec,
    EnvironmentTemplate,
    ResolvedEnvironmentSpec,
)
from noetrium_platform.infrastructure.resources.resolution import HierarchicalResourceResolver, ScopedValue
from noetrium_platform.foundation.scope.api import ScopeIdentity, ScopeRegistryPort


_T = TypeVar("_T")


class EnvironmentCatalogConflict(RuntimeError):
    pass


class EnvironmentCatalogNotFound(KeyError):
    pass


class ExecutionEnvironmentCatalog:
    """Hierarchy-aware logical environment authority.

    Logical specifications inherit through Scope System.  Physical Python/Conda/etc.
    environments remain separate instances and can be reused by many scoped bindings.
    """

    def __init__(self, scopes: ScopeRegistryPort) -> None:
        self._scopes = scopes
        self._templates: dict[str, EnvironmentTemplate] = {}
        self._specs: dict[str, EnvironmentSpec] = {}
        self._overlays: dict[str, EnvironmentOverlay] = {}
        self._assignments = HierarchicalResourceResolver[str](ancestry=scopes.ancestry)
        self._instances: dict[str, EnvironmentInstance] = {}
        self._bindings = HierarchicalResourceResolver[EnvironmentBinding](ancestry=scopes.ancestry)

    @staticmethod
    def _put(store: dict[str, _T], key: str, value: _T) -> None:
        current = store.get(key)
        if current is not None and current != value:
            raise EnvironmentCatalogConflict(key)
        store[key] = value

    def register_template(self, template: EnvironmentTemplate) -> None:
        self._put(self._templates, template.template_id, template)

    def register_spec(self, spec: EnvironmentSpec) -> None:
        if spec.parent_spec_id is not None and spec.parent_spec_id not in self._specs:
            raise EnvironmentCatalogNotFound(spec.parent_spec_id)
        if spec.template_id is not None and spec.template_id not in self._templates:
            raise EnvironmentCatalogNotFound(spec.template_id)
        self._put(self._specs, spec.spec_id, spec)

    def register_overlay(self, overlay: EnvironmentOverlay) -> None:
        if overlay.target_spec_id not in self._specs:
            raise EnvironmentCatalogNotFound(overlay.target_spec_id)
        self._put(self._overlays, overlay.overlay_id, overlay)

    def assign(self, assignment: EnvironmentAssignment) -> None:
        if assignment.spec_id not in self._specs:
            raise EnvironmentCatalogNotFound(assignment.spec_id)
        self._assignments.bind(ScopedValue("execution-environment", assignment.name, assignment.scope, assignment.spec_id, assignment.policy))

    def _spec_chain(self, spec: EnvironmentSpec) -> tuple[EnvironmentSpec, ...]:
        chain = [spec]
        seen = {spec.spec_id}
        current = spec
        while current.parent_spec_id is not None:
            try:
                current = self._specs[current.parent_spec_id]
            except KeyError as exc:
                raise EnvironmentCatalogNotFound(current.parent_spec_id) from exc
            if current.spec_id in seen:
                raise EnvironmentCatalogConflict(f"environment spec cycle: {current.spec_id}")
            seen.add(current.spec_id)
            chain.append(current)
        chain.reverse()
        return tuple(chain)

    def resolve(self, name: str, scope: ScopeIdentity) -> ResolvedEnvironmentSpec:
        assigned = self._assignments.resolve(namespace="execution-environment", name=name, scope=scope)
        try:
            leaf = self._specs[assigned.value]
        except KeyError as exc:
            raise EnvironmentCatalogNotFound(assigned.value) from exc
        chain = self._spec_chain(leaf)
        requirements: dict[str, str] = {}
        environment: dict[str, str] = {}
        source_scopes: list[ScopeIdentity] = []
        for spec in chain:
            requirements.update(spec.requirements)
            environment.update(spec.environment)
            source_scopes.append(spec.scope)
        ancestry_path = self._scopes.ancestry(scope)
        ancestry_rank = {identity: index for index, identity in enumerate(ancestry_path)}
        chain_ids = {item.spec_id for item in chain}
        overlays = tuple(sorted(
            (
                row for row in self._overlays.values()
                if row.target_spec_id in chain_ids and row.scope in ancestry_rank
            ),
            key=lambda row: ancestry_rank[row.scope],
            reverse=True,
        ))
        for overlay in overlays:
            requirements.update(overlay.requirements)
            environment.update(overlay.environment)
            source_scopes.append(overlay.scope)
        return ResolvedEnvironmentSpec(
            spec_id=leaf.spec_id,
            kind=leaf.kind,
            requested_scope=scope,
            source_scopes=tuple(source_scopes),
            source_spec_ids=tuple(item.spec_id for item in chain),
            applied_overlay_ids=tuple(item.overlay_id for item in overlays),
            requirements=tuple(sorted(requirements.items())),
            environment=tuple(sorted(environment.items())),
        )

    def register_instance(self, instance: EnvironmentInstance) -> None:
        self._put(self._instances, instance.instance_id, instance)

    def bind(self, binding: EnvironmentBinding) -> None:
        if binding.instance_id not in self._instances:
            raise EnvironmentCatalogNotFound(binding.instance_id)
        self._bindings.bind(ScopedValue("execution-environment-instance", binding.role, binding.scope, binding))

    def binding(self, role: str, scope: ScopeIdentity) -> EnvironmentBinding:
        return self._bindings.resolve(namespace="execution-environment-instance", name=role, scope=scope).value

    @staticmethod
    def resolved_digest(value: ResolvedEnvironmentSpec) -> str:
        return canonical_digest(value)


__all__ = ["EnvironmentCatalogConflict", "EnvironmentCatalogNotFound", "ExecutionEnvironmentCatalog"]
