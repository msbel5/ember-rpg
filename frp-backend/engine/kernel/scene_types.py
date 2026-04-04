"""
Kernel scene-state types for campaign-first runtime.

This module defines the neutral scene context used by campaign runtime and
save/load code. It intentionally does not provide narrator/freeform services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.kernel.actor import Actor


class SceneType(Enum):
    """Game scene states."""
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    REST = "rest"
    TRANSITION = "transition"


class EventType(Enum):
    """Narrator event types."""
    ENCOUNTER = "encounter"
    DISCOVERY = "discovery"
    DIALOGUE = "dialogue"
    COMBAT = "combat"
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    COMBAT_END_VICTORY = "combat_end_victory"
    COMBAT_END_DEFEAT = "combat_end_defeat"
    REST = "rest"
    LEVEL_UP = "level_up"
    ITEM_FOUND = "item_found"
    NPC_ENCOUNTER = "npc_encounter"
    QUEST_START = "quest_start"
    QUEST_COMPLETE = "quest_complete"
    DUNGEON_ENTRANCE = "dungeon_entrance"
    EXPLORATION = "exploration"


# Valid scene transitions: source -> allowed targets
VALID_TRANSITIONS: Dict[SceneType, set] = {
    SceneType.EXPLORATION: {
        SceneType.EXPLORATION, SceneType.COMBAT,
        SceneType.DIALOGUE, SceneType.REST, SceneType.TRANSITION,
    },
    SceneType.COMBAT: {
        SceneType.COMBAT, SceneType.EXPLORATION,
        SceneType.TRANSITION, SceneType.DIALOGUE,
    },
    SceneType.DIALOGUE: {
        SceneType.DIALOGUE, SceneType.EXPLORATION,
        SceneType.COMBAT, SceneType.REST,
    },
    SceneType.REST: {
        SceneType.REST, SceneType.EXPLORATION,
    },
    SceneType.TRANSITION: {
        SceneType.TRANSITION, SceneType.EXPLORATION,
        SceneType.COMBAT, SceneType.DIALOGUE, SceneType.REST,
    },
}


@dataclass
class SceneEvent:
    """A single scene event record."""
    type: EventType
    description: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "description": self.description,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SceneEvent":
        return cls(
            type=EventType(d["type"]),
            description=d["description"],
            data=d.get("data", {}),
        )

@dataclass
class SceneContext:
    """Snapshot of active scene state used by campaign runtime."""
    scene_type: SceneType
    location: str
    party: List["Actor"] = field(default_factory=list)
    history: List[SceneEvent] = field(default_factory=list)
    turn: int = 0
    max_history: int = 10

    @property
    def scene_type_name(self) -> str:
        return self.scene_type.value

    @scene_type_name.setter
    def scene_type_name(self, value: str) -> None:
        self.scene_type = SceneType(str(value))

    def add_event(self, event: SceneEvent) -> None:
        """Append event and trim history to max_history."""
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def advance_turn(self) -> None:
        """Increment the global turn counter."""
        self.turn += 1

    def party_summary(self) -> str:
        """Compact multi-line party status string."""
        lines = []
        for actor in self.party:
            cls_label = getattr(actor, "dominant_class", None) or "adventurer"
            name = getattr(actor, "name", "???")
            level = getattr(actor, "level", 1)
            hp = getattr(actor, "hp", 0)
            max_hp = getattr(actor, "max_hp", 0)
            lines.append(f"{name} (L{level} {cls_label}) HP:{hp}/{max_hp}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize context for save/load (party excluded)."""
        return {
            "scene_type": self.scene_type.value,
            "location": self.location,
            "turn": self.turn,
            "max_history": self.max_history,
            "history": [e.to_dict() for e in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict, party: list | None = None) -> "SceneContext":
        """Deserialize from a dict. Pass party separately (not serialized)."""
        history = [SceneEvent.from_dict(h) for h in data.get("history", [])]
        return cls(
            scene_type=SceneType(data["scene_type"]),
            location=data["location"],
            party=party or [],
            history=history,
            turn=data.get("turn", 0),
            max_history=data.get("max_history", 10),
        )


__all__ = [
    "EventType",
    "SceneContext",
    "SceneEvent",
    "SceneType",
    "VALID_TRANSITIONS",
]
