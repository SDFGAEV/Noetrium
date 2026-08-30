# Public facade and `research` CLI

The common product boundary is intentionally small:

- Python: `research_platform.api`
- CLI: `research`
- lifecycle intents: `run`, `inspect`, `stop`, `resume`, `reconcile`, `evidence`
- existing forensic tools: `research diagnose ...`
- existing management tools: `research manage ...`

`ResearchFacade` owns only product intent translation. It does not own run state, effect certainty, checkpoints, environment truth, model truth, or scientific success. A real application is injected through `ResearchApplicationPort` and must return a typed `ResearchResult` whose action and target match the request.

There is deliberately no ambient service locator and no implicit default production application.

## Python

```python
from research_platform.api import ResearchFacade

facade = ResearchFacade(my_application)
result = facade.inspect("run-123")
```

The request payload is recursively frozen at the facade boundary so callers cannot mutate an in-flight intent after dispatch.

## CLI application binding

Lifecycle commands require an explicit application factory:

```bash
research --application my_project.operator:build_application run run-123
research --application my_project.operator:build_application inspect run-123
research --application my_project.operator:build_application evidence run-123
```

Factories receive the optional `--application-config` path. Downstream projects use that hook to compose their own ROLE 03/04/05 bindings without exposing internal topology to users.

The bundled `research_platform.operator.reference` application exists only to qualify the facade, persistence and installed distribution lifecycle. It is deterministic and checksummed, but it is **not** a substitute for a production run/effect authority and its `reconcile` action does not certify external effect certainty.

## Failure rules

- Missing application bindings fail closed.
- Result action/target drift is rejected.
- Corrupt reference state fails checksum verification.
- Decoded reference state is modeled as immutable typed `ReferenceState` / `ReferenceEvent` values; exact fields and lifecycle transitions are validated before any state is accepted or persisted.
- Real external-effect uncertainty must remain with the owning runtime/reliability authority; the product layer never converts missing evidence into success.

## Generic run-control binding

`bind_run_control_application(...)` is the typed platform adapter from the product facade to ROLE03 `RunControlPort`. The adapter validates exact run identity, manifest digest, expected generation and resume checkpoint/cycle identity before dispatch. It does not persist run state, execute lifecycle effects itself, or infer external-effect certainty.

ROLE03 `RunControlReceipt` remains authoritative. Failed or recovery-required state-changing receipts surface as `ResearchOperationFailure` carrying the typed `ResearchResult`; the CLI emits that authoritative result and exits non-zero instead of flattening uncertainty into success.

This closes `CSR-06-GENERIC-RUN-LIFECYCLE-OPERATOR-HANDOFF-20260829`: ROLE06 owns product-intent translation only, ROLE03 owns durable lifecycle truth, and ROLE02 owns adjacent effect/reconciliation certainty.

## ROLE 03 run-control binding

`research_platform.operator.composition.bind_run_control_application(...)` is the canonical ROLE 06 adapter for the ROLE 03 `RunControlPort`. The adapter is a translation boundary only: ROLE 03 remains the authority for run identity, manifest identity, lifecycle phase, checkpoint identity, reconciliation and evidence. ROLE 06 does not persist a second run-state projection.

The binding requires one explicit `run_id`, its exact `run_manifest_digest`, and an injected `RunControlPort`. Payloads are intentionally exact and generation-fenced:

- `run`, `stop`, `reconcile`: `{"expected_generation": N}`
- `inspect`, `evidence`: no payload, or an optional `expected_generation`
- `resume`: `expected_generation`, `restore_checkpoint_id`, and an exact `restore_cycle_identity` object containing `run_id`, `decision_cycle_id`, `session_id`, `task_id`, and `trace_id`

The adapter rejects target, manifest, control-event-action, and evidence identity drift even if a downstream object is otherwise typed. A state-changing command that produces `failed` or `recovery_required`, or a ROLE 03 `RunControlActionFailure`, raises `ResearchOperationFailure` carrying the authoritative `ResearchResult`. The CLI serializes that result to stderr and exits with code `3`; it never rewrites an uncertain/recovery-required outcome into success.

This closes the ROLE 06 consumer side of `CSR-06-GENERIC-RUN-LIFECYCLE-OPERATOR-HANDOFF-20260829`; final availability still depends on the ROLE 03 run-control implementation being present in the integrated source cut.
