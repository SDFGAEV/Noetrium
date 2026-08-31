# Research Data Semantic Convergence

Policy: Playbook §40–§42. Owner: ROLE05 Environment & Evidence.

## Goal

ROLE05 converges Artifact/Data/Evidence toward one storage-independent research-data path without merging durable authorities. Physical paths, buckets, mounts, and hosts are provider placement state; scientific identity is content/schema/lineage based.

Target flow:

`producer authority -> portable typed identity -> verified storage binding -> read-only query federation -> export/projection`

ROLE03 owns MeasurementDefinition/MeasurementRecord scientific semantics. ROLE05 owns durable Dataset/Artifact backing, verified placement, query/index/export mechanics, and lineage persistence. Query indexes never become Run, Measurement, or Evidence authority.

## Portable Dataset authority

`DatasetVersion` contains `DatasetIdentity`, scope, `content_sha256`, optional schema identity, typed parent `DatasetIdentity` lineage, tags, and metadata. It contains no physical `location`.

SQLite Dataset authority persists the same portable contract. Legacy schemas containing `location`/`digest` fail closed rather than being silently interpreted. Parent lineage is encoded as exact `{dataset_id, version}` identities rather than `"id@version"` strings.

## Verified Artifact placement

Logical `ArtifactRecord` remains storage-independent. `artifact/content` owns typed `ArtifactStorageBinding` placement state and positive CAS generation separately from catalog identity.

`VerifiedArtifactStoragePlacement` is a snapshot proof, not a claim that an externally mutable path stays valid forever. The filesystem verifier requires an absolute existing regular file, streams SHA-256 over the bytes, and rejects missing, unreadable, non-file, unsupported-provider, or digest-mismatched placements.

`bind` and `relocate` re-verify inside the SQLite CAS transaction, and every public `resolve()` re-hashes the current bytes before returning the binding. A verify-to-CAS content race fails closed without advancing authority.

Relocation verifies the destination and may recover from a corrupted old source because logical content identity remains durable. Successful relocation preserves content SHA-256 and increments generation; post-bind, reopen, and destination tamper are detected on authoritative resolve.

## Typed research-result query federation

`data/query/cross` is a real read-only semantic boundary rather than a generic operation/checkpoint leaf. Public execution is `ResearchResultQuery -> ResearchResultPage` through typed source/query ports.

Queries use typed scientific dimensions and result kinds. Each producer adapter returns an exact `ResearchSourceCut`; callers may pin cuts for repeatable reads. Changed cuts are `STALE`, source failures are `UNAVAILABLE`/`INCOMPLETE`, and unsupported dimensions or result kinds produce typed gaps instead of a misleading complete empty result.

`ResearchResultPage` exposes `matched_count` and `truncated`; any global `limit` truncation forces `complete=False`. Source disposition and diagnostics participate in the input-cut digest, so incomplete or stale reads cannot share the identity of a complete cut.

Dataset and Artifact adapters project producer-owned identities; the federation owns no mutable research truth and exposes no generic `execute`, checkpoint, restore, or state API. Source hard limits are fail-closed as incomplete cuts rather than silent truncation.

## Cross-role dependencies

ROLE05 does not create private substitutes for missing Core/Governance contracts. Current CSRs are recorded outside the repository under `outputs/reports/role05/`:

- `CSR-ROLE05-ROLE01-PSC02-STRICT-FINITE-JSON-CUTOVER-20260831`: consume one ROLE01 strict finite JSON encode/decode/digest authority instead of keeping broad scientific-boundary ambiguity.
- `CSR-ROLE05-ROLE01-PSC05-DATA-ARTIFACT-CONTENT-REFERENCE-20260831`: define the legal typed Dataset -> Artifact immutable content-reference dependency without giving Data artifact identity authority.
- `CSR-ROLE05-ROLE01-ROLE06-SEMANTIC-BOUNDARY-GATE-20260831`: replace the historical hard-coded 81 generic-leaf gate with canonical scaffold-vs-semantic-boundary classification.

Until those producer/gate decisions are integrated, ROLE05 keeps its owned implementation narrow and does not weaken tests or restore duplicate generic authority.
