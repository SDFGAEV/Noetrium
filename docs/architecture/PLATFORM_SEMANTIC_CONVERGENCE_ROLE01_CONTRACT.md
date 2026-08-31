# ROLE01 Platform Semantic Convergence Contract

This contract implements the ROLE01 governance portion of Playbook ?41. It does not create a new top-level system, durable business authority, service locator, or universal research manager.

## Semantic-boundary classification

`research_platform.governance.architecture.classify_semantic_boundaries()` produces a deterministic source-backed inventory for every canonical catalog node. Each node is classified as exactly one of:

- `IMPLEMENTED_SEMANTIC_BOUNDARY`: its own standard planes contain direct non-template semantic source, rather than only generated ownership wrappers;
- `DECLARATIVE_ONLY`: it is a dependency/capability/component aggregation boundary but has no direct semantic implementation evidence;
- `DELETE_CANDIDATE`: it has neither direct semantic implementation evidence nor dependency/capability/component justification.

Classification examines only the node's direct `api/runtime/providers/composition` Python files. Child subsystem implementation never promotes its parent automatically. `boundary.py`, generic `owner.py`, generic `default.py`, and `__init__.py` do not by themselves count as semantic implementation.

`DELETE_CANDIDATE` is governance evidence for owner/consumer migration. It is not permission for ROLE01 to delete another owner's production path. The owning role must inventory consumers, move any surviving semantics, and commit the deletion or merge in its own path.

## Generic leaf policy

`BoundSystemLeafRuntime`, `SystemLeafRuntimeOwner`, `SystemLeafProvider`, `LeafHandler`, and `FileLeafStateStore` are neutral scaffold/governance infrastructure. Their presence proves neither domain behavior nor domain durable-state authority.

`validate_semantic_boundary_claim()` therefore fails closed when a generic/declarative boundary claims `implemented=True`, and it always rejects `GENERIC_LEAF_STATE` as domain durable authority. A real domain boundary may claim `DOMAIN_TYPED` state only when its source evidence independently qualifies as implemented.

This rule intentionally leaves low-risk generic leaf infrastructure reusable. It prevents scaffold completion from being mistaken for scientific, operational, data, environment, model, runtime, or evidence semantics.

## Current convergence consequence

On the current ROLE01 cut, `scientific/implementation`, `scientific/measurement`, `scientific/method`, `scientific/prompt`, and `scientific/protocol` are generic-shell delete candidates. This is machine evidence supporting the ROLE03-owned ?41 scientific merge/delete analysis; ROLE01 does not delete those paths.

By contrast, boundaries such as `execution/operation` contain direct typed API/provider implementation and classify as implemented even though a generic owner wrapper also exists. This prevents blanket deletion based on filenames or boilerplate counts.

## Consumer contract

ROLE03/ROLE06 compiler, introspection, doctor, schema, impact and plan surfaces may consume the public `SemanticBoundaryEvidence`/claim types. They must not reproduce the classification rules in Product or project code. Any user-visible "implemented capability" claim must be backed by an `IMPLEMENTED_SEMANTIC_BOUNDARY` result or a more specific owner-defined typed conformance authority.

This semantic-boundary inventory is only one ?41 gate. It does not replace capability compatibility, provider qualification, lifecycle conformance, evidence lineage, or external migration approval.

## PSC-02 neutral kernel primitive convergence

`research_platform.platform.kernel` exposes two deliberately different canonical boundaries. The pre-existing broad `canonical_bytes` / `canonical_text` / `canonical_digest` contract explicitly supports Platform values such as dataclasses, Enum, bytes, Path and sets. It must not be used to widen scientific/public finite-JSON acceptance. The narrow handoff is `strict_finite_json_bytes`, `strict_finite_json_text`, `strict_finite_json_digest`, `strict_json_loads`, `freeze_json`, and `thaw_json`; its encoder itself rejects bytes, Path, set/frozenset, dataclass, Enum (including string/integer Enum subclasses), non-string mapping keys, cycles, excessive depth and non-finite floats. `require_sha256` / `Sha256Digest` own canonical lowercase SHA-256 text validation.

ROLE01 itself consumes the narrow authority: ProjectManifest encoding/digest/decoding no longer carries a second duplicate-key/non-finite JSON parser or SHA-256 regex, and generic leaf contract/state mechanics no longer maintain a separate JSON-digest encoder. Tests lock byte/digest equivalence with the overlapping Artifact/Data canonical domain before any foreign-owner cutover. Consumer handoffs must name the `strict_finite_json_*` entrypoints explicitly rather than broad `canonical_*`. Strict decoding projects failures through stable `CanonicalDecodingFailureKind` values (`bom`, `duplicate_key`, `non_finite`, `syntax`, `domain`); raw parser tokens, duplicate keys, or nested encoder exception text are never public error semantics. Domain owners may map those stable kinds to their own typed decode errors without copying parser logic.

This is not a universal value framework. The kernel primitive owns representation/integrity mechanics only. Artifact identity, Dataset identity, scientific Measurement semantics, Model/Participant values, Run evidence, persistence policy, and provider behavior remain with their domain owners.

Foreign duplicate implementations are removed only by their owning roles after equivalence and consumer tests. ROLE01 issues CSRs for those cutovers and does not edit Artifact/Data/Experimentation production paths directly.

## Section 42 ProjectManifest identity stratification

`ProjectManifest.identity_facets` is a rebuildable projection over the single canonical manifest authority. It exposes `PROJECT_SPEC`, `AUTHOR_REQUIREMENTS`, `PROVIDER_BINDINGS`, `SCAFFOLD_PLATFORM_PROVENANCE`, and `TOTAL_CLOSURE` digest dimensions. No facet is written back as a second manifest truth.

The serialized `semantic_digest` field and `ProjectManifest.semantic_digest` property mean **complete manifest semantic closure** and equal the `TOTAL_CLOSURE` facet. They are not Study, Run, Measurement, Analysis, or scientific-design equivalence identities. Consumers asking whether two projects differ must name the relevant facet or use `diff_project_manifest_facets()`; a provider-only change must not be reported as a changed author-requirements identity.

Portfolio owns these author/onboarding identity projections only. ROLE03 remains the owner of compiled scientific/Run identities, ROLE04/05 own their typed binding/domain identities, and ROLE06 may render facet-aware differences without redefining equality.
