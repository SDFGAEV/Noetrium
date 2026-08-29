# Experiment reproducibility authority

ROLE 03 owns the frozen run/checkpoint/evidence identities that connect executable work to reproducible experiment records.

## Run launch manifest

The `RunLaunchManifest` is the launch identity for release, prompt/model deployment, host, participant inventories, experiment specification, command, configuration, seed, and composition plans.

Its persisted wire format is an exact versioned envelope:

- `schema_version = "1"`
- `manifest = { ... exact RunLaunchManifest fields ... }`

Unknown, missing, extra, or untyped envelope/manifest fields fail decoding. Unsupported schema versions fail closed. There is no implicit forward-compatibility path.

The canonical `RunLaunchManifest.digest()` is the stable launch/source identity consumed by evidence publication.

## Scientific evidence identity

`EvidenceBundleManifest` schema version 1 binds evidence to both `run_id` and the exact SHA-256 `run_manifest_digest`.

An optional `source_checkpoint_id` can bind evidence to a specific checkpoint cut. Raw source-of-truth streams are represented separately from rebuildable `DerivedEvidenceArtifact` projections.
Every required stream has an artifact reference, record count, content SHA-256, and explicit source-of-truth flag. Derived artifacts list the exact source stream IDs they depend on; references to absent streams are rejected.

`EvidenceBundleReceipt` repeats `run_id` and `run_manifest_digest` alongside the published manifest digest so downstream consumers cannot detach a receipt from its frozen launch identity.

## Checkpoint transaction

Workload restore validates manifest identity, component topology, codec/schema identity, payload references, and payload integrity before mutation.

Before apply, every component preimage is captured. Restore then applies components in manifest order. On failure, attempted components are rolled back in reverse order.

A successful rollback reports `ROLLED_BACK`; any rollback failure reports state certainty `UNKNOWN`. Partial mutation is never silently accepted as authoritative state.

Checkpoint manifests bind run/study/workload/branch, source cut, environment generation, method generation, task manifest, execution cut, and component payload digests.

## Validation rule

Persistence/checkpoint/recovery changes require Windows plus Server2 validation from the same committed SHA. Protected SEM execution roots, GPU0/1, and the Qwen endpoint are outside this validation path.