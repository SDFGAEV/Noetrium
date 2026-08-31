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

## Immutable Artifact content identity

`ArtifactContentIdentity(artifact_id, content_sha256)` is the portable claim-grade content identity produced by Artifact. It intentionally excludes mutable `reference_id`/generation and physical provider/location state.

`verify_artifact_content_identity(...)` composes `ArtifactRegistryPort` and `ArtifactStorageBindingPort` without creating another store. It requires exact artifact identity plus matching immutable catalog digest and current verified storage digest; missing authorities, digest drift, and foreign-identity impostors fail closed with typed verification codes. Storage relocation may change provider/location/generation while the content identity remains unchanged.

Data and ROLE03 may consume this producer-owned value only after the governance dependency cut is declared; they must not replace it with a mutable `ArtifactReference` alias or a second content authority.

## Typed research-result query federation

`data/query/cross` is a real read-only semantic boundary rather than a generic operation/checkpoint leaf. Public execution is `ResearchResultQuery -> ResearchResultPage` through typed source/query ports.

Queries use typed scientific dimensions and result kinds. Each producer adapter returns an exact `ResearchSourceCut`; callers may pin cuts for repeatable reads. Changed cuts are `STALE`, source failures are `UNAVAILABLE`/`INCOMPLETE`, and unsupported dimensions or result kinds produce typed gaps instead of a misleading complete empty result.

`ResearchResultPage` exposes `matched_count` and `truncated`; any global `limit` truncation forces `complete=False`. Source disposition and diagnostics participate in the input-cut digest, so incomplete or stale reads cannot share the identity of a complete cut.

Dataset and Artifact adapters project producer-owned identities; the federation owns no mutable research truth and exposes no generic `execute`, checkpoint, restore, or state API. Source hard limits are fail-closed as incomplete cuts rather than silent truncation.

## Canonical JSON convergence

ROLE05 consumes the ROLE01 strict finite JSON kernel producer through merge `dfd6801b1c333e3f8014c70235d2205996e55fb8`. Data aliases kernel `strict_finite_json_bytes/text/digest` and `strict_json_loads`; its former local decoder is deleted. Artifact catalog/content/lineage/reference/retention durable record digests use `strict_finite_json_digest` directly.

This keeps one encoding/decoding acceptance authority: valid finite JSON remains byte/digest-identical, while bytes, paths, sets, enums, non-finite values, cycles and other broad canonical values fail before scientific persistence.

## Cross-role dependencies

Resolved in the consumed ROLE01 producer:

- `CSR-ROLE05-ROLE01-PSC02-STRICT-FINITE-JSON-CUTOVER-20260831`: functional strict encode/decode/digest cutover is complete.
- `CSR-ROLE05-ROLE01-ROLE06-SEMANTIC-BOUNDARY-GATE-20260831`: architecture tests no longer hard-code 81 generic leaves, so `data/query/cross` remains a typed semantic boundary without fake execute/checkpoint state.

Open producer/governance dependencies are recorded outside the repository under `outputs/reports/role05/`:

- `CSR-ROLE05-ROLE01-PSC05-DATA-ARTIFACT-CONTENT-REFERENCE-20260831`: Artifact now publishes `ArtifactContentIdentity`; ROLE01 still must declare the typed Data -> Artifact dependency before Dataset can persist the producer-owned value without bypassing the catalog DAG.
- `CSR-ROLE05-ROLE03-UNIFIED-RESEARCH-RESULT-READ-PROJECTION-20260831`: publish stable ROLE03 Run/Trial/Task/Measurement/Evidence read authority so ROLE05 can adapt it into the unified read-only federation.

Until those producer decisions land, `run`, `task`, `action`, `observation`, `measurement`, and `evidence` result kinds remain explicitly representable but unsupported sources return typed `NO_SOURCE_CAPABILITY` gaps. ROLE05 does not create a private Run/Measurement registry or restore generic leaf authority.
