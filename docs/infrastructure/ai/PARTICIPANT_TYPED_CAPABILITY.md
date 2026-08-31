# Participant Typed Capability Contract

ROLE04 keeps the existing JSON `CapabilityRequest` / `CapabilityResult` path for small tool-style capabilities.
Research components whose scientific values are not naturally JSON may instead use the additive typed-carrier path.
Both paths reuse the same `CapabilityDescriptor`, provider identity and `EffectClass`; no second capability registry exists.

A typed input implements `CapabilityInputCarrier`; a typed output implements `CapabilityOutputCarrier`.
Each carrier publishes an exact `schema_id` and deterministic `digest()`.
`TypedCapabilityRequest` binds the descriptor, carrier digest and scientific execution identity while excluding trace/span-only fields.
`TypedCapabilityResult` binds the exact request digest, provider id, result schema and output carrier digest.

`FunctionalTypedCapabilityProvider` is a reference implementation for pure local capabilities only.
It rejects descriptor drift before calling the handler and rejects result-schema drift before publishing a result.
Effectful capabilities are deliberately rejected by this direct path so existing prepared-effect/reconciliation authority cannot be bypassed.

## Downstream authoring

A paper-local `NovelComponentInput` / `NovelComponentOutput` pair can implement the carrier protocols directly.
No Platform enum, source registration, implementation-class registry, endpoint table or collaboration policy edit is required.
The component may be substituted behind the same semantic descriptor as long as request/result schema and evidence identity remain exact.

This contract is intentionally transport-neutral.
An out-of-process adapter may consume the same carrier identity later, but transport lifecycle/deadline/backpressure authority remains outside this pure reference provider.
