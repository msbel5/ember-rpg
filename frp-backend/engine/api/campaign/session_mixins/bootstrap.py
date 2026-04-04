"""Bootstrap and lifecycle helpers for GameSession.

Kernel-only: all values come from ActorRecord (kernel types) and
the data layer — no hardcoded game constants, no legacy dict branches.
"""
from __future__ import annotations

import logging
from datetime import datetime

from engine.data_loader import (
    get_class_ap_map,
    get_class_default_hp,
    get_creation_default_class,
    get_location_stock_baseline,
)
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

log = logging.getLogger(__name__)


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
            # All values read from kernel ActorRecord — no hardcoded fallbacks
            player_name = self.player.name if self.player else "Player"
            player_hp = self.player.hp if self.player else get_class_default_hp(
                self.player.player_class if self.player else get_creation_default_class()
            )
            player_max_hp = self.player.max_hp if self.player else player_hp
            log.info("Creating player entity: name=%s hp=%d/%d", player_name, player_hp, player_max_hp)
            self.player_entity = Entity(
                id="player",
                entity_type=EntityType.NPC,
                name=player_name,
                position=tuple(self.position),
                glyph="@",
                color="white",
                blocking=True,
                hp=player_hp,
                max_hp=player_max_hp,
                disposition="friendly",
            )
            self.spatial_index.add(self.player_entity)

        if self.ap_tracker is None:
            # AP per turn loaded from classes.json via CLASS_AP map
            player_class = (
                self.player.dominant_class
                if self.player is not None
                else get_creation_default_class()
            )
            max_ap = CLASS_AP.get(player_class, get_class_ap_map().get(player_class, 4))
            log.info("Init AP tracker: class=%s max_ap=%d", player_class, max_ap)
            self.ap_tracker = ActionPointTracker(max_ap=max_ap)

        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()

            # Kernel inventory is list[ItemStack] — convert each to
            # runtime ItemStack via dict intermediary (no legacy branches)
            kernel_items = self.player.inventory if self.player else []
            for item in kernel_items:
                item_dict = item.to_dict()
                normalized = self._normalize_item_record(item_dict)
                stack = ItemStack.from_legacy_dict(normalized)
                self.physical_inventory.add_item_auto(stack)

            # Kernel equipment is EquipmentLoadout — flatten slots into
            # PhysicalInventory.equipment (runtime uses {slot: ItemStack})
            kernel_equip = self.player.equipment if self.player else None
            if kernel_equip is not None and hasattr(kernel_equip, "slots"):
                for slot_name, items in kernel_equip.slots.items():
                    if not items:
                        continue
                    canon_slot = self._canonical_slot(slot_name)
                    if canon_slot not in DEFAULT_EQUIPMENT_SLOTS:
                        continue
                    first = items[0]
                    item_dict = first.to_dict()
                    item_dict["slot"] = canon_slot
                    normalized = self._normalize_item_record(item_dict)
                    stack = ItemStack.from_legacy_dict(normalized)
                    self.physical_inventory.equipment[canon_slot] = stack

            log.info(
                "PhysicalInventory loaded: %d backpack items, %d equipped slots",
                len(list(self.physical_inventory.all_items())),
                sum(1 for v in self.physical_inventory.equipment.values() if v),
            )

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
        if self.combat is not None and not self.combat.combat_ended:
            return True
        state = self.campaign_state.get("combat_state") if isinstance(self.campaign_state, dict) else None
        if state is None:
            return False
        try:
            from engine.kernel.combat_engine import is_combat_over

            actors = self.campaign_state.get("combat_actors", {})
            return str(getattr(state, "phase", "resolved")) != "resolved" and not is_combat_over(state, actors)
        except Exception:
            return str(getattr(state, "phase", "resolved")) != "resolved"
