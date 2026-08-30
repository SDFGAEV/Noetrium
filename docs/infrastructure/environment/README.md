# Environment Provider Contract for New Projects

This document defines the ROLE05-owned environment/provider seam intended for downstream project scaffolds and clean-room generated-project tests.

## Public imports

Downstream projects should depend on:

- `research_platform.environment.api.ExecutionContext`
- `research_platform.environment.api.EffectReceipt`
- `research_platform.environment.api.EffectClass`
- `research_platform.environment.api.EffectCertainty`
- `research_platform.environment.api.EnvironmentProviderPort`
- `research_platform.environment.api.EnvironmentProviderCapabilities`
- `research_platform.environment.api.EnvironmentCapability`
- `research_platform.environment.api.EnvironmentSession`
- `research_platform.environment.api.EnvironmentSessionDiagnostics`
- `research_platform.environment.api.EnvironmentDiagnosticsPort`
- `research_platform.environment.api.EnvironmentCapabilityUnsupported`
- `research_platform.environment.api.EnvironmentConformanceProbe`
- `research_platform.environment.api.EnvironmentProviderConformanceReceipt`
- `research_platform.environment.api.verify_environment_provider_conformance`

Projects must not import provider-private runtime state, Minecraft bridge internals, state-machine checkpoint codecs, or platform service locators.
Provider-author tests should obtain the canonical execution context through `research_platform.environment.api.ExecutionContext`; downstream source must not import `research_platform.platform.kernel` directly. This is a public alias of the same Platform type, not a second context authority.

## Provider shape

An environment provider exposes only three things at the project boundary:

1. immutable `EnvironmentIdentity`;
2. typed optional-capability declaration;
3. `open_session(session_id=..., services=...)` returning the public `EnvironmentSession` contract.

`observe`, `act`, and `close` are baseline session behavior. Snapshot, restore, reconciliation, and diagnostics are optional capabilities that must be declared explicitly.

## Unsupported capability semantics

A provider must not make consumers discover optional behavior with `hasattr`, broad exception handling, or silent no-op fallbacks.

If a capability is absent from `EnvironmentProviderCapabilities`, the corresponding session method must fail with `EnvironmentCapabilityUnsupported` carrying the exact capability identity. The conformance runner checks this fail-closed behavior for snapshot/restore and, when an action receipt is available, reconciliation.

`UNKNOWN` external-effect state is not success. Providers that declare reconciliation support must reconcile against their authoritative action/effect state and preserve request identity. A facade must not convert an unknown or unproven effect into a confirmed one.

## Typed diagnostics

Providers that declare `DIAGNOSTICS` expose `EnvironmentDiagnosticsPort.diagnostics_snapshot()`.

The snapshot binds:

- session identity;
- immutable environment identity;
- current environment generation;
- ready/closed state;
- exact capability declaration;
- optional canonical state digest;
- optional evidence references.

Diagnostics are inspection data. They do not become lifecycle, action, checkpoint, or scientific authority.

## Minimal non-Minecraft reference provider

`research_platform.environment.composition.reference_counter_environment()` is the public Platform-owned clean-room reference composition. The implementation remains owned under `environment.providers`; downstream project source imports only the public `environment.api` contracts and, when it needs the bundled runnable reference, the public `environment.composition` factory.

It is deliberately tiny: a deterministic counter with `increment` and non-mutating `reject` actions. It uses the generic state-machine runtime, so the example exercises real action identity, effect receipts, snapshot/restore, reconciliation, diagnostics, and close semantics without requiring Java, Node, Minecraft, a server, or a benchmark-specific world.

Platform-owned and generated-project doctor/conformance tests may instantiate the reference through `research_platform.environment.composition` to prove the generic seam. A downstream project may instead implement its own provider against `research_platform.environment.api`; neither route requires importing `environment.providers` or runtime internals.

Provider conformance is exercised with:

```bash
python -m pytest -q tests/test_typed_environment_provider_npe_v1.py
```

The same test is required on Windows and on the Linux Platform validation node for an exact source revision.

## Artifact, data, and observation surfaces

New projects should reuse existing ROLE05 public contracts instead of creating project-local evidence schemas:

- `research_platform.artifact.catalog.api.ArtifactRecord` carries content SHA-256, scope, producer identity, lineage, media type, and retention declaration;
- run evidence should use a `ScopeIdentity(ScopeKind.RUN, run_id)` so the storage/catalog record carries explicit run lineage without claiming scientific acceptance;
- `research_platform.data.dataset.api.DatasetVersion` carries dataset content digest and scope;
- `research_platform.observability.api.EventEnvelope` is tagged `SIDE_PLANE_OBSERVATION` and is never primary operational/scientific authority;
- `research_platform.observability.status.api.SubsystemSnapshot` is a read-only project/doctor projection with evidence refs and stable reason codes.

ROLE03 remains the owner of run lifecycle, checkpoint policy, persisted run-control bytes, and scientific evidence finalization. ROLE05 artifact records prove storage/content identity and lineage; they do not decide whether a scientific claim is acceptable.

ROLE06 owns the common project facade, scaffold/template, and doctor/inspection commands. Those consumers should import the ROLE05 contracts above rather than define parallel environment, artifact, evidence, or diagnostics schemas.

## Provider-author checklist

Before handing a new adapter to project composition:

- freeze a non-empty environment identity with canonical artifact SHA-256;
- declare optional capabilities before opening a session;
- make unsupported optional operations fail with `EnvironmentCapabilityUnsupported`;
- preserve action identity across retries and reconciliation;
- never mutate authoritative state on a rejected action;
- make snapshot restore validate before mutation;
- expose typed diagnostics only as a read-only projection;
- run the provider conformance suite on every supported operating system;
- keep benchmark/task/scientific policy in the downstream project.
