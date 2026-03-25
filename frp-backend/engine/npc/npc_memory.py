"""
Ember RPG — Per-NPC Persistent Memory
Phase 3b
"""
from dataclasses import dataclass, field


@dataclass
class ConversationSummary:
    date: str
    summary: str
    sentiment: str  # "positive", "negative", "neutral"
    key_topics: list = field(default_factory=list)


@dataclass
class NPCMemory:
    npc_id: str
    name: str
    relationship_score: int = 0
    relationship_label: str = "stranger"
    conversations: list = field(default_factory=list)
    known_facts: list = field(default_factory=list)
    emotional_state: str = "neutral"
    current_desire: str = ""
    long_term_memory: str = ""
    last_interaction: str = ""

    def update_relationship(self, delta: int):
        self.relationship_score = max(-100, min(100, self.relationship_score + delta))
        if self.relationship_score >= 60:
            self.relationship_label = "ally"
        elif self.relationship_score >= 30:
            self.relationship_label = "friend"
        elif self.relationship_score >= 10:
            self.relationship_label = "acquaintance"
        elif self.relationship_score > -20:
            self.relationship_label = "stranger"
        elif self.relationship_score > -50:
            self.relationship_label = "unfriendly"
        else:
            self.relationship_label = "enemy"

    def add_conversation(self, summary: str, sentiment: str, game_time: str, topics: list = None):
        conv = ConversationSummary(
            date=game_time,
            summary=summary,
            sentiment=sentiment,
            key_topics=topics or [],
        )
        self.conversations.append(conv.__dict__)
        if len(self.conversations) > 10:
            oldest = self.conversations.pop(0)
            self.long_term_memory += f" {oldest['summary']}"
        if sentiment == "positive":
            self.update_relationship(5)
        elif sentiment == "negative":
            self.update_relationship(-5)
        self.last_interaction = game_time

    def add_known_fact(self, fact: str):
        if fact not in self.known_facts:
            self.known_facts.append(fact)

    def build_context(self, npc_template: dict = None) -> str:
        lines = []
        role = npc_template.get("role", "NPC") if npc_template else "NPC"
        lines.append(f"You are {self.name}, a {role}.")
        lines.append(f"Current mood: {self.emotional_state}")
        lines.append(f"Relationship with player: {self.relationship_label} (score: {self.relationship_score})")
        if self.known_facts:
            lines.append(f"You know about the player: {'; '.join(self.known_facts)}")
        if self.long_term_memory:
            lines.append(f"Long-term impression: {self.long_term_memory}")
        if self.conversations:
            recent = self.conversations[-3:]
            lines.append("Recent conversations:")
            for c in recent:
                lines.append(f"  - {c['date']}: {c['summary']}")
        if self.current_desire:
            lines.append(f"Your current desire: {self.current_desire}")
        lines.append("Stay in character. Reference past interactions naturally.")
        return "\n".join(lines)


class NPCMemoryManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memories: dict[str, NPCMemory] = {}

    def get_memory(self, npc_id: str, npc_name: str = "") -> NPCMemory:
        if npc_id not in self.memories:
            self.memories[npc_id] = NPCMemory(npc_id=npc_id, name=npc_name or npc_id)
        return self.memories[npc_id]

    def record_interaction(self, npc_id: str, summary: str, sentiment: str, game_time: str, facts: list = None):
        mem = self.get_memory(npc_id)
        mem.add_conversation(summary, sentiment, game_time)
        if facts:
            for fact in facts:
                mem.add_known_fact(fact)

    def propagate_gossip(self, source_npc_id: str, target_npc_id: str, fact: str):
        source_name = self.get_memory(source_npc_id).name
        target_mem = self.get_memory(target_npc_id)
        gossiped = f"Heard from {source_name}: {fact}"
        target_mem.add_known_fact(gossiped)

    def to_dict(self) -> dict:
        return {npc_id: mem.__dict__ for npc_id, mem in self.memories.items()}

    @classmethod
    def from_dict(cls, session_id: str, data: dict) -> "NPCMemoryManager":
        manager = cls(session_id)
        for npc_id, mem_data in data.items():
            mem = NPCMemory(**mem_data)
            manager.memories[npc_id] = mem
        return manager
