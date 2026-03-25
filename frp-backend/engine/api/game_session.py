"""
Ember RPG - API Layer
GameSession: per-player game state container
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
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
from engine.world.naming import NameGenerator
from engine.world.history import HistorySeed
from engine.world.economy import LocationStock
from engine.world.rumors import RumorNetwork
from engine.world.quest_timeout import QuestTracker
from engine.world.body_parts import BodyPartTracker
from engine.world.caravans import CaravanManager

# Entity / Spatial / Viewport / AP imports
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport
from engine.world.action_points import ActionPointTracker, CLASS_AP
from engine.map import MapData, TownGenerator


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

    # --- Entity / Spatial / Viewport / AP fields ---
    map_data: Optional[MapData] = None
    spatial_index: Optional[SpatialIndex] = None
    viewport: Optional[Viewport] = None
    player_entity: Optional[Entity] = None
    ap_tracker: Optional[ActionPointTracker] = None
    inventory: List[Dict] = field(default_factory=list)
    equipment: Dict[str, Optional[Dict]] = field(default_factory=lambda: {
        "weapon": None, "armor": None, "shield": None, "helmet": None,
        "boots": None, "gloves": None, "ring": None, "amulet": None,
    })

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

        # --- Initialize map, spatial index, viewport ---
        if self.map_data is None:
            import random as _rng
            seed = hash(self.session_id) % 1000000
            gen = TownGenerator(seed=seed)
            self.map_data = gen.generate(width=48, height=48)

        # Set player position to map spawn point if still at default origin
        if self.map_data is not None and self.position == [0, 0]:
            self.position = list(self.map_data.spawn_point)

        if self.spatial_index is None:
            self.spatial_index = SpatialIndex()

        if self.viewport is None:
            self.viewport = Viewport(width=40, height=20)
            self.viewport.center_on(self.position[0], self.position[1])
            # Compute initial FOV
            if self.map_data is not None:
                self.viewport.compute_fov(
                    lambda x, y: not self.map_data.is_walkable(x, y),
                    self.position[0], self.position[1],
                    radius=8,
                )

        if self.player_entity is None:
            # Determine player class for glyph/AP
            player_class = "warrior"
            if hasattr(self, "player") and self.player is not None:
                player_class = next(iter(self.player.classes), "warrior") if self.player.classes else "warrior"
            self.player_entity = Entity(
                id="player",
                entity_type=EntityType.NPC,  # player is a special NPC
                name=self.player.name if self.player else "Player",
                position=tuple(self.position),
                glyph="@",
                color="white",
                blocking=True,
                hp=self.player.hp if self.player else 20,
                max_hp=self.player.max_hp if self.player else 20,
                disposition="friendly",
            )
            self.spatial_index.add(self.player_entity)

        if self.ap_tracker is None:
            player_class = "warrior"
            if hasattr(self, "player") and self.player is not None:
                player_class = next(iter(self.player.classes), "warrior") if self.player.classes else "warrior"
            max_ap = CLASS_AP.get(player_class, 4)
            self.ap_tracker = ActionPointTracker(max_ap=max_ap)

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

        # --- AP tracker ---
        if self.ap_tracker:
            result["ap"] = {
                "current": self.ap_tracker.current_ap,
                "max": self.ap_tracker.max_ap,
            }

        # --- Inventory & Equipment ---
        if self.inventory:
            result["inventory"] = self.inventory
        if self.equipment:
            equipped = {slot: item for slot, item in self.equipment.items() if item is not None}
            if equipped:
                result["equipment"] = equipped

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

        # --- Spatial index entity list (Entity objects) ---
        if self.spatial_index and self.spatial_index.count() > 0:
            spatial_entities = []
            for ent in self.spatial_index.all_entities():
                if ent.id == "player":
                    continue
                spatial_entities.append(ent.to_dict())
            if spatial_entities:
                result["world_entities"] = spatial_entities

        # --- Map metadata ---
        if self.map_data:
            result["map"] = {
                "width": self.map_data.width,
                "height": self.map_data.height,
                "spawn_point": list(self.map_data.spawn_point),
            }

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
