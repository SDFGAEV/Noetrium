# Model revision transaction authority

ROLE04 owns model revision identity and transition authority under
`model/catalog/revision`. Inference clients, serving routes, and training code do
not own promotion or rollback truth.

The canonical transition is:

`proposal -> durable prepared candidate -> durable committed successor -> promotion | rejection`

Rollback is a separate durable authority event. No phase is inferred from file
presence, endpoint changes, mutable model state, or caller-selected generations.

## Typed identity and evidence

- `ModelRevisionIdentity` binds immutable model identity, revision artifact,
  exact parent revision, and lineage contract.
- `ModelUpdateProposal` binds predecessor, update contract, implementation,
  configuration, training input, randomness, and input evidence references.
- `ModelRevisionEvidence` binds one evidence digest to one exact revision and
  one semantic kind: validation, qualification, evaluation, or rollback trigger.
- `ModelPromotionDecision` binds qualification/evaluation evidence plus the
  promotion policy contract, implementation digest, and configuration digest.

## Durable authority

`SQLiteModelRevisionAuthority` is the ROLE04 local durable implementation. It
uses one SQLite transaction per state transition and stores revision/proposal,
prepared, commit, promotion, rollback, active-revision, and authority-generation
state in one database.

Callers provide only `expected_generation`. The authority compares it with the
current durable generation and allocates the next generation inside the same
transaction. A stale different operation fails with `ModelRevisionConflictError`.
An exact retry returns the previously issued durable receipt without executing
the transition again.

Preparation verifies the authoritative active predecessor and persists the exact
proposal, predecessor, candidate, recovery anchor, and validation plan. Commit
accepts only that persisted prepared object and candidate-bound validation
evidence. Promotion requires the candidate to be the exact committed successor
of the current active predecessor. Rollback requires the failed revision to be
current active and the target to be a committed ancestor in the durable lineage.

Fresh-process reopen reconstructs prepared state and current active identity from
the database. SQLite integrity failure, schema drift, missing durable rows,
digest mismatch, duplicate-key payloads, invalid lineage, and torn/non-database
content fail closed with `ModelRevisionIntegrityError`; they are never repaired
by silently recreating authority state.
