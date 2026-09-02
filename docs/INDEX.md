# Documentation Index

This directory is the single documentation root for the reusable Noetrium. Documents are grouped by platform ownership and lifecycle; downstream research repositories own their own methods, tasks, project-specific environment compositions, deployment inventories, and result documentation. Reusable first-party providers may remain upstream.

## Authority order

1. `noetrium_platform/foundation/governance/system_registry/catalog.json` is the unique platform system-topology authority.
2. `docs/architecture/VNEXT_SYSTEM_CATALOG.json` is the checked documentation mirror of that topology.
3. Current architecture, infrastructure, and governance documents describe reusable platform contracts.
4. `status/` reports the current platform development state.
5. `history/` preserves platform engineering history and never overrides a current contract.

A downstream repository may add project-local documentation, but it is not part of the upstream platform authority.

## Documentation hierarchy

- [`architecture/`](architecture/README.md) — recursive platform architecture, topology, composition, data flow, repository boundaries, and migration contracts.
- [`COMPONENT_LAYERS.md`](architecture/COMPONENT_LAYERS.md) — reusable single-agent components and higher-tier multi-agent orchestration.
- [`infrastructure/`](infrastructure/README.md) — reusable model, runtime, server, observability, storage, and execution infrastructure.
- [`governance/`](governance/README.md) — architecture gates, forensic evidence, debugging policy, no-degradation rules, and documentation policy.
- [`status/`](status/README.md) — current platform baseline and generated governance reports.
- [`history/`](history/README.md) — immutable platform engineering milestones.
- [`readme/`](readme/README.md) — multilingual README registry, section schema, translation freshness, terminology, and release gate policy.

## Repository split contract

The upstream repository contains only reusable platform code and first-party generic infrastructure. Concrete research projects belong in downstream repositories that either depend on or fork the platform.

See [`architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md`](architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md) for the supported fork/update model and [`architecture/GENERIC_PLATFORM_BOUNDARY.md`](architecture/GENERIC_PLATFORM_BOUNDARY.md) for dependency direction.

## Current status

The current development truth is [`status/CURRENT_DEVELOPMENT_BASELINE.md`](status/CURRENT_DEVELOPMENT_BASELINE.md). Generated algorithm, concurrency, and performance reports live under `status/` and describe the exact source tree for which they were produced.

Documentation changes are governed by [`governance/DOCUMENTATION_CHANGE_POLICY.md`](governance/DOCUMENTATION_CHANGE_POLICY.md). Implementation, tests, and owning documentation are expected to move together.

## Documentation rules

- Keep one canonical document per reusable platform contract.
- Put reusable capability documentation under `infrastructure/`.
- Put platform ownership and dependency rules under `architecture/` or `governance/`.
- Put project-specific scientific material only in downstream repositories.
- Add a platform history note when a platform contract or implementation boundary materially changes.
- Root `README.md` and `CONTEXT.md` are navigation documents, not alternative authorities.
