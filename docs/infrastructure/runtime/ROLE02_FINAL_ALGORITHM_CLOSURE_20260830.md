# ROLE02 Final Algorithm Closure — 2026-08-30

This change closes the avoidable ROLE02 regressions reported by `CSR-00-ROLE02-FINAL-ALGORITHM-GATE-20260830` without weakening Algorithm Governance.

`EffectJournalDocumentCodec.decode_record` validates its four fixed index bindings explicitly; the function is again O(1) while retaining complete WAL checksum, phase, request/effect and completion validation.

`IncidentLedgerSynchronizer.sync` now lazily flattens verified payload batches and performs one streaming pass. Batching remains bounded-memory, but batch partitioning is no longer represented or executed as an N-by-N nested traversal.

`EndpointAllocation.__post_init__` delegates fixed digest/time/proof-presence policies to named validators. All fencing, finite-time and bind-proof invariants remain fail-closed while the constructor returns to O(1) and a smaller control surface.

Process capture now publishes a rebuildable `<stream>.resume.json` checkpoint after durable sync/close/seal state. Normal reopen validates the active segment and successor absence in O(1) history time and reads only a bounded tail suffix.

The capture resume checkpoint is a performance/recovery projection, not evidence authority. Invalid checkpoint JSON/digest fails closed. A valid but disk-stale checkpoint is treated as crash-stale, triggers one explicit full segment recovery scan, and is atomically rebuilt. Sealed evidence is still authorized only by the existing manifest scan/digest verification.

Four remaining Algorithm Gate deltas are output-cardinality lower bounds rather than avoidable regressions: `DebugSnapshotService.build`, `FailureDiagnosisService.timeline`, `operations_open_at`, and `unclosed_operations`. These APIs return/materialize N diagnostic/operation records, so complete results require Omega(N) work. The old O(1) baseline reflects the earlier untyped/API shape.

ROLE02 does not suppress or rebaseline those four symbols. `CSR-02-ALGORITHM-OUTPUT-MATERIALIZATION-LOWER-BOUND-20260830` requests a source-bound ROLE01 Algorithm Migration authority so ROLE00 can explicitly approve a mathematically justified complexity migration on an exact source cut.
