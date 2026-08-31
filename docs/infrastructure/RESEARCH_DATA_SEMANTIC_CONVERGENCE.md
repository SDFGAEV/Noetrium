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

Current `ArtifactRecord.location` and `DatasetVersion.location` are legacy coupling points because they participate in durable record digests. They are scheduled for removal from logical authority after a shared neutral ContentIdentity primitive is available. Provider locator bindings will then be independently durable/rebuildable and relocation tests must preserve logical content/dataset/lineage identity.
