# Algorithm Governance Contract

## Complexity classification authority

Algorithm Governance classifies asymptotic control-flow growth conservatively. Structural loop counts remain evidence, but only loops whose cardinality may grow with input contribute an `N` factor. Literal finite iterables and values proven to derive exclusively from finite literal iterables are constant factors. Unknown names, calls, provider results, database results, mutable containers whose bounded provenance is invalidated, and all other unresolved iterables remain input-sized.

Python sort operations contribute `N log N` only when the sorted input cardinality is not statically bounded. Database, I/O, and subprocess calls are classified as loop amplification only when they execute under an unbounded loop; a statically finite control loop does not become `N` merely because it contains an effectful call. This does not estimate the internal complexity of the database or external service itself.

JavaScript function symbols own their own control-flow bodies. Nested callbacks/functions are analyzed as independent symbols and do not inflate the parent symbol. Ordinary brace nesting (`if`, object literals, callback bodies) is not loop nesting. Fixed literal `for...of` masks are constant factors; unresolved iterables remain `N`.

## Fail-closed rules

The classifier must never infer a finite bound from an unknown call or mutable input. Mutation of a previously bounded container invalidates its bounded status. Adversarial tests must prove both sides: finite control loops do not create false `N^2`/database-in-loop findings, while an unknown-cardinality loop containing a database call continues to emit the P1 amplification finding.

Analyzer semantic changes require a new analyzer revision. A reviewed baseline for an earlier revision is intentionally stale and the Algorithm Gate must stop at the parent analyzer-migration blocker before reporting per-symbol regressions. Baseline provenance/replay and externally approved lower-bound migrations are separate typed authorities; changing the classifier does not grant or refresh those authorities.
