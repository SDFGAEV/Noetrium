# vNext System Blueprint

## Architectural rule

The platform is designed top-down. A parent system owns only its direct responsibility and composes children through narrow contracts. Child systems never reach into parent implementation state.

```text
Platform
├── Scope
├── Portfolio
├── Experimentation
├── Execution
├── Participant
├── Scientific
├── Resource
├── Environment
├── Model
├── Runtime
├── Data
├── Artifact
├── Reliability
├── Observability
├── Governance
└── Operator
```

## Ownership boundaries

| System | Owns | Must not own |
|---|---|---|
| Scope | hierarchy, ownership path, scope identity | project metadata, experiment semantics, runtime state |
| Portfolio | workspace/program/project metadata | study/run state, model state |
| Experimentation | study/trial/measurement/analysis/experiment/run/checkpoint semantics | server/process control and concrete participant/environment/model implementations |
| Execution | workflow/operation/capability orchestration | provider storage, scientific semantics |
| Participant | participant contracts/bindings/sessions | concrete server supervision, scientific state |
| Resource | resources, leases, compute inventory, directories | environment semantics, model deployment |
| Environment | environment specs/bindings/resolution/instances | project semantics, model selection |
| Model | model assets/stacks/assignments/deployments/serving identity | process lifecycle implementation |
| Runtime | servers/processes/services/sessions | experiment semantics, model catalog truth |
| Data | durable facts, records, datasets, canonical state, projections | immutable content storage identity |
| Artifact | immutable content and identity/reference | mutable business state |
| Reliability | effects, failures, recovery, forensics | scientific truth, UI views |
| Observability | logs, telemetry, status, observation projections | durable failure/state authority |
| Governance | architecture/release/quality/system topology rules | business execution |
| Operator | human query/command surfaces | domain authority |

## Standard internal shape

Every independently replaceable system follows the same recursive boundary:

```text
System
├── api/             # identities, contracts, ports
├── runtime/         # orchestration only
├── providers/       # concrete implementation/backends
└── composition/     # external wiring only
```

No API package owns workers, locks, persistence mutation, buffering, process control or provider branching.

## Migration order

1. Establish the complete system graph and ownership metadata.
2. Establish child-system skeletons and authority declarations.
3. Establish debug/log/failure/diagnostic seams.
4. Migrate organizational ownership: Portfolio/Scope/Experimentation.
5. Migrate Environment, Model, Resource and Artifact authorities.
6. Migrate Runtime and Execution orchestration.
7. Migrate Reliability and Observability implementations.
8. Migrate Operator and Governance surfaces.
9. Migrate participant and downstream research implementations behind Experimentation-owned Study/Trial contracts.
10. Delete obsolete historical boundaries instead of adapting them.

## Debug hierarchy

All systems expose stable correlation coordinates rather than implementation-specific knowledge:

```text
platform
→ system
→ subsystem
→ scope
→ operation
→ component
→ trace/span
→ state/effect/model/artifact reference
→ log/failure/evidence
```

This allows root-cause analysis at platform, project, run, operation and component level without coupling the debug system to a domain implementation.
