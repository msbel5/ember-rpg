"""Campaign context serialization helpers."""
from __future__ import annotations

import copy
from typing import Any, Dict

from engine.api.campaign.debug_trace import trace_event
from engine.api.session_utils import normalize_conversation_state
from engine.data_loader import get_location_stock_baseline


class SaveCampaignStateMixin:
    """CampaignContext serialization and deserialization."""

    _CAMPAIGN_ROOT_KEY = "campaign"

    @classmethod
    def _campaign_root(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        campaign_state = data.get("campaign_state", {})
        if isinstance(campaign_state, dict):
            raw_campaign = campaign_state.get(cls._CAMPAIGN_ROOT_KEY)
            if isinstance(raw_campaign, dict):
                return copy.deepcopy(raw_campaign)
        return {}

    @classmethod
    def _validate_campaign_root(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        campaign_root = cls._campaign_root(data)
        if not campaign_root:
            return {}

        from engine.kernel import GameState, WorldState as KernelWorldState

        kernel_game_state = campaign_root.get("game_state")
        if not isinstance(kernel_game_state, dict):
            trace_event("campaign_save_validation_failed", reason="missing_game_state")
            raise ValueError("Campaign save is missing game_state")
        try:
            GameState.from_dict(dict(kernel_game_state))
        except Exception as exc:
            trace_event("campaign_save_validation_failed", reason="invalid_game_state", error=str(exc))
            raise

        kernel_world_state = campaign_root.get("world_state")
        if not isinstance(kernel_world_state, dict):
            trace_event("campaign_save_validation_failed", reason="missing_world_state")
            raise ValueError("Campaign save is missing world_state")
        try:
            KernelWorldState.from_dict(dict(kernel_world_state))
        except Exception as exc:
            trace_event("campaign_save_validation_failed", reason="invalid_world_state", error=str(exc))
            raise

        return campaign_root

    @staticmethod
    def _serialize_campaign_context(context) -> Dict[str, Any]:
        context.ensure_consistency()

        data: Dict[str, Any] = {
            "campaign_id": context.campaign_id,
            "created_at": context.created_at.isoformat(),
            "last_action": context.last_action.isoformat(),
            "position": list(context.position),
            "facing": context.facing,
            "player": context.player.to_dict(),
        }
        if context.dm_context is not None:
            data["dm_context"] = context.dm_context.to_dict()
        if context.game_time is not None:
            data["game_time"] = context.game_time.to_dict()
        if context.map_data is not None:
            data["map_data"] = context.map_data.to_dict()
        if context.viewport is not None:
            data["viewport"] = context.viewport.to_dict()
        if context.spatial_index is not None:
            data["spatial_entities"] = [entity.to_dict() for entity in context.spatial_index.all_entities()]
        if context.player_entity is not None:
            data["player_entity"] = context.player_entity.to_dict()
        if context.ap_tracker is not None:
            data["ap_tracker"] = context.ap_tracker.to_dict()
        if getattr(context, "physical_inventory", None) is not None:
            data["physical_inventory"] = context.physical_inventory.to_dict()

        if context.entities:
            serialized_entities = {}
            for entity_id, entity in context.entities.items():
                entity_copy = dict(entity)
                needs = entity_copy.get("needs")
                if needs is not None and hasattr(needs, "to_dict"):
                    entity_copy["needs"] = needs.to_dict()
                schedule = entity_copy.get("schedule")
                if schedule is not None and hasattr(schedule, "to_dict"):
                    entity_copy["schedule"] = schedule.to_dict()
                body = entity_copy.get("body")
                if body is not None and hasattr(body, "to_dict"):
                    entity_copy["body"] = body.to_dict()
                entity_copy.pop("entity_ref", None)
                serialized_entities[entity_id] = entity_copy
            data["entities"] = serialized_entities

        if context.world_state is not None:
            data["world_state"] = context.world_state.to_dict()
        if context.npc_memory is not None:
            data["npc_memory"] = context.npc_memory.to_dict()
        if context.cascade_engine is not None:
            data["cascade_engine"] = context.cascade_engine.to_dict()
        if context.location_stock is not None:
            data["location_stock"] = context.location_stock.to_dict()
        if context.rumor_network is not None:
            data["rumor_network"] = context.rumor_network.to_dict()
        if context.quest_tracker is not None:
            data["quest_tracker"] = context.quest_tracker.to_dict()
        if context.body_tracker is not None:
            data["body_tracker"] = context.body_tracker.to_dict()
        if context.caravan_manager is not None:
            data["caravan_manager"] = context.caravan_manager.to_dict()
        if context.history_seed is not None:
            data["history_seed"] = context.history_seed.to_dict()

        from engine.api.campaign.context import CampaignContext

        data["quest_offers"] = CampaignContext.normalize_quest_offers(
            getattr(context, "quest_offers", []),
            default_source="authored",
        )
        data["campaign_state"] = dict(getattr(context, "campaign_state", {}))
        data["narration_context"] = dict(getattr(context, "narration_context", {}))
        data["conversation_state"] = dict(getattr(context, "conversation_state", {}))
        data["timed_conditions"] = copy.deepcopy(getattr(context, "timed_conditions", {}))
        data["last_save_slot"] = getattr(context, "last_save_slot", None)
        return data

    @staticmethod
    def _deserialize_campaign_context(data: Dict[str, Any]):
        from datetime import datetime as dt

        from engine.api.campaign.context import CampaignContext
        from engine.kernel.actor_records import ActorRecord
        from engine.kernel.scene_types import SceneContext, SceneType
        from engine.map import MapData
        from engine.npc.npc_memory import NPCMemoryManager
        from engine.world import WorldState
        from engine.world.action_points import ActionPointTracker, CLASS_AP
        from engine.world.body_parts import BodyPartTracker
        from engine.world.caravans import CaravanManager
        from engine.world.consequence import CascadeEngine
        from engine.world.economy import LocationStock
        from engine.world.entity import Entity, EntityType
        from engine.world.history import HistorySeed
        from engine.world.inventory import PhysicalInventory
        from engine.world.quest_timeout import QuestTracker
        from engine.world.rumors import RumorNetwork
        from engine.world.schedules import GameTime as LivingGameTime, NPCSchedule
        from engine.world.spatial_index import SpatialIndex
        from engine.world.viewport import Viewport

        player = ActorRecord.from_dict(data["player"])
        dm_context = None
        if "dm_context" in data:
            dm_context = SceneContext.from_dict(data["dm_context"], party=[player])
        map_data = MapData.from_dict(data["map_data"]) if "map_data" in data else None
        game_time = LivingGameTime.from_dict(data["game_time"]) if "game_time" in data else None
        viewport = Viewport.from_dict(data["viewport"]) if "viewport" in data else None
        viewport_missing = "viewport" not in data
        ap_tracker = ActionPointTracker.from_dict(data["ap_tracker"]) if "ap_tracker" in data else None
        location_stock = LocationStock.from_dict(data["location_stock"]) if "location_stock" in data else None
        rumor_network = RumorNetwork.from_dict(data["rumor_network"]) if "rumor_network" in data else None
        quest_tracker = QuestTracker.from_dict(data["quest_tracker"]) if "quest_tracker" in data else None
        body_tracker = BodyPartTracker.from_dict(data["body_tracker"]) if "body_tracker" in data else None
        caravan_manager = CaravanManager.from_dict(data["caravan_manager"]) if "caravan_manager" in data else None
        history_seed = HistorySeed.from_dict(data["history_seed"]) if "history_seed" in data else None
        world_state = WorldState.from_dict(data["world_state"]) if "world_state" in data else None
        npc_memory = None
        if "npc_memory" in data:
            npc_memory = NPCMemoryManager.from_dict(
                session_id=data.get("campaign_id", "restored"),
                data=data["npc_memory"],
            )
        cascade_engine = CascadeEngine()
        if "cascade_engine" in data:
            cascade_engine.from_dict(data["cascade_engine"])

        spatial_index = SpatialIndex()
        player_entity = None
        spatial_entities_present = "spatial_entities" in data
        if spatial_entities_present:
            for entity_data in data["spatial_entities"]:
                entity = Entity.from_dict(entity_data)
                if entity.id == "player":
                    player_entity = entity
                spatial_index.add(entity)

        if player_entity is None and "player_entity" in data:
            player_entity = Entity.from_dict(data["player_entity"])
            if spatial_index.get_position("player") is None:
                spatial_index.add(player_entity)

        context = object.__new__(CampaignContext)
        context.campaign_id = data.get("campaign_id", "restored")
        context.adapter_id = ""
        context.profile_id = ""
        context.seed = 0
        context.world = None
        context.region_snapshot = None
        context.settlement_state = {}
        context.recent_event_log = []
        context.kernel_runtime = {}
        context.player = player
        context.dm_context = dm_context if dm_context else SceneContext(
            scene_type=SceneType.EXPLORATION,
            location="Unknown",
            party=[player],
        )
        context.world_state = world_state
        context.npc_memory = npc_memory
        context.cascade_engine = cascade_engine
        context.created_at = dt.fromisoformat(data["created_at"]) if "created_at" in data else dt.now()
        context.last_action = dt.fromisoformat(data["last_action"]) if "last_action" in data else dt.now()
        context.position = data.get("position", [0, 0])
        context.facing = data.get("facing", "north")
        context.game_time = game_time
        context.name_gen = None
        context.location_stock = location_stock
        context.rumor_network = rumor_network
        context.quest_tracker = quest_tracker
        context.body_tracker = body_tracker
        context.caravan_manager = caravan_manager
        context.history_seed = history_seed

        raw_entities = data.get("entities", {})
        for entity_id, entity in raw_entities.items():
            needs_data = entity.get("needs")
            if isinstance(needs_data, dict):
                from engine.world.npc_needs import NPCNeeds

                entity["needs"] = NPCNeeds.from_dict(needs_data)
            schedule_data = entity.get("schedule")
            if isinstance(schedule_data, dict) and "npc_id" in schedule_data:
                entity["schedule"] = NPCSchedule.from_dict(schedule_data)
            body_data = entity.get("body")
            if isinstance(body_data, dict):
                entity["body"] = BodyPartTracker.from_dict(body_data)
        context.entities = raw_entities
        context.quest_offers = CampaignContext.normalize_quest_offers(
            data.get("quest_offers", []),
            default_source="authored",
        )
        context.campaign_state = dict(data.get("campaign_state", {}))
        campaign_root = SaveCampaignStateMixin._validate_campaign_root(data)
        if campaign_root:
            context.campaign_state[SaveCampaignStateMixin._CAMPAIGN_ROOT_KEY] = copy.deepcopy(campaign_root)
        context.narration_context = dict(data.get("narration_context", {}))
        context.conversation_state = normalize_conversation_state(data.get("conversation_state", {}))
        context.timed_conditions = copy.deepcopy(data.get("timed_conditions", {}))
        context.last_save_slot = data.get("last_save_slot")
        context.map_data = map_data
        context.spatial_index = spatial_index
        context.viewport = viewport
        context.player_entity = player_entity
        context.ap_tracker = ap_tracker

        if "physical_inventory" in data:
            context.physical_inventory = PhysicalInventory.from_dict(data["physical_inventory"])
        else:
            context.physical_inventory = PhysicalInventory()

        if context.world_state is None:
            from engine.world import WorldState as WS

            context.world_state = WS(game_id=context.campaign_id)
        if context.npc_memory is None:
            context.npc_memory = NPCMemoryManager(session_id=context.campaign_id)
        if context.game_time is None:
            context.game_time = LivingGameTime(hour=8)
        if context.name_gen is None:
            from engine.world.naming import NameGenerator

            context.name_gen = NameGenerator()
        if context.location_stock is None:
            context.location_stock = LocationStock(
                location_id="default",
                baseline=get_location_stock_baseline(),
            )
        if context.rumor_network is None:
            context.rumor_network = RumorNetwork()
        if context.quest_tracker is None:
            context.quest_tracker = QuestTracker()
        if context.body_tracker is None:
            context.body_tracker = BodyPartTracker()
        if context.caravan_manager is None:
            context.caravan_manager = CaravanManager()
        if context.history_seed is None:
            import random

            context.history_seed = HistorySeed().generate(seed=random.randint(0, 999999))
        if context.ap_tracker is None:
            _classes = getattr(player, "classes", None) or (getattr(player, "raw_payload", None) or {}).get("classes", {})
            from engine.data.classes import get_creation_default_class
            _fallback = get_creation_default_class()
            dominant_class = (getattr(player, "dominant_class", None) or next(iter(_classes), _fallback) or _fallback)
            context.ap_tracker = ActionPointTracker(max_ap=CLASS_AP.get(str(dominant_class).lower(), 4))

        if player_entity is None:
            context.player_entity = Entity(
                id="player",
                entity_type=EntityType.NPC,
                name=player.name,
                position=tuple(context.position),
                glyph="@",
                color="white",
                blocking=True,
                hp=player.hp,
                max_hp=player.max_hp,
                disposition="friendly",
            )
        else:
            context.player_entity = player_entity
            context.player_entity.position = tuple(context.position)
            context.player_entity.hp = player.hp
            context.player_entity.max_hp = player.max_hp
            context.player_entity.blocking = True

        if context.spatial_index.get_position("player") is None:
            context.spatial_index.add(context.player_entity)

        def _spatial_entity_by_id(entity_id: str) -> Optional[Entity]:
            for live_entity in context.spatial_index.all_entities():
                if live_entity.id == entity_id:
                    return live_entity
            return None

        if not spatial_entities_present and context.entities:
            for entity_id, record in context.entities.items():
                entity_type_name = str(record.get("type", "npc")).upper()
                try:
                    entity_type = EntityType[entity_type_name]
                except KeyError:
                    entity_type = EntityType.NPC
                live_entity = Entity(
                    id=entity_id,
                    entity_type=entity_type,
                    name=record.get("name", entity_id),
                    position=tuple(record.get("position", [0, 0])),
                    glyph=record.get("glyph", "?"),
                    color=record.get("color", "white"),
                    blocking=bool(record.get("blocking", entity_type == EntityType.NPC)),
                    hp=int(record.get("hp", 8)),
                    max_hp=int(record.get("max_hp", record.get("hp", 8) or 8)),
                    faction=record.get("faction"),
                    job=record.get("role"),
                    disposition=record.get("disposition", "friendly"),
                    needs=record.get("needs"),
                    body=record.get("body"),
                    schedule=record.get("schedule"),
                )
                if context.spatial_index.get_position(entity_id) is None:
                    context.spatial_index.add(live_entity)
                record["entity_ref"] = live_entity
        elif context.entities and context.spatial_index is not None:
            for entity_id, record in context.entities.items():
                live_entity = _spatial_entity_by_id(entity_id)
                if live_entity is not None:
                    record["entity_ref"] = live_entity

        if context.viewport is None:
            context.viewport = Viewport(width=40, height=20)
            context.viewport.center_on(context.position[0], context.position[1])

        if context.viewport is not None and context.map_data is not None:
            if viewport_missing:
                context.viewport.center_on(context.position[0], context.position[1])
            context.viewport.compute_fov(
                lambda x, y: not context.map_data.is_walkable(x, y),
                context.position[0],
                context.position[1],
                radius=8,
            )
        if hasattr(context, "reattach_entity_refs"):
            context.reattach_entity_refs()
        if hasattr(context, "ensure_consistency"):
            context.ensure_consistency()
        return context
