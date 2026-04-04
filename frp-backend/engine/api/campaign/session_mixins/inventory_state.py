"""Inventory and equipment helpers for GameSession."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.api.session_utils import (
    canonical_offer_source,
    canonical_slot,
    display_name,
    infer_slot,
    is_stackable,
    item_stack_key,
    merge_quest_offers as merge_quest_offer_payloads,
    normalize_item_record,
    normalize_quest_offer as normalize_quest_offer_payload,
    normalize_quest_offers as normalize_quest_offer_payloads,
)
from engine.world.inventory import ItemStack, PhysicalInventory

from .constants import DEFAULT_EQUIPMENT_SLOTS, LEGACY_SLOT_ALIASES


class SessionInventoryMixin:
    """Inventory, equipment, and quest-offer normalization methods."""

    @property
    def inventory(self) -> List[Dict]:
        if self.physical_inventory is None:
            return []
        return self.physical_inventory.all_items_flat()

    @inventory.setter
    def inventory(self, value: List[Dict]) -> None:
        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
        for container in self.physical_inventory.all_containers():
            for inst_id in list(container.placed_items.keys()):
                container.remove_item(inst_id)
        for item_dict in (value or []):
            normalized = self._normalize_item_record(item_dict)
            stack = ItemStack.from_legacy_dict(normalized)
            self.physical_inventory.add_item_auto(stack)

    @property
    def equipment(self) -> Dict[str, Optional[Dict]]:
        if self.physical_inventory is None:
            return dict(DEFAULT_EQUIPMENT_SLOTS)
        result = {}
        for slot in DEFAULT_EQUIPMENT_SLOTS:
            stack = self.physical_inventory.equipment.get(slot)
            result[slot] = stack.to_legacy_dict() if stack is not None else None
        return result

    @equipment.setter
    def equipment(self, value: Dict[str, Optional[Dict]]) -> None:
        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
        for slot in DEFAULT_EQUIPMENT_SLOTS:
            item = (value or {}).get(slot)
            if item is None:
                self.physical_inventory.equipment[slot] = None
            elif isinstance(item, dict):
                normalized = self._normalize_item_record(item)
                stack = ItemStack.from_legacy_dict(normalized)
                self.physical_inventory.equipment[slot] = stack
            elif isinstance(item, str):
                normalized = self._normalize_item_record({"id": item, "slot": slot})
                stack = ItemStack.from_legacy_dict(normalized)
                self.physical_inventory.equipment[slot] = stack

    def set_equipment_slot(self, slot: str, item: Any) -> None:
        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
        canon = self._canonical_slot(slot) or slot
        if canon not in DEFAULT_EQUIPMENT_SLOTS and canon not in self.physical_inventory.equipment:
            return
        if item is None:
            self.physical_inventory.equipment[canon] = None
            return
        if isinstance(item, dict):
            item_id = item.get("id", "")
            if item_id:
                self.physical_inventory.remove_item(item_id)
            normalized = self._normalize_item_record(item)
            normalized["slot"] = canon
            stack = ItemStack.from_legacy_dict(normalized)
            self.physical_inventory.equipment[canon] = stack
            return
        if isinstance(item, str):
            self.physical_inventory.remove_item(item)
            normalized = self._normalize_item_record({"id": item, "slot": canon})
            stack = ItemStack.from_legacy_dict(normalized)
            self.physical_inventory.equipment[canon] = stack

    def get_equipment_slot(self, slot: str) -> Optional[Dict[str, Any]]:
        if self.physical_inventory is None:
            return None
        canon = self._canonical_slot(slot) or slot
        stack = self.physical_inventory.equipment.get(canon)
        if stack is None:
            return None
        return stack.to_legacy_dict()

    @staticmethod
    def _canonical_slot(slot: Optional[str]) -> Optional[str]:
        return canonical_slot(slot, LEGACY_SLOT_ALIASES)

    @staticmethod
    def _display_name(item_id: str) -> str:
        return display_name(item_id)

    @classmethod
    def _infer_slot(cls, item: Dict[str, Any]) -> Optional[str]:
        return infer_slot(item, LEGACY_SLOT_ALIASES)

    @classmethod
    def _normalize_item_record(cls, item: Any) -> Dict[str, Any]:
        return normalize_item_record(item, LEGACY_SLOT_ALIASES)

    @classmethod
    def _item_stack_key(cls, item: Dict[str, Any]) -> tuple:
        return item_stack_key(item)

    @classmethod
    def _is_stackable(cls, item: Dict[str, Any]) -> bool:
        return is_stackable(item)

    @staticmethod
    def _canonical_offer_source(source: Optional[str], default_source: str = "authored") -> str:
        return canonical_offer_source(source, default_source)

    @classmethod
    def normalize_quest_offer(cls, offer: Any, default_source: str = "authored") -> Dict[str, Any]:
        return normalize_quest_offer_payload(offer, default_source)

    @classmethod
    def normalize_quest_offers(
        cls,
        offers: Optional[List[Dict[str, Any]]],
        default_source: str = "authored",
    ) -> List[Dict[str, Any]]:
        return normalize_quest_offer_payloads(offers, default_source)

    @classmethod
    def merge_quest_offers(
        cls,
        existing: Optional[List[Dict[str, Any]]],
        new_offers: Optional[List[Dict[str, Any]]],
        new_default_source: str = "emergent",
    ) -> List[Dict[str, Any]]:
        return merge_quest_offer_payloads(existing, new_offers, new_default_source)

    def find_inventory_item(self, query: str) -> Optional[Dict[str, Any]]:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return None
        stack = self.physical_inventory.find_item(query_lower)
        if stack is not None:
            return stack.to_legacy_dict()
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
        stack = self.physical_inventory.remove_item(query, quantity)
        if stack is None:
            return None
        self.sync_player_state()
        return stack.to_legacy_dict()

    def equip_item(self, query: str) -> Optional[Dict[str, Any]]:
        removed_dict = self.remove_item(query)
        if removed_dict is None:
            return None
        slot = self._infer_slot(removed_dict)
        if slot not in DEFAULT_EQUIPMENT_SLOTS:
            self.add_item(removed_dict)
            return None
        previous = self.physical_inventory.equipment.get(slot)
        if previous is not None:
            self.physical_inventory.equipment[slot] = None
            self.add_item(previous.to_legacy_dict())
        removed_dict["slot"] = slot
        stack = ItemStack.from_legacy_dict(removed_dict)
        self.physical_inventory.equipment[slot] = stack
        self.sync_player_state()
        return removed_dict

    def unequip_item(self, query: str) -> Optional[Dict[str, Any]]:
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return None
        for slot, stack in self.physical_inventory.equipment.items():
            if stack is None:
                continue
            if query_lower == slot or query_lower in stack.item_id.lower() or query_lower in stack.name.lower():
                self.physical_inventory.equipment[slot] = None
                item_dict = stack.to_legacy_dict()
                self.add_item(item_dict)
                self.sync_player_state()
                return item_dict
        return None
