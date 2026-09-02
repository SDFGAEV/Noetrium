import unittest

from noetrium_platform.capabilities.environment.minecraft.runtime import MinecraftTaskKind, MinecraftTaskSpec, score_blueprint
from noetrium_platform.capabilities.participant.agent.runtime import AgentCoordinationHub, AgentConversationManager, ConversationKind


class MinecraftTaskAssetsV1Tests(unittest.TestCase):
    def test_construction_fixture_is_typed_and_scored(self) -> None:
        task = MinecraftTaskSpec.from_mapping({
            "task_id": "house-1",
            "type": "construction",
            "goal": "build the house",
            "agent_count": 2,
            "timeout": 120,
            "blueprint": [{"position": {"x": 0, "y": 64, "z": 0}, "block": "oak_planks"}],
        })
        self.assertIs(task.kind, MinecraftTaskKind.CONSTRUCTION)
        self.assertTrue(score_blueprint(task, {"0,64,0": "oak_planks"}).complete)
        self.assertEqual(score_blueprint(task, {"0,64,0": "dirt"}).matches, 0)

    def test_conversation_priority_and_resume_preserve_pending_messages(self) -> None:
        manager = AgentConversationManager(agent_id="agent-a")
        manager.connect("agent-b")
        manager.receive("agent-b", "routine", priority=1)
        manager.receive("agent-b", "stop", priority=10, kind=ConversationKind.INTERRUPT)
        self.assertEqual(manager.drain("agent-b")[0].text, "stop")
        manager.disconnect("agent-b")
        self.assertEqual(manager.resume("agent-b").pending[0].kind, ConversationKind.INTERRUPT)

    def test_coordination_hub_routes_bounded_multi_agent_messages(self) -> None:
        hub = AgentCoordinationHub(max_agents=2)
        hub.register("agent-a")
        hub.register("agent-b")
        hub.send("agent-a", "agent-b", "deliver the logs", priority=4)
        self.assertEqual(hub.pending("agent-b", "agent-a")[0].text, "deliver the logs")
        hub.disconnect("agent-b")
        with self.assertRaises(RuntimeError):
            hub.send("agent-a", "agent-b", "late message")


if __name__ == "__main__":
    unittest.main()
