# ROLE02 public preflight facts — 2026-08-31

This note closes the ROLE02-owned NPE question of whether a new runtime/resource/recovery state authority is needed for doctor/compiler preflight. It is not needed.

The public domain facts already required by a downstream read-only consumer are:

- Runtime: `runtime.server.health.api.ServerDiagnosticReport` and its typed status/issues.
- Resource: `resource.compute.api.ComputeRequirement`, `ComputeHost`, and allocation contracts.
- Reliability: `reliability.recovery.api.RecoveryDecisionReport` and typed recommendations.
- Scope identity remains supplied by the existing `scope.api` authority.

`tests/test_runtime_preflight_public_contract_v1.py` proves a consumer can determine candidate placement, runtime readiness and recovery blocking using only `*.api` imports. The reference consumer imports no provider, composition or implementation-runtime module and performs no allocation, launch, reconcile, lease renewal or durable write.

These facts remain producer-owned domain truth. ROLE02 must not add `InfrastructureState`, a generic transition enum, a service locator, or a project-owned durable preflight store.

PSC08 still requires one neutral compiler/doctor projection. That layer is intentionally deferred until ROLE01 publishes PSC03 `BindingMetadata` / `DiagnosticProjection` (or the exact approved equivalents) and the canonical `runtime -> resource` dependency. The future ROLE02 adapter should only map the public facts above into that neutral vocabulary.

Local versus Server2 placement is therefore a binding/composition concern: the scientific definition need not own SSH paths, process internals, lease files, recovery files, or provider-specific state.