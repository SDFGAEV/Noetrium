"""Foreign dict state/decision normalization without importing LangGraph."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noetrium.adapters.bridges import (
    LangGraphDecisionAdapter, reference_state_mapping,
)
from components.reference.single_agent.agent import (
    ReferenceAgentState,
)

class ForeignState:
    def convert(self, state):
        return reference_state_mapping(state)

class FakeGraph:
    def invoke(self, state):
        return {"kind": "final", "name": "final", "content": state["task"]}

decision = LangGraphDecisionAdapter(
    FakeGraph(), state_converter=ForeignState(),
).decide(ReferenceAgentState("bridge demo"))
print(decision.action.content)
