from __future__ import annotations

from collections.abc import Callable

from noetrium_platform.capabilities.participant.capability.api import CapabilityDescriptor, CapabilityRequest, CapabilityResult
from noetrium_platform.capabilities.participant.capability.api.policy import (
    CapabilityApprovalDenied,
    CapabilityPolicyDenied,
    CapabilityPolicySet,
    CapabilityPostPolicyViolation,
    GuardVerdict,
)


class CapabilityInvocationPipeline:
    """Policy waterfall around the existing effect-safe execution engine.

    Guards are monotonic: a DENY terminates the pipeline and no later stage can
    convert it back to ALLOW.  This layer never implements side-effect retry or
    reconciliation; those remain in the underlying executor.
    """

    def __init__(self, policy: CapabilityPolicySet | None = None) -> None:
        self._policy = policy or CapabilityPolicySet()

    def invoke(
        self,
        *,
        descriptor: CapabilityDescriptor,
        request: CapabilityRequest,
        execute: Callable[[], CapabilityResult],
    ) -> CapabilityResult:
        for guard in self._policy.guards:
            decision = guard.evaluate(descriptor, request)
            if decision.guard_id != guard.guard_id:
                raise ValueError("capability guard returned mismatched guard_id")
            if decision.verdict is GuardVerdict.DENY:
                raise CapabilityPolicyDenied(
                    guard_id=decision.guard_id,
                    reason_code=decision.reason_code,
                )
        if self._policy.approval is not None and not self._policy.approval.approve(descriptor, request):
            raise CapabilityApprovalDenied("capability invocation was not approved")
        result = execute()
        for post in self._policy.post_policies:
            try:
                post.validate(descriptor, request, result)
            except Exception as exc:
                raise CapabilityPostPolicyViolation(policy_id=post.policy_id, result=result) from exc
        return result




class CapabilityInvocationPipelineFactory:
    def create(self, policy: CapabilityPolicySet | None = None) -> CapabilityInvocationPipeline:
        return CapabilityInvocationPipeline(policy)


__all__ = ["CapabilityInvocationPipeline", "CapabilityInvocationPipelineFactory"]
