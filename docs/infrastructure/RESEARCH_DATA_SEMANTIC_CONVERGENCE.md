# Research Data Semantic Convergence

Policy: Playbook §40–§41. Owner: ROLE05 Environment & Evidence.

## Goal

ROLE05 converges Artifact/Data/Evidence toward one storage-independent logical data path without merging their durable authorities. Physical paths, buckets, mounts and hosts are provider metadata; scientific identity is content/schema/lineage based.

The target collaboration is:

`logical content identity -> Artifact/Data authority -> typed lineage/reference -> provider storage binding -> query/export projection`

ROLE03 remains the owner of MeasurementDefinition/MeasurementRecord scientific semantics. ROLE05 owns durable backing, query/index/export, verified large-content references and lineage persistence.

## Primitive convergence

Artifact/Data canonical encoding and digest use the public Platform Kernel canonical primitives when semantics match. ROLE05 does not maintain parallel canonical encoders merely to avoid a declared dependency. Data retains only strict duplicate-key/non-finite decoding behavior not yet owned by Kernel.

Durable fact decoding is schema-bound: `FactSchema[T]` identifies one fact type/version and `FactDecoderPort[T]` returns a typed result. Internal heterogeneous registry convenience does not reintroduce `object` into the public decoder contract.

## Dependency rule

Artifact/Data -> Platform Kernel canonical imports require an explicit governance catalog dependency. This is tracked through a ROLE05->ROLE01 CSR; no private import exception or wrapper shim is acceptable.

## Storage relocation

`ArtifactRecord` is now storage-independent: physical `location` is not part of the logical artifact contract, SQLite catalog schema, or record digest. Acquisition returns verified operational placement separately from the immutable logical record.

`artifact/content` owns typed `ArtifactStorageBinding` state: artifact/content digest, storage provider, physical locator, and a positive generation. Initial binding is idempotent only for the same generation-1 value; relocation uses explicit expected-generation CAS, preserves the content digest, and increments generation. Unknown schema shapes and digest-tampered rows fail closed, while readers remain SQLite `query_only`.

Relocation acceptance requires the same bytes acquired under storage root A and storage root B to produce equal logical `ArtifactRecord` values. Moving A -> B changes only the storage binding; stale-generation relocation and attempts to retarget the same artifact identity to a different content digest are rejected.

`DatasetVersion.location` remains the second legacy coupling point. ROLE05 will remove it only against the shared neutral ContentIdentity primitive owned by ROLE01, rather than creating a temporary third content-reference authority.
