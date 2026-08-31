# Current Development Baseline

**Baseline date:** 2026-08-28
**Platform version:** 0.43.1
**Repository role:** reusable upstream platform

This document is the current development truth for the generic Noetrium repository. Concrete research methods, benchmark tasks, project-specific environment composition, model selections, machine inventories, experiment matrices, and scientific results are downstream-owned. Reusable first-party environment providers may remain upstream; Minecraft is bundled.

## Repository boundary

The reusable package boundary is `research_platform/`. Packaging publishes only `research_platform*`; the upstream must import, test, build, release, and run its generic doctor without any `projects/` tree or project-owned environment/provider package. Approved bundled providers are governed explicitly by the repository-boundary allowlist.

The enforceable split contract is [`../architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md`](../architecture/DOWNSTREAM_PROJECT_REPOSITORY_CONTRACT.md) and `scripts/platform_repository_boundary.py`.

## Platform ownership

The upstream owns generic contracts and runtime systems for experiment identity, participants, agents, methods, environments, models, prompts, services, processes, servers, artifacts, storage, recovery, observability, governance, testing, and release control.

Concrete downstream behavior binds through public contracts and may add scientific methods, benchmark adapters, environment providers, model profiles, deployment inventory, application CLIs, and result/evidence interpretation without becoming an upstream dependency.

## Current source validation

The frozen source-validation pass on 2026-08-28 completed with **1083 passed, 6 skipped, 0 failed, 0 errors, and 4 subtests passed**.
Algorithm governance scanned **5732 symbols / 348 candidates**. Concurrency governance scanned **286 hotspots / 1 finding / 0 blocker debt**. Performance governance scanned **76 hotspots / 88 findings / 0 blocker debt**. Architecture and test-system source gates pass.

The three source inventories explicitly exclude `.server-state`, so local controller state, audit clones, transfer staging, and forensic scratch files cannot contaminate platform governance evidence.

SQLite WAL lock contention is handled by the generic deadline-retry primitive in `platform.kernel`; `scope` declares this dependency explicitly rather than relying on a hidden cross-system exemption.

Structured deadline propagation is stress-qualified: the child-first inherited-group deadline race passed 50/50 independent repetitions, and the complete concurrency runtime module passed 37/37.

Repository test identity is explicit: `tests/__init__.py` prevents third-party top-level `tests` packages from shadowing repository helpers, while pytest config exposes `tests/` for legacy helper-module imports. Release-regression diagnostic logs are captured as bytes and decoded fail-safe for human diagnostics, so non-UTF-8 child-process output cannot abort machine-readable release evidence generation.

## Packaging and deployment

The generic Docker image stays lightweight. Minecraft is a bundled upstream provider with an opt-in `Dockerfile.minecraft` / Compose overlay rather than forcing Java and Node into every platform deployment.

The 0.43.1 Minecraft candidate image passed `minecraft-doctor` on Linux with Python 3.12.3, Java 21.0.12, Node 22.22.2, npm 10.9.7, Mineflayer 4.37.1, pathfinder 2.4.5, pvp 1.3.2 and vec3 0.1.8. Its bridge suite passed 14/14 tests; image id `sha256:75661da87c84f474869c66a24ded79a26a8adaacf87321766221d7a8fe663cc8`.

Version 0.43.0 established the repository-extraction boundary; 0.43.1 corrects that split by restoring the reusable Minecraft provider to upstream while keeping benchmark/scientific composition downstream. A release is authoritative only when the release subsystem regenerates `RELEASE_MANIFEST.json`, `RELEASE_EVIDENCE.json`, and `RELEASE_AUTHORITY.json` from the exact source tree and the final repository-boundary/package verification gates pass.

## Release qualification contract

A qualifying release must prove all of the following without weakening a gate: no downstream-owned source in the upstream manifest; complete test taxonomy; full regression; architecture/algorithm/concurrency/performance gates; wheel/sdist membership; generic container doctor; and self-verifying release authority/evidence.

Release source inventory prunes generated dependency-install trees such as `node_modules` at the manifest walker itself. A developer may run lockfile-qualified Node tests in place without those transient dependencies entering a source manifest or release package.

Historical release files remain evidence for their historical tree only. They are never reused as current development truth after the source tree changes.

## Downstream continuity

Repository extraction does not discard project history. Downstream repositories retain their own source, configuration, tests, documentation, deployment inventory, evidence, and Git history and consume the platform through the documented one-way dependency boundary.
