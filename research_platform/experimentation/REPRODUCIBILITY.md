# Experiment reproducibility authority

ROLE 03 owns the frozen run/checkpoint/evidence identities that connect executable work to reproducible experiment records.

## Run launch manifest

The `RunLaunchManifest` is the launch identity for release, prompt/model deployment, host, participant inventories, experiment specification, command, configuration, seed, and composition plans.

Its persisted wire format is an exact versioned envelope:

- `schema_version = "2"`
- `manifest = { ... exact RunLaunchManifest fields ... }`

Schema v2 adds the required canonical `project_manifest_digest` to frozen launch identity. Schema v1 is intentionally rejected rather than upgraded implicitly.

Unknown, missing, extra, or untyped envelope/manifest fields fail decoding. Unsupported schema versions and semantically equivalent noncanonical bytes fail closed. The encoded v2 bytes are therefore part of frozen launch authority; there is no implicit forward-compatibility path.

The canonical `RunLaunchManifest.digest()` is the stable launch/source identity consumed by evidence publication.

## Run artifact finalization authority

Mutable run artifacts are not scientific evidence merely because a caller knows a path. `DirectoryRunArtifactStore.finalize()` is the authority boundary that snapshots a completed artifact and emits a typed `RunArtifactSnapshotReceipt`.

A snapshot receipt binds the run ID, run-local artifact reference, artifact kind, logical generation, content SHA-256, byte size, and authoritative record count for record streams. Generation is derived only from logical run/artifact identity plus authoritative content facts; it never contains device, inode, mtime, or ctime. A complete backup restored under a different root or filesystem therefore preserves the same scientific artifact identity.

The per-reference seal is the single durable finalization commit point and is published first with the Platform `atomic_replace_bytes` durability authority. Once the seal exists, normal publish/append operations fail closed even if generation-index publication later fails or the store is reopened. The generation ledger is only a derived lookup index: reopen/idempotent finalization recreates a missing index and repairs a corrupt one from the authoritative seal.

`verify_finalized()` does not trust the receipt alone. It requires the durable seal and re-snapshots the current artifact; if a generation index exists it must agree, but absence of that derived index cannot reopen or invalidate sealed authority. Missing/unfinalized artifacts, receipt forgery, content/count drift, run mismatch, or a non-identical-content restore fail closed. Byte-identical backup/restore or replacement remains the same logical generation by design.

The directory provider performs the O(n) content hash/record-count pass at finalization/verification, not after every JSONL append. Append throughput therefore remains single-writer sequential I/O without a per-record full-file rehash.

## Scientific evidence identity

`EvidenceBundleManifest` schema version 2 binds evidence to both `run_id` and the exact SHA-256 `run_manifest_digest`.

Raw evidence streams no longer carry caller-asserted `artifact_ref`, `record_count`, and `content_sha256` fields. Each `EvidenceStreamDescriptor` embeds the artifact authority's typed `RunArtifactSnapshotReceipt`; the bundle rejects receipt/run identity drift and requires record-stream receipts with authoritative counts.

For `COMPLETE` publication, `RunArtifactEvidenceBundlePublisher` verifies every stream receipt through `RunArtifactVerificationPort` before writing the manifest. A hand-constructed descriptor, an existing-but-unfinalized path, or a finalized stream that later changes cannot authorize COMPLETE evidence.

The evidence manifest itself is atomically published and finalized through the same run-artifact authority. `EvidenceBundleReceipt` preserves the typed finalized manifest `RunArtifactSnapshotReceipt` together with `run_id` and `run_manifest_digest`; it does not collapse the manifest authority back into caller-supplied path/hash strings. Publication replay is idempotent only when the existing sealed manifest has the identical authoritative content digest.

An optional `source_checkpoint_id` can bind evidence to a specific checkpoint cut. Raw source-of-truth streams remain separate from rebuildable `DerivedEvidenceArtifact` projections, and derived artifacts list the exact source stream IDs they depend on.

## Checkpoint transaction

Workload restore validates manifest identity, component topology, codec/schema identity, payload references, and payload integrity before mutation.

Before apply, every component preimage is captured. Restore then applies components in manifest order. On failure, attempted components are rolled back in reverse order.

A successful rollback reports `ROLLED_BACK`; any rollback failure reports state certainty `UNKNOWN`. Partial mutation is never silently accepted as authoritative state.

Checkpoint manifests bind run/study/workload/branch, source cut, environment generation, method generation, task manifest, execution cut, and component payload digests.

`RunCheckpointManifestCodec` treats canonical JSON bytes as part of immutable checkpoint authority: a payload must decode to the exact typed manifest, match its digest, and byte-for-byte equal the canonical re-encoding. Semantic-equivalent pretty/reordered JSON is corruption rather than an alternate representation.

`experimentation.checkpoint.composition.build_project_run_checkpoint_store(project_state_root)` is the public project composition seam for the owner-defined crash-durable checkpoint provider. It places generic run checkpoints beneath the explicit project state root and returns only the public `RunCheckpointStore` contract; downstream common-path source need not import `experimentation.checkpoint.providers` or reproduce checkpoint durability.

## Durable generic run control

`experimentation/run/control` is the generic operator-facing lifecycle authority for `run`, `inspect`, `stop`, `resume`, `reconcile`, and `evidence`. It binds every command to the exact `RunIdentity.digest()` and `RunLaunchManifest.digest()` and requires `expected_generation` on every state-changing request.

Effectful lifecycle actions use a prepared-before-effect protocol. The directory ledger first atomically publishes an immutable `PREPARED` record with a deterministic operation ID and the exact base generation/checkpoint identity. Only after that publication returns may the lifecycle adapter perform an external effect. A separate immutable `TERMINAL` record advances the control generation only after an authoritative outcome exists.

A restart that finds an unresolved `PREPARED` record reconstructs `RECOVERY_REQUIRED` at the prior generation. Replaying the same request returns that pending projection and never reissues the lifecycle effect; a different request conflicts. Resolution requires the Execution reconciliation projection of ROLE02 effect authority. `UNKNOWN`, possible/unknown effect certainty, or verification-required evidence remains pending and can never report `RUNNING`.

If terminal publication fails after an effect may have happened, the pending prepared authority survives restart. If atomic terminal publication crossed its commit point before the caller observed an error, the controller re-reads the immutable ledger and returns the reconstructed terminal receipt instead of fabricating recovery. Corrupt, truncated, reordered, duplicate, identity-drifted, or semantically equivalent but noncanonical wire bytes fail closed; persisted immutable record authority therefore includes exact canonical bytes, not only decoded JSON meaning.

`inspect` and `evidence` are read-only and never advance the generation. `resume` additionally binds the exact checkpoint manifest digest and restore decision-cycle identity. Evidence replies accept only same-run/same-manifest `EvidenceBundleReceipt` values whose manifest artifact verifies through `RunArtifactVerificationPort`.

## New-project public construction and outcome authority

`research_platform.experimentation.api.ProjectRunDefinition` is the common project-facing construction boundary. It consumes only the narrow public ROLE 01 project-manifest projection (`identity.project_id`, `study_ids`, `semantic_digest`) and joins that authority with the existing `ExperimentSpec`, `StudyProtocol`, `ExperimentRunSpec`, `RunIdentity`, and `RunLaunchManifest` authorities. It rejects project/experiment/study/repetition/task-manifest/seed/run/manifest identity drift. `RunLaunchManifest.project_manifest_digest` must equal the canonical project manifest semantic digest, so durable run-control and evidence identity remain bound to the exact project configuration after construction. The `definition_digest` is a reproducible projection of those existing authorities; it owns no lifecycle or persistence state and does not parse or persist ProjectManifest bytes.

The same public package re-exports the producer-owned `RunControlPort` request/receipt contracts used by Operator and downstream projects. Projects therefore do not need to assemble checkpoint, workflow, or run-control stores in common-path code. Runtime composition injects one `RunControlPort`; the six application actions continue to execute against that sole ROLE 03 lifecycle authority.

Every `RunControlReceipt` carries an explicit `RunOutcomeProjection`. Execution outcome is derived only from durable run-control phase, task outcome remains `NOT_EVALUATED` unless a task authority is added in a future version, evidence validity is `NOT_OBSERVED`, `NOT_FINALIZED`, or `FINALIZED_VALID` according to the evidence command/finalized receipt, and scientific validity remains `NOT_EVALUATED`. The receipt rejects contradictory or caller-forged cross-authority outcomes. Consequently execution success, task success, evidence validity, and scientific validity cannot collapse into one boolean or status string.

## Validation rule

Persistence/checkpoint/recovery/evidence-finalization changes require Windows plus Server2 validation from the same committed SHA. Protected SEM execution roots, GPU0/1, and the Qwen endpoint are outside this validation path.
