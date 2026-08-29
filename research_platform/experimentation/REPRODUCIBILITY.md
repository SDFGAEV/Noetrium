# Experiment reproducibility authority

ROLE 03 owns the frozen run/checkpoint/evidence identities that connect executable work to reproducible experiment records.

## Run launch manifest

The `RunLaunchManifest` is the launch identity for release, prompt/model deployment, host, participant inventories, experiment specification, command, configuration, seed, and composition plans.

Its persisted wire format is an exact versioned envelope:

- `schema_version = "1"`
- `manifest = { ... exact RunLaunchManifest fields ... }`

Unknown, missing, extra, or untyped envelope/manifest fields fail decoding. Unsupported schema versions fail closed. There is no implicit forward-compatibility path.

The canonical `RunLaunchManifest.digest()` is the stable launch/source identity consumed by evidence publication.

## Run artifact finalization authority

Mutable run artifacts are not scientific evidence merely because a caller knows a path. `DirectoryRunArtifactStore.finalize()` is the authority boundary that snapshots a completed artifact and emits a typed `RunArtifactSnapshotReceipt`.

A snapshot receipt binds the run ID, run-local artifact reference, artifact kind, opaque generation, content SHA-256, byte size, and authoritative record count for record streams. Finalization writes a durable receipt ledger through the same serialized run-artifact writer.

`verify_finalized()` does not trust the receipt alone. It requires the durable finalization ledger and re-snapshots the current artifact. Missing/unfinalized artifacts, receipt forgery, content/count drift, run mismatch, or stale/rebound artifact identity fail closed.

The directory provider performs the O(n) content hash/record-count pass at finalization/verification, not after every JSONL append. Append throughput therefore remains single-writer sequential I/O without a per-record full-file rehash.

## Scientific evidence identity

`EvidenceBundleManifest` schema version 2 binds evidence to both `run_id` and the exact SHA-256 `run_manifest_digest`.

Raw evidence streams no longer carry caller-asserted `artifact_ref`, `record_count`, and `content_sha256` fields. Each `EvidenceStreamDescriptor` embeds the artifact authority's typed `RunArtifactSnapshotReceipt`; the bundle rejects receipt/run identity drift and requires record-stream receipts with authoritative counts.

For `COMPLETE` publication, `RunArtifactEvidenceBundlePublisher` verifies every stream receipt through `RunArtifactVerificationPort` before writing the manifest. A hand-constructed descriptor, an existing-but-unfinalized path, or a finalized stream that later changes cannot authorize COMPLETE evidence.

The evidence manifest itself is atomically published and finalized through the same run-artifact authority. `EvidenceBundleReceipt` repeats `run_id` and `run_manifest_digest` alongside the finalized manifest SHA-256.

An optional `source_checkpoint_id` can bind evidence to a specific checkpoint cut. Raw source-of-truth streams remain separate from rebuildable `DerivedEvidenceArtifact` projections, and derived artifacts list the exact source stream IDs they depend on.

## Checkpoint transaction

Workload restore validates manifest identity, component topology, codec/schema identity, payload references, and payload integrity before mutation.

Before apply, every component preimage is captured. Restore then applies components in manifest order. On failure, attempted components are rolled back in reverse order.

A successful rollback reports `ROLLED_BACK`; any rollback failure reports state certainty `UNKNOWN`. Partial mutation is never silently accepted as authoritative state.

Checkpoint manifests bind run/study/workload/branch, source cut, environment generation, method generation, task manifest, execution cut, and component payload digests.

## Validation rule

Persistence/checkpoint/recovery/evidence-finalization changes require Windows plus Server2 validation from the same committed SHA. Protected SEM execution roots, GPU0/1, and the Qwen endpoint are outside this validation path.
