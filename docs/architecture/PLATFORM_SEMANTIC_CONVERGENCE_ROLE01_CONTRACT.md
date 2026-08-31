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

ROLE03 exact producer `80eff508ec95c32b61c3d4345ab79f474a671157` deletes the redundant `research_platform.scientific/**` shell after folding reusable research semantics into Experimentation Study/Trial contracts. ROLE01 therefore removes the stale Scientific catalog authority and `SystemLayer` identity, while leaving the producer-side source deletion exclusively to ROLE03.

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


## PSC-03 neutral binding/diagnostic envelope

`research_platform.governance.architecture.api` now owns only the neutral transport/projection mechanics required by Playbook Section 41.6 and the Supervisor PSC-03 decision. `BindingDiagnosticCode` validates a stable namespaced code value without defining Model, Participant, Environment, Runtime, or project-specific code enumerations. `BindingDiagnostic` carries typed severity, blocking state, owner/subject identities, requirement digest/address, optional provider/profile identity, typed identity/evidence references, bounded remediation category/action, and concise rendering text. Its `machine_digest` excludes the human `summary`, so rewording cannot change diagnostic truth.

`BindingProof` carries successful neutral provenance: producer owner, consumer subject, requirement digest, provider/profile identities, binding generation, and evidence refs. `BindingResolution[T]` is fail-closed XOR state: success requires a producer-owned typed `T` payload plus `BindingProof` and forbids diagnostics; diagnostic state requires an immutable, machine-unique set with at least one blocking diagnostic and forbids a binding/proof. Diagnostic ordering and the neutral `projection_digest` are deterministic. The success projection digest covers only neutral proof metadata; it deliberately does **not** absorb domain payload identity, which remains owned by the producer binding type.

`BindingResolverPort[RequirementT, BindingT]` gives Research Compiler/Product consumers one small generic protocol without introducing `Mapping[str, object]`, `Any`, a provider registry, service locator, mutable context, or durable binding authority in Governance. ROLE04 may adapt Model/Participant project binding results while retaining their typed requirements, domain code enums, qualification/provenance semantics and concrete bindings. ROLE02/05 may project only project/preflight binding diagnostics through the envelope; runtime/session diagnostics such as `EnvironmentSessionDiagnostics` remain outside it. ROLE03 consumes producer projections and ROLE06 renders them; neither re-diagnoses producer domain truth.

Acceptance tests cover successful typed Model/Participant-like payload preservation, missing/ambiguous provider, capability/interface mismatch, qualification-unready, provenance-drift, deterministic diagnostic ordering/projection digest, human-summary non-authority, and rejection of mixed success/diagnostic or untyped/mutable metadata. Consumer cutover remains cross-Role work through the PSC-03 CSR; ROLE01 does not edit producer implementation paths.

### PSC-03 consumer handoff

- **ROLE02 Runtime/Reliability:** expose compiler/preflight binding outcomes through `BindingResolution[RuntimeOwnedBinding]`, `BindingProof`, and `BindingDiagnostic`; keep resource leases, lifecycle and effect/recovery diagnostics in ROLE02.
- **ROLE03 Execution/Experimentation:** consume `BindingResolverPort[RequirementT, BindingT]` and `BindingResolution[T]` in the side-effect-free Research Compiler; do not reclassify producer diagnostic codes or provider readiness.
- **ROLE04 Participant/Model:** adapt project requirement/profile resolvers to the neutral envelope while retaining `ParticipantRequirement`, `ModelCapabilityRequirement`, domain binding payloads, domain code enums and qualification provenance as ROLE04 truth.
- **ROLE05 Environment/Evidence:** use the envelope only for project/preflight binding facts where applicable; `EnvironmentSessionDiagnostics`, world/action reconciliation, evidence and storage authorities remain unchanged and outside PSC-03.
- **ROLE06 Product/Assurance:** render `BindingResolutionState`, diagnostic machine metadata and producer summaries for doctor/plan/schema clients; Product must not invent fallback bindings, rewrite blocking status, or turn rendering text into diagnostic identity.

## Algorithm-governance closure for convergence scanners

Semantic-boundary classification scans each catalog node and each direct plane source exactly once. The implementation keeps per-file marker inspection in an independent helper so the analyzer does not mistake disjoint `catalog -> plane -> file -> marker` syntax for Cartesian `O(N^3+)` work; the catalog classifier itself is now `O(N log N)` with no P1 finding.

Architecture report construction keeps historical-source caching and owner-scoped migration semantics unchanged, but historical observation replay is isolated from report assembly. Report materialization now creates one typed `ArchitectureReport` draft and derives the location-independent digest from that typed value rather than duplicating every field into a second hand-built payload.

Generic-leaf conformance tests intentionally validate every retained `SystemLeafContract` without freezing an exact leaf count. Architecture convergence is allowed to delete or merge unjustified shells; per-leaf contract/runtime/provider/composition conformance remains mandatory for every shell that survives.

## PSC-02 consumer-test cutover after duplicate deletion

ROLE01 convergence tests no longer import `research_platform.artifact._canonical` or other foreign private helpers as permanent equivalence authorities. Once a domain owner deletes a proven duplicate, restoring that private module for test compatibility would violate the migration state machine.

`test_typed_canonicalization_v2.py` therefore freezes the kernel's own strict byte/digest contract and separately proves ROLE01-owned ProjectManifest code consumes `strict_finite_json_bytes`, `strict_finite_json_digest`, and `strict_json_loads` rather than reimplementing them. Artifact/Data equivalence is producer-cutover evidence owned by ROLE05 while those duplicate implementations exist; after deletion, integrated tests consume only the surviving public/kernel authority.

### Parent-level shared-kernel dependency declaration

Artifact and Data are producer-owned domain systems, but their surviving implementations consume Platform kernel primitives. The canonical system catalog therefore declares `artifact -> platform` and `data -> platform` once at the truthful parent-system level. Data cross-query composition also consumes Artifact catalog/content identity, so the parent Data descriptor declares `data -> artifact` rather than repeating that dependency across query leaves. Child subsystems inherit these dependencies for source-invariant governance; the declarations do not move Data/Artifact domain authority into Platform or each other.

### Downstream architecture migration supersession

An active migration proposal is unique per overlapping owner scope. Historical rows remain immutable evidence, but a newer exact source contributes no stacked headroom: only a source/projection/delta-matching ROLE00 approval can become applicable. Current successors are ROLE03 `80eff508` at `+50` Execution/Experimentation imports, ROLE04 `866751f8` at `+101` Participant/Model imports, ROLE05 `7c401246d39e...` at `+63` Environment/Data/Artifact/Observability imports, and ROLE06 `cd664e2` at `+55` Operator/API imports. Older approvals remain historical evidence and contribute zero headroom to these successor source cuts until ROLE00 independently approves the exact new facts.

### Platform Trial runtime consumer cutover

Platform composition consumes the Experimentation-owned neutral Trial contract, not legacy Scientific/Workflow aliases. The runtime builder accepts `ExperimentTrialProtocol`, executes it through `ExperimentTrialCycleExecutor`, and binds `trial_protocol_identity`; default AgentTurn and ContextAction compositions inject their TrialProtocol implementations explicitly. Governance signature auditing follows `runtime/trial_cycle.py` so removed Scientific-cycle files cannot remain an implicit authority.
### Section 42 scaffold-only catalog contraction

ROLE02 proved that twenty-five Runtime/Resource/Reliability catalog nodes are generated/declarative shells with no substantive Python implementation and no external Python consumers. ROLE01 therefore retires those descriptors rather than preserving empty authorities. Their semantics remain facets of retained parent Runtime, Resource, Failure, Diagnostics, Recovery, and Reliability authorities; ROLE02 owns the physical 222-file deletion and ROLE06 owns release-manifest regeneration.

Catalog/source completeness is bidirectional for package authorities. A concrete standard-shaped package without a catalog owner is `unregistered_standard_system`; a catalog descriptor whose declared Python package is absent is `stale_catalog_package`. Non-package facets/projections must be represented explicitly outside this package-authority descriptor contract rather than by a descriptor pointing at missing source. This keeps scaffold deletion fail-closed without turning filesystem discovery into topology authority.

### PSC-08 Runtime read-only Resource topology

Runtime declares the top-level `resource` dependency because standard preflight composition consumes ROLE02's read-only `ComputeCandidatePort`; allocation, lease mutation and resource lifecycle remain Resource authority. The edge is acyclic: Resource has no dependency path back to Runtime. The historical ROLE02 `+8` migration remains evidence only after the 795b2d53 scaffold contraction; the contracted scope is below its frozen import baseline and needs no new growth allowance.
