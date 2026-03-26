"""Core GameSession dataclass composed from focused mixins."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.dm_agent import DMContext
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

from .bootstrap import SessionBootstrapMixin
from .conversation import SessionConversationMixin
from .encumbrance import SessionEncumbranceMixin
from .entity_state import SessionEntityMixin
from .inventory_state import SessionInventoryMixin
from .player_state import SessionPlayerStateMixin
from .serialization import SessionSerializationMixin
from .timed_conditions import SessionTimedConditionMixin


@dataclass
class GameSession(
    SessionBootstrapMixin,
    SessionInventoryMixin,
    SessionEntityMixin,
    SessionTimedConditionMixin,
    SessionEncumbranceMixin,
    SessionPlayerStateMixin,
    SessionConversationMixin,
    SessionSerializationMixin,
):
    """Canonical per-player runtime session state."""

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
