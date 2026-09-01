from __future__ import annotations

from tests_support import FakeParticipantResolver, runtime_identity_for_test
from tests_support import agent_turn_runtime

import hashlib

from research_platform.participant.agent.api import AgentIdentity, AgentSnapshot, AgentTurnResult
from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityEffectReconciliationResult,
    CapabilityRequest,
    CapabilityResult,
    capability_effect_request_id,
    capability_request_digest,
)
from research_platform.reliability.effect.api import EffectReconciliationDisposition, PreparedEffectHandle
from research_platform.reliability.effect.runtime import InMemoryEffectIntentJournal
from research_platform.platform.kernel import EffectCertainty, EffectClass, EffectReceipt
from research_platform.participant.core.api.contracts import ParticipantImplementationIdentity
from research_platform.execution.workflow.implementations.agent_turn.agent_turn_workflow import AgentTurnTrialProtocol
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.experimentation.experiment.runtime import ExperimentRuntime
from research_platform.experimentation.experiment.api import ExperimentParticipantSpec, ExperimentSpec


class RobotSession:
    effect_recovery_durability = "crash_durable"
    execute_calls = 0
    reconcile_calls = 0

    def __init__(self, identity: ParticipantImplementationIdentity, session_id: str) -> None:
        self.implementation = identity
        self.session_id = session_id

    @property
    def capabilities(self):
        return (
            CapabilityDescriptor(
                "robot.move",
                "1",
                "robot.move.request.v1",
                "robot.move.result.v1",
                EffectClass.NON_IDEMPOTENT,
            ),
        )

    def prepare_capability_effect(self, request):
        return PreparedEffectHandle.build(
            request_id=capability_effect_request_id(request),
            request_digest=capability_request_digest(request),
            provider_schema="robot.move.recovery.v1",
            opaque_payload=b"robot-command-42",
            provider_instance_id="robot-arm-1",
        )

    @staticmethod
    def _result(digest):
        return CapabilityResult(
            "robot.move",
            {"moved": True},
            effect=EffectReceipt(
                "robot-effect-42",
                digest,
                EffectClass.NON_IDEMPOTENT,
                EffectCertainty.EFFECT_CONFIRMED,
                "robot-arm-1",
            ),
        )

    def execute_prepared_capability(self, request, handle):
        type(self).execute_calls += 1
        assert handle.request_digest == capability_request_digest(request)
        return self._result(handle.request_digest)

    def reconcile_prepared_capability(self, handle, context):
        del context
        type(self).reconcile_calls += 1
        return CapabilityEffectReconciliationResult(
            "robot.move",
            EffectReconciliationDisposition.APPLIED,
            self._result(handle.request_digest),
        )

    def invoke(self, request):
        raise AssertionError("non-idempotent robot movement must use prepared-effect path")

    def checkpoint(self):
        return b"robot"

    def restore(self, snapshot): snapshot.verify()
    def close(self): pass


class Robot:
    implementation_identity = ParticipantImplementationIdentity("robot", "arm", "1", "1", "1")
    def open_session(self, *, session_id: str, services: object):
        del services
        return RobotSession(self.implementation_identity, session_id)


class AgentSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def run_turn(self, request, capabilities):
        result = capabilities.invoke(
            CapabilityRequest(
                "robot.move",
                {"target": request.input_payload},
                request.context,
                "move-slot-1",
            )
        )
        return AgentTurnResult(result.payload, "agent-g1")

    def checkpoint(self):
        payload=b"agent"
        return AgentSnapshot("robot-agent","1","1",self.session_id,hashlib.sha256(payload).hexdigest(),payload)
    def restore(self,snapshot): snapshot.opaque_payload
    def diagnostics(self): return {}
    def close(self): pass


class Agent:
    identity = AgentIdentity("robot-agent", "1", "1", "1", "a" * 64)
    def open_session(self, *, session_id: str, services: object):
        del services
        return AgentSession(session_id)


def _spec():
    return ExperimentSpec(
        experiment_id="robot-agent-study",
        study_id="default-study",
        project_id="default-project",
        participants=(
            ExperimentParticipantSpec("arm", ParticipantImplementationIdentity("robot", "arm", "1", "1", "1"), runtime_identity_for_test("robot"), "d" * 64),
            ExperimentParticipantSpec("agent", ParticipantImplementationIdentity("agent", "robot-agent", "1", "1", "1", "a" * 64), runtime_identity_for_test("agent"), "d" * 64, depends_on_roles=("arm",)),
        ),
        model_stack_digest="a" * 64, prompt_generation="prompt", workload_digest="b" * 64, seed_digest="c" * 64,
        repetitions=1, trial_protocol_id="agent_turn.v1",
        trial_protocol_configuration_digest="44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    )


def _runtime(journal):
    agents=FakeParticipantResolver(); agents.register("agent", "robot-agent", Agent)
    participants=FakeParticipantResolver(); participants.register("robot", "arm", Robot)
    return agent_turn_runtime(
        agents,
        runtime_plugins=participants,
        effect_journal=journal,
    )


def test_arbitrary_runtime_participant_can_export_crash_safe_capability_without_provider_wrapper():
    RobotSession.execute_calls=RobotSession.reconcile_calls=0
    runtime=_runtime(InMemoryEffectIntentJournal())
    cycle=DecisionCycleIdentity("run","dc","session","task","trace")
    first=runtime.execute_cycle(_spec(),task="move",input_payload={"x":1},cycle_identity=cycle)
    second=runtime.execute_cycle(_spec(),task="move",input_payload={"x":1},cycle_identity=cycle)

    assert first.primary_result.output == second.primary_result.output == {"moved": True}
    assert RobotSession.execute_calls == 1
    assert RobotSession.reconcile_calls == 1
    second_ids=[row.operation_id for row in second.operation_results]
    assert any("capability.effect.reconcile:" in row for row in second_ids)
    assert not any("capability.invoke:robot.move:key:" in row for row in second_ids)
