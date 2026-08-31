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
is deliberately ROLE04-typed; the cross-system neutral contribution envelope is
a separate ROLE01 PSC-03 dependency.
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
envelope and does not import ROLE03 compiler internals. When the ROLE01 PSC-03
neutral contribution/diagnostic contract is available in the authorized
integration dependency chain, composition can wrap these payloads without
changing their domain identity.

The separate strict-finite-JSON convergence CSR is also still external to this
slice. This Level-0 authoring contract neither copies that primitive nor weakens
the existing Model/Participant canonicalization boundaries.

## Artifact and configuration digest identity

Level-0 Participant declarations treat provided `artifact_digest` and
`configuration_digest` values as canonical lowercase SHA-256 identities. Arbitrary
labels such as `artifact-v1` or `config-v1` are rejected before a canonical
`ParticipantRequirement` can be emitted. Absence is typed explicitly as `None`;
an empty string is rejected and is never overloaded as a digest sentinel. The
Agent/Method identity -> ParticipantRequirement projection preserves `None` or the
exact lowercase SHA-256 value without inventing a replacement identity.
