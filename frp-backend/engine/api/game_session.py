"""
Ember RPG - API Layer
GameSession: per-player game state container
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime
import copy
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
from engine.map import MapData, TownGenerator, DungeonGenerator, WildernessGenerator


DEFAULT_EQUIPMENT_SLOTS = {
    "weapon": None,
    "armor": None,
    "shield": None,
    "helmet": None,
    "boots": None,
    "gloves": None,
    "ring": None,
    "amulet": None,
}

LEGACY_SLOT_ALIASES = {
    "offhand": "shield",
    "off_hand": "shield",
    "accessory": "ring",
}


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
    quest_offers: List[Dict[str, Any]] = field(default_factory=list)
    campaign_state: Dict[str, Any] = field(default_factory=dict)
    narration_context: Dict[str, Any] = field(default_factory=dict)
    last_save_slot: Optional[str] = None

    # --- Entity / Spatial / Viewport / AP fields ---
    map_data: Optional[MapData] = None
    spatial_index: Optional[SpatialIndex] = None
    viewport: Optional[Viewport] = None
    player_entity: Optional[Entity] = None
    ap_tracker: Optional[ActionPointTracker] = None
    inventory: List[Dict] = field(default_factory=list)
    equipment: Dict[str, Optional[Dict]] = field(default_factory=lambda: dict(DEFAULT_EQUIPMENT_SLOTS))

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
            seed = hash(self.session_id) % 1000000
            location = (self.dm_context.location if self.dm_context else "").lower()
            if any(word in location for word in ["dungeon", "cave", "crypt", "ruin", "tower", "keep"]):
                gen = DungeonGenerator(seed=seed)
            elif any(word in location for word in ["forest", "road", "wilderness", "swamp", "wilds"]):
                gen = WildernessGenerator(seed=seed)
            else:
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

    def touch(self):
        """Update last_action timestamp."""
        self.last_action = datetime.now()

    def in_combat(self) -> bool:
        """Return True if session has active combat."""
        return self.combat is not None and not self.combat.combat_ended

    @staticmethod
    def _canonical_slot(slot: Optional[str]) -> Optional[str]:
        if slot is None:
            return None
        slot_lower = slot.lower().strip()
        return LEGACY_SLOT_ALIASES.get(slot_lower, slot_lower)

    @staticmethod
    def _display_name(item_id: str) -> str:
        return item_id.replace("_", " ").strip().title() or "Unknown Item"

    @classmethod
    def _infer_slot(cls, item: Dict[str, Any]) -> Optional[str]:
        item_type = str(item.get("type", "")).lower()
        item_id = str(item.get("id", "")).lower()
        name = str(item.get("name", "")).lower()
        slot = cls._canonical_slot(item.get("slot"))
        if slot:
            return slot
        candidates = f"{item_type} {item_id} {name}"
        if "shield" in candidates or item_type == "shield":
            return "shield"
        if "helmet" in candidates or "helm" in candidates:
            return "helmet"
        if "boot" in candidates:
            return "boots"
        if "glove" in candidates or "gauntlet" in candidates:
            return "gloves"
        if "ring" in candidates:
            return "ring"
        if "amulet" in candidates or "necklace" in candidates:
            return "amulet"
        if "armor" in candidates or "mail" in candidates or "robe" in candidates:
            return "armor"
        if item_type == "weapon" or any(word in candidates for word in ["sword", "axe", "dagger", "mace", "staff", "bow", "wand", "hammer"]):
            return "weapon"
        return None

    @classmethod
    def _normalize_item_record(cls, item: Any) -> Dict[str, Any]:
        if isinstance(item, str):
            data: Dict[str, Any] = {"id": item, "name": cls._display_name(item), "qty": 1}
        else:
            data = dict(item or {})
        item_id = str(data.get("id") or data.get("item_id") or data.get("name", "")).strip()
        if not item_id:
            item_id = f"item_{uuid.uuid4().hex[:8]}"
        data["id"] = item_id
        data["name"] = str(data.get("name") or cls._display_name(item_id))
        qty = data.get("qty", data.get("quantity", 1))
        try:
            data["qty"] = max(1, int(qty))
        except (TypeError, ValueError):
            data["qty"] = 1
        slot = cls._infer_slot(data)
        if slot:
            data["slot"] = slot
        data.setdefault("type", slot or "item")
        quality = data.get("quality")
        if hasattr(quality, "value"):
            data["quality"] = quality.value
        data.setdefault("instance_id", data.get("ground_instance_id") or f"{item_id}-{uuid.uuid4().hex[:8]}")
        if data.get("ground_instance_id") is None and data.get("entity_id"):
            data["ground_instance_id"] = data["entity_id"]
        return data

    @classmethod
    def _item_stack_key(cls, item: Dict[str, Any]) -> tuple:
        return (
            item.get("id"),
            item.get("name"),
            item.get("type"),
            item.get("slot"),
            item.get("material"),
            item.get("quality"),
            item.get("damage"),
            item.get("ac_bonus"),
            item.get("heal"),
            item.get("restore_sp"),
            item.get("uses"),
        )

    @classmethod
    def _is_stackable(cls, item: Dict[str, Any]) -> bool:
        if item.get("slot"):
            return False
        if item.get("uses") is not None:
            return False
        return item.get("type") not in {"weapon", "armor", "shield"}

    @staticmethod
    def _canonical_offer_source(source: Optional[str], default_source: str = "authored") -> str:
        source_value = str(source or default_source or "authored").strip().lower()
        if source_value not in {"authored", "emergent"}:
            return "authored"
        return source_value

    @classmethod
    def normalize_quest_offer(cls, offer: Any, default_source: str = "authored") -> Dict[str, Any]:
        data = copy.deepcopy(dict(offer or {}))
        offer_id = str(data.get("id") or "").strip()
        if not offer_id:
            offer_id = f"quest_offer_{uuid.uuid4().hex[:8]}"
        data["id"] = offer_id
        data["source"] = cls._canonical_offer_source(data.get("source"), default_source)
        return data

    @classmethod
    def normalize_quest_offers(
        cls,
        offers: Optional[List[Dict[str, Any]]],
        default_source: str = "authored",
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for offer in offers or []:
            normalized_offer = cls.normalize_quest_offer(offer, default_source=default_source)
            offer_id = normalized_offer["id"]
            if offer_id in seen_ids:
                continue
            normalized.append(normalized_offer)
            seen_ids.add(offer_id)
        return normalized

    @classmethod
    def merge_quest_offers(
        cls,
        existing: Optional[List[Dict[str, Any]]],
        new_offers: Optional[List[Dict[str, Any]]],
        new_default_source: str = "emergent",
    ) -> List[Dict[str, Any]]:
        merged = cls.normalize_quest_offers(existing, default_source="authored")
        seen_ids = {offer["id"] for offer in merged}
        for offer in cls.normalize_quest_offers(new_offers, default_source=new_default_source):
            if offer["id"] in seen_ids:
                continue
            merged.append(offer)
            seen_ids.add(offer["id"])
        return merged

    def sync_entity_record(self, entity_id: str, entity_ref: Optional[Entity] = None) -> Optional[Dict[str, Any]]:
        record = self.entities.get(entity_id)
        if record is None:
            return None
        live_entity = entity_ref or record.get("entity_ref")
        if live_entity is None:
            return record

        record["entity_ref"] = live_entity
        record["position"] = [live_entity.position[0], live_entity.position[1]]
        record["hp"] = live_entity.hp
        record["max_hp"] = live_entity.max_hp
        record["alive"] = live_entity.alive
        record["blocking"] = live_entity.blocking
        record.setdefault("name", live_entity.name)
        record.setdefault("type", live_entity.entity_type.value)
        if getattr(live_entity, "faction", None) is not None:
            record.setdefault("faction", live_entity.faction)
        if getattr(live_entity, "job", None) is not None:
            record.setdefault("role", live_entity.job)

        live_body = getattr(live_entity, "body", None)
        if live_body is not None:
            record["body"] = live_body
        elif record.get("body") is not None:
            live_entity.body = record["body"]

        live_needs = getattr(live_entity, "needs", None)
        if live_needs is not None:
            record["needs"] = live_needs
        elif record.get("needs") is not None:
            live_entity.needs = record["needs"]

        live_schedule = getattr(live_entity, "schedule", None)
        if live_schedule is not None:
            record["schedule"] = live_schedule
        elif record.get("schedule") is not None:
            live_entity.schedule = record["schedule"]

        return record

    def reattach_entity_refs(self) -> None:
        if not self.entities or self.spatial_index is None:
            return
        live_entities = {entity.id: entity for entity in self.spatial_index.all_entities()}
        for entity_id in list(self.entities.keys()):
            live_entity = live_entities.get(entity_id)
            if live_entity is None:
                continue
            self.sync_entity_record(entity_id, live_entity)

    @staticmethod
    def _armor_type_from_item(item: Optional[Dict[str, Any]]) -> str:
        if not item:
            return "none"
        candidates = f"{item.get('id', '')} {item.get('name', '')} {item.get('material', '')}".lower()
        if "plate" in candidates or item.get("material") == "steel":
            return "plate_armor"
        if "chain" in candidates or item.get("material") == "iron":
            return "chain_mail"
        if "leather" in candidates:
            return "leather"
        if "robe" in candidates or "cloth" in candidates:
            return "cloth"
        return "none"

    @staticmethod
    def _armor_tokens(slot: str, item: Dict[str, Any]) -> List[str]:
        candidates = f"{item.get('id', '')} {item.get('name', '')} {item.get('material', '')}".lower()
        if slot == "helmet":
            return ["helmet"]
        if slot == "shield":
            return ["shield"]
        if slot == "gloves":
            return ["gauntlets"]
        if slot == "boots":
            return ["boots"]
        if slot != "armor":
            return []
        if "plate" in candidates:
            return ["breastplate"]
        if "chain" in candidates or item.get("material") in {"iron", "steel"}:
            return ["chainmail"]
        if "leather" in candidates:
            return ["boots"]
        return []

    def inventory_item_ids(self) -> List[str]:
        ids: List[str] = []
        for item in self.inventory:
            ids.extend([item.get("id", "")] * max(1, int(item.get("qty", 1))))
        return [item_id for item_id in ids if item_id]

    def equipment_ids(self) -> Dict[str, Optional[str]]:
        equipment_ids: Dict[str, Optional[str]] = {}
        for slot in DEFAULT_EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                equipment_ids[slot] = item.get("id")
        if equipment_ids.get("shield"):
            equipment_ids["offhand"] = equipment_ids["shield"]
        return equipment_ids

    def ensure_consistency(self) -> None:
        raw_inventory = list(self.inventory or [])
        if not raw_inventory and hasattr(self.player, "inventory"):
            raw_inventory = list(getattr(self.player, "inventory", []) or [])
        normalized_inventory: List[Dict[str, Any]] = []
        for item in raw_inventory:
            normalized = self._normalize_item_record(item)
            if self._is_stackable(normalized):
                existing = next(
                    (entry for entry in normalized_inventory if self._item_stack_key(entry) == self._item_stack_key(normalized)),
                    None,
                )
                if existing is not None:
                    existing["qty"] += normalized.get("qty", 1)
                    continue
            normalized_inventory.append(normalized)
        self.inventory = normalized_inventory

        merged_equipment = dict(DEFAULT_EQUIPMENT_SLOTS)
        raw_equipment = dict(self.equipment or {})
        if not any(raw_equipment.values()) and hasattr(self.player, "equipment"):
            raw_equipment.update(getattr(self.player, "equipment", {}) or {})
        for slot_name, item in raw_equipment.items():
            slot = self._canonical_slot(slot_name)
            if slot not in merged_equipment:
                continue
            if item is None:
                merged_equipment[slot] = None
            elif isinstance(item, str):
                inv_item = next((entry for entry in self.inventory if entry.get("id") == item), None)
                merged_equipment[slot] = copy.deepcopy(inv_item) if inv_item else self._normalize_item_record({"id": item, "slot": slot})
            else:
                normalized = self._normalize_item_record(item)
                normalized["slot"] = slot
                merged_equipment[slot] = normalized
        self.equipment = merged_equipment
        self.quest_offers = self.normalize_quest_offers(self.quest_offers, default_source="authored")
        self.reattach_entity_refs()
        self.sync_player_state()

    def sync_player_state(self) -> None:
        if self.player is None:
            return
        self.player.inventory = self.inventory_item_ids()
        self.player.equipment = self.equipment_ids()
        base_ac = getattr(self.player, "base_ac", None)
        if base_ac is None:
            base_ac = getattr(self.player, "_base_ac", self.player.ac or 10)
        self.player.base_ac = base_ac
        self.player._base_ac = base_ac
        armor_bonus = sum((item or {}).get("ac_bonus", 0) for item in self.equipment.values())
        self.player.ac = base_ac + armor_bonus
        equipped_armor: List[str] = []
        for slot, item in self.equipment.items():
            if item:
                equipped_armor.extend(self._armor_tokens(slot, item))
        self.player.equipped_armor = equipped_armor
        weapon = self.equipment.get("weapon")
        self.player.weapon_material = (weapon or {}).get("material", "iron")
        if self.ap_tracker is not None:
            self.player.ap = self.ap_tracker.current_ap
            self.player.max_ap = self.ap_tracker.max_ap
            self.ap_tracker.set_armor(self._armor_type_from_item(self.equipment.get("armor")))
        if self.player_entity is not None:
            self.player_entity.hp = self.player.hp
            self.player_entity.max_hp = self.player.max_hp
            self.player_entity.position = tuple(self.position)
        if self.dm_context is not None:
            self.dm_context.party = [self.player]

    def add_item(self, item: Any, merge: bool = True) -> Dict[str, Any]:
        normalized = self._normalize_item_record(item)
        if merge and self._is_stackable(normalized):
            existing = next(
                (entry for entry in self.inventory if self._item_stack_key(entry) == self._item_stack_key(normalized)),
                None,
            )
            if existing is not None:
                existing["qty"] += normalized.get("qty", 1)
                self.sync_player_state()
                return existing
        self.inventory.append(normalized)
        self.sync_player_state()
        return normalized

    def find_inventory_item(self, query: str) -> Optional[Dict[str, Any]]:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return None
        for item in self.inventory:
            if query_lower in {
                str(item.get("id", "")).lower(),
                str(item.get("instance_id", "")).lower(),
                str(item.get("ground_instance_id", "")).lower(),
            }:
                return item
            if query_lower in str(item.get("name", "")).lower() or query_lower in str(item.get("id", "")).lower():
                return item
        return None

    def remove_item(self, query: str, quantity: int = 1) -> Optional[Dict[str, Any]]:
        item = self.find_inventory_item(query)
        if item is None:
            return None
        qty = max(1, quantity)
        if item.get("qty", 1) > qty:
            item["qty"] -= qty
            detached = copy.deepcopy(item)
            detached["qty"] = qty
            detached["instance_id"] = f"{detached['id']}-{uuid.uuid4().hex[:8]}"
            self.sync_player_state()
            return detached
        self.inventory.remove(item)
        self.sync_player_state()
        return item

    def equip_item(self, query: str) -> Optional[Dict[str, Any]]:
        item = self.remove_item(query)
        if item is None:
            return None
        slot = self._infer_slot(item)
        if slot not in self.equipment:
            self.add_item(item)
            return None
        previous = self.equipment.get(slot)
        if previous is not None:
            self.add_item(previous)
        item["slot"] = slot
        self.equipment[slot] = item
        self.sync_player_state()
        return item

    def unequip_item(self, query: str) -> Optional[Dict[str, Any]]:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return None
        for slot, item in self.equipment.items():
            if item is None:
                continue
            if query_lower == slot or query_lower in str(item.get("id", "")).lower() or query_lower in str(item.get("name", "")).lower():
                self.equipment[slot] = None
                self.add_item(item)
                self.sync_player_state()
                return item
        return None

    def replace_with(self, other: "GameSession", preserve_session_id: bool = False) -> None:
        current_session_id = self.session_id
        for field_name in self.__dataclass_fields__:
            setattr(self, field_name, getattr(other, field_name))
        if preserve_session_id:
            self.session_id = current_session_id
        self.ensure_consistency()

    def to_dict(self) -> dict:
        """Serialize session state for API responses."""
        self.ensure_consistency()
        player_payload = {
            "name": self.player.name,
            "level": self.player.level,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "spell_points": self.player.spell_points,
            "max_spell_points": self.player.max_spell_points,
            "xp": self.player.xp,
            "classes": self.player.classes,
            "gold": getattr(self.player, "gold", 0),
            "inventory": copy.deepcopy(self.inventory),
            "equipment": {slot: copy.deepcopy(item) for slot, item in self.equipment.items() if item is not None},
            "position": list(self.position),
            "facing": self.facing,
        }
        result = {
            "session_id": self.session_id,
            "scene": self.dm_context.scene_type.value,
            "location": self.dm_context.location,
            "player": player_payload,
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
            result["player"]["ap"] = dict(result["ap"])

        # --- Inventory & Equipment ---
        if self.inventory:
            result["inventory"] = copy.deepcopy(self.inventory)
        if self.equipment:
            equipped = {slot: item for slot, item in self.equipment.items() if item is not None}
            if equipped:
                result["equipment"] = copy.deepcopy(equipped)

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
                ground_items = [ent for ent in spatial_entities if ent.get("entity_type") == EntityType.ITEM.value]
                if ground_items:
                    result["ground_items"] = ground_items

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
        if self.quest_offers:
            result["quest_offers"] = copy.deepcopy(self.quest_offers)
        if self.campaign_state:
            result["campaign_state"] = copy.deepcopy(self.campaign_state)

        if self.body_tracker:
            injuries = self.body_tracker.get_injury_effects()
            if injuries:
                result["body_status"] = injuries
        if self.narration_context:
            result["narration_context"] = copy.deepcopy(self.narration_context)
        if self.last_save_slot:
            result["last_save_slot"] = self.last_save_slot

        return result
