"""Session serialization helpers."""
from __future__ import annotations

import copy
from typing import Any, Dict

from engine.api.session_utils import normalize_conversation_state
from engine.data_loader import get_location_stock_baseline
from .combat_state import SaveCombatStateMixin


class SaveSessionStateMixin:
    """GameSession serialization and deserialization."""

    @staticmethod
    def _serialize_session(session) -> Dict[str, Any]:
        if hasattr(session, "ensure_consistency"):
            session.ensure_consistency()

        data: Dict[str, Any] = {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_action": session.last_action.isoformat(),
            "position": list(session.position),
            "facing": session.facing,
            "player": session.player.to_dict(),
        }
        if session.dm_context is not None:
            data["dm_context"] = session.dm_context.to_dict()
        if session.combat is not None:
            data["combat"] = SaveCombatStateMixin._serialize_combat(session.combat)
        if session.game_time is not None:
            data["game_time"] = session.game_time.to_dict()
        if session.map_data is not None:
            data["map_data"] = session.map_data.to_dict()
        if session.viewport is not None:
            data["viewport"] = session.viewport.to_dict()
        if session.spatial_index is not None:
            data["spatial_entities"] = [entity.to_dict() for entity in session.spatial_index.all_entities()]
        if session.player_entity is not None:
            data["player_entity"] = session.player_entity.to_dict()
        if session.ap_tracker is not None:
            data["ap_tracker"] = session.ap_tracker.to_dict()
        if getattr(session, "physical_inventory", None) is not None:
            data["physical_inventory"] = session.physical_inventory.to_dict()
        data["inventory"] = list(session.inventory) if session.inventory else []
        data["equipment"] = dict(session.equipment) if session.equipment else {}

        if session.entities:
            serialized_entities = {}
            for entity_id, entity in session.entities.items():
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

        if session.world_state is not None:
            data["world_state"] = session.world_state.to_dict()
        if session.npc_memory is not None:
            data["npc_memory"] = session.npc_memory.to_dict()
        if session.cascade_engine is not None:
            data["cascade_engine"] = session.cascade_engine.to_dict()
        if session.location_stock is not None:
            data["location_stock"] = session.location_stock.to_dict()
        if session.rumor_network is not None:
            data["rumor_network"] = session.rumor_network.to_dict()
        if session.quest_tracker is not None:
            data["quest_tracker"] = session.quest_tracker.to_dict()
        if session.body_tracker is not None:
            data["body_tracker"] = session.body_tracker.to_dict()
        if session.caravan_manager is not None:
            data["caravan_manager"] = session.caravan_manager.to_dict()
        if session.history_seed is not None:
            data["history_seed"] = session.history_seed.to_dict()

        from engine.api.game_session import GameSession

        data["quest_offers"] = GameSession.normalize_quest_offers(
            getattr(session, "quest_offers", []),
            default_source="authored",
        )
        data["campaign_state"] = dict(getattr(session, "campaign_state", {}))
        data["narration_context"] = dict(getattr(session, "narration_context", {}))
        data["conversation_state"] = dict(getattr(session, "conversation_state", {}))
        data["timed_conditions"] = copy.deepcopy(getattr(session, "timed_conditions", {}))
        data["last_save_slot"] = getattr(session, "last_save_slot", None)
        return data

    @staticmethod
    def _deserialize_session(data: Dict[str, Any]):
        from datetime import datetime as dt

        from engine.api.game_session import GameSession
        from engine.core.character import Character
        from engine.core.dm_agent import DMContext, SceneType
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

        player = Character.from_dict(data["player"])
        dm_context = None
        if "dm_context" in data:
            dm_context = DMContext.from_dict(data["dm_context"], party=[player])
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
                session_id=data.get("session_id", "restored"),
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

        session = object.__new__(GameSession)
        session.session_id = data.get("session_id", "restored")
        session.player = player
        session.dm_context = dm_context if dm_context else DMContext(
            scene_type=SceneType.EXPLORATION,
            location="Unknown",
            party=[player],
        )
        session.combat = SaveCombatStateMixin._deserialize_combat(data.get("combat"), player)
        session.world_state = world_state
        session.npc_memory = npc_memory
        session.cascade_engine = cascade_engine
        session.created_at = dt.fromisoformat(data["created_at"]) if "created_at" in data else dt.now()
        session.last_action = dt.fromisoformat(data["last_action"]) if "last_action" in data else dt.now()
        session.position = data.get("position", [0, 0])
        session.facing = data.get("facing", "north")
        session.game_time = game_time
        session.name_gen = None
        session.location_stock = location_stock
        session.rumor_network = rumor_network
        session.quest_tracker = quest_tracker
        session.body_tracker = body_tracker
        session.caravan_manager = caravan_manager
        session.history_seed = history_seed

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
        session.entities = raw_entities
        session.quest_offers = GameSession.normalize_quest_offers(
            data.get("quest_offers", []),
            default_source="authored",
        )
        session.campaign_state = dict(data.get("campaign_state", {}))
        session.narration_context = dict(data.get("narration_context", {}))
        session.conversation_state = normalize_conversation_state(data.get("conversation_state", {}))
        session.timed_conditions = copy.deepcopy(data.get("timed_conditions", {}))
        session.last_save_slot = data.get("last_save_slot")
        session.map_data = map_data
        session.spatial_index = spatial_index
        session.viewport = viewport
        session.player_entity = player_entity
        session.ap_tracker = ap_tracker

        if "physical_inventory" in data:
            session.physical_inventory = PhysicalInventory.from_dict(data["physical_inventory"])
        else:
            session.physical_inventory = PhysicalInventory()
            session.inventory = data.get("inventory", [])
            default_equipment = {
                "weapon": None,
                "armor": None,
                "shield": None,
                "helmet": None,
                "boots": None,
                "gloves": None,
                "ring": None,
                "amulet": None,
            }
            saved_equip = data.get("equipment", {})
            default_equipment.update(saved_equip)
            session.equipment = default_equipment

        if session.world_state is None:
            from engine.world import WorldState as WS

            session.world_state = WS(game_id=session.session_id)
        if session.npc_memory is None:
            session.npc_memory = NPCMemoryManager(session_id=session.session_id)
        if session.game_time is None:
            session.game_time = LivingGameTime(hour=8)
        if session.name_gen is None:
            from engine.world.naming import NameGenerator

            session.name_gen = NameGenerator()
        if session.location_stock is None:
            session.location_stock = LocationStock(
                location_id="default",
                baseline=get_location_stock_baseline(),
            )
        if session.rumor_network is None:
            session.rumor_network = RumorNetwork()
        if session.quest_tracker is None:
            session.quest_tracker = QuestTracker()
        if session.body_tracker is None:
            session.body_tracker = BodyPartTracker()
        if session.caravan_manager is None:
            session.caravan_manager = CaravanManager()
        if session.history_seed is None:
            import random

            session.history_seed = HistorySeed().generate(seed=random.randint(0, 999999))
        if session.ap_tracker is None:
            dominant_class = (player.dominant_class or next(iter(player.classes), "warrior") or "warrior")
            session.ap_tracker = ActionPointTracker(max_ap=CLASS_AP.get(str(dominant_class).lower(), 4))

        if player_entity is None:
            session.player_entity = Entity(
                id="player",
                entity_type=EntityType.NPC,
                name=player.name,
                position=tuple(session.position),
                glyph="@",
                color="white",
                blocking=True,
                hp=player.hp,
                max_hp=player.max_hp,
                disposition="friendly",
            )
        else:
            session.player_entity = player_entity
            session.player_entity.position = tuple(session.position)
            session.player_entity.hp = player.hp
            session.player_entity.max_hp = player.max_hp
            session.player_entity.blocking = True

        if session.spatial_index.get_position("player") is None:
            session.spatial_index.add(session.player_entity)

        if not spatial_entities_present and session.entities:
            for entity_id, record in session.entities.items():
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
                if session.spatial_index.get_position(entity_id) is None:
                    session.spatial_index.add(live_entity)

        if session.viewport is None:
            session.viewport = Viewport(width=40, height=20)
            session.viewport.center_on(session.position[0], session.position[1])

        if session.viewport is not None and session.map_data is not None:
            if viewport_missing:
                session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0],
                session.position[1],
                radius=8,
            )
        if hasattr(session, "reattach_entity_refs"):
            session.reattach_entity_refs()
        if hasattr(session, "ensure_consistency"):
            session.ensure_consistency()
        return session
