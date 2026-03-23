"""
Ember RPG — World State Ledger
Phase 3a: Persistent, structured world state tracking all changes.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GameTime:
    day: int = 1
    hour: int = 8
    minute: int = 0

    def advance(self, hours: float):
        total_minutes = self.minute + int(hours * 60)
        extra_hours = total_minutes // 60
        self.minute = total_minutes % 60
        total_hours = self.hour + extra_hours
        self.hour = total_hours % 24
        self.day += total_hours // 24

    def to_string(self) -> str:
        return f"Day {self.day}, {self.hour:02d}:{self.minute:02d}"

    def to_dict(self) -> dict:
        return {"day": self.day, "hour": self.hour, "minute": self.minute}

    @classmethod
    def from_dict(cls, data: dict) -> "GameTime":
        return cls(day=data.get("day", 1), hour=data.get("hour", 8), minute=data.get("minute", 0))


@dataclass
class LocationState:
    id: str
    name: str
    discovered: bool = False
    cleared: bool = False
    hostile: bool = False
    loot_collected: bool = False
    npcs_present: list = field(default_factory=list)
    items_on_ground: list = field(default_factory=list)
    custom_flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "LocationState":
        return cls(**data)


@dataclass
class NPCWorldState:
    id: str
    alive: bool = True
    location: str = ""
    disposition: int = 0
    met_player: bool = False
    inventory: list = field(default_factory=list)
    dialogue_flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "NPCWorldState":
        return cls(**data)


@dataclass
class FactionState:
    id: str
    name: str
    reputation: int = 0
    hostile: bool = False
    active_quests: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "FactionState":
        return cls(**data)


@dataclass
class QuestEntry:
    quest_id: str
    title: str
    status: str = "active"
    objectives: list = field(default_factory=list)
    location: str = ""
    rewards: dict = field(default_factory=dict)
    flags_on_complete: dict = field(default_factory=dict)
    giver_npc_id: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "QuestEntry":
        return cls(**data)


@dataclass
class WorldEvent:
    timestamp: str
    event_type: str
    description: str
    affected_entities: list = field(default_factory=list)
    real_timestamp: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "WorldEvent":
        return cls(**data)


class WorldState:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.current_time = GameTime()
        self.locations: dict[str, LocationState] = {}
        self.npc_states: dict[str, NPCWorldState] = {}
        self.factions: dict[str, FactionState] = {}
        self.quest_log: list[QuestEntry] = []
        self.flags: dict[str, Any] = {}
        self.history: list[WorldEvent] = []

    def log_event(self, event_type: str, description: str, affected_entities: list = None):
        event = WorldEvent(
            timestamp=self.current_time.to_string(),
            event_type=event_type,
            description=description,
            affected_entities=affected_entities or [],
            real_timestamp=datetime.now().isoformat(),
        )
        self.history.append(event)

    def get_npc_state(self, npc_id: str) -> NPCWorldState:
        if npc_id not in self.npc_states:
            self.npc_states[npc_id] = NPCWorldState(id=npc_id, location="unknown")
        return self.npc_states[npc_id]

    def get_location_state(self, location_id: str) -> LocationState:
        if location_id not in self.locations:
            self.locations[location_id] = LocationState(id=location_id, name=location_id)
        return self.locations[location_id]

    def update_npc_killed(self, npc_id: str, witnessed: bool = False):
        npc = self.get_npc_state(npc_id)
        npc.alive = False
        self.log_event("npc_killed", f"NPC {npc_id} was killed", [npc_id])

    def update_location_discovered(self, location_id: str, name: str = ""):
        loc = self.get_location_state(location_id)
        loc.discovered = True
        if name:
            loc.name = name
        self.log_event("location_discovered", f"Discovered {name or location_id}", [location_id])

    def build_ai_context(self, current_location_id: str = None) -> str:
        context_parts = []
        for event in self.history[-5:]:
            context_parts.append(f"Recently: {event.description}")
        if current_location_id and current_location_id in self.locations:
            loc = self.locations[current_location_id]
            if loc.cleared:
                context_parts.append(f"{loc.name} has been cleared of enemies.")
            if loc.hostile:
                context_parts.append(f"{loc.name} is currently hostile territory.")
        dead_npcs = [npc_id for npc_id, s in self.npc_states.items() if not s.alive]
        if dead_npcs:
            context_parts.append(f"Dead and unavailable: {', '.join(dead_npcs)}")
        return "\n".join(context_parts)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "current_time": self.current_time.to_dict(),
            "locations": {k: v.to_dict() for k, v in self.locations.items()},
            "npc_states": {k: v.to_dict() for k, v in self.npc_states.items()},
            "factions": {k: v.to_dict() for k, v in self.factions.items()},
            "quest_log": [q.to_dict() for q in self.quest_log],
            "flags": self.flags,
            "history": [e.to_dict() for e in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        ws = cls(game_id=data["game_id"])
        ws.current_time = GameTime.from_dict(data.get("current_time", {}))
        ws.locations = {k: LocationState.from_dict(v) for k, v in data.get("locations", {}).items()}
        ws.npc_states = {k: NPCWorldState.from_dict(v) for k, v in data.get("npc_states", {}).items()}
        ws.factions = {k: FactionState.from_dict(v) for k, v in data.get("factions", {}).items()}
        ws.quest_log = [QuestEntry.from_dict(q) for q in data.get("quest_log", [])]
        ws.flags = data.get("flags", {})
        ws.history = [WorldEvent.from_dict(e) for e in data.get("history", [])]
        return ws
