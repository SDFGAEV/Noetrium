# Agent Research Platform

[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)

A contract-driven platform for building, running, recovering, observing, optimizing, and auditing long-horizon AI-agent systems and research workloads.

The platform is intentionally **project-agnostic**. It provides reusable infrastructure for experiments, agents, models, environments, processes, artifacts, evidence, recovery, observability, governance, and release control without embedding the scientific semantics of any one downstream project.

## Why this platform?

Long-running agent systems fail in more ways than ordinary scripts: processes crash, external effects become uncertain, environments drift, model deployments change, checkpoints become incompatible, and partial logs can be mistaken for valid evidence.

Agent Research Platform treats these concerns as explicit systems with typed contracts, stable ownership, durable identities, and fail-closed recovery semantics.

## Core capabilities

- **Recursive system architecture** — explicit ownership, narrow public APIs, typed ports, and composition-time provider binding.
- **Experiment infrastructure** — study, run, branch, task, variant, workload, checkpoint, and resume identities.
- **Agent runtime** — participant, capability, action, memory, workflow, and execution boundaries without hidden global lookup.
- **Model infrastructure** — model catalogues, revisions, deployment qualification, serving identities, request envelopes, and prompt bindings.
- **Environment infrastructure** — environment specification, lifecycle, readiness, observation, action effects, snapshots, and recovery.
- **Process and server runtime** — process supervision, sessions, toolchains, remote execution, lifecycle control, and operation journals.
- **Durable data and artifacts** — checksummed state, WAL-backed recovery, lineage, retention, and content-addressed evidence.
- **Reliability** — classified failures, effect certainty, reconciliation, replay, incident handling, and fail-closed recovery.
- **Observability** — structured logs, events, metrics, traces, diagnostics, projections, and health signals.
- **Governance** — architecture, dependency, algorithm, concurrency, performance, forensic, release, and no-degradation gates.

## Architecture

The platform separates composition, execution, and observation:

```text
system topology / contracts
          │
          ▼
composition root ── freezes provider identities and bindings
          │
          ▼
runtime execution ── uses only injected narrow ports
          │
          ▼
observation plane ── logs, metrics, traces, diagnostics, evidence
```
The central dependency rule is simple:

```text
parent system
  └─ composes direct children through public contracts
       └─ runtime receives only the exact capability port it needs
```

Runtime code does not discover providers from a global service locator. Observability does not become a second command bus. Durable state has one owner, and external effects remain `CONFIRMED`, `REJECTED`, or `UNKNOWN` until reconciliation proves otherwise.

The authoritative system topology lives in:

```text
research_platform/governance/system_registry/catalog.json
```

See [Platform Architecture](docs/architecture/PLATFORM_ARCHITECTURE.md) and the [documentation index](docs/INDEX.md) for the full design.

## Platform vs. downstream projects

This repository is designed to be usable as an independent platform package.

Research methods, benchmark tasks, project-specific environment composition, experiment matrices, model choices, deployment inventories, and scientific interpretation belong in **downstream repositories**. Reusable environment providers may be bundled upstream when they are independently useful across projects; Minecraft is one such first-party provider. A typical workflow is:

```text
agent-research-platform
        │
        ├── install as a dependency, or
        └── fork as a platform baseline
                 │
                 ▼
       downstream research repository
       ├── project-specific method
       ├── experiment composition
       ├── task/environment bindings
       └── project evidence and results
```
Downstream code may consume platform contracts and provide project-owned implementations. The platform must not import a downstream project to decide scientific meaning, task semantics, model policy, or deployment policy.

This separation keeps the core reusable and allows project repositories to evolve independently without turning one experiment into platform-wide technical debt.

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- Docker / Docker Compose for containerized workflows
- Optional external runtimes only for providers that explicitly require them

### Install for development

```bash
git clone git@github.com:SDFGAEV/agent-research-platform-system.git
cd agent-research-platform-system

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Use the canonical product surface

The common Python API is `research_platform.api`; the common CLI is `research`.
Production lifecycle commands bind an explicit downstream application rather than discovering hidden providers:

```python
from research_platform.api import ResearchFacade

facade = ResearchFacade(my_application)
status = facade.inspect("run-123")
```

```bash
research --help
research --application my_project.operator:build_application inspect run-123
research diagnose --help
research manage --help
```

Architecture/algorithm/concurrency/performance CLIs remain specialized governance tools for maintainers.
See [Public facade and CLI](docs/product/PUBLIC_FACADE_AND_CLI.md).

## Container workflow

A reusable Linux image and Compose definition are maintained under `deploy/`:

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

The deployment layer is intended to separate immutable software from mutable runtime state. Host-specific paths and secrets belong in ignored environment/profile files, not in committed composition code.

For reproducible fleet deployment, build an immutable image once, bind it to an exact source revision, export or publish that image, and reuse the same image identity on execution nodes instead of rebuilding independently on every host.

### Bundled Minecraft provider

Minecraft is a first-party reusable environment provider. The base image stays lightweight; use the optional overlay when Java/Node/Mineflayer runtime support is required:

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

Task suites, benchmark manifests and scientific composition remain downstream. See [Minecraft infrastructure](docs/infrastructure/minecraft/README.md).

## Repository layout

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Reusable platform implementation and public system boundaries |
| `configs/` | Versioned configuration examples, model/runtime profiles, and non-secret templates |
| `deploy/` | Container image, Compose runtime, and deployment bootstrap assets |
| `docs/` | Architecture, infrastructure, governance, status, and historical documentation |
| `scripts/` | Thin operator, audit, release, maintenance, and development entry points |
| `tests/` | Hierarchical regression and contract tests |
| `research_platform/environment/minecraft/` | Bundled reusable Minecraft environment provider; project task suites remain downstream |
| `build/` | Local/generated build outputs |

The reusable package boundary is `research_platform/`. Project-specific code should migrate to or originate in downstream repositories rather than becoming a dependency of the platform core.

## Root-level repository artifacts

Several tracked files intentionally remain at the repository root because they are entry points or frozen release/validation projections:

| File | Purpose |
| --- | --- |
| `README.md` | Public GitHub project entry point |
| `CONTEXT.md` | Short platform composition vocabulary and navigation aid |
| `CURRENT_VALIDATION.json` | Checked-in validation snapshot; not a substitute for rerunning the current tree |
| `RELEASE_MANIFEST.json` | Frozen file manifest for a generated release |
| `RELEASE_EVIDENCE.json` | Frozen regression, architecture, algorithm, concurrency, and performance evidence for a release |
| `RELEASE_AUTHORITY.json` | Digests that bind the release manifest and release evidence |
| `ALGORITHM_SCAN.md` | Root compatibility projection retained for release-manifest stability |
| `CONCURRENCY_SCAN.md` | Root compatibility projection retained for release-manifest stability |
| `PERF_SCAN.md` | Root compatibility projection retained for release-manifest stability |
| `pyproject.toml` | Python package metadata, dependencies, and console entry points |
| `tests_support.py` | Shared regression support used by the repository test system |

Current governance reports belong under `docs/status/`. Root scan files must not be treated as the live authority unless they were regenerated for the exact release being inspected.

## Testing and verification

Run the repository regression suite with:

```bash
python -m pytest -q
```

For architecture and governance checks:

```bash
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
research-platform-algorithm scan
research-platform-concurrency scan
research-platform-performance scan
```
The platform also maintains a hierarchical test taxonomy so new tests remain assigned to an explicit subsystem/contract level rather than becoming an unstructured collection of files. See `tests/TEST_SYSTEM.json` and `scripts/test_system.py`.

Formal product assurance also validates provider-conformance classes and installed wheel/sdist artifacts. See [Distribution qualification](docs/release/DISTRIBUTION_QUALIFICATION.md).

A passing historical validation or release artifact does not prove the current working tree. Re-run the gates that matter for the exact revision you intend to publish or deploy.

## Design principles

1. **One owner per durable state.** Projections may accelerate reads but do not silently become authorities.
2. **Composition before execution.** Provider selection is explicit and frozen before the runtime hot path.
3. **Narrow runtime ports.** Consumers receive the exact capability they need, not a universal service locator.
4. **External effects are evidence-bearing.** Timeouts do not imply that an effect did or did not happen.
5. **Recovery is identity-aware.** Resume requires compatible source, configuration, provider, checkpoint, and environment identities.
6. **No silent degradation.** The platform does not lower quality, skip evidence, change a provider, or weaken a contract merely to make a run succeed.
7. **Observation is not authority.** Logs, metrics, traces, and diagnostics describe execution; they do not secretly control it.
8. **Performance changes preserve semantics.** Optimizations that can alter externally visible or scientific values must be versioned as semantic changes, not disguised as implementation details.
9. **Documentation moves with implementation.** Owner documentation and current-status projections are updated in the same change set as material code/configuration changes.
10. **Projects stay downstream.** Project-specific scientific meaning must not leak into reusable platform contracts.

## Extending the platform

Add a new capability at the smallest owning boundary:

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Prefer a new provider when the contract already exists. Add a new contract only when the capability itself is new. Avoid generic wrappers that hide unrelated algorithms or external effects behind one interface.

## Documentation

Start with the [documentation index](docs/INDEX.md).

Key platform references:

- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Final architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Documentation change policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)
- [Algorithm governance report](docs/status/algorithm/ALGORITHM_REPORT.md)
- [Concurrency governance report](docs/status/concurrency/CONCURRENCY_REPORT.md)
- [Performance governance report](docs/status/performance/PERFORMANCE_REPORT.md)
- [Historical engineering rounds](docs/history/README.md)

Architecture documents define reusable ownership and contracts. Status documents describe the current development tree. Historical rounds preserve evidence for the state that existed when they were written.

## Security and configuration

- Never commit passwords, private keys, access tokens, runtime secrets, or machine-local credentials.
- Keep host-specific paths and secrets in ignored local profiles or environment-bound stores.
- Prefer key/agent-based unattended authentication for remote automation.
- Keep external-effect commands typed, bounded, journaled, and attributable to an operation identity.
- Treat logs and evidence as potentially sensitive operational data; publish only the artifacts required by the intended release/research boundary.

## Contributing

Changes should be small enough to review by ownership boundary and should include the tests and documentation required to prove the change.

Before opening a pull request:

```bash
python -m pytest -q
python scripts/architecture_gate.py
```

For changes that touch governed hot paths, also run the relevant algorithm, concurrency, performance, forensic, or release checks.
A contribution is expected to:

- preserve system ownership and public-contract boundaries;
- add or update focused regression coverage;
- update the owning documentation in the same change set;
- avoid unrelated refactors in the same commit;
- preserve fail-closed behavior for uncertain external effects;
- document any intentional semantic or compatibility change explicitly.

See [Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md) for the repository documentation rule.

## Development status

The platform is under active architectural and runtime development.

Historical changes are intentionally kept out of this README; use docs/history/ for immutable engineering records. The current development truth is maintained in `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`. Versioned release evidence at the repository root describes the release for which it was generated; it is intentionally separate from the mutable working-tree status.

For current architecture and engineering status, use the documents under `docs/status/` and re-run the validation gates on the exact revision you plan to use.
