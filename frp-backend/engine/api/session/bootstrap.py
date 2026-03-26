"""Bootstrap and lifecycle helpers for GameSession."""
from __future__ import annotations

from datetime import datetime

from engine.data_loader import get_location_stock_baseline
from engine.map import DungeonGenerator, TownGenerator, WildernessGenerator
from engine.npc.npc_memory import NPCMemoryManager
from engine.world import WorldState
from engine.world.action_points import ActionPointTracker, CLASS_AP
from engine.world.body_parts import BodyPartTracker
from engine.world.caravans import CaravanManager
from engine.world.consequence import CascadeEngine
from engine.world.economy import LocationStock
from engine.world.entity import Entity, EntityType
from engine.world.history import HistorySeed
from engine.world.inventory import ItemStack, PhysicalInventory
from engine.world.naming import NameGenerator
from engine.world.quest_timeout import QuestTracker
from engine.world.rumors import RumorNetwork
from engine.world.schedules import GameTime as LivingGameTime
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport

from .constants import DEFAULT_EQUIPMENT_SLOTS


class SessionBootstrapMixin:
    """Construction and lifecycle methods for GameSession."""

    def __post_init__(self) -> None:
        if self.world_state is None:
            self.world_state = WorldState(game_id=self.session_id)
        if self.npc_memory is None:
            self.npc_memory = NPCMemoryManager(session_id=self.session_id)
        if self.cascade_engine is None:
            self.cascade_engine = CascadeEngine()
        if self.game_time is None:
            self.game_time = LivingGameTime(hour=8)
        if self.name_gen is None:
            self.name_gen = NameGenerator()
        if self.location_stock is None:
            self.location_stock = LocationStock(
                location_id="default",
                baseline=get_location_stock_baseline(),
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

        if self.map_data is None:
            seed = hash(self.session_id) % 1000000
            location = (self.dm_context.location if self.dm_context else "").lower()
            if any(word in location for word in ["dungeon", "cave", "crypt", "ruin", "tower", "keep"]):
                gen = DungeonGenerator(seed=seed)
            elif any(word in location for word in ["forest", "road", "wilderness", "swamp", "wilds"]):
                gen = WildernessGenerator(seed=seed)
            else:
                gen = TownGenerator(seed=seed)
            self.map_data = gen.generate(width=48, height=48)

        if self.map_data is not None and self.position == [0, 0]:
            self.position = list(self.map_data.spawn_point)

        if self.spatial_index is None:
            self.spatial_index = SpatialIndex()

        if self.viewport is None:
            self.viewport = Viewport(width=40, height=20)
            self.viewport.center_on(self.position[0], self.position[1])
            if self.map_data is not None:
                self.viewport.compute_fov(
                    lambda x, y: not self.map_data.is_walkable(x, y),
                    self.position[0],
                    self.position[1],
                    radius=8,
                )

        if self.player_entity is None:
            self.player_entity = Entity(
                id="player",
                entity_type=EntityType.NPC,
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
                dominant = self.player.dominant_class or next(iter(self.player.classes), "warrior")
                player_class = str(dominant or "warrior").lower()
            max_ap = CLASS_AP.get(player_class, 4)
            self.ap_tracker = ActionPointTracker(max_ap=max_ap)

        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
            player_inventory = list(getattr(self.player, "inventory", None) or [])
            player_equipment = dict(getattr(self.player, "equipment", None) or {})
            for item in player_inventory:
                if isinstance(item, str):
                    normalized = self._normalize_item_record({"id": item, "name": self._display_name(item)})
                else:
                    normalized = self._normalize_item_record(item)
                stack = ItemStack.from_legacy_dict(normalized)
                self.physical_inventory.add_item_auto(stack)
            for slot, item in player_equipment.items():
                if item is None:
                    continue
                canon_slot = self._canonical_slot(slot)
                if canon_slot not in DEFAULT_EQUIPMENT_SLOTS:
                    continue
                if isinstance(item, str):
                    normalized = self._normalize_item_record({"id": item, "slot": canon_slot})
                else:
                    normalized = self._normalize_item_record(item)
                    normalized["slot"] = canon_slot
                stack = ItemStack.from_legacy_dict(normalized)
                self.physical_inventory.equipment[canon_slot] = stack

        if not self.campaign_state:
            self.campaign_state = {
                "active_quests": [],
                "completed_quests": [],
                "failed_quests": [],
                "completed_quest_ids": [],
                "failed_quest_ids": [],
                "emergent_counter": 0,
            }
        self.ensure_consistency()

    def touch(self) -> None:
        """Update last_action timestamp."""
        self.last_action = datetime.now()

    def in_combat(self) -> bool:
        """Return True if session has active combat."""
        return self.combat is not None and not self.combat.combat_ended
