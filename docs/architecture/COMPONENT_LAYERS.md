# Noetrium Component Layers

Noetrium is intentionally split into three dependency tiers:

1. research_platform/ is the infrastructure and authority tier. It owns
   identity, bindings, execution, recovery, measurements, artifacts, evidence,
   and typed producer ports.
2. components/agent, components/memory, and components/tools are reusable
   single-agent method components. They depend on public Platform contracts
   only. A downstream paper can import ReAct, Reflexion, Plan-and-Solve,
   Working/Episodic/Vector Memory, and ToolRegistry, then replace only its
   novel policy/component.
3. components/multi_agent/ is a higher orchestration tier. It owns explicit
   agent-node topology, message delivery, GroupChat, Debate, and Hierarchical
   coordination. It does not own agent cognition, memory, scientific results,
   or provider state.

The dependency direction is one-way:

downstream project -> components -> research_platform

research_platform never imports components, and no component registry is
global. Composition constructs each registry/topology and injects it into a
method.

## Paper reproduction patterns

| Paper contribution | Reuse | Downstream change |
| --- | --- | --- |
| ReAct-like control loop | ReActAgent | decision policy |
| Self-reflection/refinement | ReflexionAgent | reflection policy |
| Explicit planning | PlanAndSolveAgent | planner/solver |
| Short-term context | WorkingMemory | capacity or item policy |
| Long-term episodes | EpisodicMemoryStore | retrieval policy or durable adapter |
| Embedding retrieval | VectorMemoryStore | embedder or indexed store |
| Tool use | ToolRegistry | typed definitions and handlers |
| Debate/group/hierarchy | components.multi_agent | node implementations and topology |

A whole-method paper can implement AgentDecisionPort and run unchanged through
the same public host, or replace the full loop without editing Platform source.
A novel component should remain downstream when it is scientific novelty; only
generic reusable mechanisms belong in components.

These in-memory implementations are deterministic reference components. A
claim-grade project binds durable Platform artifact/evidence ports around them
and records the exact component/source/configuration identities.
