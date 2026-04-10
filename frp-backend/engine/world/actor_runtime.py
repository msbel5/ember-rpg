"""Canonical actor runtime data model for ambient-life and visual-tick subsystems."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.world.behavior_tree import BehaviorContext, BehaviorNode, Status

SCR_OVERRIDE = 0
SCR_AREA = 1
SCR_SPECIFICS = 2
SCR_RESERVED = 3
SCR_CLASS = 4
SCR_RACE = 5
SCR_GENERAL = 6
SCR_DEFAULT = 7
MAX_SCRIPTS = 8

IF_JUSTDIED = 0x2
IF_FROMGAME = 0x4
IF_REALLYDIED = 0x8
IF_NORETICLE = 0x10
IF_NOINT = 0x20
IF_CLEANUP = 0x40
IF_RUNNING = 0x80
IF_INITIALIZED = 0x200
IF_USEEXIT = 0x1000
IF_ACTIVE = 0x10000
IF_VISIBLE = 0x40000
IF_IDLE = 0x100000
IF_FORCEUPDATE = 0x400000

_VALID_FACINGS = {"north", "east", "south", "west", "ne", "nw", "se", "sw"}


@dataclass
class ActorStats:
    str_val: int = 10
    dex_val: int = 10
    con_val: int = 10
    int_val: int = 10
    wis_val: int = 10
    cha_val: int = 10
    hp: int = 1
    max_hp: int = 1
    ac: int = 10
    thac0: int = 20
    level: int = 1
    xp: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "str_val": self.str_val,
            "dex_val": self.dex_val,
            "con_val": self.con_val,
            "int_val": self.int_val,
            "wis_val": self.wis_val,
            "cha_val": self.cha_val,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
            "thac0": self.thac0,
            "level": self.level,
            "xp": self.xp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorStats":
        return cls(**{key: int(value) for key, value in data.items() if key in cls.__dataclass_fields__})


@dataclass
class CombatInfo:
    in_combat: bool = False
    initiative: int = 0
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    movement_remaining: int = 6

    def to_dict(self) -> dict[str, Any]:
        return {
            "in_combat": self.in_combat,
            "initiative": self.initiative,
            "action_available": self.action_available,
            "bonus_action_available": self.bonus_action_available,
            "reaction_available": self.reaction_available,
            "movement_remaining": self.movement_remaining,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatInfo":
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})


@dataclass
class ActorAnimationState:
    current_state: str = "stand"
    facing: str = "south"
    frame_cursor: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_state": self.current_state,
            "facing": self.facing,
            "frame_cursor": self.frame_cursor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorAnimationState":
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})


@dataclass
class TriggerEvent:
    event_type: str
    source_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source_id": self.source_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerEvent":
        return cls(
            event_type=str(data.get("event_type", "")),
            source_id=str(data.get("source_id", "")),
            payload=dict(data.get("payload") or {}),
        )


@dataclass
class Actor:
    id: str
    kind: str = "npc"
    position: tuple[int, int] = (0, 0)
    facing: str = "south"
    state_flags: int = IF_ACTIVE | IF_VISIBLE
    script_slots: list[Optional[BehaviorNode]] = field(default_factory=lambda: [None] * MAX_SCRIPTS)
    stats_ref: ActorStats = field(default_factory=ActorStats)
    combat_info: CombatInfo = field(default_factory=CombatInfo)
    animation_state: ActorAnimationState = field(default_factory=ActorAnimationState)
    current_path: list[tuple[int, int]] = field(default_factory=list)
    trigger_queue: list[TriggerEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.position = self._coerce_position(self.position)
        self.facing = self._normalize_facing(self.facing)
        self.animation_state.facing = self._normalize_facing(self.animation_state.facing)
        if len(self.script_slots) != MAX_SCRIPTS:
            normalized = list(self.script_slots[:MAX_SCRIPTS])
            normalized.extend([None] * (MAX_SCRIPTS - len(normalized)))
            self.script_slots = normalized
        self.current_path = [self._coerce_position(step) for step in self.current_path]
        self.trigger_queue = [
            item if isinstance(item, TriggerEvent) else TriggerEvent.from_dict(dict(item))
            for item in self.trigger_queue
        ]

    def is_active(self) -> bool:
        return self.has_flag(IF_ACTIVE)

    def is_visible(self) -> bool:
        return self.has_flag(IF_VISIBLE)

    def is_idle(self) -> bool:
        return self.has_flag(IF_IDLE)

    def is_dead(self) -> bool:
        return self.get_hp() <= 0 or self.has_flag(IF_REALLYDIED)

    def is_running(self) -> bool:
        return self.has_flag(IF_RUNNING)

    def is_in_combat(self) -> bool:
        return bool(self.combat_info.in_combat)

    def set_flag(self, flag: int) -> None:
        self.state_flags |= flag

    def clear_flag(self, flag: int) -> None:
        self.state_flags &= ~flag

    def toggle_flag(self, flag: int) -> None:
        self.state_flags ^= flag

    def has_flag(self, flag: int) -> bool:
        return (self.state_flags & flag) == flag

    def get_position(self) -> tuple[int, int]:
        return self.position

    def set_position(self, pos: tuple[int, int]) -> None:
        self.position = self._coerce_position(pos)

    def get_facing(self) -> str:
        return self.facing

    def set_facing(self, facing: str) -> None:
        normalized = self._normalize_facing(facing)
        self.facing = normalized
        self.animation_state.facing = normalized

    def get_stat(self, stat_id: str) -> int:
        if not hasattr(self.stats_ref, stat_id):
            raise KeyError(stat_id)
        return int(getattr(self.stats_ref, stat_id))

    def set_stat(self, stat_id: str, value: int) -> None:
        if not hasattr(self.stats_ref, stat_id):
            raise KeyError(stat_id)
        setattr(self.stats_ref, stat_id, int(value))

    def modify_stat(self, stat_id: str, delta: int) -> int:
        value = self.get_stat(stat_id) + int(delta)
        self.set_stat(stat_id, value)
        return self.get_stat(stat_id)

    def attach_script(self, slot: int, tree: BehaviorNode) -> None:
        self._validate_slot(slot)
        self.script_slots[slot] = tree

    def detach_script(self, slot: int) -> None:
        self._validate_slot(slot)
        self.script_slots[slot] = None

    def get_script(self, slot: int) -> Optional[BehaviorNode]:
        self._validate_slot(slot)
        return self.script_slots[slot]

    def apply_damage(self, amount: int, source_id: str = "") -> int:
        actual = min(max(int(amount), 0), self.get_hp())
        self.stats_ref.hp = max(0, self.stats_ref.hp - actual)
        if actual > 0 and source_id:
            self.trigger_queue.append(TriggerEvent(event_type="damage", source_id=source_id, payload={"amount": actual}))
        if self.stats_ref.hp <= 0:
            self.stats_ref.hp = 0
            self.set_flag(IF_JUSTDIED)
            self.clear_flag(IF_IDLE)
        return actual

    def apply_heal(self, amount: int) -> int:
        actual = min(max(int(amount), 0), max(0, self.get_max_hp() - self.get_hp()))
        self.stats_ref.hp += actual
        return actual

    def get_hp(self) -> int:
        return int(self.stats_ref.hp)

    def get_max_hp(self) -> int:
        return int(self.stats_ref.max_hp)

    def tick(self, context: BehaviorContext) -> Status:
        if hasattr(context, "entity"):
            context.entity = self
        if not hasattr(context, "blackboard") or context.blackboard is None:
            context.blackboard = {}

        if self.has_flag(IF_JUSTDIED):
            self.clear_flag(IF_JUSTDIED)
            self.set_flag(IF_REALLYDIED)
            self.clear_flag(IF_ACTIVE)
            self.clear_flag(IF_RUNNING)
            self.clear_flag(IF_IDLE)
            return Status.SUCCESS

        self.clear_flag(IF_IDLE)
        for slot in range(MAX_SCRIPTS):
            tree = self.script_slots[slot]
            if tree is None:
                continue
            result = tree.tick(context)
            if result == Status.RUNNING:
                self.set_flag(IF_RUNNING)
                return result
            if result == Status.SUCCESS:
                self.clear_flag(IF_RUNNING)
                return result
        self.clear_flag(IF_RUNNING)
        self.set_flag(IF_IDLE)
        return Status.FAILURE

    def query_state(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "position": list(self.position),
            "facing": self.facing,
            "hp": self.get_hp(),
            "max_hp": self.get_max_hp(),
            "flags": self.state_flags,
            "active": self.is_active(),
            "visible": self.is_visible(),
            "idle": self.is_idle(),
            "dead": self.is_dead(),
            "running": self.is_running(),
            "in_combat": self.is_in_combat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "position": list(self.position),
            "facing": self.facing,
            "state_flags": self.state_flags,
            "script_slot_names": [slot.__class__.__name__ if slot is not None else None for slot in self.script_slots],
            "stats_ref": self.stats_ref.to_dict(),
            "combat_info": self.combat_info.to_dict(),
            "animation_state": self.animation_state.to_dict(),
            "current_path": [list(step) for step in self.current_path],
            "trigger_queue": [item.to_dict() for item in self.trigger_queue],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Actor":
        return cls(
            id=str(data["id"]),
            kind=str(data.get("kind", "npc")),
            position=tuple(data.get("position", (0, 0))),
            facing=str(data.get("facing", "south")),
            state_flags=int(data.get("state_flags", IF_ACTIVE | IF_VISIBLE)),
            stats_ref=ActorStats.from_dict(dict(data.get("stats_ref") or {})),
            combat_info=CombatInfo.from_dict(dict(data.get("combat_info") or {})),
            animation_state=ActorAnimationState.from_dict(dict(data.get("animation_state") or {})),
            current_path=[tuple(step) for step in data.get("current_path", [])],
            trigger_queue=[TriggerEvent.from_dict(dict(item)) for item in data.get("trigger_queue", [])],
        )

    @staticmethod
    def _coerce_position(pos: tuple[int, int] | list[int] | tuple[Any, ...]) -> tuple[int, int]:
        if len(pos) < 2:
            raise ValueError("position must contain at least two coordinates")
        return (int(pos[0]), int(pos[1]))

    @staticmethod
    def _normalize_facing(facing: str) -> str:
        normalized = str(facing or "south").strip().lower()
        if normalized not in _VALID_FACINGS:
            raise ValueError(f"unsupported facing: {facing}")
        return normalized

    @staticmethod
    def _validate_slot(slot: int) -> None:
        if slot < 0 or slot >= MAX_SCRIPTS:
            raise IndexError(f"script slot out of range: {slot}")


__all__ = [
    "Actor",
    "ActorAnimationState",
    "ActorStats",
    "CombatInfo",
    "TriggerEvent",
    "MAX_SCRIPTS",
    "SCR_OVERRIDE",
    "SCR_AREA",
    "SCR_SPECIFICS",
    "SCR_RESERVED",
    "SCR_CLASS",
    "SCR_RACE",
    "SCR_GENERAL",
    "SCR_DEFAULT",
    "IF_JUSTDIED",
    "IF_FROMGAME",
    "IF_REALLYDIED",
    "IF_NORETICLE",
    "IF_NOINT",
    "IF_CLEANUP",
    "IF_RUNNING",
    "IF_INITIALIZED",
    "IF_USEEXIT",
    "IF_ACTIVE",
    "IF_VISIBLE",
    "IF_IDLE",
    "IF_FORCEUPDATE",
]
