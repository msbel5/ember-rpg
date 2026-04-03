"""
Ember RPG - Kernel Narrator Module
Kernel-native replacement for engine.core.dm_agent.
Exports same SceneType/EventType enums, NarratorEvent, NarratorContext
dataclasses, and a simplified NarratorService for LLM calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

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
class NarratorEvent:
    """A single narrated game event."""
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
    def from_dict(cls, d: dict) -> "NarratorEvent":
        return cls(
            type=EventType(d["type"]),
            description=d["description"],
            data=d.get("data", {}),
        )


# Legacy alias for NarratorEvent.
DMEvent = NarratorEvent


@dataclass
class NarratorContext:
    """Snapshot of game state visible to the narrator."""
    scene_type: SceneType
    location: str
    party: List["Actor"] = field(default_factory=list)
    history: List[NarratorEvent] = field(default_factory=list)
    turn: int = 0
    max_history: int = 10

    def add_event(self, event: NarratorEvent) -> None:
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
    def from_dict(cls, data: dict, party: list | None = None) -> "NarratorContext":
        """Deserialize from a dict. Pass party separately (not serialized)."""
        history = [NarratorEvent.from_dict(h) for h in data.get("history", [])]
        return cls(
            scene_type=SceneType(data["scene_type"]),
            location=data["location"],
            party=party or [],
            history=history,
            turn=data.get("turn", 0),
            max_history=data.get("max_history", 10),
        )


# Legacy alias for NarratorContext.
DMContext = NarratorContext


class NarratorService:
    """Kernel-native narrator that wraps LLM calls."""

    def transition(self, ctx: NarratorContext, target: SceneType) -> bool:
        """Transition ctx to target scene. Raises ValueError if invalid."""
        allowed = VALID_TRANSITIONS.get(ctx.scene_type, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {ctx.scene_type.value} -> {target.value}"
            )
        ctx.scene_type = target
        return True

    def build_prompt(self, event: NarratorEvent, ctx: NarratorContext) -> str:
        """Build a structured LLM prompt from event + context."""
        history_block = ""
        if ctx.history:
            recent = ctx.history[-5:]
            history_block = "\n".join(
                f"- [{e.type.value}] {e.description}" for e in recent
            )
        return (
            "You are the Dungeon Master of Ember RPG, a dark fantasy world.\n\n"
            f"## Current Scene\n"
            f"Location: {ctx.location}\n"
            f"Scene: {ctx.scene_type.value}\n"
            f"Turn: {ctx.turn}\n\n"
            f"## Party\n{ctx.party_summary()}\n\n"
            f"## Recent History\n"
            f"{history_block or '(no recent events)'}\n\n"
            f"## Event\n"
            f"Type: {event.type.value}\n"
            f"Description: {event.description}\n\n"
            f"## Task\n"
            "Narrate this event in 2-3 sentences. "
            "Keep the tone dark, immersive, and concise."
        )

    def narrate(
        self,
        event: NarratorEvent,
        ctx: NarratorContext,
        llm: Optional[Callable[[str], str]] = None,
    ) -> str:
        """Generate narrative for event. Uses LLM if provided, else raw description."""
        ctx.add_event(event)
        if llm is not None:
            prompt = self.build_prompt(event, ctx)
            result = llm(prompt)
            if result is not None:
                return result
        # Fallback: return the event description directly.
        return event.description

# Legacy alias for DMAIAgent.
DMAIAgent = NarratorService
