# Forensic Ledger Invariants

Authoritative forensic ledgers are append-only hash chains; SQLite projections are disposable accelerators.

- A projection synchronizes against a typed `VerifiedLedgerCut` that binds the source checkpoint row/hash to one verified total row count and tail hash.
- Production projection rebuilds do not materialize the entire verified suffix. After verifying the cut, they re-verify that fixed cut while yielding bounded payload batches.
- The second pass is bound to the previously verified row count, checkpoint hash, and tail hash. Appends after the cut are deferred to the next synchronization; prefix mutation or truncation between passes fails with `HashChainError`.
- Incident projection changes stay inside one SQLite transaction while the full fixed cut is streamed. A later integrity failure therefore rolls back earlier projected batches.
- The legacy materialized `VerifiedLedgerSlice` remains suitable for low-volume diagnostic reads and tests, but production rebuild paths use bounded streaming.
- Failure and mutation ledgers fsync every authoritative append. Event telemetry may batch fsync/projection according to its explicit durability policy; integrity verification still spans the global event hash chain.
- Projection freshness is never authoritative evidence of ledger truth. It is accepted only when its row/hash checkpoint matches the verified authoritative prefix.
