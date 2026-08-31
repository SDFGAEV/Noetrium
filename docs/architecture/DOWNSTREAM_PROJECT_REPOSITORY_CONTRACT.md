# Downstream Project Repository Contract

## Purpose

Noetrium is an upstream reusable platform. Research methods, benchmark suites, project-specific environment composition, model selections, host inventories, experiment matrices, and scientific results belong in downstream repositories. Reusable providers that serve multiple independent projects may be bundled upstream; Minecraft is one such provider.

The supported relationship is intentionally one-way:

```text
upstream platform repository
        |
        +-- installed as a dependency, or
        +-- forked as a platform baseline
                 |
                 v
       downstream project repository
```

The platform must never import a downstream project. A downstream project may import public platform contracts and bind project-owned providers at its composition root.

## Recommended fork model

For a research program that needs tight integration, fork the upstream platform and keep project additions in isolated project-owned paths rather than editing platform internals.

```text
projects/<project>/
  pyproject.toml        optional independent project package
  src/                  project-owned Python package
  configs/              project-owned experiment/model/deployment config
  docs/                 project-owned scientific and operational docs
  tests/                project-owned regression and live integration tests
```

The downstream project should prefer its own package metadata under the project directory. Keeping project CLI entry points and dependencies out of the upstream root `pyproject.toml` minimizes merge conflicts when syncing upstream.

## Upstream synchronization

A downstream fork should configure remotes as:

```bash
git remote rename origin upstream
git remote add origin <downstream-fork-url>
git fetch upstream
```

Normal synchronization is then:

```bash
git fetch upstream
git merge upstream/master
# or rebase project-only commits when that repository policy allows it
```

Project code should not require edits to `research_platform/` merely to register itself. If a missing generic capability is discovered, implement that capability upstream behind a public contract first, then consume it downstream.

## Dependency rules

Allowed:

```text
downstream project -> research_platform.<system>.api
downstream composition -> public platform composition ports
downstream provider -> platform protocol it implements
```

Forbidden:

```text
research_platform -> downstream project package
platform runtime -> project-specific registry or service locator
downstream project -> platform-private implementation when a public contract exists
```

## Upstream purity gates

The upstream repository must remain independently buildable and testable with no `projects/` directory present. CI should fail if any of these conditions regress:

- root package metadata includes downstream project packages;
- `research_platform/**/*.py` imports a project package;
- the system catalog contains an unapproved downstream environment/project node;
- the upstream Docker image copies project code or installs project-only runtimes;
- release manifests include project-owned paths;
- platform tests require a concrete downstream project fixture.

The canonical automated check is `scripts/platform_repository_boundary.py`.

## Downstream ownership

A downstream repository owns all project-specific scientific truth and operational inventory: project methods, environment adapters that exist only for that project, model choices, host placement, experimental protocols, runbooks, live evidence, and results.

Generic fixes discovered while developing a downstream project should be promoted back upstream only when they can be expressed without importing or naming the project. This keeps the fork thin and makes future upstream synchronization tractable.

## Split milestone

Platform version `0.43.0` establishes the pure-platform repository boundary. Earlier revisions may contain mixed project/platform history; they remain Git history, not current-tree ownership.
