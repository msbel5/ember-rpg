"""
Ember RPG - Core Engine
AI Dungeon Master Agent
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, TYPE_CHECKING
from enum import Enum
import random

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

# Rich narrative templates per event type (English)
# Each event type has 5+ templates with {placeholders} for dynamic content.
NARRATIVE_TEMPLATES: dict = {
    EventType.ENCOUNTER: ["{description}"],
    EventType.DISCOVERY: ["{description}"],
    EventType.DIALOGUE: ["{description}"],
    EventType.REST: ["{description}"],

    EventType.COMBAT_START: [
        "Steel sings through the air as {enemy_name} lunges forward — there's no time to think, only to fight!",
        "A guttural war cry shatters the silence. {enemy_name} charges at {player_name} with murderous intent.",
        "Shadows shift and {enemy_name} erupts from the darkness. Weapons are drawn — blood will be spilled today.",
        "The air crackles with tension. {enemy_name} bares its fangs and the battle is joined in {location}.",
        "Without warning, {enemy_name} attacks! {player_name} barely has time to raise a defense.",
        "The clash of iron echoes across {location} as {enemy_name} makes the first move. There is no retreat.",
        "Eyes locked, blades gleaming — {enemy_name} takes the offensive and combat erupts like a sudden storm.",
    ],

    EventType.COMBAT_END: [
        "The clash of steel fades. {description}",
        "Dust settles over the battlefield. {description}",
    ],

    EventType.COMBAT_END_VICTORY: [
        "{player_name} stands victorious over the fallen {enemy_name}. The silence that follows tastes of hard-won glory.",
        "The last enemy drops with a final shudder. {player_name} catches their breath — the battle is won.",
        "{enemy_name} crumbles at {player_name}'s feet. Another threat ended, another step deeper into legend.",
        "With a decisive blow, {player_name} finishes it. The air still hums with fading violence and hard-earned triumph.",
        "Victory! {player_name} surveys the carnage and sheathes their weapon. {xp_gained} experience, bought in steel and sweat.",
        "The fight is over. {enemy_name} will trouble this land no more — {player_name} made sure of that.",
        "Panting, bleeding, but alive — {player_name} has prevailed. The echo of combat fades into the wind.",
    ],

    EventType.COMBAT_END_DEFEAT: [
        "{player_name} collapses under the relentless assault of {enemy_name}. Darkness closes in...",
        "The ground rushes up to meet {player_name}. Through blurred vision, {enemy_name} looms overhead, victorious.",
        "Overwhelmed and outmatched, {player_name} is forced to flee {location} with nothing but their life.",
        "Wounds mount faster than they can be endured. {player_name} retreats into the shadows, defeated but breathing.",
        "{enemy_name} proves too formidable. {player_name} barely escapes with their life — today belongs to the enemy.",
        "The battle is lost. {player_name} stumbles away from {location}, battered and humbled by {enemy_name}.",
    ],

    EventType.EXPLORATION: [
        "The {location} stretches out before {player_name} — moss-covered stones and flickering torchlight paint an eerie tableau.",
        "Silence reigns in {location}. Every creak and drip seems amplified, the darkness keeping its secrets close.",
        "{player_name} moves cautiously through {location}. The air smells of old stone, rust, and something else — danger, perhaps.",
        "The {location} is vast and unsettling. Strange symbols mark the walls; someone — or something — has been here.",
        "Filtered light barely touches the corners of {location}. Dust motes dance in the beam, undisturbed for years.",
        "The path through {location} twists unexpectedly. Somewhere ahead, water drips with metronomic patience.",
        "Ancient and oppressive, {location} holds its breath as {player_name} steps deeper inside.",
    ],

    EventType.NPC_ENCOUNTER: [
        "A figure emerges from the shadows — {npc_name} regards {player_name} with unreadable eyes.",
        "{npc_name} looks up from their work, sizing {player_name} up before offering a cautious nod of acknowledgment.",
        "The sound of footsteps announces {npc_name}. 'I don't see many travelers in these parts,' they say.",
        "{npc_name} leans against the wall, arms folded. 'You're either brave or foolish to be here,' they murmur.",
        "From across the room, {npc_name} calls out — their tone could mean business or trouble, it's hard to tell.",
        "{npc_name} pauses, studying {player_name} with the practiced wariness of someone who has survived by trusting no one.",
    ],

    EventType.ITEM_FOUND: [
        "Something catches {player_name}'s eye — half-hidden in the shadows lies {item_name}.",
        "{player_name} reaches into the crevice and finds {item_name}, dusty but intact.",
        "Among the debris, a glimmer: {item_name}, waiting patiently as if placed here just for this moment.",
        "Fortune smiles — {player_name} discovers {item_name} tucked behind a loose stone.",
        "The search pays off: {item_name} rests in the rubble, surprisingly undamaged.",
        "{item_name} rolls free as {player_name} kicks aside the dust. A lucky find.",
    ],

    EventType.LEVEL_UP: [
        "A surge of power courses through {player_name} — they have reached level {level}! Muscles remember, instincts sharpen.",
        "Something shifts deep within {player_name}. Hard-won experience crystallizes into mastery — level {level} achieved!",
        "{player_name} closes their eyes and feels the change — {xp_gained} experience has forged new capability.",
        "The trials endured have not been in vain. {player_name} rises to level {level}, stronger and wiser.",
        "Growth is often invisible until it isn't. {player_name} reaches level {level} — the road ahead is clearer now.",
        "Level {level}! {player_name}'s body and mind have evolved through battle-tested experience.",
    ],

    EventType.QUEST_START: [
        "The weight of a new purpose settles on {player_name}'s shoulders. The quest begins in earnest.",
        "A mission unlike any before: {player_name} accepts the charge and sets out with grim determination.",
        "The task sounds simple enough. Experience has taught {player_name} that nothing ever is.",
        "With a nod of understanding, {player_name} commits. The path ahead is uncertain — but so is the reward.",
        "The quest is accepted. {player_name} reviews the details once more, eyes already scanning the horizon.",
        "Some quests find the hero. {player_name} suspects this is one of those — and steps forward anyway.",
    ],

    EventType.QUEST_COMPLETE: [
        "The task is done. {player_name} exhales slowly, savoring the rare satisfaction of a promise kept.",
        "Against all odds, {player_name} has succeeded. The quest is complete — and the world is slightly better for it.",
        "The final piece falls into place. {player_name} allows themselves a moment of quiet pride.",
        "Completion. {player_name} marks it as won — not by luck, but by persistence and will.",
        "The quest is finished. {player_name} returns with proof of victory, already thinking about the next challenge.",
        "Hard work, danger, sacrifice — and now, the sweet resolution of a completed mission. Well done, {player_name}.",
    ],

    EventType.DUNGEON_ENTRANCE: [
        "The dungeon mouth yawns before {player_name} — cold air breathes out from the dark like a sleeping beast.",
        "Carved stone frames a descent into absolute darkness. {player_name} checks their gear and steps inside.",
        "The entrance to {location} reeks of old death and older secrets. This is not a place that welcomes visitors.",
        "Torchlight flickers at the threshold of {location}. Whatever lies within has swallowed many who came before.",
        "A chill runs down {player_name}'s spine as they cross into {location}. The door — if there was one — is far behind now.",
        "The dungeon doesn't threaten. It simply waits, patient and vast, as {player_name} descends into its depths.",
        "Stone walls press close in {location}'s entrance corridor. The air is stale; the silence, absolute.",
    ],

    EventType.LEVEL_UP: [
        "A surge of power courses through {player_name} — they have reached level {level}! Muscles remember, instincts sharpen.",
        "Something shifts deep within {player_name}. Hard-won experience crystallizes into mastery — level {level} achieved!",
        "{player_name} closes their eyes and feels the change — {xp_gained} experience has forged new capability.",
        "The trials endured have not been in vain. {player_name} rises to level {level}, stronger and wiser.",
        "Growth is often invisible until it isn't. {player_name} reaches level {level} — the road ahead is clearer now.",
        "Level {level}! {player_name}'s body and mind have evolved through battle-tested experience.",
    ],
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

        # Fallback: template-based narrative with random selection
        templates = NARRATIVE_TEMPLATES.get(event.type)
        if templates:
            template = random.choice(templates)
        else:
            template = "{description}"

        # Build a safe format dict from event data + description
        fmt = {
            "description": event.description,
            "player_name": event.data.get("player_name", "the adventurer"),
            "enemy_name": event.data.get("enemy_name", "the enemy"),
            "npc_name": event.data.get("npc_name", "the stranger"),
            "location": context.location,
            "item_name": event.data.get("item_name", "a mysterious item"),
            "level": event.data.get("level", "?"),
            "xp_gained": event.data.get("xp_gained", ""),
            **event.data,
        }
        try:
            return template.format(**fmt)
        except (KeyError, ValueError):
            return event.description
