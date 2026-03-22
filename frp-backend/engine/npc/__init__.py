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
    options: List[str] = field(default_factory=list)  # Player choices
    next_nodes: Dict[int, str] = field(default_factory=dict)  # option_idx → node_key


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
            Disposition.HOSTILE: f"{self.name} sizi tehditkâr bir bakışla süzüyor. 'Ne istiyorsun?'",
            Disposition.UNFRIENDLY: f"{self.name} soğuk bir bakış atıyor. 'Evet?'",
            Disposition.NEUTRAL: f"{self.name} sizi karşılıyor. 'Nasıl yardımcı olabilirim?'",
            Disposition.FRIENDLY: f"{self.name} sıcak bir gülümsemeyle karşılıyor. 'Hoş geldiniz!'",
            Disposition.ALLIED: f"{self.name} mutlulukla karşılıyor. 'Arkadaşım! Sizi görmeye sevindim!'",
        }
        return greetings[self.disposition]

    def react_to_player(self, player_input: str) -> str:
        """
        Generate a contextual reaction to player input.
        Uses keyword matching + disposition for template-based response.
        """
        lower = player_input.lower()
        mem = self.memory

        # Hostile NPCs don't cooperate
        if self.disposition == Disposition.HOSTILE:
            return f"{self.name} homurdanıyor. 'Seninle konuşacak bir şeyim yok.'"

        # Trade / buy
        if any(w in lower for w in ["satın", "buy", "trade", "al", "sat"]):
            if self.inventory:
                items = ", ".join(self.inventory[:3])
                return f"{self.name}: 'Şu an elimde bunlar var: {items}.'"
            return f"{self.name}: 'Üzgünüm, şu an satacak bir şeyim yok.'"

        # Quest
        if any(w in lower for w in ["görev", "quest", "iş", "yardım", "help"]):
            if self.quest:
                return f"{self.name}: '{self.quest}'"
            return f"{self.name}: 'Sana verebileceğim bir görev yok şu an.'"

        # Information / ask
        if any(w in lower for w in ["nerede", "where", "who", "kim", "ne", "nasıl", "how"]):
            return f"{self.name} düşünüyor... 'O konuda pek bilgim yok, ama belki başka biri yardımcı olabilir.'"

        # Reputation-based response
        if mem.reputation > 50:
            return f"{self.name} güvenle: 'Sizin için her zaman buradayım.'"
        if mem.reputation < -30:
            return f"{self.name} temkinli: 'Dikkatli olun, güvenmiyorum size.'"

        # Personality fallback
        return f"{self.name}: '{self._personality_line()}'"

    def _personality_line(self) -> str:
        lines_by_role = {
            NPCRole.MERCHANT: "En iyi fiyatı size veriyorum, and kelimeme güvenin.",
            NPCRole.GUARD: "Burası koruma altında. Sorun çıkarmayın.",
            NPCRole.INNKEEPER: "Yorgun görünüyorsunuz. Bir oda ayırtayım mı?",
            NPCRole.QUEST_GIVER: "Aslında... belki bana yardım edebilirsiniz.",
            NPCRole.VILLAIN: "Sizi durdurabilecek hiçbir şey yok.",
            NPCRole.ALLY: "Yanınızdayım ne olursa olsun.",
            NPCRole.COMMONER: "Zor günler bunlar.",
            NPCRole.MONSTER: "GRRRRR...",
        }
        return lines_by_role.get(self.role, "...")

    def build_prompt(self, player_input: str) -> str:
        """
        Build an LLM prompt for this NPC's response.
        Used when a real LLM backend is connected.
        """
        history = "\n".join(f"- {e}" for e in self.memory.events[-3:])
        return (
            f"You are {self.name}, a {self.role.value} in a fantasy RPG.\n"
            f"Personality: {self.personality}\n"
            f"Disposition toward player: {self.disposition.value}\n"
            f"Reputation: {self.memory.reputation}/100\n"
            f"Recent interactions:\n{history or '(none)'}\n\n"
            f"Player says: \"{player_input}\"\n"
            f"Respond in character, 1-3 sentences, in Turkish. "
            f"Stay true to personality and disposition."
        )


class NPCManager:
    """
    Manages a collection of NPCs for a game session.

    Handles NPC spawning, lookup, and interaction routing.

    Usage:
        manager = NPCManager()
        manager.add_npc(NPC(name="Barkeep", role=NPCRole.INNKEEPER))
        npc = manager.find("barkeep")
        response = manager.interact(npc, "Bir oda var mı?")
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
        # Exact match
        if name_lower in self.npcs:
            return self.npcs[name_lower]
        # Partial match
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

        # Mark as met
        if not npc.memory.has_met_player:
            npc.memory.has_met_player = True

        # Record event
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

        if "meyhane" in location.lower() or "inn" in location.lower() or "kasaba" in location.lower():
            innkeeper = NPC(
                name="Barkeep",
                role=NPCRole.INNKEEPER,
                disposition=Disposition.FRIENDLY,
                personality="Friendly but cautious, knows local gossip.",
                location=location,
                inventory=["Cheap Room (5g)", "Ale (1g)", "Stew (2g)"],
                quest="Kellerin altında fareler var, temizler misin? 50 altın ödüllü.",
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
