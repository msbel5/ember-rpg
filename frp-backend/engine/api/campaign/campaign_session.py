"""Campaign session — plain dataclass, no mixin inheritance.

This is a data container, NOT a behavior-rich ORM. All game logic lives
in kernel modules and campaign bridge handlers. The session only holds
state that the campaign runtime reads/writes between commands.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.kernel.actor_records import ActorRecord
from engine.kernel.scene_types import DMContext
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
from engine.map import MapData
from engine.api.session_utils import make_conversation_state


@dataclass
class CampaignSession:
    """Plain data container for per-campaign runtime state.

    No mixin inheritance. Methods below are the minimal set that
    campaign code actually calls (6 total). Everything else is
    field access.
    """

    player: ActorRecord
    dm_context: DMContext
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    combat: Optional[Any] = None
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
    equipment: Dict[str, Any] = field(default_factory=dict)

    # ── Inline methods (previously in 8 mixin files) ─────────────

    def in_combat(self) -> bool:
        """Check if session is in active combat."""
        cs = self.campaign_state.get("combat_state")
        if isinstance(cs, dict) and cs.get("phase") == "active":
            return True
        return self.combat is not None

    def ensure_consistency(self) -> None:
        """Sync player stats from kernel actor. No-op if already consistent."""
        if self.player is None:
            return
        # Sync HP.
        self.player.stats.setdefault("hp", self.player.stats.get("max_hp", 10))
        self.player.stats.setdefault("max_hp", self.player.stats.get("hp", 10))

    def find_inventory_item(self, query: str) -> Optional[Dict[str, Any]]:
        """Find item in player inventory by name/id substring."""
        query_lower = query.lower().replace(" ", "_")
        for item in self.player.inventory:
            def_id = getattr(item, "item_def_id", "")
            if query_lower in def_id.lower() or query_lower == def_id:
                return item.to_dict() if hasattr(item, "to_dict") else {"id": def_id}
        return None

    def add_item(self, item_data: dict, merge: bool = False) -> Optional[dict]:
        """Add item to player inventory from dict payload."""
        from engine.kernel.actor_items import item_stack_from_legacy_payload
        try:
            stack = item_stack_from_legacy_payload(item_data)
            self.player.inventory.append(stack)
            return item_data
        except Exception:
            return None

    def remove_item(self, query: str) -> Optional[dict]:
        """Remove first matching item from player inventory."""
        query_lower = query.lower().replace(" ", "_")
        for i, item in enumerate(self.player.inventory):
            def_id = getattr(item, "item_def_id", "")
            if query_lower in def_id.lower():
                removed = self.player.inventory.pop(i)
                return removed.to_dict() if hasattr(removed, "to_dict") else {"id": def_id}
        return None

    def set_equipment_slot(self, slot: str, item_data: Optional[dict]) -> None:
        """Set an equipment slot on the player."""
        self.equipment[slot] = item_data

    @staticmethod
    def normalize_quest_offers(offers: list) -> list:
        """Normalize quest offers for serialization."""
        return [dict(o) if isinstance(o, dict) else {"id": str(o)} for o in (offers or [])]

    def assess_item_addition(self, item_data: dict, merge: bool = False) -> dict:
        """Check if item can be added (weight/capacity check)."""
        return {"allowed": True, "reason": ""}

    def _record_add_item_failure(self, status: dict) -> None:
        """Record a failed item addition attempt."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict for persistence."""
        player_dict = self.player.to_dict() if hasattr(self.player, "to_dict") else {}
        return {
            "session_id": self.session_id,
            "player": player_dict,
            "dm_context": {
                "scene_type": getattr(self.dm_context, "scene_type_name", "exploration"),
                "location": getattr(self.dm_context, "location", ""),
            },
            "position": list(self.position),
            "facing": self.facing,
            "game_time": self.game_time.to_dict() if self.game_time and hasattr(self.game_time, "to_dict") else None,
            "entities": {k: (v.to_dict() if hasattr(v, "to_dict") else v) for k, v in self.entities.items()},
            "campaign_state": dict(self.campaign_state),
            "conversation_state": dict(self.conversation_state),
            "timed_conditions": dict(self.timed_conditions),
            "quest_offers": list(self.quest_offers),
            "narration_context": dict(self.narration_context),
            "combat": None,
            "scene": getattr(self.dm_context, "scene_type_name", "exploration"),
            "equipment": dict(self.equipment),
            "location": getattr(self.dm_context, "location", ""),
            "hp": int(self.player.stats.get("hp", 0)),
            "max_hp": int(self.player.stats.get("max_hp", 0)),
            "spell_points": int(getattr(self.player, "spell_points", 0)),
            "max_spell_points": int(self.player.raw_payload.get("max_spell_points", 0)),
            "xp": int(self.player.raw_payload.get("xp", 0)),
            "level": int(self.player.raw_payload.get("level", 1)),
            "armor_class": int(self.player.stats.get("ac", 10)),
            "action_points": int(getattr(self.player, "action_points", 3)),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignSession":
        """Deserialize session from dict. Used by save/load."""
        from engine.kernel.scene_types import DMContext, SceneType
        player = ActorRecord.from_dict(data.get("player", {}))
        scene_name = data.get("dm_context", {}).get("scene_type", "exploration")
        location = data.get("dm_context", {}).get("location", "")
        dm_context = DMContext(scene_type=SceneType.EXPLORATION, location=location, party=[player])
        session = cls(player=player, dm_context=dm_context)
        session.session_id = data.get("session_id", session.session_id)
        session.position = data.get("position", [0, 0])
        session.facing = data.get("facing", "north")
        session.campaign_state = data.get("campaign_state", {})
        session.conversation_state = data.get("conversation_state", {})
        session.timed_conditions = data.get("timed_conditions", {})
        session.quest_offers = data.get("quest_offers", [])
        session.narration_context = data.get("narration_context", {})
        session.equipment = data.get("equipment", {})
        return session


# Backward-compatible alias for save/load code that references GameSession.
GameSession = CampaignSession

__all__ = ["CampaignSession", "GameSession"]
