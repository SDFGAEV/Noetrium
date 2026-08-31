# Noetrium: Reproducible Research Infrastructure for AI Agents



<!-- readme-nav:start -->
<p align="center">
  <strong>English</strong> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.de.md">Deutsch</a> ·
  <a href="README.ru.md">Русский</a>
</p>
<!-- readme-nav:end -->



<!-- readme-locale:en -->

<!-- readme-source-sha256:9dd7f68d71e7c6bfc9c059ec68315c5e86dc1ccac0a179645d1e0879c40c283f -->



**Build agents. Run experiments. Verify results.**

Reproducible, evidence-driven infrastructure for rigorous AI-agent research.



[![Python](https://img.shields.io/badge/Python-%3E%3D3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.43.1-blue)](pyproject.toml)
[![Architecture](https://img.shields.io/badge/architecture-contract--driven-6f42c1)](docs/architecture/PLATFORM_ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)



<!-- readme-section:overview -->

## Overview

Noetrium is a project-agnostic platform for building, running, recovering, observing, optimizing, and auditing long-horizon AI-agent systems and research workloads.

Reusable infrastructure stays in the platform; paper-specific scientific meaning, benchmark choices, experiment matrices, and deployment policy stay in downstream projects.

<!-- readme-section:why -->

## Why this platform?

Long-running agent systems fail in more ways than ordinary scripts: processes crash, external effects become uncertain, environments drift, model deployments change, checkpoints become incompatible, and partial logs can be mistaken for valid evidence.

The platform models these concerns as explicit systems with typed contracts, stable ownership, durable identities, evidence-bearing effects, and fail-closed recovery semantics.

<!-- readme-section:capabilities -->

## Core capabilities

- Recursive architecture — explicit ownership, narrow public APIs, typed ports, composition-time provider binding.
- Experiment infrastructure — study, run, branch, task, variant, workload, checkpoint, resume and reproducibility identities.
- Agent runtime — participant, capability, action, memory, workflow and execution boundaries without hidden global lookup.
- Model infrastructure — catalogues, revisions, qualification, serving identities, request envelopes and prompt bindings.
- Environment infrastructure — specification, lifecycle, readiness, observation, effects, snapshots and recovery.
- Process/server runtime — supervision, sessions, toolchains, remote execution, lifecycle control and journals.
- Durable data/artifacts — checksummed state, WAL recovery, lineage, retention and content-addressed evidence.
- Reliability — classified failures, effect certainty, reconciliation, replay, incidents and fail-closed recovery.
- Observability — structured logs, events, metrics, traces, diagnostics, projections and health signals.
- Governance — architecture, dependency, algorithm, concurrency, performance, forensic, release and no-degradation gates.

<!-- readme-section:architecture -->

## Architecture

Composition, execution and observation are separate authority planes.

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

Runtime code does not discover providers from a global service locator. Observability is not a second command bus. Durable state has one owner, and uncertain external effects remain UNKNOWN until reconciliation proves otherwise.

`research_platform/governance/system_registry/catalog.json`

<!-- readme-section:downstream -->

## Platform vs. downstream projects

This repository is an independent reusable platform package. Research methods, task suites, project-specific environment composition, experiment matrices, model choices, deployment inventories and scientific interpretation belong downstream.

```text
noetrium
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

Downstream code consumes public platform contracts and provides project-owned implementations; the platform must not import a downstream project to decide scientific meaning or deployment policy.

<!-- readme-section:quick-start -->

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- Docker / Docker Compose for container workflows
- Optional external runtimes only for providers that explicitly require them

### Install for development

```bash
git clone git@github.com:SDFGAEV/noetrium.git
cd noetrium
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Inspect the platform

```bash
research-platform-architecture-gate
research-platform-algorithm --help
research-platform-concurrency --help
research-platform-performance --help
research-platform-manage --help
```

<!-- readme-section:containers -->

## Container workflow

A reusable Linux image and Compose definition are maintained under `deploy/`.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```

The deployment layer separates immutable software from mutable runtime state; host-specific paths and secrets stay outside committed composition code.

### Bundled Minecraft provider

Minecraft is a first-party reusable environment provider. Task suites and scientific composition remain downstream.

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml build platform-runtime
docker compose -f deploy/compose.yaml -f deploy/compose.minecraft.yaml run --rm platform-runtime minecraft-doctor
```

[Minecraft infrastructure](docs/infrastructure/minecraft/README.md)

<!-- readme-section:repository-layout -->

## Repository layout

| Path | Responsibility |
| --- | --- |
| `research_platform/` | Reusable platform implementation and public system boundaries |
| `configs/` | Versioned configuration examples and non-secret templates |
| `deploy/` | Container image, Compose runtime and deployment bootstrap assets |
| `docs/` | Architecture, infrastructure, governance, status and history |
| `scripts/` | Thin operator, audit, release and maintenance entry points |
| `tests/` | Hierarchical regression and contract tests |
| `research_platform/environment/minecraft/` | Bundled reusable Minecraft environment provider |
| `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.md` | Apache-2.0 and third-party license notices |

`research_platform/` is the reusable package boundary; project-specific code stays downstream.

<!-- readme-section:testing -->

## Testing and verification

Run the repository regression suite and governance gates on the exact revision being evaluated.

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/public_contract_audit.py
python scripts/no_degradation_audit.py
python scripts/check_readme_i18n.py
```

A historical green result does not prove the current tree. Re-run the gates that matter for the exact revision you intend to publish or deploy.

The repository uses a hierarchical test taxonomy so every test belongs to an explicit contract level and release evidence can prove what was actually exercised. See `tests/TEST_SYSTEM.json`.

<!-- readme-section:principles -->

## Design principles

1. One owner per durable state.
2. Composition before execution.
3. Narrow runtime ports.
4. External effects are evidence-bearing.
5. Recovery is identity-aware.
6. No silent degradation.
7. Observation is not authority.
8. Performance changes preserve semantics.
9. Documentation moves with implementation.
10. Projects stay downstream.

<!-- readme-section:extending -->

## Extending the platform

Add a capability at the smallest owning boundary. Prefer a new provider when the public contract already exists; add a new contract only when the capability itself is new.

```text
<system>/
├── api/          public contracts and identities
├── runtime/      lifecycle and execution semantics
├── providers/    replaceable adapters owned by the system
└── composition/  provider-to-port binding
```

Avoid generic wrappers that hide unrelated algorithms, provider discovery or external effects behind one interface.

<!-- readme-section:documentation -->

## Documentation

Start with the documentation index.

### Key references

- [Documentation index](docs/INDEX.md)
- [Platform architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [Detailed system map](docs/architecture/VNEXT_DETAILED_SYSTEM_MAP.md)
- [Architecture migration contract](docs/architecture/FINAL_ARCHITECTURE_MIGRATION_CONTRACT.md)
- [Infrastructure documentation](docs/infrastructure/README.md)
- [Governance documentation](docs/governance/README.md)
- [Current status](docs/status/README.md)
- [Engineering history](docs/history/README.md)

Architecture documents define reusable ownership and contracts; status documents describe the current development tree; history preserves evidence for the state that existed when it was written.

<!-- readme-section:security -->

## Security and configuration

- Never commit passwords, private keys, access tokens, runtime secrets or machine-local credentials.
- Keep host-specific paths and secrets in ignored local profiles or environment-bound stores.
- Prefer key/agent-based unattended authentication for remote automation.
- Keep external-effect commands typed, bounded, journaled and attributable to an operation identity.
- Treat logs and evidence as potentially sensitive operational data.

<!-- readme-section:contributing -->

## Contributing

Changes should be reviewable by ownership boundary and include the tests and documentation needed to prove them.

### Before opening a pull request

```bash
python -m pytest -q
python scripts/architecture_gate.py
python scripts/check_readme_i18n.py
```

- preserve system ownership and public-contract boundaries
- add or update focused regression coverage
- update owning documentation in the same change set
- avoid unrelated refactors in the same commit
- preserve fail-closed behavior for uncertain external effects
- document intentional semantic or compatibility changes explicitly

[Documentation Change Policy](docs/governance/DOCUMENTATION_CHANGE_POLICY.md)

<!-- readme-section:license -->

## License

Noetrium is licensed under the Apache License, Version 2.0. The authoritative legal text is the root LICENSE file.

Third-party components remain governed by their own licenses; see THIRD_PARTY_NOTICES.md. Independently distributed model weights, datasets or benchmark assets may state separate terms.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

<!-- readme-section:status -->

## Development status

The platform is under active architecture and runtime development.

For production, publication or scientific claims, re-run the relevant gates and inspect release evidence bound to the exact source revision rather than relying on an old green result.

Historical changes are intentionally kept out of this README; use `docs/history/` for immutable engineering records.

The current development truth is `docs/status/CURRENT_DEVELOPMENT_BASELINE.md`; release and scientific claims must be bound to exact evidence for the revision being evaluated.

`docs/status/` · `docs/history/`
