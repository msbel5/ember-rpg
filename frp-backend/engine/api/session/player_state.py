"""Player-state synchronization helpers for GameSession."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.api.session_utils import normalize_conversation_state
from engine.world.inventory import PhysicalInventory

from .constants import DEFAULT_EQUIPMENT_SLOTS, TIMED_CONDITION_NAMES


class SessionPlayerStateMixin:
    """Consistency and player-state synchronization methods."""

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
        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
        self.quest_offers = self.normalize_quest_offers(self.quest_offers, default_source="authored")
        current_turn = self.dm_context.turn if self.dm_context is not None else 0
        self.conversation_state = normalize_conversation_state(self.conversation_state, turn=current_turn)
        self.clear_expired_timed_conditions()
        self.reattach_entity_refs()
        self.sync_player_state()

    def sync_player_state(self) -> None:
        if self.player is None:
            return
        self.player.inventory = self.inventory_item_ids()
        self.player.equipment = self.equipment_ids()
        self.player.sync_derived_progression()
        active_timed = self.active_timed_conditions()
        persistent_conditions = [
            condition
            for condition in getattr(self.player, "conditions", [])
            if condition not in TIMED_CONDITION_NAMES
        ]
        for condition_name in active_timed:
            if condition_name not in persistent_conditions:
                persistent_conditions.append(condition_name)
        self.player.conditions = persistent_conditions
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
            self.ap_tracker.set_armor(self._armor_type_from_item(self.equipment.get("armor")))
            ap_current = self.ap_tracker.current_ap
            ap_max = self.ap_tracker.max_ap
            if self.in_combat() and self.combat is not None:
                player_combatant = next(
                    (combatant for combatant in self.combat.combatants if combatant.name == self.player.name),
                    None,
                )
                if player_combatant is not None:
                    ap_current = int(player_combatant.ap)
                    ap_max = 3
            self.player.ap = ap_current
            self.player.max_ap = ap_max
        if self.player_entity is not None:
            self.player_entity.hp = self.player.hp
            self.player_entity.max_hp = self.player.max_hp
            self.player_entity.position = tuple(self.position)
        if self.dm_context is not None:
            self.dm_context.party = [self.player]
