# Platform Architecture — Contract-Driven Noetrium

## Goal

Provide a reusable research platform where scientific method, agent, environment, capability providers, persistence backends and runtime supervisors are independently replaceable without rewriting the surrounding evidence, recovery, release and observability systems.

The design preference is **small modules + narrow ports + one authority per durable/effect domain + explicit composition roots**.

## Top-level planes

```text
Composition Root
├── Stable Contract Plane
│   ├── kernel
│   ├── participant_api / service_api / prompt_api
│   ├── capability_api / workflow_api / status_api
│   ├── effect_api / failure_api / observability_api
│   ├── model_request_api / scope_api / projection_api
│   └── record_api / fact_api / process_api / diagnostics_api
├── Runtime Plane
│   ├── participant_runtime / workflow_runtime
│   ├── model_request_runtime / scope_runtime / projection_runtime
│   ├── capability_runtime / status_runtime
│   ├── runtime_manager / service_os / model_os / prompt_os
│   └── server_session / process_capture
├── Durable Truth / Evidence Plane
│   ├── effect_journal / state
│   ├── forensics / failure ledger / mutation evidence
│   ├── release manifest + release evidence
│   └── method-owned durable scientific state
├── Side-Plane Observation
│   └── telemetry / diagnostic projections / operator views
└── Scientific Implementations
    └── downstream_project/method/implementation
```

## Implementation vs runtime

A scientific/functional implementation is not itself a runtime supervisor.

```text
Implementation identity
        +
Session/runtime identity
        +
Configuration identity
        ↓
Frozen runtime binding
        ↓
Runtime endpoint/session
```

Checkpoint identity binds the runtime binding, so changing a runtime backend cannot silently restore a snapshot produced by another runtime.

## Record planes

Three planes are explicit and mechanically distinct:

```text
DURABLE_FACT
    may participate in replay/reconstruction/scientific proof

LIVE_INTERCEPTION
    may affect the current execution only;
    durable/model-visible changes require an explicit durable fact

SIDE_PLANE_OBSERVATION
    telemetry/diagnostics only;
    failure must not change primary truth
```

The system deliberately does **not** collapse all domain journals into one universal event log.

## Reconstructable model-visible requests

The exact semantic request shown to a model is now a durable fact.

```text
Prompt resolution
→ compile
→ request body build
→ durable CAS writes
   ├─ canonical request body
   ├─ compiled prompt
   └─ tool schema bundle
→ ModelRequestEnvelope append
→ verify model-visible bytes
→ reconstruct durable request body
→ provider/model invocation
```

`ModelRequestEnvelope` binds `ExecutionContext`, full `ImmutableModelIdentity`, prompt generation/id/digest, content refs and source artifact/state refs.

Invariant:

```text
actual model-visible bytes == durable reconstruction bytes
```

## Capability invocation

Capability policy and external-effect safety are separate authorities.

```text
Scoped capability resolution
→ monotonic guards
→ approval
→ existing crash-safe/effect-safe executor
→ post policies
→ final outcome
```

The capability pipeline cannot weaken effect certainty, WAL, reconciliation or retry rules. If post-policy rejects after execution, the outcome records that execution already happened and is not safe to blindly retry.

Composition-time capability binding canonicalizes contract-local offer/requirement order before plan identity is hashed, so declaration order cannot create false identity drift. Provider offers are indexed once by capability and interface; requirement resolution does not repeatedly rescan the full offer set. Interface ABI digests cover the effective inherited public callable/property surface with normal MRO override semantics, so parent-port signature changes invalidate descendant contract identities.

## Scope/lifetime model

Temporary registrations are owned by hierarchical scopes rather than global registries.

```text
Study/Run scopes
└── DecisionCycle scope
    ├── temporary capability registrations
    ├── leases
    └── child scopes
```

Individual registrations are reversibly retired through handles. Scope disposal is quiescent: it waits for active leases and multiple concurrent dispose callers converge on the same terminal boundary.

## Projection model

Derived read models are disposable and incremental.

```text
Authoritative source
→ ProjectionTail(
     source identity/version,
     start watermark,
     end watermark,
     suffix items)
→ projector
→ projection checkpoint
```

Rewind, source replacement, same-watermark identity drift or projector-version drift fails closed and triggers rebuild. A projection never becomes authoritative merely because it is faster to query.

## Architecture report

The analyzer now reports:

1. physical import graph;
2. package cycles;
3. declared component/state/effect authority violations;
4. source invariants and source-authority violations;
5. capability provider/consumer graph;
6. operation emission graph;
7. event producer/consumer graph;
8. structural and optimization hotspots.

Current development report: **2245 import edges, 0 violations/cycles, 6 capability edges, 30 operation edges, 12 event edges**.

Architecture report internals retain typed immutable finding, hotspot, risk, seam, system, and subsystem records. Mutable/dictionary-shaped JSON is produced only at explicit digest, CLI, artifact, or gate compatibility boundaries.

## Concurrency analyzer boundary

Python concurrency governance separates rule classification, intra-file helper-call propagation, per-function AST metrics/findings, and file-level orchestration. Blocking-helper reachability is propagated over reverse call edges with a worklist rather than repeated whole-graph fixed-point scans; analyzer revision and finding semantics remain stable when only this internal algorithm changes.

## System registry authority

`noetrium_platform/foundation/governance/system_registry/catalog.json` is the sole declaration authority for every registered node's identity, parentage, package ownership, authority identity, standard shape, `requires`, `provides`, and `components`. The Python loader validates that dependency targets exist and that provided capabilities have one owner; it derives typed `SystemDescriptor` values without a second metadata table.

## Operator management dispatch boundary

The operator deployment management surface is a routing boundary rather than a service monolith. CLI argument registration, deployment-spec decoding/selection, ordinary deployment/fleet/resource actions, and qualification planning/application/runtime verification live in separate modules. `management.deployments` remains a thin facade that preserves the stable `GROUP/register/dispatch` entrypoints; business authority remains in the model/resource/environment services reached through `ManagementCommandContext`.

## Forensic index read boundary

Forensic SQLite reads separate strict row decoding, SQL projection queries, owned read-session lifecycle, and one-shot reader facade. Read sessions force SQLite `query_only`, reject use after close, and fail closed on malformed projection records; correlation queries preserve `NULL` run identity explicitly rather than relying on SQL `NULL = NULL` semantics.

## Non-negotiable boundaries

1. Cross-system code depends on APIs/ports, not concrete implementation packages.
2. Composition roots are the only places allowed to assemble unrelated concrete subsystems.
3. Platform packages never import downstream scientific implementation types.
4. Method packages never import concrete environment or server/process-management implementations.
5. `J_audit/J_eval` have no path into materialized method memory.
6. Prompt/model/runtime identity changes cannot hide behind compatibility aliases.
7. Recovery cannot degrade model/revision/engine/dtype/quantization/context or scientific method identity.
8. External effects use effect intent + certainty + reconciliation; `UNKNOWN` is never a blind retry.
9. Side-plane observer failure cannot alter primary scientific/operational truth.
10. Release evidence is generated only after exact regression and architecture/quality gates bind the same source manifest.

## Debug path

```text
Study → Run → Task → DecisionCycle → Operation → Component
     → ModelRequest / Effect / State Mutation
     → FailureEnvelope
     → causal/triage/debug projections
```

A model decision can additionally be traced back through the exact reconstructed model request, prompt generation, method/evidence cut, tool schema and immutable model identity.
