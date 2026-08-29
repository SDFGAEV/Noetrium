# Model Serving OS — Round 11

## Frozen role-to-model assignment

Each LLM role maps to exactly one qualified deployment in `RoleModelManifest`. This is not failover routing. There is no ordered backup list. If the assigned deployment is unavailable, the run pauses/fails into exact recovery rather than silently switching model quality or semantics.

## Qualification becomes a deployment certificate

A `QualificationCertificate` binds:

- exact `ModelStackSpec` digest;
- target host inventory fingerprint;
- qualified roles;
- measured resource envelope;
- qualification evidence digest.

The resource envelope records measured peak GPU/host memory, maximum qualified concurrency and latency/throughput bounds. Placement therefore uses measured target-host evidence rather than optimistic model-size guesses.

Persisted host inventory and resource-delta evidence is immutable and fail-closed. Each evidence document is checksum-protected, bound inside the document to the exact runtime-manifest digest, and decoded through exact schema/type/range invariants. Rebinding a valid receipt under another manifest path, recomputing a checksum over malformed typed facts, changing the phase identity, or overwriting an existing manifest/phase evidence identity is rejected.

## Backpressure, not degradation

`ModelAdmissionController` caps concurrent requests at the qualified concurrency. Saturation waits or times out. It never reduces context, output tokens, precision, tensor parallelism, prompt content or model size.

## Crash-reconcilable one-click recovery

Recovery now includes `RECONCILE_STUDY` and has a durable attempt record. Before each recovery step the store records the step as running. If the operator process itself dies during a state-changing step:

- interrupted `RESTART_EXACT_MODEL` resumes from `RECONCILE_PROCESS`;
- interrupted `RESUME_STUDY_EXACT` resumes from `RECONCILE_STUDY`;
- verification-only steps may retry the exact same check.

Thus “recovery interrupted while recovering” cannot cause blind duplicate restarts or duplicate Study writers.
