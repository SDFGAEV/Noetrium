from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from noetrium_platform.foundation.kernel.kernel import canonical_digest

from ..api.contracts import MinecraftJsonValue


class MinecraftTaskKind(StrEnum):
    TECHTREE = "techtree"
    COOKING = "cooking"
    CONSTRUCTION = "construction"
    DEBUG = "debug"
    HUMAN_AI = "human_ai"


@dataclass(frozen=True, slots=True)
class MinecraftBlueprintCell:
    position: Mapping[str, float]
    expected: str

    def __post_init__(self) -> None:
        if set(self.position) != {"x", "y", "z"} or any(not isinstance(value, (int, float)) for value in self.position.values()):
            raise ValueError("blueprint cell position must contain numeric x/y/z")
        if not self.expected.strip():
            raise ValueError("blueprint cell expected block is required")


@dataclass(frozen=True, slots=True)
class MinecraftTaskSpec:
    """Typed, digestable version of a Minecraft benchmark task.

    This is an evaluation contract, not an execution command. World setup is
    owned by a fixture provider and must produce independent setup evidence.
    """

    task_id: str
    kind: MinecraftTaskKind
    goal: str
    agent_count: int
    timeout_s: int
    initial_inventory: Mapping[str, int] = field(default_factory=dict)
    target_item: str | None = None
    target_count: int | None = None
    max_depth: int | None = None
    blocked_actions: tuple[str, ...] = ()
    blueprint: tuple[MinecraftBlueprintCell, ...] = ()
    conversation: bool = False
    human_count: int = 0
    source_ref: str = ""

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.goal.strip():
            raise ValueError("Minecraft task identity and goal are required")
        if self.agent_count < 1 or self.agent_count > 5 or self.human_count < 0:
            raise ValueError("Minecraft task agent counts are out of range")
        if self.timeout_s < 1:
            raise ValueError("Minecraft task timeout must be positive")
        if self.target_count is not None and self.target_count < 1:
            raise ValueError("Minecraft task target_count must be positive")
        if self.max_depth is not None and self.max_depth < 0:
            raise ValueError("Minecraft task max_depth cannot be negative")
        inventory = self.initial_inventory or {}
        if any(not str(name).strip() or not isinstance(count, int) or count < 0 for name, count in inventory.items()):
            raise ValueError("Minecraft task initial inventory is invalid")
        if self.kind is MinecraftTaskKind.CONSTRUCTION and not self.blueprint:
            raise ValueError("construction task requires a blueprint")

    @property
    def digest(self) -> str:
        return canonical_digest({
            "task_id": self.task_id,
            "kind": self.kind.value,
            "goal": self.goal,
            "agent_count": self.agent_count,
            "human_count": self.human_count,
            "timeout_s": self.timeout_s,
            "initial_inventory": dict(sorted((self.initial_inventory or {}).items())),
            "target_item": self.target_item,
            "target_count": self.target_count,
            "max_depth": self.max_depth,
            "blocked_actions": self.blocked_actions,
            "blueprint": [{"position": dict(cell.position), "expected": cell.expected} for cell in self.blueprint],
            "conversation": self.conversation,
            "source_ref": self.source_ref,
        })

    def as_payload(self) -> dict[str, MinecraftJsonValue]:
        return {
            "task_id": self.task_id,
            "type": self.kind.value,
            "goal": self.goal,
            "agent_count": self.agent_count,
            "human_count": self.human_count,
            "timeout": self.timeout_s,
            "initial_inventory": dict(self.initial_inventory),
            "target": self.target_item,
            "number_of_target": self.target_count,
            "max_depth": self.max_depth,
            "blocked_actions": list(self.blocked_actions),
            "conversation": self.conversation,
            "source_ref": self.source_ref,
            "blueprint": [{"position": dict(cell.position), "block": cell.expected} for cell in self.blueprint],
            "task_digest": self.digest,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, MinecraftJsonValue]) -> "MinecraftTaskSpec":
        required = {"task_id", "type", "goal", "agent_count", "timeout"}
        missing = required - set(value)
        if missing:
            raise ValueError(f"Minecraft task is missing required fields: {sorted(missing)}")
        try:
            kind = MinecraftTaskKind(str(value["type"]))
        except ValueError as exc:
            raise ValueError(f"unsupported Minecraft task type: {value.get('type')}") from exc
        raw_inventory = value.get("initial_inventory", {})
        if not isinstance(raw_inventory, Mapping):
            raise ValueError("initial_inventory must be a mapping")
        raw_blueprint = value.get("blueprint", [])
        if not isinstance(raw_blueprint, list):
            raise ValueError("blueprint must be a list")
        cells: list[MinecraftBlueprintCell] = []
        for row in raw_blueprint:
            if not isinstance(row, Mapping) or not isinstance(row.get("position"), Mapping):
                raise ValueError("blueprint cell shape is invalid")
            position = row["position"]
            if set(position) != {"x", "y", "z"}:
                raise ValueError("blueprint cell position must contain exactly x/y/z")
            cells.append(MinecraftBlueprintCell({axis: float(position[axis]) for axis in ("x", "y", "z")}, str(row.get("block", row.get("expected", "")))))
        blocked = value.get("blocked_actions", [])
        if not isinstance(blocked, list) or any(not isinstance(item, str) or not item.strip() for item in blocked):
            raise ValueError("blocked_actions must be a list of non-empty strings")
        return cls(
            task_id=str(value["task_id"]), kind=kind, goal=str(value["goal"]),
            agent_count=int(value["agent_count"]), human_count=int(value.get("human_count", 0)),
            timeout_s=int(value["timeout"]), initial_inventory={str(name): int(count) for name, count in raw_inventory.items()},
            target_item=str(value["target"]) if value.get("target") is not None else None,
            target_count=int(value["number_of_target"]) if value.get("number_of_target") is not None else None,
            max_depth=int(value["max_depth"]) if value.get("max_depth") is not None else None,
            blocked_actions=tuple(blocked), blueprint=tuple(cells), conversation=bool(value.get("conversation", False)), source_ref=str(value.get("source_ref", "")),
        )


@dataclass(frozen=True, slots=True)
class MinecraftConstructionScore:
    expected: int
    matches: int
    mismatches: tuple[Mapping[str, MinecraftJsonValue], ...]

    @property
    def ratio(self) -> float:
        return self.matches / self.expected if self.expected else 1.0

    @property
    def complete(self) -> bool:
        return self.expected > 0 and not self.mismatches


def score_blueprint(task: MinecraftTaskSpec, observed: Mapping[str, str]) -> MinecraftConstructionScore:
    if task.kind is not MinecraftTaskKind.CONSTRUCTION:
        raise ValueError("blueprint scoring requires a construction task")
    mismatches: list[Mapping[str, MinecraftJsonValue]] = []
    matches = 0
    for cell in task.blueprint:
        key = ",".join(str(cell.position[axis]).rstrip("0").rstrip(".") for axis in ("x", "y", "z"))
        actual = observed.get(key, "air")
        if actual == cell.expected:
            matches += 1
        else:
            mismatches.append({"position": dict(cell.position), "expected": cell.expected, "actual": actual})
    return MinecraftConstructionScore(len(task.blueprint), matches, tuple(mismatches))


__all__ = ["MinecraftBlueprintCell", "MinecraftConstructionScore", "MinecraftTaskKind", "MinecraftTaskSpec", "score_blueprint"]
