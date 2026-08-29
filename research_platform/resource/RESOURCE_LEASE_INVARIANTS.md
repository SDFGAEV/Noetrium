# Resource Lease Invariants

ROLE 02 treats lease time as fencing state, not display metadata.

- Every lease TTL, expiry timestamp, renewal interval, bind observation time, and provider observation clock must be finite.
- `NaN` and positive/negative infinity are invalid at typed-contract and provider boundaries. A non-finite expiry can otherwise become an immortal stale lease because ordered expiry comparisons never succeed.
- Endpoint reservation is not listener ownership. Allocation remains `RESERVED` until a current-fencing `EndpointBindingProof` is confirmed by the allocation authority.
- Renewal preserves the current fencing token. Expiry/reallocation must advance fencing before the same resource can be owned by a new holder.
- SQLite and in-memory authorities enforce the same temporal contract; durable restoration is not allowed to weaken it.
- Heartbeat failure is fail-closed and must surface to the owning structured task rather than silently extending logical ownership.

The downstream Minecraft bind cutover remains a consumer responsibility tracked by the existing cross-system change request; Resource does not infer `BOUND` from its own reservation record.
