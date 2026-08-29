# Minecraft action capability system

## Scope

The Minecraft environment owns a provider-neutral typed action ABI. Mineflayer
is one provider implementation; downstream planners, memory systems and research methods do
not import Mineflayer or JavaScript action handlers.

The action catalog is authoritative in
`research_platform/environment/minecraft/api/contracts.py`. Each entry declares
its category, effect behavior, bounded timeout, purpose and planner-visible
argument contract. The same catalog drives Python validation, planner tool
publication, transport command support and the Mineflayer handshake check.

## Provider modules

| Module | Responsibility |
|---|---|
| `runtime.js` | Bot binding, navigation primitives, entity/inventory lookup and stable result construction |
| `movement.js` | Coordinate navigation, entity navigation and bounded retreat |
| `resources.js` | Collection, crafting, furnace operations and block placement |
| `inventory.js` | Equipment, consumption, discard/give and container transactions |
| `combat.js` | Entity/player melee, ranged attack and bounded self-defence |
| `bridge.js` | JSONL lifecycle, snapshots, routing, capability handshake and result envelopes |

The bridge has no task-planning, prompt, memory or evolution authority.

## Effect evidence

Every external task action emits exactly one `action_result` with:

- the exact requested `action_id`;
- an action object whose `tool` equals the requested action type;
- a stable outcome `status` and `code`;
- a mapping outcome containing observable before/after facts;
- a Boolean `verified` flag.

`applied` requires observed evidence of the requested effect. `rejected` means
the provider deterministically established that the requested effect was not
applied. `partial` means some progress or an unconfirmed external effect may
exist and therefore requires reconciliation. Transport acknowledgement alone
never proves an MC effect.

Internal observation queries carry no task action ID and are audit-only. They
cannot overwrite `last_action_verified` or be treated by downstream memory as successful task
experience.

### Completion and reconciliation authority

Planner intent is never completion authority. A `planner_finish` goal can close only when
the last action receipt is accepted and either explicitly verified or carries a confirmed
effect certainty. Accepted-but-unverified/possible effects remain incomplete.

Environment-to-agent receipts preserve the kernel effect certainty instead of inferring it
from a Boolean verification field: confirmed effects map to `confirmed`, possible effects
remain `possible`, rejected/no-effect outcomes map to `rejected`, and unresolved evidence
remains `unknown`. The provider effect identity is copied from the authoritative
`EffectReceipt`; it is not reconstructed from diagnostics.

Prepared-action and generic reconciliation preserve the same four-way semantics:
`APPLIED -> EFFECT_CONFIRMED`, `REJECTED -> EFFECT_REJECTED`,
`NOT_APPLIED -> NO_EFFECT`, and `UNKNOWN` produces no terminal effect truth. A missing
action-recovery record is therefore unknown, never retry-safe absence.

## Craft and resource invariants

- Collection proves both broken blocks and a positive inventory delta.
- Crafting resolves the canonical registry item, uses a nearby crafting table
  or places an available one, computes recipe output per execution and verifies
  the requested inventory increase.
- Smelting rejects conflicting furnace contents, calculates bounded fuel use,
  closes the furnace in all paths and verifies output returned to inventory.
- Furnace clearing and chest operations close windows in `finally` paths.
- Placement verifies the resulting world block instead of treating a
  Mineflayer call return as sufficient proof.

## Combat invariants

- Targets are resolved by exact entity ID, exact player username or bounded
  name query according to the action contract.
- Melee equips the strongest available weapon, bounds pressure by `max_hits`
  cycles and always stops the PvP plugin.
- A target death or Mineflayer `entityHurt` event is required for confirmed
  melee success. Swing attempts alone remain partial.
- Ranged attacks require weapon and ammunition, bound shot count/charge time,
  and use hurt/death signals for confirmation. Ammunition loss without a hit
  remains partial.
- Self-defence considers an explicit bounded hostile registry, target count and
  radius.

## Hot-path selection

Drop association and nearby dropped-item selection scan candidates once and retain the
nearest eligible entity. They deliberately do not sort the full candidate set: target
selection is `O(N)` while preserving the same nearest-by-bot-distance semantics and stable
first-candidate tie behavior.

## Verification

Provider module tests run without a Minecraft server:

```bash
cd research_platform/environment/minecraft/providers/assets/mineflayer_bridge
npm ci
node --test actions.test.js
```

Python contract, transport, state/evidence and planner tests are in
`tests/test_minecraft_environment_v1.py`,
`tests/test_sem_minecraft_evidence_v1.py`,
`tests/test_sem_minecraft_runtime_adapter_v1.py` and
`tests/test_sem_model_planner_v1.py`.

A real Java server smoke remains a separate environment qualification step. It
never silently substitutes mocks for live Minecraft evidence. The operator may
provide a pinned server JAR or explicitly request official Mojang acquisition;
both routes preserve the exact content digest in the run identity. See
`MC_RUNTIME_BOOTSTRAP_AND_SCENARIOS.md` for the source-world fixture and live
smoke contract.
