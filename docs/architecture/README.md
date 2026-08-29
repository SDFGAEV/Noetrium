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

`RepositorySourceTree` prunes generated/vendor directories before descent,
preserves exact filesystem-byte SHA-256 identity and orders files by canonical
POSIX relative path on every operating system. Source-invariant diagnostics use
the same POSIX-relative path identity so report digests do not vary by host OS.
`RepositorySourceIndex` is a read-only IR over that frozen cut: Python syntax is parsed once and analyzers
request ASTs by `relative_path + sha256`. Algorithm, concurrency, performance,
quality and architecture consumers therefore bind to the same source identity
instead of independently rescanning the live filesystem.

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

`research_platform/governance/architecture/ARCHITECTURE_BUDGET.json` is a v2
reviewed migration ledger, not an editable global ceiling. Its baseline authority
binds the frozen Git SHA, canonical source digest and independently recomputable
complexity projection. The semantic document is pinned by a reviewed SHA-256, so
changing baseline metrics or migration allowances without a corresponding
review-authority change fails closed.

Every growth allowance carries a unique migration id, owner Role, exact reviewed
source Git SHA, per-dimension delta and substantive justification. Effective
limits are computed as `baseline + sum(reviewed deltas)`; there is no standalone
`limits` field to raise. Review tests materialize the frozen baseline and each
migration source with `git archive`, rebuild the canonical SourceIndex and verify
the declared deltas. The current reviewed ledger composes `4749 + 72 = 4821`
import edges from ROLE01–06 exact source bindings while keeping all topology,
contract and authority counts frozen.
