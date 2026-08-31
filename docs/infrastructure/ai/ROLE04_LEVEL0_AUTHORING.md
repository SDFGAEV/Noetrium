# ROLE04 Level-0 Participant and Model authoring

ROLE04 Level-0 authoring is a pure declaration-to-requirement projection. It
does not select providers, open runtimes, allocate resources, execute models, or
write durable Experiment/Run state.

The canonical Participant path is:

`AgentProjectDefinition | MethodProjectDefinition -> ParticipantRequirement`

Both definitions compile to the existing `ParticipantImplementationIdentity`
family. Agent uses `kind="agent"`; Method uses `kind="method"`. No second
lightweight Participant authority is introduced.

Each definition can emit a `ParticipantRequirementContribution` containing the
exact author-definition digest and the canonical typed requirement. The payload
remains deliberately ROLE04-typed; cross-system compilation may wrap it, but
cannot replace or reinterpret the producer-owned requirement identity.
## Model authoring

The canonical Model path is:

`ModelProjectDefinition -> ModelCapabilityRequirement -> ProjectModelBinding`

A Level-0 generation author declares a semantic `prompt_id`, role, capability
requirements, context requirement, and optional tool-schema identity. The author
does not repeat the active prompt generation or prompt digest. A read-only
`PromptSelectionPort` resolves those exact identities from the current Prompt
authority before a canonical `ModelCapabilityRequirement` is produced.

Non-generation capabilities such as embedding, scoring, value inference, or a
project-local capability do not consume Prompt authority and therefore do not
fabricate prompt identity. They compile directly to the same existing
`ModelCapabilityRequirement` family used by advanced providers.
## Identity and authority boundaries

Author-definition identity is independent from the current Prompt generation and
from provider/deployment selection. Re-publishing a prompt generation therefore
changes the compiled Model requirement/contribution without claiming that the
paper author changed their definition. Provider replacement occurs later and
changes binding identity while preserving the author definition and requirement
when compatibility is unchanged.

`PromptSelectionIdentity` is an observation/projection of Prompt authority, not a
new writable registry. Level-0 compilation performs no provider discovery,
qualification, runtime opening, resource allocation, execution, or durable Run
mutation. Advanced Level-1 callers may still construct the same canonical
Participant/Model requirements directly.
## Cross-system integration status

`ParticipantRequirementContribution` and `ModelRequirementContribution` remain
producer-typed ROLE04 payloads. ROLE04 does not define the cross-system compiler
envelope and does not import ROLE03 compiler internals.

When the accepted ROLE01 PSC-03 producer is present, ROLE04 composition adapters
project successful `ProjectModelBinding` / `ProjectParticipantBinding` values and
producer-owned binding diagnostics into the neutral typed `BindingResolution`
envelope. Domain requirement types, diagnostic enums, provider qualification and
binding authority remain ROLE04-owned. Owner and project subject identities are
explicit composition inputs rather than ambient registry lookups.

ROLE04 also consumes Platform Kernel `freeze_json`, `strict_json_loads`, and
`strict_finite_json_bytes` instead of private Model/Participant JSON acceptance
helpers. The consumer cut is verified on an exact ROLE01+ROLE04 disposable union;
formal dependency integration into the authoritative branch remains a ROLE00/DAG
decision rather than a worker-side merge.

## Artifact and configuration digest identity

Level-0 Participant declarations treat non-empty `artifact_digest` and
`configuration_digest` values as canonical lowercase SHA-256 identities. Arbitrary
labels such as `artifact-v1` or `config-v1` are rejected before a canonical
`ParticipantRequirement` can be emitted. The empty string remains the explicit
absence of a separately published artifact/configuration digest; it is not
reinterpreted as a digest value.
