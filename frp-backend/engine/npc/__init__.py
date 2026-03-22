"""
Ember RPG - Phase 5: NPC Agent System
NPC personality, dialogue, memory, and DM-driven conversation.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from enum import Enum
import random


class Disposition(Enum):
    """How an NPC feels toward the player."""
    HOSTILE = "hostile"
    UNFRIENDLY = "unfriendly"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    ALLIED = "allied"


class NPCRole(Enum):
    """NPC archetype/role in the world."""
    MERCHANT = "merchant"
    GUARD = "guard"
    INNKEEPER = "innkeeper"
    QUEST_GIVER = "quest_giver"
    VILLAIN = "villain"
    ALLY = "ally"
    COMMONER = "commoner"
    MONSTER = "monster"


@dataclass
class NPCMemory:
    """
    What an NPC remembers about the player and events.

    Attributes:
        player_name: Remembered player name (if known)
        events: List of notable interactions (max 10)
        reputation: Numeric reputation with this NPC (-100 to 100)
        has_met_player: Whether NPC has spoken to player before
    """
    player_name: Optional[str] = None
    events: List[str] = field(default_factory=list)
    reputation: int = 0
    has_met_player: bool = False
    MAX_EVENTS = 10

    def add_event(self, event: str) -> None:
        """Add an event; trim to MAX_EVENTS."""
        self.events.append(event)
        if len(self.events) > self.MAX_EVENTS:
            self.events = self.events[-self.MAX_EVENTS:]

    def adjust_reputation(self, delta: int) -> None:
        """Adjust reputation, clamped to [-100, 100]."""
        self.reputation = max(-100, min(100, self.reputation + delta))


@dataclass
class DialogueLine:
    """
    A single dialogue option or NPC response.

    Attributes:
        text: What the NPC says
        condition: Optional callable(npc, player_input) -> bool
        reputation_effect: Reputation change when this line is triggered
        leads_to: Key of next dialogue node (None = end conversation)
    """
    text: str
    condition: Optional[Callable] = None
    reputation_effect: int = 0
    leads_to: Optional[str] = None


@dataclass
class DialogueNode:
    """A dialogue tree node with NPC line and player options."""
    npc_line: str
    options: List[str] = field(default_factory=list)
    next_nodes: Dict[int, str] = field(default_factory=dict)


@dataclass
class NPC:
    """
    A non-player character with personality and dialogue.

    Attributes:
        name: NPC name
        role: NPC archetype
        disposition: Current attitude toward player
        personality: Short personality description (used in prompts)
        location: Current location name
        memory: NPC's memory of player interactions
        dialogue_tree: Keyed dialogue nodes
        inventory: Items for trade/quest
        quest: Optional quest this NPC offers
    """
    name: str
    role: NPCRole = NPCRole.COMMONER
    disposition: Disposition = Disposition.NEUTRAL
    personality: str = "A quiet, reserved person of few words."
    location: str = "Unknown"
    memory: NPCMemory = field(default_factory=NPCMemory)
    dialogue_tree: Dict[str, DialogueNode] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)
    quest: Optional[str] = None

    def greet(self) -> str:
        """Return disposition-appropriate greeting."""
        greetings = {
            Disposition.HOSTILE:    f"{self.name} eyes you with contempt. 'What do you want?'",
            Disposition.UNFRIENDLY: f"{self.name} gives you a cold look. 'Yes?'",
            Disposition.NEUTRAL:    f"{self.name} meets your gaze. 'How can I help you?'",
            Disposition.FRIENDLY:   f"{self.name} smiles warmly. 'Welcome, traveler!'",
            Disposition.ALLIED:     f"{self.name} greets you with delight. 'My friend! Good to see you!'",
        }
        return greetings[self.disposition]

    def react_to_player(self, player_input: str) -> str:
        """
        Generate a contextual reaction to player input.
        Uses keyword matching + disposition for template-based response.
        """
        lower = player_input.lower()

        if self.disposition == Disposition.HOSTILE:
            return f"{self.name} growls. 'I have nothing to say to you.'"

        if any(w in lower for w in ["buy", "trade", "sell", "purchase", "satın", "al", "sat"]):
            if self.inventory:
                items = ", ".join(self.inventory[:3])
                return f"{self.name}: 'I have these available: {items}.'"
            return f"{self.name}: 'Sorry, I have nothing to sell right now.'"

        if any(w in lower for w in ["quest", "job", "task", "help", "görev", "iş", "yardım"]):
            if self.quest:
                return f"{self.name}: '{self.quest}'"
            return f"{self.name}: 'I have no work for you at the moment.'"

        if any(w in lower for w in ["where", "who", "what", "how", "nerede", "kim", "ne", "nasıl"]):
            return f"{self.name} thinks for a moment... 'I don't know much about that, but perhaps someone else can help.'"

        if self.memory.reputation > 50:
            return f"{self.name} says warmly, 'I'm always here for you, friend.'"
        if self.memory.reputation < -30:
            return f"{self.name} says warily, 'Careful now. I don't fully trust you.'"

        return f"{self.name}: '{self._personality_line()}'"

    def _personality_line(self) -> str:
        lines_by_role = {
            NPCRole.MERCHANT:    "Best prices in town — you have my word.",
            NPCRole.GUARD:       "This area is under watch. Don't cause trouble.",
            NPCRole.INNKEEPER:   "You look weary. Shall I prepare a room?",
            NPCRole.QUEST_GIVER: "Actually... perhaps you could help me with something.",
            NPCRole.VILLAIN:     "Nothing can stop what is coming.",
            NPCRole.ALLY:        "I'm with you, whatever happens.",
            NPCRole.COMMONER:    "These are hard times.",
            NPCRole.MONSTER:     "GRRRR...",
        }
        return lines_by_role.get(self.role, "...")

    def build_prompt(self, player_input: str) -> str:
        """
        Build an LLM prompt for this NPC's response.
        Used when a real LLM backend is connected.
        """
        history = "\n".join(f"- {e}" for e in self.memory.events[-3:])
        return (
            f"You are {self.name}, a {self.role.value} in a dark fantasy RPG.\n"
            f"Personality: {self.personality}\n"
            f"Disposition toward player: {self.disposition.value}\n"
            f"Reputation: {self.memory.reputation}/100\n"
            f"Recent interactions:\n{history or '(none)'}\n\n"
            f"Player says: \"{player_input}\"\n"
            f"Respond in character, 1-3 sentences, in English. "
            f"Stay true to your personality and disposition."
        )


class NPCManager:
    """
    Manages a collection of NPCs for a game session.

    Handles NPC registration, lookup, and interaction routing.

    Usage:
        manager = NPCManager()
        manager.add_npc(NPC(name="Barkeep", role=NPCRole.INNKEEPER))
        npc = manager.find("barkeep")
        response = manager.interact(npc, "Do you have a room?")
    """

    def __init__(self, llm: Optional[Callable[[str], str]] = None):
        self.npcs: Dict[str, NPC] = {}
        self.llm = llm

    def add_npc(self, npc: NPC) -> None:
        """Register an NPC."""
        self.npcs[npc.name.lower()] = npc

    def find(self, name: str) -> Optional[NPC]:
        """Find NPC by name (case-insensitive, partial match)."""
        name_lower = name.lower()
        if name_lower in self.npcs:
            return self.npcs[name_lower]
        for key, npc in self.npcs.items():
            if name_lower in key:
                return npc
        return None

    def interact(
        self,
        npc: NPC,
        player_input: str,
        llm: Optional[Callable[[str], str]] = None,
    ) -> str:
        """
        Process player input and return NPC response.

        Args:
            npc: The NPC being spoken to
            player_input: Player's raw text
            llm: Optional LLM override for this interaction

        Returns:
            NPC response string
        """
        backend = llm or self.llm

        if not npc.memory.has_met_player:
            npc.memory.has_met_player = True

        npc.memory.add_event(f"Player: {player_input[:60]}")

        if backend:
            prompt = npc.build_prompt(player_input)
            response = backend(prompt)
        else:
            response = npc.react_to_player(player_input)

        npc.memory.add_event(f"{npc.name}: {response[:60]}")
        return response

    def spawn_default_npcs(self, location: str) -> List[NPC]:
        """Spawn a set of default NPCs for a location type."""
        spawned = []

        if any(w in location.lower() for w in ["tavern", "inn", "town", "meyhane", "kasaba"]):
            innkeeper = NPC(
                name="Barkeep",
                role=NPCRole.INNKEEPER,
                disposition=Disposition.FRIENDLY,
                personality="Friendly but cautious, knows local gossip.",
                location=location,
                inventory=["Cheap Room (5g)", "Ale (1g)", "Stew (2g)"],
                quest="There are rats in my cellar. Clear them out and I'll pay you 50 gold.",
            )
            self.add_npc(innkeeper)
            spawned.append(innkeeper)

        guard = NPC(
            name="Guard",
            role=NPCRole.GUARD,
            disposition=Disposition.NEUTRAL,
            personality="Stern and dutiful. Doesn't trust strangers.",
            location=location,
        )
        self.add_npc(guard)
        spawned.append(guard)

        return spawned

    def list_npcs(self) -> List[NPC]:
        """Return all registered NPCs."""
        return list(self.npcs.values())
