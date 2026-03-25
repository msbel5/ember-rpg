"""
Ember RPG -- Save/Load System
Serializes and deserializes complete game state to JSON files.
Provides full roundtrip fidelity for all game systems.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from engine.save.save_models import CURRENT_SCHEMA_VERSION

# ── Save directory (sibling of engine/) ──────────────────────────────
SAVE_DIR = Path(__file__).parent.parent.parent / "saves"


class SaveSystem:
    """Manages game save/load operations with full state roundtrip."""

    def __init__(self, save_dir: Path = SAVE_DIR):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_combat(combat) -> Optional[Dict[str, Any]]:
        if combat is None:
            return None
        return {
            "current_turn": combat.current_turn,
            "round": combat.round,
            "combat_ended": combat.combat_ended,
            "log": list(combat.log),
            "combatants": [
                {
                    "character": {
                        **combatant.character.to_dict(),
                        **(
                            {"_entity_id": getattr(combatant.character, "_entity_id")}
                            if hasattr(combatant.character, "_entity_id")
                            else {}
                        ),
                        **(
                            {"role": getattr(combatant.character, "role")}
                            if hasattr(combatant.character, "role")
                            else {}
                        ),
                        **(
                            {"equipped_armor": list(getattr(combatant.character, "equipped_armor", []))}
                            if hasattr(combatant.character, "equipped_armor")
                            else {}
                        ),
                        **(
                            {"weapon_material": getattr(combatant.character, "weapon_material")}
                            if hasattr(combatant.character, "weapon_material")
                            else {}
                        ),
                    },
                    "initiative": combatant.initiative,
                    "ap": combatant.ap,
                    "conditions": [condition.__dict__ for condition in combatant.conditions],
                    "is_dead": combatant.is_dead,
                }
                for combatant in combat.combatants
            ],
        }

    @staticmethod
    def _deserialize_combat(data: Optional[Dict[str, Any]], player):
        if not data:
            return None
        from engine.core.character import Character
        from engine.core.combat import CombatManager, Combatant, Condition

        combat = object.__new__(CombatManager)
        combat.combatants = []
        for combatant_data in data.get("combatants", []):
            char_data = dict(combatant_data.get("character", {}))
            entity_id = char_data.pop("_entity_id", None)
            role = char_data.pop("role", None)
            equipped_armor = list(char_data.pop("equipped_armor", []) or [])
            weapon_material = char_data.pop("weapon_material", None)
            character = player if char_data.get("name") == getattr(player, "name", None) else Character.from_dict(char_data)
            if entity_id is not None:
                character._entity_id = entity_id
            if role is not None:
                character.role = role
            if equipped_armor is not None:
                character.equipped_armor = equipped_armor
            if weapon_material is not None:
                character.weapon_material = weapon_material
            combat.combatants.append(
                Combatant(
                    character=character,
                    initiative=combatant_data.get("initiative", 0),
                    ap=combatant_data.get("ap", 3),
                    conditions=[Condition(**condition) for condition in combatant_data.get("conditions", [])],
                    is_dead=combatant_data.get("is_dead", False),
                )
            )
        combat.current_turn = data.get("current_turn", 0)
        combat.round = data.get("round", 1)
        combat.log = list(data.get("log", []))
        combat.combat_ended = data.get("combat_ended", False)
        return combat

    @staticmethod
    def _serialize_session(session) -> Dict[str, Any]:
        """Serialize a GameSession to a plain dict.

        Captures every subsystem so load_game can reconstruct perfectly.
        """
        if hasattr(session, "ensure_consistency"):
            session.ensure_consistency()

        data: Dict[str, Any] = {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_action": session.last_action.isoformat(),
            "position": list(session.position),
            "facing": session.facing,
        }

        # Player character
        data["player"] = session.player.to_dict()

        # DM context
        if session.dm_context is not None:
            data["dm_context"] = session.dm_context.to_dict()
        if session.combat is not None:
            data["combat"] = SaveSystem._serialize_combat(session.combat)

        # Game time (Living World GameTime from schedules)
        if session.game_time is not None:
            data["game_time"] = session.game_time.to_dict()

        # Map data (full tile grid)
        if session.map_data is not None:
            data["map_data"] = session.map_data.to_dict()

        # Viewport (center + fog_of_war explored set)
        if session.viewport is not None:
            data["viewport"] = session.viewport.to_dict()

        # Spatial index entities (serialize all Entity objects)
        if session.spatial_index is not None:
            entities = []
            for ent in session.spatial_index.all_entities():
                entities.append(ent.to_dict())
            data["spatial_entities"] = entities

        # Player entity (separate from spatial_index list for identity)
        if session.player_entity is not None:
            data["player_entity"] = session.player_entity.to_dict()

        # AP tracker
        if session.ap_tracker is not None:
            data["ap_tracker"] = session.ap_tracker.to_dict()

        # Physical Inventory (full grid-based system)
        if getattr(session, "physical_inventory", None) is not None:
            data["physical_inventory"] = session.physical_inventory.to_dict()
        # Legacy fallback fields for backward compatibility
        data["inventory"] = list(session.inventory) if session.inventory else []
        data["equipment"] = dict(session.equipment) if session.equipment else {}

        # Living World entities dict (legacy NPC dict)
        # NPCNeeds objects need serialization
        if session.entities:
            serialized_entities = {}
            for eid, ent in session.entities.items():
                ent_copy = dict(ent)
                needs = ent_copy.get("needs")
                if needs is not None and hasattr(needs, "to_dict"):
                    ent_copy["needs"] = needs.to_dict()
                schedule = ent_copy.get("schedule")
                if schedule is not None and hasattr(schedule, "to_dict"):
                    ent_copy["schedule"] = schedule.to_dict()
                body = ent_copy.get("body")
                if body is not None and hasattr(body, "to_dict"):
                    ent_copy["body"] = body.to_dict()
                # Remove non-serializable entity_ref
                ent_copy.pop("entity_ref", None)
                serialized_entities[eid] = ent_copy
            data["entities"] = serialized_entities

        # World state
        if session.world_state is not None:
            data["world_state"] = session.world_state.to_dict()

        # NPC memory
        if session.npc_memory is not None:
            data["npc_memory"] = session.npc_memory.to_dict()
        if session.cascade_engine is not None:
            data["cascade_engine"] = session.cascade_engine.to_dict()

        # Location stock
        if session.location_stock is not None:
            data["location_stock"] = session.location_stock.to_dict()

        # Rumor network
        if session.rumor_network is not None:
            data["rumor_network"] = session.rumor_network.to_dict()

        # Quest tracker
        if session.quest_tracker is not None:
            data["quest_tracker"] = session.quest_tracker.to_dict()

        # Body tracker
        if session.body_tracker is not None:
            data["body_tracker"] = session.body_tracker.to_dict()

        # Caravan manager
        if session.caravan_manager is not None:
            data["caravan_manager"] = session.caravan_manager.to_dict()

        # History seed
        if session.history_seed is not None:
            data["history_seed"] = session.history_seed.to_dict()
        from engine.api.game_session import GameSession

        data["quest_offers"] = GameSession.normalize_quest_offers(
            getattr(session, "quest_offers", []),
            default_source="authored",
        )
        data["campaign_state"] = dict(getattr(session, "campaign_state", {}))
        data["narration_context"] = dict(getattr(session, "narration_context", {}))
        data["last_save_slot"] = getattr(session, "last_save_slot", None)

        return data

    @staticmethod
    def _deserialize_session(data: Dict[str, Any]):
        """Reconstruct a GameSession from a saved dict.

        Rebuilds all subsystems: Character, DMContext, MapData,
        SpatialIndex, Viewport, AP tracker, Living World systems.
        """
        from engine.core.character import Character
        from engine.core.dm_agent import DMContext, SceneType
        from engine.api.game_session import GameSession
        from engine.map import MapData
        from engine.world.entity import Entity
        from engine.world.spatial_index import SpatialIndex
        from engine.world.viewport import Viewport
        from engine.world.action_points import ActionPointTracker
        from engine.world.schedules import GameTime as LivingGameTime
        from engine.world.economy import LocationStock
        from engine.world.rumors import RumorNetwork
        from engine.world.quest_timeout import QuestTracker
        from engine.world.body_parts import BodyPartTracker
        from engine.world.caravans import CaravanManager
        from engine.world.history import HistorySeed
        from engine.world import WorldState
        from engine.npc.npc_memory import NPCMemoryManager
        from engine.world.consequence import CascadeEngine

        # 1. Player character
        player = Character.from_dict(data["player"])

        # 2. DM context (needs party list)
        dm_context = None
        if "dm_context" in data:
            dm_context = DMContext.from_dict(data["dm_context"], party=[player])

        # 3. Map data (full tile grid reconstruction)
        map_data = None
        if "map_data" in data:
            map_data = MapData.from_dict(data["map_data"])

        # 4. Game time
        game_time = None
        if "game_time" in data:
            game_time = LivingGameTime.from_dict(data["game_time"])

        # 5. Viewport
        viewport = None
        if "viewport" in data:
            viewport = Viewport.from_dict(data["viewport"])

        # 6. AP tracker
        ap_tracker = None
        if "ap_tracker" in data:
            ap_tracker = ActionPointTracker.from_dict(data["ap_tracker"])

        # 7. Location stock
        location_stock = None
        if "location_stock" in data:
            location_stock = LocationStock.from_dict(data["location_stock"])

        # 8. Rumor network
        rumor_network = None
        if "rumor_network" in data:
            rumor_network = RumorNetwork.from_dict(data["rumor_network"])

        # 9. Quest tracker
        quest_tracker = None
        if "quest_tracker" in data:
            quest_tracker = QuestTracker.from_dict(data["quest_tracker"])

        # 10. Body tracker
        body_tracker = None
        if "body_tracker" in data:
            body_tracker = BodyPartTracker.from_dict(data["body_tracker"])

        # 11. Caravan manager
        caravan_manager = None
        if "caravan_manager" in data:
            caravan_manager = CaravanManager.from_dict(data["caravan_manager"])

        # 12. History seed
        history_seed = None
        if "history_seed" in data:
            history_seed = HistorySeed.from_dict(data["history_seed"])

        # 13. World state
        world_state = None
        if "world_state" in data:
            world_state = WorldState.from_dict(data["world_state"])

        # 14. NPC memory
        npc_memory = None
        if "npc_memory" in data:
            npc_memory = NPCMemoryManager.from_dict(
                session_id=data.get("session_id", "restored"),
                data=data["npc_memory"],
            )
        cascade_engine = CascadeEngine()
        if "cascade_engine" in data:
            cascade_engine.from_dict(data["cascade_engine"])

        # 15. Spatial index (rebuild from entity list)
        spatial_index = SpatialIndex()
        player_entity = None

        if "spatial_entities" in data:
            for ent_data in data["spatial_entities"]:
                entity = Entity.from_dict(ent_data)
                if entity.id == "player":
                    player_entity = entity
                spatial_index.add(entity)

        # If player_entity was serialized separately and not in spatial list
        if player_entity is None and "player_entity" in data:
            player_entity = Entity.from_dict(data["player_entity"])
            # Add to spatial index if not already there
            if spatial_index.get_position("player") is None:
                spatial_index.add(player_entity)

        # Build the GameSession without triggering __post_init__ defaults
        # by passing all fields explicitly
        from datetime import datetime as dt

        session = object.__new__(GameSession)
        session.session_id = data.get("session_id", "restored")
        session.player = player
        session.dm_context = dm_context if dm_context else DMContext(
            scene_type=SceneType.EXPLORATION,
            location="Unknown",
            party=[player],
        )
        session.combat = SaveSystem._deserialize_combat(data.get("combat"), player)
        session.world_state = world_state
        session.npc_memory = npc_memory
        session.cascade_engine = cascade_engine
        session.created_at = (
            dt.fromisoformat(data["created_at"])
            if "created_at" in data
            else dt.now()
        )
        session.last_action = (
            dt.fromisoformat(data["last_action"])
            if "last_action" in data
            else dt.now()
        )
        session.position = data.get("position", [0, 0])
        session.facing = data.get("facing", "north")

        # Living World fields
        session.game_time = game_time
        session.name_gen = None  # NameGenerator is stateless, recreated on demand
        session.location_stock = location_stock
        session.rumor_network = rumor_network
        session.quest_tracker = quest_tracker
        session.body_tracker = body_tracker
        session.caravan_manager = caravan_manager
        session.history_seed = history_seed
        # Reconstruct entities with NPCNeeds objects
        raw_entities = data.get("entities", {})
        for eid, ent in raw_entities.items():
            needs_data = ent.get("needs")
            if isinstance(needs_data, dict):
                from engine.world.npc_needs import NPCNeeds
                ent["needs"] = NPCNeeds.from_dict(needs_data)
            schedule_data = ent.get("schedule")
            if isinstance(schedule_data, dict) and "npc_id" in schedule_data:
                from engine.world.schedules import NPCSchedule
                ent["schedule"] = NPCSchedule.from_dict(schedule_data)
            body_data = ent.get("body")
            if isinstance(body_data, dict):
                ent["body"] = BodyPartTracker.from_dict(body_data)
        session.entities = raw_entities
        session.quest_offers = GameSession.normalize_quest_offers(
            data.get("quest_offers", []),
            default_source="authored",
        )
        session.campaign_state = dict(data.get("campaign_state", {}))
        session.narration_context = dict(data.get("narration_context", {}))
        session.last_save_slot = data.get("last_save_slot")

        # Entity / Spatial / Viewport / AP fields
        session.map_data = map_data
        session.spatial_index = spatial_index
        session.viewport = viewport
        session.player_entity = player_entity
        session.ap_tracker = ap_tracker

        # Physical Inventory system
        from engine.world.inventory import PhysicalInventory
        if "physical_inventory" in data:
            session.physical_inventory = PhysicalInventory.from_dict(data["physical_inventory"])
        else:
            # Migrate from legacy flat inventory/equipment format
            session.physical_inventory = PhysicalInventory()
            session.inventory = data.get("inventory", [])
            _default_equipment = {
                "weapon": None, "armor": None, "shield": None, "helmet": None,
                "boots": None, "gloves": None, "ring": None, "amulet": None,
            }
            saved_equip = data.get("equipment", {})
            _default_equipment.update(saved_equip)
            session.equipment = _default_equipment

        # Lazy-init subsystems that were None
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
                baseline={"food": 20, "ale": 10, "iron_bar": 5, "bread": 15,
                          "healing_potion": 3, "leather": 8, "cloth": 10},
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

        # Recompute viewport FOV if we have map + position
        if session.viewport is not None and session.map_data is not None:
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0], session.position[1],
                radius=8,
            )
        if hasattr(session, "reattach_entity_refs"):
            session.reattach_entity_refs()
        if hasattr(session, "ensure_consistency"):
            session.ensure_consistency()

        return session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_game(
        self,
        session,
        slot_name: str = "autosave",
        *,
        player_name: Optional[str] = None,
    ) -> str:
        """Save full game state to a JSON file.

        Args:
            session: GameSession instance
            slot_name: Save slot name (default "autosave")

        Returns:
            Path to the saved file as string
        """
        if hasattr(session, "last_save_slot"):
            session.last_save_slot = slot_name
        state = self._serialize_session(session)
        save_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "slot_name": slot_name,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name or (session.player.name if session.player else "Unknown"),
            "player_level": session.player.level if session.player else 1,
            "location": session.dm_context.location if session.dm_context else "Unknown",
            "game_time_display": (
                session.game_time.to_string()
                if session.game_time else "Day 1, 08:00"
            ),
            "session_state": state,
        }

        filename = f"{slot_name}.json"
        filepath = self.save_dir / filename

        # Atomic write via temp file
        tmp = filepath.with_suffix(".tmp")
        tmp.write_text(json.dumps(save_data, indent=2, default=str), encoding="utf-8")
        # On Windows, rename fails if target exists; remove first
        if filepath.exists():
            filepath.unlink()
        tmp.rename(filepath)

        return str(filepath)

    def read_save(self, slot_name: str) -> Optional[Dict[str, Any]]:
        filepath = self.save_dir / f"{slot_name}.json"
        if not filepath.exists():
            return None
        text = filepath.read_text(encoding="utf-8")
        return json.loads(text)

    def get_save_metadata(self, slot_name: str) -> Optional[Dict[str, Any]]:
        try:
            save_data = self.read_save(slot_name)
        except json.JSONDecodeError:
            return None
        if save_data is None:
            return None
        return {
            "slot_name": save_data.get("slot_name", slot_name),
            "player_name": save_data.get("player_name", "Unknown"),
            "player_level": save_data.get("player_level", 1),
            "location": save_data.get("location", "Unknown"),
            "timestamp": save_data.get("timestamp", ""),
            "game_time": save_data.get("game_time_display", ""),
            "schema_version": save_data.get("schema_version", ""),
            "session_id": save_data.get("session_state", {}).get("session_id"),
        }

    def find_slot_by_session_id(self, session_id: str) -> Optional[str]:
        for save in self.list_saves():
            if save.get("session_id") == session_id:
                return save.get("slot_name")
        return None

    def load_game(self, slot_name: str = "autosave", *, strict: bool = False):
        """Load game state from JSON file and reconstruct GameSession.

        Args:
            slot_name: Save slot name

        Returns:
            Reconstructed GameSession, or None if file not found
        """
        try:
            save_data = self.read_save(slot_name)
            if save_data is None:
                if strict:
                    raise FileNotFoundError(slot_name)
                return None
            state = save_data.get("session_state", {})
            if not state or "player" not in state:
                if strict:
                    raise ValueError(f"Corrupt save slot: {slot_name}")
                return None  # Corrupt/incomplete save
            return self._deserialize_session(state)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            if strict:
                raise
            return None  # Corrupt save file

    def list_saves(self, player_name: Optional[str] = None) -> List[Dict]:
        """List all save files with metadata (sorted newest first)."""
        saves = []
        for f in sorted(self.save_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entry = {
                    "slot_name": data.get("slot_name", f.stem),
                    "player_name": data.get("player_name", "Unknown"),
                    "player_level": data.get("player_level", 1),
                    "location": data.get("location", "Unknown"),
                    "timestamp": data.get("timestamp", ""),
                    "game_time": data.get("game_time_display", ""),
                    "schema_version": data.get("schema_version", ""),
                    "session_id": data.get("session_state", {}).get("session_id"),
                }
                if player_name and entry["player_name"] != player_name:
                    continue
                saves.append(entry)
            except (json.JSONDecodeError, KeyError):
                pass  # Skip corrupt files
        return saves

    def delete_save(self, slot_name: str) -> bool:
        """Delete a save file.

        Returns:
            True if deleted, False if not found
        """
        filename = f"{slot_name}.json"
        filepath = self.save_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def autosave(self, session) -> str:
        """Quick autosave (called after important events)."""
        return self.save_game(session, "autosave")

    def save_exists(self, slot_name: str) -> bool:
        """Check if a save slot exists."""
        return (self.save_dir / f"{slot_name}.json").exists()
