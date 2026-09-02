"""Run a reusable ReAct component without editing Platform source."""

from components.agent import (
    AgentAction, AgentActionKind, AgentDecision, ReActAgent,
    RegistryAgentToolPort,
)
from components.tools import ToolArguments, ToolDefinition, ToolRegistry, ToolResult


class Policy:
    def decide(self, state):
        if state.step == 0:
            return AgentDecision(
                AgentAction(
                    AgentActionKind.TOOL,
                    "lookup",
                    (("query", state.task),),
                    "look up the task",
                )
            )
        return AgentDecision(AgentAction(AgentActionKind.FINAL, "answer", content="reused component"))


def main() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("lookup", "deterministic lookup", "lookup.v1"),
        lambda args: ToolResult("lookup", True, f"found:{args.as_mapping()['query']}"),
    )
    result = ReActAgent(Policy(), RegistryAgentToolPort(registry)).run("hello", max_steps=4)
    print(result.status.value, result.answer)


if __name__ == "__main__":
    main()
