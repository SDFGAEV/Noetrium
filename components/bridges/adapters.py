"""Optional, dependency-free bridges for popular agent runtimes.

No framework is imported or made mandatory. A downstream project wraps its
LangGraph/AutoGen/CrewAI object in the small typed protocol for its installed
version, keeping foreign payloads outside the Noetrium method boundary.
"""

from __future__ import annotations

from typing import Protocol

from components.agent import AgentDecision, AgentDecisionPort, AgentState


class LangGraphRunnable(Protocol):
    def invoke(self, state: AgentState) -> AgentDecision: ...


class AutoGenRunnable(Protocol):
    def run(self, state: AgentState) -> AgentDecision: ...


class CrewAIRunnable(Protocol):
    def kickoff(self, state: AgentState) -> AgentDecision: ...


class LangGraphDecisionAdapter:
    def __init__(self, runnable: LangGraphRunnable) -> None:
        self._runnable = runnable

    def decide(self, state: AgentState) -> AgentDecision:
        decision = self._runnable.invoke(state)
        if type(decision) is not AgentDecision:
            raise TypeError("LangGraph adapter must return AgentDecision")
        return decision


class AutoGenDecisionAdapter:
    def __init__(self, runnable: AutoGenRunnable) -> None:
        self._runnable = runnable

    def decide(self, state: AgentState) -> AgentDecision:
        decision = self._runnable.run(state)
        if type(decision) is not AgentDecision:
            raise TypeError("AutoGen adapter must return AgentDecision")
        return decision


class CrewAIDecisionAdapter:
    def __init__(self, runnable: CrewAIRunnable) -> None:
        self._runnable = runnable

    def decide(self, state: AgentState) -> AgentDecision:
        decision = self._runnable.kickoff(state)
        if type(decision) is not AgentDecision:
            raise TypeError("CrewAI adapter must return AgentDecision")
        return decision


__all__ = [
    "AutoGenDecisionAdapter",
    "AutoGenRunnable",
    "CrewAIDecisionAdapter",
    "CrewAIRunnable",
    "LangGraphDecisionAdapter",
    "LangGraphRunnable",
]
