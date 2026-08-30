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
migration authority, not an editable global ceiling. The immutable baseline binds
an exact Git SHA, canonical source digest and recomputable complexity projection.
Each migration additionally carries a ROLE00 approval state and evidence reference.
`proposed` migrations contribute zero allowance.

An approved migration contributes growth only when its owner-scoped import
projection matches the current exact source cut. This prevents a ROLE01-only cut
from pre-spending ROLE02–06 headroom: current ROLE01 remains limited to 4776 even
if later proposed migrations exist in the ledger. Formal audit also requires Git
source authority and independently resolves the baseline plus every approved
migration from exact Git objects before applying any allowance. Missing, stale or
mismatched provenance fails closed.

The Git provider consumes raw object-database bytes with `ls-tree`/`cat-file`, not
`git archive`, because archive output can be affected by host EOL/export settings.
Synthetic filesystem tests must inject their source index explicitly; production
release-quality never silently falls back from Git authority to a mutable checkout.
