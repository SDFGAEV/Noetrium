# Participant Topology and Architecture Revision

ROLE04 now exposes immutable scientific identities for multi-participant experiments without moving collaboration policy into Platform.
`AgentCoordinationHub` remains a bounded runtime router for its existing workload; it is not the topology authority.

`ParticipantTopologyMember` binds participant id, scientific role, participant requirement, accepted binding, and participant architecture revision.
`ParticipantTopology` canonicalizes member ordering so declaration order is not mistaken for scientific topology.
A later topology revision must bind the exact predecessor digest.
`ParticipantTopologyTransition` records explicit add/remove/replace/rebind changes; silent mutation is not an accepted transition.

`ParticipantMessageSchedule` is a distinct identity from the member topology.
It binds topology digest, participant set, zero-based message order, sender/recipients, and causal parent message ids.
Therefore two runs with the same message set but a different schedule have different schedule digests.
Unknown participants, duplicate messages, non-contiguous order, and future/self causal dependencies fail closed.
## Participant architecture revisions

`ParticipantArchitectureRevision` binds a participant to an immutable set of component identities.
Each component separates semantic capability id from implementation digest, configuration digest, and optional state schema.
`ParticipantArchitectureTransition` records typed add/remove/replace/reconfigure operations between exact revision digests.
Checkpoint/resume helpers require exact topology and architecture revision digests and reject incompatible continuation.

These contracts intentionally do not define planner/team policy, routing strategy, scheduling algorithm, or runtime service placement.
They are producer-owned scientific identity/provenance facts for ROLE03 replay, checkpoint and evidence binding.
Downstream projects may define arbitrary collaboration and cognition modules while reusing these identities without adding a Platform registry entry.