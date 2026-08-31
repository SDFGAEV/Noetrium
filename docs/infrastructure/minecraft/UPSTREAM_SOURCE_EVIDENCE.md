# Minecraft upstream source evidence

## Locked dependency

- Upstream repository: `PrismarineJS/mineflayer`.
- Locked Mineflayer version: `4.37.1`.
- Official release commit recorded by the workspace source audit: `03eba44`.
- Cached official tag archive SHA-256: `AA2728EB1FC5850CDBACBDC0480EC6DA7ADFCED855836427BB4A5DA3B38C2CF6`.
- Local bridge package requires Node `>=22` and pins Mineflayer exactly to `4.37.1`.

This evidence is the source lock for Minecraft provider changes. The cached archive is an immutable read-only input; provider behavior must not be inferred from an unpinned latest package.

## Upstream semantics used by the provider

The locked Mineflayer API exposes separate entity lifecycle events including `entitySpawn`, `itemDrop`, and `playerCollect(collector, collected)`. The provider uses these signals only as observations for drop association and collection; a transport/event occurrence by itself is not durable external-effect certainty.

The locked connection lifecycle forwards client error/end state to bot lifecycle events. Upstream promise/timeout helpers are process-local and do not provide crash-durable intent, exactly-once execution, or action reconciliation. Agent Research Platform therefore owns the durable action-recovery journal and must preserve `UNKNOWN` when durable external-effect evidence is absent or corrupt.

## Local extension and non-degradation rule

The local provider intentionally adds stronger semantics than upstream:

- action request and provider identity binding;
- crash-durable action recovery and four-way reconciliation;
- environment/effect receipts that retain confirmed/possible/rejected/unknown certainty;
- drop association that keeps Mineflayer event semantics but chooses the nearest eligible entity in one linear scan rather than sorting all candidates.

Any future Mineflayer version change must repeat the exact-version source audit before changing lifecycle, entity, pathfinding, inventory, combat, or recovery behavior.
