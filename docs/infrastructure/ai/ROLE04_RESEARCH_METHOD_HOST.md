# ROLE04 Research Method Host

Noetrium exposes two complementary downstream method paths.

The component path uses reusable Agent/Participant/Model capabilities when a paper changes one mechanism. The whole-method path uses `ResearchMethodProgram[TaskT, InputT, ResultT]` when the paper owns the complete cognition/control graph.

`ResearchMethodProgram` is a structural public contract in `research_platform.participant.method.api`. A downstream method does not subclass a Platform runtime class and does not register a paper algorithm name upstream.

Concrete `TaskT`, `InputT`, and `ResultT` remain project-typed. They are not converted to `Any`, `object`, a universal JSON payload, or text merely to satisfy the host contract.

Dependencies such as Model, Environment, Artifact, or project-local capability ports are constructor-injected by composition. The method contract performs no provider discovery and owns no ambient registry.

`MethodProgramIdentity` binds the exact `MethodIdentity` implementation with an optional canonical configuration SHA-256. Implementation and configuration therefore remain distinct scientific identity facets.

## Authority boundary

`ResearchMethodProgram.run(...)` executes the downstream scientific control graph only after an external Trial/Run boundary has already been established. It does not own Run lifecycle, assignment expansion, resource acquisition, effect reconciliation, checkpoint stores, evidence finalization, or scientific validity.

ROLE03 remains the Trial/Run orchestration owner. Its public adapter should bind a `ResearchMethodProgram` into the neutral Trial lifecycle and freeze the exact program identity in run provenance. ROLE04 does not import ROLE03 runtime or compiler internals.

The existing `MethodSession` contract remains the first-party memory/recall/task-completion archetype used by older Agent workloads. It is not the universal definition of a research method. Consumer migration may eventually narrow or remove that archetype after ROLE03 cutover, but no compatibility alias should redefine `ResearchMethodProgram` in terms of `recall()` or `task_completed()`.

Stateful method checkpoint/open/close/revision traits remain orthogonal. They must compose through existing Participant/checkpoint/revision authorities rather than grow into mandatory no-op methods on `ResearchMethodProgram`.

## Conformance evidence

`tests/test_typed_role04_research_method_host_v1.py` defines a project-only control graph with typed dataclass task/input/result values and an injected scoring port. It implements neither `recall()` nor `task_completed()` and still satisfies `ResearchMethodProgram` structurally.

The same suite rejects non-canonical configuration/runtime artifact digests and proves configuration identity changes the bound program digest without changing the implementation identity.
