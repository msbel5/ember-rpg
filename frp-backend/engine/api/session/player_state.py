"""Player-state synchronization — kernel-native, data-driven.

sync_player_state() keeps the ActorRecord, Entity and PhysicalInventory
in sync every time ensure_consistency() runs.  It does NOT write flat
string IDs back into the kernel types — PhysicalInventory is the
authoritative source for inventory/equipment, and ActorRecord.conditions
is list[ConditionRecord].

All armor/material classification reads from item data — no hardcoded
material or armor-type strings.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.api.session_utils import normalize_conversation_state
from engine.world.inventory import PhysicalInventory

from .constants import DEFAULT_EQUIPMENT_SLOTS, TIMED_CONDITION_NAMES

log = logging.getLogger(__name__)


# ── Armor classification table loaded from classes.json ────────
# Maps class armor_type → lookup tokens for the AP tracker.
# Built lazily and cached at module level.
_ARMOR_KEYWORD_MAP: dict[str, str] | None = None


def _armor_keyword_map() -> dict[str, str]:
    """Return material/keyword → armor_type map derived from classes data.

    e.g. {"plate": "plate_armor", "steel": "plate_armor",
          "chain": "chain_mail", "iron": "chain_mail",
          "leather": "leather", "robe": "cloth", "cloth": "cloth"}
    """
    global _ARMOR_KEYWORD_MAP
    if _ARMOR_KEYWORD_MAP is not None:
        return _ARMOR_KEYWORD_MAP
    from engine.data.classes import get_class, list_class_ids
    mapping: dict[str, str] = {}
    for class_id in list_class_ids():
        cls = get_class(class_id)
        armor_type = cls.get("armor_type", "")
        if not armor_type:
            continue
        # Each class declares an armor_type; build lookup keywords
        # from the class starting_equipment armor entries
        for item in cls.get("starting_equipment", []):
            if item.get("slot") == "armor" or item.get("type") == "armor":
                mat = str(item.get("material", "")).lower()
                if mat:
                    mapping[mat] = armor_type
                # Also index words from the armor name
                for word in str(item.get("name", "")).lower().split():
                    if len(word) > 3:
                        mapping[word] = armor_type
    # Ensure canonical entries exist
    mapping.setdefault("plate", "plate_armor")
    mapping.setdefault("steel", "plate_armor")
    mapping.setdefault("chain", "chain_mail")
    mapping.setdefault("iron", "chain_mail")
    mapping.setdefault("leather", "leather")
    mapping.setdefault("cloth", "cloth")
    mapping.setdefault("robe", "cloth")
    _ARMOR_KEYWORD_MAP = mapping
    return _ARMOR_KEYWORD_MAP


class SessionPlayerStateMixin:
    """Consistency and player-state synchronization methods."""

    # ── Armor classification helpers (data-driven) ──────────────

    @staticmethod
    def _armor_type_from_item(item: Optional[Dict[str, Any]]) -> str:
        """Determine armor type for AP tracker from item dict.

        Matches item id/name/material against the keyword map built
        from classes.json starting_equipment data.
        """
        if not item:
            return "none"
        keywords = _armor_keyword_map()
        candidates = (
            f"{item.get('id', '')} {item.get('name', '')} "
            f"{item.get('material', '')}"
        ).lower()
        for keyword, armor_type in keywords.items():
            if keyword in candidates:
                return armor_type
        return "none"

    @staticmethod
    def _armor_tokens(slot: str, item: Dict[str, Any]) -> List[str]:
        """Build armor token list for a slot/item pair.

        Tokens are used by the combat system to determine damage
        reduction layers.
        """
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
        # For body armor, derive token from material/name via keyword map
        keywords = _armor_keyword_map()
        candidates = (
            f"{item.get('id', '')} {item.get('name', '')} "
            f"{item.get('material', '')}"
        ).lower()
        for keyword, armor_type in keywords.items():
            if keyword in candidates:
                if armor_type == "plate_armor":
                    return ["breastplate"]
                if armor_type == "chain_mail":
                    return ["chainmail"]
                if armor_type == "leather":
                    return ["leather"]
                return [armor_type]
        return []

    # ── Flat-ID projections from PhysicalInventory ─────────────
    # These read from the session's PhysicalInventory (the truth for
    # items in the session), NOT from the player's kernel inventory.

    def inventory_item_ids(self) -> List[str]:
        """Return flat list of item IDs from PhysicalInventory."""
        ids: List[str] = []
        for item in self.inventory:  # property → PhysicalInventory
            ids.extend(
                [item.get("id", "")] * max(1, int(item.get("qty", 1)))
            )
        return [i for i in ids if i]

    def equipment_ids(self) -> Dict[str, Optional[str]]:
        """Return {slot: item_id | None} from PhysicalInventory."""
        result: Dict[str, Optional[str]] = {}
        for slot in DEFAULT_EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)  # property → PhysicalInventory
            if item:
                result[slot] = item.get("id")
        if result.get("shield"):
            result["offhand"] = result["shield"]
        return result

    # ── Main consistency entry point ───────────────────────────

    def ensure_consistency(self) -> None:
        if self.physical_inventory is None:
            self.physical_inventory = PhysicalInventory()
        self.quest_offers = self.normalize_quest_offers(
            self.quest_offers, default_source="authored",
        )
        current_turn = (
            self.dm_context.turn if self.dm_context is not None else 0
        )
        self.conversation_state = normalize_conversation_state(
            self.conversation_state, turn=current_turn,
        )
        self.clear_expired_timed_conditions()
        self.reattach_entity_refs()
        self.sync_player_state()

    # ── Player sync: kernel-native ─────────────────────────────

    def sync_player_state(self) -> None:
        """Sync derived combat stats on the ActorRecord.

        PhysicalInventory owns the items.  We read equipment dicts
        from it (via the session properties) and compute AC, armor
        tokens, weapon material, and AP on the ActorRecord.  We do
        NOT overwrite ActorRecord.inventory or ActorRecord.equipment.
        """
        if self.player is None:
            return

        # ── Conditions: merge timed conditions into kernel list ─
        active_timed = self.active_timed_conditions()
        existing_names: list[str] = self.player.condition_names
        persistent = [
            n for n in existing_names if n not in TIMED_CONDITION_NAMES
        ]
        for cond_name in active_timed:
            if cond_name not in persistent:
                persistent.append(cond_name)
        self.player.set_conditions_from_names(persistent)

        # ── AC: base + equipped armor bonus ─────────────────────
        base_ac = self.player.base_ac or self.player.ac
        self.player.base_ac = base_ac
        armor_bonus = sum(
            (item or {}).get("ac_bonus", 0)
            for item in self.equipment.values()
        )
        self.player.ac = base_ac + armor_bonus

        # ── Armor tokens & weapon material ──────────────────────
        equipped_armor: List[str] = []
        for slot, item in self.equipment.items():
            if item:
                equipped_armor.extend(self._armor_tokens(slot, item))
        self.player.equipped_armor = equipped_armor

        weapon = self.equipment.get("weapon")
        self.player.weapon_material = (
            (weapon or {}).get("material") or self.player.weapon_material
        )

        # ── AP from tracker ─────────────────────────────────────
        if self.ap_tracker is not None:
            self.ap_tracker.set_armor(
                self._armor_type_from_item(self.equipment.get("armor"))
            )
            ap_current = self.ap_tracker.current_ap
            ap_max = self.ap_tracker.max_ap
            if self.in_combat() and self.combat is not None:
                player_combatant = next(
                    (c for c in self.combat.combatants
                     if c.name == self.player.name),
                    None,
                )
                if player_combatant is not None:
                    ap_current = int(player_combatant.ap)
                    ap_max = 3
            self.player.ap = ap_current
            self.player.max_ap = ap_max

        # ── Keep player Entity in sync ──────────────────────────
        if self.player_entity is not None:
            self.player_entity.hp = self.player.hp
            self.player_entity.max_hp = self.player.max_hp
            self.player_entity.position = tuple(self.position)

        # ── Keep DM context party reference up to date ──────────
        if self.dm_context is not None:
            self.dm_context.party = [self.player]
