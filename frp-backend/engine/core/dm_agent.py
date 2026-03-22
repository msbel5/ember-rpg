"""
Ember RPG - Core Engine
AI Dungeon Master Agent
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from engine.core.character import Character


class SceneType(Enum):
    """Game scene states."""
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    REST = "rest"
    TRANSITION = "transition"


class EventType(Enum):
    """DM event types."""
    ENCOUNTER = "encounter"
    DISCOVERY = "discovery"
    DIALOGUE = "dialogue"
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    REST = "rest"
    LEVEL_UP = "level_up"
    ITEM_FOUND = "item_found"


# Valid scene transitions: from -> set of allowed targets
VALID_TRANSITIONS: Dict[SceneType, set] = {
    SceneType.EXPLORATION: {
        SceneType.EXPLORATION,
        SceneType.COMBAT,
        SceneType.DIALOGUE,
        SceneType.REST,
        SceneType.TRANSITION,
    },
    SceneType.COMBAT: {
        SceneType.COMBAT,
        SceneType.EXPLORATION,
        SceneType.TRANSITION,
        SceneType.DIALOGUE,
    },
    SceneType.DIALOGUE: {
        SceneType.DIALOGUE,
        SceneType.EXPLORATION,
        SceneType.COMBAT,
    },
    SceneType.REST: {
        SceneType.REST,
        SceneType.EXPLORATION,
    },
    SceneType.TRANSITION: {
        SceneType.TRANSITION,
        SceneType.EXPLORATION,
        SceneType.COMBAT,
        SceneType.DIALOGUE,
        SceneType.REST,
    },
}

# Fallback narrative templates per event type (Turkish)
NARRATIVE_TEMPLATES = {
    EventType.ENCOUNTER: "{description}",
    EventType.DISCOVERY: "{description}",
    EventType.DIALOGUE: "{description}",
    EventType.COMBAT_START: "Silahlar çekildi! {description}",
    EventType.COMBAT_END: "Çeliğin çarpışması yatışıyor. {description}",
    EventType.REST: "{description}",
    EventType.LEVEL_UP: "İçinizde güçlü bir his kabarıyor. {description}",
    EventType.ITEM_FOUND: "Gözünüze bir şey çarpıyor — {description}",
}


@dataclass
class DMEvent:
    """
    A game event for the DM to narrate.

    Attributes:
        type: Event category
        description: Raw description of what happened
        data: Optional structured data (e.g. combat results)
    """
    type: EventType
    description: str
    data: dict = field(default_factory=dict)


@dataclass
class DMContext:
    """
    Current game state seen by the DM Agent.

    Attributes:
        scene_type: Current scene state
        location: Location name/description
        party: List of player characters
        history: Recent event history
        turn: Global turn counter
        max_history: Max events to keep in history
    """
    scene_type: SceneType
    location: str
    party: List['Character']
    history: List[DMEvent] = field(default_factory=list)
    turn: int = 0
    max_history: int = 10

    def add_event(self, event: DMEvent):
        """
        Add an event to history, trimming to max_history.

        Args:
            event: DMEvent to record
        """
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def advance_turn(self):
        """Increment the global turn counter."""
        self.turn += 1

    def party_summary(self) -> str:
        """
        Generate a compact party status summary.

        Returns:
            Multi-line string with name, HP, level per character
        """
        lines = []
        for char in self.party:
            lines.append(
                f"{char.name} (L{char.level} {char.dominant_class or 'adventurer'}) "
                f"HP:{char.hp}/{char.max_hp}"
            )
        return "\n".join(lines)


class DMAIAgent:
    """
    AI Dungeon Master Agent.

    Builds prompts for LLM backends and generates narrative text.
    Can operate with or without an LLM (fallback templates when no LLM provided).

    Usage:
        agent = DMAIAgent()
        event = DMEvent(type=EventType.ENCOUNTER, description="A troll blocks the path.")
        narrative = agent.narrate(event, context, llm=my_llm_fn)
    """

    def transition(self, context: DMContext, new_scene: SceneType) -> bool:
        """
        Transition the scene to a new state.

        Args:
            context: Current DMContext (mutated on success)
            new_scene: Target scene state

        Returns:
            True on success

        Raises:
            ValueError: If transition is not valid from current state
        """
        allowed = VALID_TRANSITIONS.get(context.scene_type, set())
        if new_scene not in allowed:
            raise ValueError(
                f"Invalid transition: {context.scene_type.value} → {new_scene.value}"
            )
        context.scene_type = new_scene
        return True

    def build_prompt(self, event: DMEvent, context: DMContext) -> str:
        """
        Build a structured LLM prompt for a given event and context.

        Args:
            event: The event to narrate
            context: Current game context

        Returns:
            Prompt string ready for an LLM backend
        """
        history_lines = ""
        if context.history:
            recent = context.history[-5:]  # Last 5 events
            history_lines = "\n".join(
                f"- [{e.type.value}] {e.description}" for e in recent
            )

        prompt = (
            f"You are the Dungeon Master of Ember RPG, a dark fantasy world.\n\n"
            f"## Current Scene\n"
            f"Location: {context.location}\n"
            f"Scene: {context.scene_type.value}\n"
            f"Turn: {context.turn}\n\n"
            f"## Party\n"
            f"{context.party_summary()}\n\n"
            f"## Recent History\n"
            f"{history_lines if history_lines else '(no recent events)'}\n\n"
            f"## Event\n"
            f"Type: {event.type.value}\n"
            f"Description: {event.description}\n"
            f"Data: {event.data}\n\n"
            f"## Task\n"
            f"Narrate this event in 2-3 sentences. "
            f"Keep the tone dark, immersive, and concise. "
            f"Do not repeat party member names unnecessarily."
        )
        return prompt

    def narrate(
        self,
        event: DMEvent,
        context: DMContext,
        llm: Optional[Callable[[str], str]] = None,
    ) -> str:
        """
        Generate narrative text for an event.

        Args:
            event: Event to narrate
            context: Current game context
            llm: Optional callable(prompt) -> str for LLM backend

        Returns:
            Narrative string
        """
        # Record event in history
        context.add_event(event)

        if llm is not None:
            prompt = self.build_prompt(event, context)
            return llm(prompt)

        # Fallback: template-based narrative
        template = NARRATIVE_TEMPLATES.get(
            event.type,
            "{description}"
        )
        return template.format(description=event.description)
