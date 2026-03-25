"""
Ember RPG - API Layer
GameSession: per-player game state container
"""
from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime
import uuid

from engine.core.character import Character
from engine.core.dm_agent import DMContext, SceneType
from engine.core.combat import CombatManager
from engine.world import WorldState
from engine.npc.npc_memory import NPCMemoryManager
from engine.world.consequence import CascadeEngine

# Living World imports
from engine.world.schedules import GameTime as LivingGameTime
from engine.world.tick_scheduler import WorldTickScheduler
from engine.world.naming import NameGenerator
from engine.world.npc_needs import NPCNeeds
from engine.world.ethics import FACTION_ETHICS
from engine.world.history import HistorySeed
from engine.world.economy import LocationStock
from engine.world.rumors import RumorNetwork
from engine.world.quest_timeout import QuestTracker
from engine.world.body_parts import BodyPartTracker
from engine.world.caravans import CaravanManager


@dataclass
class GameSession:
    """
    Holds all state for one player's game session.

    Attributes:
        session_id: Unique session identifier (UUID)
        player: Player character
        dm_context: DM context (scene, location, history)
        combat: Active CombatManager (None if not in combat)
        created_at: Session creation timestamp
        last_action: Timestamp of last player action
    """
    player: Character
    dm_context: DMContext
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    combat: Optional[CombatManager] = None
    world_state: Optional[WorldState] = None
    npc_memory: Optional[NPCMemoryManager] = None
    cascade_engine: Optional[CascadeEngine] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_action: datetime = field(default_factory=datetime.now)
    position: list = field(default_factory=lambda: [0, 0])
    facing: str = "north"

    # --- Living World fields ---
    game_time: Optional[LivingGameTime] = None
    name_gen: Optional[NameGenerator] = None
    location_stock: Optional[LocationStock] = None
    rumor_network: Optional[RumorNetwork] = None
    quest_tracker: Optional[QuestTracker] = None
    body_tracker: Optional[BodyPartTracker] = None
    caravan_manager: Optional[CaravanManager] = None
    history_seed: Optional[HistorySeed] = None
    entities: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.world_state is None:
            self.world_state = WorldState(game_id=self.session_id)
        if self.npc_memory is None:
            self.npc_memory = NPCMemoryManager(session_id=self.session_id)
        if self.cascade_engine is None:
            self.cascade_engine = CascadeEngine()
        # Initialize Living World defaults
        if self.game_time is None:
            self.game_time = LivingGameTime(hour=8)
        if self.name_gen is None:
            self.name_gen = NameGenerator()
        if self.location_stock is None:
            self.location_stock = LocationStock(
                location_id="default",
                baseline={"food": 20, "ale": 10, "iron_bar": 5, "bread": 15,
                          "healing_potion": 3, "leather": 8, "cloth": 10},
            )
        if self.rumor_network is None:
            self.rumor_network = RumorNetwork()
        if self.quest_tracker is None:
            self.quest_tracker = QuestTracker()
        if self.body_tracker is None:
            self.body_tracker = BodyPartTracker()
        if self.caravan_manager is None:
            self.caravan_manager = CaravanManager()
        if self.history_seed is None:
            import random
            self.history_seed = HistorySeed().generate(seed=random.randint(0, 999999))

    def touch(self):
        """Update last_action timestamp."""
        self.last_action = datetime.now()

    def in_combat(self) -> bool:
        """Return True if session has active combat."""
        return self.combat is not None and not self.combat.combat_ended

    def to_dict(self) -> dict:
        """Serialize session state for API responses."""
        result = {
            "session_id": self.session_id,
            "scene": self.dm_context.scene_type.value,
            "location": self.dm_context.location,
            "player": {
                "name": self.player.name,
                "level": self.player.level,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "spell_points": self.player.spell_points,
                "max_spell_points": self.player.max_spell_points,
                "xp": self.player.xp,
                "classes": self.player.classes,
            },
            "in_combat": self.in_combat(),
            "turn": self.dm_context.turn,
            "position": list(self.position),
            "facing": self.facing,
        }

        # --- Living World state ---
        if self.game_time:
            result["game_time"] = self.game_time.to_dict()

        if self.entities:
            result["entities"] = [
                {"id": eid, "name": e.get("name", eid), "type": e.get("type", "npc"),
                 "position": e.get("position", [0, 0]), "faction": e.get("faction", ""),
                 "role": e.get("role", "")}
                for eid, e in self.entities.items()
            ]

        if self.quest_tracker:
            active_quests = self.quest_tracker.get_active_quests()
            if active_quests:
                result["active_quests"] = [
                    {"quest_id": q.quest_id, "title": q.title,
                     "deadline": q.deadline_hour, "status": q.status.value}
                    for q in active_quests
                ]

        if self.body_tracker:
            injuries = self.body_tracker.get_injury_effects()
            if injuries:
                result["body_status"] = injuries

        return result
