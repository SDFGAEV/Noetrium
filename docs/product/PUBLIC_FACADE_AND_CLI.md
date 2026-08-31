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

## Section 42 receipt-authority dependency

The common product envelope must eventually preserve producer-owned receipt contract identity/version and an immutable receipt/content reference; ROLE06 must not invent those semantics from a status string. The current ROLE03 `RunControlReceipt` exposes a typed authoritative `RunControlEventReceipt.event_digest` and independent outcome projections, but it does not yet expose a producer-owned semantic contract version or a digest/reference for the complete receipt. Until that producer handoff lands, `ResearchResult` remains a product projection and is **not** treated as a Section-42 claim-grade receipt envelope. The dependency is tracked by `CSR-06-ROLE03-URE-RUN-CONTROL-RECEIPT-IDENTITY-20260831`.

ROLE06 also waits for the ROLE01 PSC-03 neutral diagnostic metadata envelope instead of creating a competing diagnostic taxonomy.

## Downstream project experience

`research project create <project-id> <destination> --version <version>` now defaults to the Section-40/41 **author-first Level-0** profile. It binds canonical Portfolio `ProjectManifest` identity/provenance and generates only obvious paper-author modules (`methods.py`, `tasks.py`, `measurements.py`, `studies.py`) plus public-boundary structural tests. It does **not** generate Participant/Model/Environment provider implementations, direct `RunControlPort` wiring, checkpoint stores, resource leases or evidence publishers.

Provider authors explicitly opt in with `--template provider`. That advanced template retains the public Participant/Model/Environment requirement/provider stubs and application binding seam and deliberately fails closed until real bindings are supplied. Provider-specific plumbing is therefore no longer the default New Project Experience.

`research project test --project .` first builds and installs the generated downstream package into an isolated temporary `site-packages`, then runs the generated conformance suite against that installed copy with user-site and ambient `PYTHONPATH` disabled. A source-tree-only import is not accepted as project-test success. `research project doctor --project .` always verifies canonical manifest identity, installed Platform provenance, generated files and the downstream public-import boundary. For the author profile it additionally reports `level0_standard_bindings` blocked until ROLE02/03/04/05 producer-owned compiler/binding/runtime/evidence contracts can supply the standard composition. For the provider profile it verifies typed Participant/Model/Environment diagnostics, Environment readiness and explicit application binding.

`--project` is profile-aware. The default AUTHOR profile must eventually route through the producer-owned ROLE03 Research Compiler and standard bindings; until that producer handoff is available it fails closed with an explicit compiler/binding blocker and never searches for or generates `application.py`. The explicit PROVIDER profile may use direct application loading as a Level-2/provider-author escape hatch:

```bash
research run --project ./provider-project run-123 --payload '{"expected_generation":0}'
research inspect --project ./provider-project run-123
```

The provider loader derives the package identity from the canonical manifest and rejects an application module that resolves outside the explicit project root. `--project` and `--application` are mutually exclusive authority sources.

## NPE reference authority

The historical `research_platform.operator.reference` workload remains a narrow CLI/distribution smoke fixture only. It persists its own synthetic phase/generation/event state and therefore is **not** Section-37 New Project Experience lifecycle evidence.

Claim-grade NPE reference acceptance must instead compose producer-owned contracts: ROLE03 `RunControlPort`/checkpoint/evidence authority, ROLE05 public Environment provider/session authority, and ROLE02 typed runtime/resource/recovery facts where required. ROLE06 may translate those receipts but may not manufacture replacement lifecycle, effect, checkpoint, environment or evidence truth.

Until the public producer seams required by the NPE acceptance ledger are present, installed-artifact NPE qualification must remain blocked rather than inheriting a PASS from the historical Operator smoke workload.
