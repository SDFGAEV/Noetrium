# LangGraph source review and Noetrium adapter boundary

Status: implemented as a framework-neutral ROLE04 method boundary.
Reviewed source revision: `11ee185999b86bfea2d8c0e69cef9a5e37acf686`.
Repository: `langchain-ai/langgraph`.

This document records the source-level review used for the refactor. The
review covered the 78 Python modules in `libs/langgraph/langgraph`
(27,905 lines), plus the checkpoint/store/cache libraries and the matching
graph, interruption, persistence, retry, streaming, subgraph, and time-travel
tests. The CLI/SDK/deployment code was reviewed as an integration surface, not
as a dependency of the Noetrium core.

## Executive conclusion

LangGraph is a capable execution runtime, not a research-method model and not
an evidence/provenance authority. Its highest-value ideas belong at the
execution/method-host seam:

- StateGraph gives downstream authors a declarative node/edge authoring model.
- Pregel gives the runtime a clear super-step, trigger, write, retry, and
  recovery model.
- Functional API gives authors a sequential workflow style with durable tasks.
- Checkpoints, interrupts, subgraphs, streams, stores, and caches are separate
  capabilities rather than one global state object.
- The public graph/runtime APIs are sufficient for an adapter; private
  `_internal` and `pregel` modules must not cross the Noetrium boundary.

Noetrium therefore borrows the contracts and invariants, while keeping
LangGraph optional and replaceable.
## Source map

| Source area | Valuable mechanism | Noetrium treatment |
| --- | --- | --- |
| `graph/state.py` | Typed state schema, reducers, nodes, static/conditional edges, compile-time validation | Downstream method authors may implement graph behavior behind `MethodGraphProgram`; no algorithm registry |
| `pregel/main.py`, `pregel/_loop.py`, `pregel/_algo.py` | Discrete super-steps, channel versions, triggers, pending writes, fan-out, graph drain | Execution semantics stay provider-owned; adapter exposes only typed invocation/result/event |
| `func/__init__.py` | `entrypoint`, durable `task`, previous value, task futures, task-level retry/cache/timeout | Map to a method program and explicit platform operation boundaries |
| `checkpoint/base`, `checkpoint/memory` | Versioned checkpoint, metadata, parent, pending writes, thread history, replay | Noetrium `ParticipantCheckpoint` is the outer identity/checksum authority; graph payload is opaque |
| `types.py` | `Command`, `Interrupt`, `Send`, `RetryPolicy`, `TimeoutPolicy`, stream parts, snapshots | `MethodGraphRequest.resume`, typed `MethodGraphInterrupt`, typed `MethodGraphEvent` |
| `store/base` | Namespaces, batch operations, filtering, semantic search, TTL | Optional downstream memory/store capability; never ambient global state |
| `cache/base`, `_internal/_cache.py` | Deterministic cache keys, namespace isolation, TTL | Optional provider optimization; never evidence or scientific state |
| `stream/*` | Multiple projections, sequence ordering, transformers, lifecycle/failure hooks | Adapter decodes to immutable events and rejects non-monotonic sequence |
| `runtime.py`, `config.py` | Run context, store, writer, heartbeat, previous value, cooperative drain | Explicit injected dependencies; map identity to Noetrium ExecutionContext |
| `errors.py`, `pregel/_retry.py` | Typed interruption/drain/timeout/node failure and retry classification | Preserve failure certainty and reconciliation in Noetrium effect receipts |
| `remote.py`, SDK, CLI | Out-of-process graph execution, reconnectable streams, deployment packaging | Future external adapter; never import remote/private runtime types in core |
## Invariants worth carrying forward

### 1. Compile before execute

StateGraph separates graph construction from compiled execution. This catches
missing nodes, invalid edges, unknown channels, and incompatible schemas before a
research run starts. Noetrium should keep this as a downstream method validation
step, while the platform validates only the method identity, binding, and
experiment contract.

### 2. Recovery is a boundary operation

LangGraph checkpoints at execution boundaries and can replay a node from its
beginning. Side effects inside a replayed node must be idempotent or isolated
behind a durable task. This is directly compatible with Noetrium's
COMMIT_ONLY/UNKNOWN reconciliation model: a checkpoint is not proof that an
external effect committed.

### 3. One checkpoint authority

LangGraph can persist graph state, while Noetrium persists participant binding,
component identity, session identity, and payload checksum. These are different
responsibilities. The adapter delegates graph bytes through
`MethodGraphCheckpointPort`; it does not create a second platform checkpoint
envelope or reinterpret a LangGraph thread as a scientific Run.

### 4. Interrupts are durable control flow

`interrupt()` pauses at a durable boundary and resumes through an explicit
command. The adapter carries resume values as `ResumeT`, projects returned
interrupts as `MethodGraphInterrupt`, and leaves approval/authority decisions
to the caller and platform governance.

### 5. Streams are projections, not state

LangGraph exposes values, updates, messages, custom data, checkpoints, tasks,
and debug streams. These are views over execution. Noetrium's
`MethodGraphEvent` is immutable, typed by the downstream codec, carries a
sequence, and is checked for strict ordering. Events do not replace
measurements, artifacts, or evidence receipts.
## Noetrium public boundary

The following public types are now available from
`noetrium_platform.capabilities.participant.method.api`:

- `MethodGraphRequest[TaskT, InputT, ResumeT]`: typed task/input, explicit
  ExecutionContext, session and invocation identity, optional resume value.
- `MethodGraphResult[ResultT]`: typed result plus typed interrupt projections.
- `MethodGraphEvent[EventT]`: immutable ordered event projection.
- `MethodGraphProgram`: provider-neutral invoke/stream protocol.
- `MethodGraphCheckpointPort`: optional graph-state capability.
- `LangGraphMethodProgram`: optional stateless adapter in
  `participant.method.providers`; `LangGraphStatefulMethodProgram` is the
  explicit variant for graphs that expose the checkpoint capability.
- `LangGraphAsyncInvoker`: optional public `ainvoke/astream` capability exposed
  by the same adapter; async support is structural and remains provider-optional.

The adapter deliberately requires a codec. A codec owns:

1. converting project-owned typed inputs to the graph's public input;
2. constructing the provider config, including its thread/session key;
3. converting the Noetrium ExecutionContext to provider context;
4. decoding provider outputs, interrupts, and stream parts.

This prevents a generic JSON dictionary from becoming the method ABI and makes
every paper method's schema visible at its own downstream boundary.

## What is intentionally not copied

- LangGraph's private Pregel/channel/checkpoint classes are not imported.
- LangGraph's `thread_id` is not used as a Noetrium Run, Trial, Assignment, or
  scientific identity.
- Provider cache hits are not evidence of a scientific result.
- Provider stream payloads are not silently promoted to measurements.
- LangGraph's serialization allowlist is not treated as a universal security
  boundary for Noetrium artifacts.
- A provider retry is not automatically a scientific repetition.
- LangGraph Server/LangSmith deployment and tracing are not required by the
  platform core.

## Extension path for downstream papers

A downstream project can implement `ResearchMethodProgram` directly when it
does not need graph runtime features. It can implement `MethodGraphProgram`
when it wants explicit invoke/resume/stream semantics. It can use
`LangGraphMethodProgram` when its implementation is a LangGraph graph, or
write an equivalent adapter for another runtime. In every case, the same
Noetrium method identity, participant binding, checkpoint envelope, operation
effects, measurements, artifacts, and evidence bundle remain authoritative.

The next integration slice should connect graph events to ROLE03 operation
observations through a reviewed cross-system change request. That connection is
kept separate from this ROLE04 adapter so ownership boundaries remain auditable.
