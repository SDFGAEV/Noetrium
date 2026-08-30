from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from research_platform.model.api.project import (
    ModelBindingDiagnostic,
    ModelBindingDiagnosticCode,
    ModelBindingDiagnosticSeverity,
    ModelCapabilityRequirement,
    ModelProjectBindingError,
    ModelProviderProfile,
    ProjectModelBinding,
    ProjectModelClientPort,
    ProjectModelProviderPort,
    ProjectModelRequest,
    ProjectModelResponse,
)
from research_platform.model.serving.endpoint.api import (
    ModelEndpointPort,
    ModelEndpointRequest,
    QualifiedModelEndpointBinding,
    QualifiedModelEndpointBindingPort,
)


EndpointFactory = Callable[[QualifiedModelEndpointBinding], ModelEndpointPort]


def _diagnostic(
    profile: ModelProviderProfile,
    requirement: ModelCapabilityRequirement,
    code: ModelBindingDiagnosticCode,
    message: str,
) -> ModelBindingDiagnostic:
    return ModelBindingDiagnostic(
        code=code,
        severity=ModelBindingDiagnosticSeverity.ERROR,
        message=message,
        requirement_digest=requirement.digest(),
        provider_id=profile.provider_id,
    )


@dataclass(frozen=True, slots=True)
class _QualifiedProjectModelClient:
    binding: ProjectModelBinding
    requirement: ModelCapabilityRequirement
    endpoint: ModelEndpointPort

    def complete(self, request: ProjectModelRequest) -> ProjectModelResponse:
        if request.requirement_digest != self.binding.requirement_digest:
            raise ValueError("project model request requirement drift")
        envelope = request.envelope
        if envelope.role != self.binding.role or envelope.model != self.binding.model:
            raise ValueError("project model request model binding drift")
        if (
            envelope.prompt_generation_id != self.requirement.prompt_generation_id
            or envelope.prompt_id != self.requirement.prompt_id
            or envelope.prompt_digest != self.requirement.prompt_digest
        ):
            raise ValueError("project model request prompt provenance drift")
        if self.requirement.tool_schema_sha256 is not None:
            if (
                envelope.tool_schema_bundle is None
                or envelope.tool_schema_bundle.sha256 != self.requirement.tool_schema_sha256
            ):
                raise ValueError("project model request tool schema provenance drift")
        route = self.endpoint.route
        if (
            route.deployment_id != self.binding.deployment_id
            or route.deployment_generation != self.binding.deployment_generation
        ):
            raise ValueError("project model endpoint route provenance drift")
        response = self.endpoint.complete(
            ModelEndpointRequest(
                request=envelope,
                deployment_id=self.binding.deployment_id,
                deployment_generation=self.binding.deployment_generation,
                body=request.body,
            )
        )
        return ProjectModelResponse(
            request_digest=request.request_digest,
            binding_digest=self.binding.digest(),
            response=response,
        )


class QualifiedModelProjectProvider(ProjectModelProviderPort):
    """Reference adapter from qualified Model authorities to the project seam."""

    def __init__(
        self,
        profile: ModelProviderProfile,
        bindings: QualifiedModelEndpointBindingPort,
        endpoint_factory: EndpointFactory,
    ) -> None:
        if not isinstance(profile, ModelProviderProfile):
            raise TypeError("project model provider profile must be typed")
        self._profile = profile
        self._bindings = bindings
        self._endpoint_factory = endpoint_factory

    @property
    def profile(self) -> ModelProviderProfile:
        return self._profile

    def _resolve(
        self, requirement: ModelCapabilityRequirement
    ) -> tuple[QualifiedModelEndpointBinding | None, tuple[ModelBindingDiagnostic, ...]]:
        if not isinstance(requirement, ModelCapabilityRequirement):
            raise TypeError("project model requirement must be typed")
        missing = tuple(
            capability
            for capability in requirement.required_capabilities
            if capability not in self._profile.capabilities
        )
        if missing:
            return None, (
                _diagnostic(
                    self._profile,
                    requirement,
                    ModelBindingDiagnosticCode.CAPABILITY_MISSING,
                    "qualified model provider lacks capabilities: " + ", ".join(missing),
                ),
            )
        try:
            binding = self._bindings.binding_for(
                role=requirement.role,
                prompt_generation=requirement.prompt_generation_id,
            )
        except Exception as exc:
            return None, (
                _diagnostic(
                    self._profile,
                    requirement,
                    ModelBindingDiagnosticCode.QUALIFIED_BINDING_UNAVAILABLE,
                    f"qualified model binding unavailable: {type(exc).__name__}",
                ),
            )
        if (
            binding.role != requirement.role
            or binding.prompt_generation != requirement.prompt_generation_id
        ):
            return None, (
                _diagnostic(
                    self._profile,
                    requirement,
                    ModelBindingDiagnosticCode.BINDING_PROVENANCE_DRIFT,
                    "qualified model binding changed requested role or prompt generation",
                ),
            )
        if binding.model.context_length < requirement.minimum_context_tokens:
            return None, (
                _diagnostic(
                    self._profile,
                    requirement,
                    ModelBindingDiagnosticCode.CONTEXT_INSUFFICIENT,
                    "qualified model context length is below the project requirement",
                ),
            )
        return binding, ()

    def diagnose(
        self, requirement: ModelCapabilityRequirement
    ) -> tuple[ModelBindingDiagnostic, ...]:
        _, diagnostics = self._resolve(requirement)
        return diagnostics

    def bind(self, requirement: ModelCapabilityRequirement) -> ProjectModelClientPort:
        binding, diagnostics = self._resolve(requirement)
        if diagnostics or binding is None:
            raise ModelProjectBindingError(diagnostics)
        project_binding = ProjectModelBinding(
            requirement_digest=requirement.digest(),
            provider_id=self._profile.provider_id,
            provider_profile_digest=self._profile.digest(),
            role=requirement.role,
            model=binding.model,
            deployment_id=binding.deployment_id,
            deployment_generation=binding.deployment_generation,
            model_stack_digest=binding.model_stack_digest,
            qualification_certificate_digest=binding.qualification_certificate_digest,
            runtime_qualification_digest=binding.runtime_qualification_digest,
            host_identity_digest=binding.host_identity_digest,
            prompt_generation_id=requirement.prompt_generation_id,
            prompt_id=requirement.prompt_id,
            prompt_digest=requirement.prompt_digest,
            capabilities=self._profile.capabilities,
            runtime_canary_evidence_digests=binding.runtime_canary_evidence_digests,
        )
        try:
            endpoint = self._endpoint_factory(binding)
        except Exception as exc:
            raise ModelProjectBindingError(
                (
                    _diagnostic(
                        self._profile,
                        requirement,
                        ModelBindingDiagnosticCode.QUALIFIED_BINDING_UNAVAILABLE,
                        f"qualified model endpoint materialization failed: {type(exc).__name__}",
                    ),
                )
            ) from exc
        if (
            endpoint.route.deployment_id != binding.deployment_id
            or endpoint.route.deployment_generation != binding.deployment_generation
        ):
            raise ModelProjectBindingError(
                (
                    _diagnostic(
                        self._profile,
                        requirement,
                        ModelBindingDiagnosticCode.BINDING_PROVENANCE_DRIFT,
                        "materialized model endpoint does not match qualified deployment generation",
                    ),
                )
            )
        return _QualifiedProjectModelClient(project_binding, requirement, endpoint)


__all__ = ["EndpointFactory", "QualifiedModelProjectProvider"]
