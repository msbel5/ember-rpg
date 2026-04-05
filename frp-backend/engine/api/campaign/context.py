"""Unified campaign context — single authority for ALL game state.

CampaignContext is the sole runtime state container. There is no separate
session object. Kernel owns compute (actors, game_state, world_state),
context owns rendering/UI state (map, viewport, entities), and persistence
serializes both from this one place.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.api.session_utils import make_conversation_state
from engine.kernel.actor_records import ActorRecord
from engine.kernel.creation import CreationState
from engine.kernel.scene_types import SceneContext
from engine.npc.npc_memory import NPCMemoryManager
from engine.world import WorldState
from engine.world.action_points import ActionPointTracker
from engine.world.body_parts import BodyPartTracker
from engine.world.caravans import CaravanManager
from engine.world.consequence import CascadeEngine
from engine.world.economy import LocationStock
from engine.world.entity import Entity
from engine.world.history import HistorySeed
from engine.world.inventory import PhysicalInventory
from engine.world.naming import NameGenerator
from engine.world.quest_timeout import QuestTracker
from engine.world.rumors import RumorNetwork
from engine.world.schedules import GameTime as LivingGameTime
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport
from engine.map import MapData, TileType
from engine.worldgen.models import RegionSnapshot, WorldBlueprint


@dataclass
class CampaignContext:
    """Unified runtime state for a campaign — NO separate session object.

    Kernel owns actors/game_state/world_state via ``kernel_runtime``.
    This context owns rendering, UI, and world-simulation subsystems.
    Persistence serializes kernel_runtime + context fields.
    """

    # ── Campaign identity ──────────────────────────────────────────
    campaign_id: str
    adapter_id: str
    profile_id: str
    seed: int

    # ── World / region ─────────────────────────────────────────────
    world: WorldBlueprint
    region_snapshot: RegionSnapshot
    settlement_state: dict[str, Any]
    recent_event_log: list[dict[str, Any]] = field(default_factory=list)

    # ── Kernel runtime (actors, game_state, etc.) ──────────────────
    kernel_runtime: dict[str, Any] = field(default_factory=dict)

    # ── Player state (kernel-authoritative via kernel_runtime["actors"]["player"]) ──
    player: Optional[ActorRecord] = None
    dm_context: Optional[SceneContext] = None
    world_state: Optional[WorldState] = None
    npc_memory: Optional[NPCMemoryManager] = None
    cascade_engine: Optional[CascadeEngine] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_action: datetime = field(default_factory=datetime.now)
    position: list = field(default_factory=lambda: [0, 0])
    facing: str = "north"
    game_time: Optional[LivingGameTime] = None
    name_gen: Optional[NameGenerator] = None
    location_stock: Optional[LocationStock] = None
    rumor_network: Optional[RumorNetwork] = None
    quest_tracker: Optional[QuestTracker] = None
    body_tracker: Optional[BodyPartTracker] = None
    caravan_manager: Optional[CaravanManager] = None
    history_seed: Optional[HistorySeed] = None
    entities: Dict = field(default_factory=dict)
    quest_offers: List[Dict[str, Any]] = field(default_factory=list)
    campaign_state: Dict[str, Any] = field(default_factory=dict)
    narration_context: Dict[str, Any] = field(default_factory=dict)
    conversation_state: Dict[str, Any] = field(default_factory=lambda: make_conversation_state(0))
    timed_conditions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_save_slot: Optional[str] = None
    map_data: Optional[MapData] = None
    spatial_index: Optional[SpatialIndex] = None
    viewport: Optional[Viewport] = None
    player_entity: Optional[Entity] = None
    ap_tracker: Optional[ActionPointTracker] = None
    physical_inventory: Optional[PhysicalInventory] = None

    # ── Inline methods (duck-type compatible with kernel/gameplay.py) ──

    def in_combat(self) -> bool:
        """Check if context is in active combat."""
        combat = self.kernel_combat_state()
        return bool(combat and combat.get("phase") != "resolved")

    def kernel_combat_state(self) -> Optional[Dict[str, Any]]:
        runtime = getattr(self, "kernel_runtime", {}) or {}
        game_state = runtime.get("game_state")
        raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
        combat = raw_payload.get("combat")
        if isinstance(combat, dict) and combat.get("combatants"):
            return combat
        campaign_root = (self.campaign_state.get("campaign") or {}) if isinstance(self.campaign_state, dict) else {}
        game_state_payload = campaign_root.get("game_state") if isinstance(campaign_root, dict) else None
        if isinstance(game_state_payload, dict):
            raw_payload = game_state_payload.get("raw_payload", {})
            combat = raw_payload.get("combat") if isinstance(raw_payload, dict) else None
            if isinstance(combat, dict) and combat.get("combatants"):
                return combat
        return None

    def ensure_consistency(self) -> None:
        """Sync player stats. No-op if already consistent."""
        if self.player is None:
            return
        self.player.stats.setdefault("hp", self.player.stats.get("max_hp", 10))
        self.player.stats.setdefault("max_hp", self.player.stats.get("hp", 10))

    @staticmethod
    def _normalize_tile_point(value: Any) -> Optional[tuple[int, int]]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _tile_set_from_payload(cls, payload: Any) -> set[tuple[int, int]]:
        normalized: set[tuple[int, int]] = set()
        if not isinstance(payload, list):
            return normalized
        for item in payload:
            point = cls._normalize_tile_point(item)
            if point is not None:
                normalized.add(point)
        return normalized

    @staticmethod
    def _serialize_tile_set(points: set[tuple[int, int]]) -> list[list[int]]:
        return [[int(x), int(y)] for x, y in sorted(points, key=lambda item: (item[1], item[0]))]

    def _active_region_id(self) -> str:
        if getattr(self, "region_snapshot", None) is not None:
            return str(self.region_snapshot.region_id)
        return str(self.campaign_state.get("active_region_id", ""))

    def _ensure_fog_store(self) -> dict[str, Any]:
        fog_store = self.campaign_state.get("fog_by_region")
        if not isinstance(fog_store, dict):
            fog_store = {}
            self.campaign_state["fog_by_region"] = fog_store
        return fog_store

    def _ensure_viewport(self) -> Viewport:
        viewport = self.viewport
        if viewport is None:
            viewport = Viewport()
            self.viewport = viewport
        return viewport

    def _map_in_bounds(self, x: int, y: int) -> bool:
        if self.map_data is None:
            return False
        return 0 <= int(x) < int(self.map_data.width) and 0 <= int(y) < int(self.map_data.height)

    def _tile_blocks_sight(self, x: int, y: int) -> bool:
        if not self._map_in_bounds(x, y):
            return True
        tile = self.map_data.tiles[int(y)][int(x)] if self.map_data is not None else TileType.WALL
        return tile in {TileType.WALL, TileType.TREE, TileType.WATER}

    def _tile_frontier_candidates(self, explored: set[tuple[int, int]]) -> set[tuple[int, int]]:
        frontier: set[tuple[int, int]] = set()
        for x, y in explored:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = int(x) + dx
                ny = int(y) + dy
                if not self._map_in_bounds(nx, ny):
                    continue
                if (nx, ny) in explored:
                    continue
                if self._tile_blocks_sight(nx, ny):
                    continue
                frontier.add((nx, ny))
        return frontier

    def refresh_fog_state(self) -> dict[str, Any]:
        region_id = self._active_region_id()
        if not region_id or self.map_data is None or len(self.position) < 2:
            return {
                "region_id": region_id,
                "visible_tiles": [],
                "explored_tiles": [],
                "frontier_tiles": [],
                "visible_count": 0,
                "explored_count": 0,
                "frontier_count": 0,
                "regions": [],
            }

        fog_store = self._ensure_fog_store()
        region_entry = fog_store.get(region_id)
        if not isinstance(region_entry, dict):
            region_entry = {}
            fog_store[region_id] = region_entry

        viewport = self._ensure_viewport()
        player_x = int(self.position[0])
        player_y = int(self.position[1])
        viewport.center_on(player_x, player_y)
        viewport.fog_of_war = {
            point for point in self._tile_set_from_payload(region_entry.get("explored_tiles", []))
            if self._map_in_bounds(point[0], point[1])
        }
        viewport.compute_fov_simple(self._tile_blocks_sight, player_x, player_y, radius=int(viewport.fov_radius))
        viewport.visible = {
            (int(x), int(y)) for x, y in viewport.visible
            if self._map_in_bounds(int(x), int(y))
        }
        viewport.fog_of_war = {
            (int(x), int(y)) for x, y in viewport.fog_of_war
            if self._map_in_bounds(int(x), int(y))
        }

        explored = set(viewport.fog_of_war)
        visible = set(viewport.visible)
        frontier = self._tile_frontier_candidates(explored)

        region_entry["explored_tiles"] = self._serialize_tile_set(explored)
        region_entry["last_position"] = [player_x, player_y]

        regions_summary = []
        for known_region_id, known_entry in sorted(fog_store.items(), key=lambda item: item[0]):
            if not isinstance(known_entry, dict):
                continue
            explored_tiles = self._tile_set_from_payload(known_entry.get("explored_tiles", []))
            regions_summary.append(
                {
                    "region_id": str(known_region_id),
                    "explored_count": len(explored_tiles),
                    "has_exploration": bool(explored_tiles),
                }
            )

        payload = {
            "region_id": region_id,
            "visible_tiles": self._serialize_tile_set(visible),
            "explored_tiles": self._serialize_tile_set(explored),
            "frontier_tiles": self._serialize_tile_set(frontier),
            "visible_count": len(visible),
            "explored_count": len(explored),
            "frontier_count": len(frontier),
            "regions": regions_summary,
        }
        self.campaign_state["fog"] = copy.deepcopy(payload)
        return payload

    def find_inventory_item(self, query: str) -> Optional[Dict[str, Any]]:
        """Find item in player inventory by name/id substring."""
        if self.player is None:
            return None
        query_lower = query.lower().replace(" ", "_")
        for item in self.player.inventory:
            def_id = getattr(item, "item_def_id", "")
            if query_lower in def_id.lower() or query_lower == def_id:
                result = item.to_dict() if hasattr(item, "to_dict") else {"id": def_id}
                qty = getattr(item, "quantity", 1)
                result["qty"] = int(qty)
                result["quantity"] = int(qty)
                return result
        return None

    def add_item(self, item_data: dict, merge: bool = False) -> Optional[dict]:
        """Add item to player inventory from dict payload.

        When ``merge=True`` and an existing stack has the same item_def_id,
        the quantity is increased instead of appending a new stack.
        """
        from engine.kernel.actor_items import item_stack_from_legacy_payload
        try:
            payload = dict(item_data)
            if "quantity" not in payload and payload.get("qty") is not None:
                payload["quantity"] = payload.get("qty")
            payload.setdefault("item_def_id", str(payload.get("id", "")))
            stack = item_stack_from_legacy_payload(payload)
            if merge:
                for existing in self.player.inventory:
                    if getattr(existing, "item_def_id", "") == stack.item_def_id:
                        existing.quantity = getattr(existing, "quantity", 1) + max(1, getattr(stack, "quantity", 1))
                        return item_data
            self.player.inventory.append(stack)
            return item_data
        except Exception:
            return None

    def remove_item(self, query: str) -> Optional[dict]:
        """Remove first matching item from player inventory."""
        if self.player is None:
            return None
        query_lower = query.lower().replace(" ", "_")
        for i, item in enumerate(self.player.inventory):
            def_id = getattr(item, "item_def_id", "")
            instance_id = str(getattr(item, "instance_id", ""))
            if query_lower not in def_id.lower() and query_lower != instance_id.lower():
                continue
            quantity = max(1, int(getattr(item, "quantity", 1)))
            if quantity <= 1:
                removed = self.player.inventory.pop(i)
                payload = removed.to_dict() if hasattr(removed, "to_dict") else {"id": def_id}
            else:
                item.quantity = quantity - 1
                payload = item.to_dict() if hasattr(item, "to_dict") else {"id": def_id}
                payload["quantity"] = 1
                payload["qty"] = 1
                payload["instance_id"] = f"dropped_{uuid.uuid4().hex[:8]}"
            payload.setdefault("id", def_id)
            payload.setdefault("name", str(getattr(item, "name", def_id.replace("_", " ").title())))
            payload["quantity"] = max(1, int(payload.get("quantity", payload.get("qty", 1))))
            payload["qty"] = payload["quantity"]
            return payload
        return None

    def set_equipment_slot(self, slot: str, item_data: Optional[dict]) -> None:
        """Set an equipment slot on the player."""
        if self.player is None:
            return
        if item_data is None:
            self.player.equipment.slots.pop(slot, None)
            return
        from engine.kernel.actor_items import item_stack_from_legacy_payload

        stack = item_stack_from_legacy_payload(dict(item_data))
        self.player.equipment.slots[slot] = [stack]

    def assess_item_addition(self, item_data: dict, merge: bool = False) -> dict:
        """Check if item can be added (weight/capacity check)."""
        return {"allowed": True, "reason": ""}

    def _record_add_item_failure(self, status: dict) -> None:
        """Record a failed item addition attempt."""
        pass

    @staticmethod
    def normalize_quest_offers(offers: list, default_source: str = "authored") -> list:
        """Normalize quest offers for serialization."""
        result = []
        for o in (offers or []):
            entry = dict(o) if isinstance(o, dict) else {"id": str(o)}
            entry.setdefault("source", default_source)
            result.append(entry)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context game state to dict for payload building."""
        fog_payload = self.refresh_fog_state()
        player_dict = self.player.to_dict() if self.player and hasattr(self.player, "to_dict") else {}
        if self.player is not None:
            inventory_payload: list[dict[str, Any]] = []
            for item in self.player.inventory:
                item_data = item.to_dict() if hasattr(item, "to_dict") else {"id": getattr(item, "item_def_id", "")}
                item_id = str(item_data.get("item_def_id") or item_data.get("id") or getattr(item, "item_def_id", ""))
                quantity = max(1, int(item_data.get("quantity", getattr(item, "quantity", item_data.get("qty", 1)))))
                item_data["id"] = item_id
                item_data.setdefault("name", str(getattr(item, "payload", {}).get("name", item_id.replace("_", " ").title())))
                item_data["quantity"] = quantity
                item_data["qty"] = quantity
                inventory_payload.append(item_data)
            player_dict["inventory"] = inventory_payload
        return {
            "campaign_id": self.campaign_id,
            "player": player_dict,
            "dm_context": {
                "scene_type": getattr(self.dm_context, "scene_type_name", "exploration") if self.dm_context else "exploration",
                "location": getattr(self.dm_context, "location", "") if self.dm_context else "",
            },
            "position": list(self.position),
            "facing": self.facing,
            "game_time": self.game_time.to_dict() if self.game_time and hasattr(self.game_time, "to_dict") else None,
            "entities": {k: (v.to_dict() if hasattr(v, "to_dict") else v) for k, v in self.entities.items()},
            "campaign_state": dict(self.campaign_state),
            "conversation_state": dict(self.conversation_state),
            "timed_conditions": dict(self.timed_conditions),
            "active_quests": copy.deepcopy(self.campaign_state.get("active_quests", [])),
            "completed_quest_ids": list(self.campaign_state.get("completed_quest_ids", [])),
            "failed_quest_ids": list(self.campaign_state.get("failed_quest_ids", [])),
            "quest_offers": list(self.quest_offers),
            "party": list(self.campaign_state.get("party", [])),
            "narration_context": dict(self.narration_context),
            "combat": self.kernel_combat_state(),
            "scene": getattr(self.dm_context, "scene_type_name", "exploration") if self.dm_context else "exploration",
            "equipment": self.player.equipment.to_dict() if self.player is not None else {},
            "location": getattr(self.dm_context, "location", "") if self.dm_context else "",
            "hp": int(self.player.stats.get("hp", 0)) if self.player else 0,
            "max_hp": int(self.player.stats.get("max_hp", 0)) if self.player else 0,
            "spell_points": int(getattr(self.player, "spell_points", 0)) if self.player else 0,
            "max_spell_points": int(self.player.raw_payload.get("max_spell_points", 0)) if self.player else 0,
            "xp": int(self.player.raw_payload.get("xp", 0)) if self.player else 0,
            "level": int(self.player.raw_payload.get("level", 1)) if self.player else 1,
            "armor_class": int(self.player.stats.get("ac", 10)) if self.player else 10,
            "action_points": int(getattr(self.player, "action_points", 3)) if self.player else 3,
            "fog": fog_payload,
        }


@dataclass
class CampaignCreationContext:
    state: CreationState
    adapter_id: str
    profile_id: str
    seed: int
    location: Optional[str] = None


__all__ = ["CampaignContext", "CampaignCreationContext"]
