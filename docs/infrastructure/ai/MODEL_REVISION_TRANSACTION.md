# Model revision transaction authority

ROLE04 owns model revision identity under `model/catalog/revision`.
Inference clients do not own model mutation, promotion, or rollback authority.

The public transition is intentionally split:

`proposal -> prepared candidate -> committed successor -> promotion | rejection`

Rollback is a separate explicit authority event. No phase may infer another phase
from file presence, mutable model state, or a changed serving endpoint.

## Identity rules

- `ModelRevisionIdentity` binds immutable model identity, revision artifact digest,
  lineage contract, and optional exact parent revision digest.
- `ModelUpdateProposal` binds predecessor, open update-contract identity,
  implementation/configuration/training-input digests, optional randomness digest,
  and evidence references.
- `PreparedModelRevision` is the recoverable pre-commit state and must name a
  distinct candidate whose parent is the exact predecessor.
- `ModelRevisionCommit` carries the prepared object and exact successor object;
  construction rejects any successor other than the prepared candidate.
- `ModelPromotionDecision` binds the candidate revision to both qualification and
  evaluation evidence before activation.
- `ModelPromotionReceipt` cannot be created from a rejected decision.
- `ModelRollbackReceipt` binds failed-active revision, rollback target, triggering
  evidence, recovery anchor, and rollback generation.

## Failure and recovery semantics

A crash after preparation leaves a typed `PreparedModelRevision`; it does not
look committed. A commit requires explicit validation evidence and generation.
Promotion does not rewrite the predecessor. Rollback creates another receipt and
never silently edits revision lineage.

Update kinds are open semantic contract identifiers rather than a Platform enum,
so fine-tuning, online learning, distillation, policy update, or future project
methods do not require editing Platform source.
