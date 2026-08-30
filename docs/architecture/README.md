# Architecture Documents

This directory owns the final platform architecture and its topology-facing
design. The source-of-truth topology remains
`research_platform/governance/system_registry/catalog.json`; the JSON mirror in
this directory is generated and checked against it.

Use these documents for recursive ownership, composition-time binding,
runtime ports, event-spine boundaries, migration rules and data flow. Project
method details do not belong here.

## Current topology-query implementation notes

The in-memory system registry may maintain derived child indexes for query efficiency, but `governance/system_registry/catalog.json` remains the only topology authority. Indexed `children()` and `descendants()` projections must preserve deterministic sorted breadth-first ordering and must never become independent durable state.

Architecture hotspot scanning likewise reuses the source index and performs one AST-node traversal per module; optimization may remove repeated parsing/traversal but may not change the public hotspot scoring formula.

## Governance source-analysis boundary

Repository discovery is a Governance provider responsibility exposed through
`RepositorySourcePort` / `RepositorySourceIndexPort`. A release-quality or
architecture composition root freezes one `RepositorySourceSnapshot` before any
consumer runs. Directory traversal, file read, UTF-8 decode and Python parse
failures raise `RepositorySourceIncompleteError`; a partial cut is never exposed.

`RepositorySourceTree` remains the explicit filesystem provider for synthetic and
non-Git test fixtures. Formal architecture and release-quality composition uses
`GitRepositorySourceTree`: it resolves one exact commit and reads canonical paths
from `git ls-tree` plus raw blob bytes from `git cat-file --batch`. It therefore
never depends on checkout state, `core.autocrlf`, export filters, a later HEAD, or
files created while a scan is running. Both providers order files by canonical
POSIX relative path. `RepositorySourceIndex` records its `source_authority` and
`source_revision`, parses Python once, and serves analyzers by exact frozen bytes.

Snapshot/index reuse is explicit composition-time policy, never an ambient
global cache or a second source truth. Source identity changes require a new
cut; an analyzer cannot silently accept digest drift. Root-level derived release
projections such as `RELEASE_EVIDENCE.json`, `RELEASE_MANIFEST.json` and
`DEVELOPMENT_ARCHITECTURE_REPORT.json` are excluded from source identity so a
governance report cannot recursively change the source cut that produced it.

## Registry contract projection

`governance/system_registry/catalog.json` remains the only durable declaration
authority for topology, ownership, requires/provides and component metadata.
Governance does not import leaf boundary modules or maintain `_NODE_METADATA`.
Instead, source invariants statically inspect existing literal
`SystemLeafContract` declarations and compare their identity/authority/ownership
fields with the catalog. A mismatch is `leaf_contract_catalog_drift` and fails
closed until the owning Role resolves the contract through CSR when required.

Nodes that do not yet declare `SystemLeafContract` are not synthesized from the
catalog. Adding such a public contract belongs to the system owner; ROLE01 only
verifies declarations that exist and guards the canonical registry.

## Architecture complexity budget

`research_platform/governance/architecture/ARCHITECTURE_BUDGET.json` is a v3
migration proposal ledger, not an approval authority or editable global ceiling.
The immutable baseline binds an exact Git SHA, canonical source digest and
recomputable complexity projection. Proposal rows may describe expected growth,
but they contribute zero headroom by themselves.

Migration approval is supplied independently by the Supervisor/Integrator. Formal
audit accepts a typed external approval set only when its file SHA-256 is supplied
through trusted composition, then verifies every approval-record SHA-256 and exact
source identity. Version-1 approval records authorize only pure `import_edges`
migrations under `architecture-import-edge-migration-only`; they contribute zero
headroom if any other complexity dimension is non-zero. Version-2 records bind the
complete five-dimensional `ArchitectureComplexity` delta and require scope
`architecture-complexity-migration-only`. A worker proposal cannot authorize itself.

An externally approved migration contributes growth only when the approved complete
delta matches the proposal, the historical Git cut independently reconstructs that
delta, and the current immutable cut matches the approved owner-scoped source bytes
and import projection. Missing dimensions, stale source identities, copied approvals,
scope mismatches, or partial approvals contribute zero headroom.

The Git provider consumes raw object-database bytes with `ls-tree`/`cat-file`, not
`git archive`, because archive output can be affected by host EOL/export settings.
Synthetic filesystem tests must inject their source index explicitly; production
release-quality never silently falls back from Git authority to a mutable checkout.

## Architecture gate failure projection

`ArchitectureReportGate` is a fail-closed adapter, not an exception suppressor or a fallback source authority. If immutable source acquisition, provenance verification, or architecture report construction fails, evaluation returns a non-passing `governance.architecture` child report containing exactly the ERROR finding `ARCHITECTURE_SOURCE_UNAVAILABLE`. The finding exposes only the exception type; exception messages, secrets, paths, and tracebacks are not projected into gate evidence.

`CompositeGate` therefore retains the architecture child in provenance even when report construction cannot complete. This behavior must never be replaced by a mutable-filesystem retry, an omitted child, or a false-green empty report. Synthetic non-Git callers that need architecture analysis must inject an explicit source index at the architecture composition boundary rather than relying on production fallback.

### Canonical generic run-control registration

`experimentation/run/control` is a canonical ROLE03-owned standard subsystem whose topology declaration is governed by ROLE01. Its authority is `run_control`; it owns durable generic run lifecycle control and fenced control generations, and must not own operator product intent, server-supervision internals, or duplicate run manifest/checkpoint truth. The descriptor requires the exact platform/execution/checkpoint/run identity-lifecycle-manifest authorities it consumes and uniquely provides `run.control`.

Catalog topology growth is accounted separately from producer import growth: ROLE01 carries the registry node/contract/authority complexity delta, while ROLE03 `693c481...` carries only its exact `+38` import-edge migration. Both remain subject to independent external ROLE00 migration approval; neither catalog presence nor a proposal grants headroom by itself.
