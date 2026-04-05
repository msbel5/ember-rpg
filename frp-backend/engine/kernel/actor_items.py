from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.world.action_points import ARMOR_WEIGHT_PENALTY


CANONICAL_EQUIPMENT_SLOTS = [
    "main_hand",
    "off_hand",
    "head",
    "face",
    "neck",
    "shoulders",
    "chest",
    "arms",
    "hands",
    "belt",
    "legs",
    "feet",
    "ring_left",
    "ring_right",
    "trinket_1",
    "trinket_2",
    "attunement_1",
    "attunement_2",
    "attunement_3",
]
LEGACY_SLOT_ALIASES = {
    "weapon": "main_hand",
    "weapon_1": "main_hand",
    "weapon_2": "off_hand",
    "weapon_3": "main_hand",
    "weapon_4": "main_hand",
    "main_hand": "main_hand",
    "off_hand": "off_hand",
    "shield": "off_hand",
    "helmet": "head",
    "head": "head",
    "face": "face",
    "amulet": "neck",
    "neck": "neck",
    "cover": "shoulders",
    "cloak": "shoulders",
    "shoulders": "shoulders",
    "armor": "chest",
    "chest": "chest",
    "arms": "arms",
    "gloves": "hands",
    "hands": "hands",
    "belt": "belt",
    "legs": "legs",
    "boots": "feet",
    "feet": "feet",
    "left_ring": "ring_left",
    "ring_left": "ring_left",
    "right_ring": "ring_right",
    "ring_right": "ring_right",
    "trinket_1": "trinket_1",
    "trinket_2": "trinket_2",
    "attunement_1": "attunement_1",
    "attunement_2": "attunement_2",
    "attunement_3": "attunement_3",
}
NON_WEARABLE_SLOT_PREFIXES = ("quiver_", "quick_item_")
NON_WEARABLE_SLOTS = {"quiver", "backpack"}
STORAGE_SLOT_PREFERENCES = {
    "main_hand": ["main_hand", "weapon_1", "weapon"],
    "off_hand": ["off_hand", "shield", "weapon_2"],
    "head": ["helmet", "head"],
    "face": ["face"],
    "neck": ["amulet", "neck"],
    "shoulders": ["cover", "cloak", "shoulders"],
    "chest": ["armor", "chest"],
    "arms": ["arms"],
    "hands": ["gloves", "hands"],
    "belt": ["belt"],
    "legs": ["legs"],
    "feet": ["boots", "feet"],
    "ring_left": ["left_ring", "ring_left"],
    "ring_right": ["right_ring", "ring_right"],
    "trinket_1": ["trinket_1"],
    "trinket_2": ["trinket_2"],
    "attunement_1": ["attunement_1"],
    "attunement_2": ["attunement_2"],
    "attunement_3": ["attunement_3"],
}
CANONICAL_SLOT_COVERAGE = {
    "main_hand": [],
    "off_hand": ["left_arm"],
    "head": ["head", "neck"],
    "face": ["head"],
    "neck": ["neck"],
    "shoulders": ["chest", "left_arm", "right_arm"],
    "chest": ["chest", "torso"],
    "arms": ["left_arm", "right_arm"],
    "hands": ["left_arm", "right_arm"],
    "belt": ["torso"],
    "legs": ["left_leg", "right_leg"],
    "feet": ["left_leg", "right_leg"],
    "ring_left": [],
    "ring_right": [],
    "trinket_1": [],
    "trinket_2": [],
    "attunement_1": [],
    "attunement_2": [],
    "attunement_3": [],
}
ARMOR_WEIGHT_DEFAULTS = {
    "none": "none",
    "light": "leather",
    "medium": "chain_mail",
    "heavy": "plate_armor",
    "cloth": "cloth",
    "leather": "leather",
    "chain_mail": "chain_mail",
    "plate_armor": "plate_armor",
}
STEALTH_NOISE_BY_WEIGHT = {
    "none": 0,
    "cloth": 0,
    "leather": 0,
    "chain_mail": 1,
    "plate_armor": 2,
}
SPELL_INTERFERENCE_BY_WEIGHT = {
    "none": 0,
    "cloth": 0,
    "leather": 1,
    "chain_mail": 2,
    "plate_armor": 3,
}
BODY_ZONE_ORDER = [
    "head",
    "neck",
    "chest",
    "torso",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
]


def _normalize_slot_token(slot: Any) -> str:
    return str(slot or "").strip().lower()


def is_nonwearable_slot(slot: Any) -> bool:
    normalized = _normalize_slot_token(slot)
    if not normalized:
        return False
    if normalized in NON_WEARABLE_SLOTS:
        return True
    return normalized.startswith(NON_WEARABLE_SLOT_PREFIXES)


def canonical_equipment_slot(slot: Any) -> str | None:
    normalized = _normalize_slot_token(slot)
    if not normalized or is_nonwearable_slot(normalized):
        return None
    if normalized in CANONICAL_EQUIPMENT_SLOTS:
        return normalized
    return LEGACY_SLOT_ALIASES.get(normalized)


def storage_slots_for_canonical_slot(slot: Any) -> list[str]:
    canonical = canonical_equipment_slot(slot)
    if canonical is None:
        normalized = _normalize_slot_token(slot)
        return [normalized] if normalized else []
    preferred = list(STORAGE_SLOT_PREFERENCES.get(canonical, [canonical]))
    aliases = [
        legacy_slot
        for legacy_slot, mapped in LEGACY_SLOT_ALIASES.items()
        if mapped == canonical and legacy_slot not in preferred and not is_nonwearable_slot(legacy_slot)
    ]
    return preferred + sorted(aliases)


def canonical_slot_query_aliases(slot: Any) -> list[str]:
    normalized = _normalize_slot_token(slot)
    if not normalized:
        return []
    canonical = canonical_equipment_slot(normalized)
    if canonical is None:
        return [normalized]
    aliases = [canonical]
    for storage_slot in storage_slots_for_canonical_slot(canonical):
        if storage_slot not in aliases:
            aliases.append(storage_slot)
    return aliases


def _occupied_canonical_slots(loadout: "EquipmentLoadout | None") -> set[str]:
    occupied: set[str] = set()
    if loadout is None:
        return occupied
    for slot, items in loadout.slots.items():
        if not items:
            continue
        canonical = canonical_slot_for_item_payload({}, explicit_slot=slot)
        if canonical:
            occupied.add(canonical)
    return occupied


def _first_available_slot(candidates: list[str], occupied_slots: set[str]) -> str | None:
    for candidate in candidates:
        if candidate not in occupied_slots:
            return candidate
    return candidates[0] if candidates else None


def _payload_text(payload: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            str(payload.get("type", "")),
            str(payload.get("slot", "")),
            str(payload.get("equip_slot", "")),
            str(payload.get("equipped_slot", "")),
            str(payload.get("item_def_id", payload.get("id", ""))),
            str(payload.get("name", "")),
        )
        if part
    ).lower()


def candidate_canonical_slots_for_item_payload(
    payload: dict[str, Any],
    *,
    occupied_slots: set[str] | None = None,
) -> list[str]:
    normalized_payload = dict(payload or {})
    explicit_candidates: list[str] = []
    for candidate in (
        normalized_payload.get("canonical_slot"),
        normalized_payload.get("equipped_slot"),
        normalized_payload.get("equip_slot"),
        normalized_payload.get("slot"),
        normalized_payload.get("legacy_slot"),
    ):
        canonical = canonical_equipment_slot(candidate)
        if canonical and canonical not in explicit_candidates:
            explicit_candidates.append(canonical)
    if explicit_candidates:
        explicit = explicit_candidates[0]
        if explicit == "ring_left":
            return ["ring_left", "ring_right"]
        if explicit == "trinket_1":
            return ["trinket_1", "trinket_2"]
        return [explicit]
    text = _payload_text(normalized_payload)
    item_type = str(normalized_payload.get("type", "")).strip().lower()
    occupied = set(occupied_slots or set())
    if "shield" in text or item_type == "shield":
        return ["off_hand"]
    if "ring" in text:
        return ["ring_left", "ring_right"]
    if any(token in text for token in ("amulet", "necklace", "gorget", "pendant")):
        return ["neck"]
    if any(token in text for token in ("cloak", "cape", "mantle", "shawl", "pauldron")):
        return ["shoulders"]
    if any(token in text for token in ("mask", "visor", "goggles", "spectacles")):
        return ["face"]
    if any(token in text for token in ("helmet", "helm", "hood", "circlet", "crown")):
        return ["head"]
    if any(token in text for token in ("glove", "gauntlet")):
        return ["hands"]
    if any(token in text for token in ("bracer", "vambrace")):
        return ["arms"]
    if any(token in text for token in ("belt", "girdle", "sash")):
        return ["belt"]
    if any(token in text for token in ("greaves", "leggings", "pants", "trousers", "skirt")):
        return ["legs"]
    if any(token in text for token in ("boot", "shoe", "sandal", "sabaton")):
        return ["feet"]
    if any(token in text for token in ("trinket", "charm", "talisman", "relic", "idol", "focus")):
        preferred = _first_available_slot(["trinket_1", "trinket_2"], occupied)
        return [preferred] if preferred else ["trinket_1", "trinket_2"]
    if item_type == "weapon" or any(token in text for token in ("sword", "axe", "dagger", "mace", "staff", "bow", "hammer", "spear")):
        return ["main_hand"]
    if any(token in text for token in ("armor", "mail", "plate", "cuirass", "breastplate", "robe", "tunic", "vest")):
        return ["chest"]
    return []


def canonical_slot_for_item_payload(
    payload: dict[str, Any],
    *,
    explicit_slot: Any | None = None,
    occupied_slots: set[str] | None = None,
) -> str | None:
    normalized_payload = dict(payload or {})
    occupied = set(occupied_slots or set())
    canonical_hint = canonical_equipment_slot(normalized_payload.get("canonical_slot"))
    if canonical_hint is not None:
        return canonical_hint
    for candidate in (
        explicit_slot,
        normalized_payload.get("equipped_slot"),
        normalized_payload.get("equip_slot"),
        normalized_payload.get("slot"),
        normalized_payload.get("legacy_slot"),
    ):
        canonical = canonical_equipment_slot(candidate)
        if canonical == "ring_left" and "ring_left" in occupied and "ring_right" not in occupied:
            return "ring_right"
        if canonical is not None:
            return canonical
    candidates = candidate_canonical_slots_for_item_payload(normalized_payload, occupied_slots=occupied)
    return _first_available_slot(candidates, occupied)


def preferred_storage_slot_for_item(
    canonical_slot: str,
    payload: dict[str, Any],
    *,
    requested_slot: Any | None = None,
) -> str:
    requested = _normalize_slot_token(requested_slot)
    if requested and requested in storage_slots_for_canonical_slot(canonical_slot):
        return requested
    if canonical_slot == "off_hand":
        text = _payload_text(payload)
        if "shield" in text or str(payload.get("type", "")).strip().lower() == "shield":
            return "shield"
    return storage_slots_for_canonical_slot(canonical_slot)[0]


def coverage_zones_for_item(item: "ItemStack", slot: Any) -> list[str]:
    payload = dict(getattr(item, "payload", {}) or {})
    raw_coverage = payload.get("coverage") or payload.get("covers") or []
    coverage: list[str] = []
    seen: set[str] = set()
    for entry in raw_coverage:
        zone = str(entry or "").strip()
        if not zone or zone in seen:
            continue
        seen.add(zone)
        coverage.append(zone)
    if coverage:
        return coverage
    canonical = canonical_slot_for_item_payload(payload, explicit_slot=slot)
    if canonical is None:
        return []
    return list(CANONICAL_SLOT_COVERAGE.get(canonical, []))


def armor_weight_class_for_item(item: "ItemStack", slot: Any) -> str:
    payload = dict(getattr(item, "payload", {}) or {})
    for key in ("armor_weight_class", "weight_class", "armor_weight"):
        value = str(payload.get(key, "")).strip().lower()
        if value:
            return ARMOR_WEIGHT_DEFAULTS.get(value, value)
    armor_type = str(payload.get("armor_type", "")).strip().lower()
    if armor_type:
        return ARMOR_WEIGHT_DEFAULTS.get(armor_type, armor_type)
    canonical = canonical_slot_for_item_payload(payload, explicit_slot=slot)
    if canonical not in {"head", "face", "shoulders", "chest", "arms", "hands", "legs", "feet"}:
        return "none"
    text = _payload_text(payload)
    if "plate" in text:
        return "plate_armor"
    if "chain" in text or "mail" in text:
        return "chain_mail"
    if "leather" in text or "hide" in text:
        return "leather"
    if any(token in text for token in ("robe", "cloth", "linen", "silk")):
        return "cloth"
    if canonical in {"feet", "hands", "shoulders"}:
        return "leather"
    return "none"


def movement_penalty_for_item(item: "ItemStack", slot: Any) -> int:
    payload = dict(getattr(item, "payload", {}) or {})
    explicit = payload.get("movement_penalty")
    if explicit not in (None, ""):
        return max(0, int(explicit))
    return int(ARMOR_WEIGHT_PENALTY.get(armor_weight_class_for_item(item, slot), 0))


def stealth_noise_for_item(item: "ItemStack", slot: Any) -> int:
    payload = dict(getattr(item, "payload", {}) or {})
    explicit = payload.get("stealth_noise")
    if explicit not in (None, ""):
        return max(0, int(explicit))
    return int(STEALTH_NOISE_BY_WEIGHT.get(armor_weight_class_for_item(item, slot), 0))


def spell_interference_for_item(item: "ItemStack", slot: Any) -> int:
    payload = dict(getattr(item, "payload", {}) or {})
    explicit = payload.get("spell_interference")
    if explicit not in (None, ""):
        return max(0, int(explicit))
    return int(SPELL_INTERFERENCE_BY_WEIGHT.get(armor_weight_class_for_item(item, slot), 0))


def attunement_required_for_item(item: "ItemStack") -> bool:
    payload = dict(getattr(item, "payload", {}) or {})
    explicit = payload.get("attunement_required")
    if explicit is not None:
        return bool(explicit)
    explicit = payload.get("requires_attunement")
    if explicit is not None:
        return bool(explicit)
    tags = {str(tag).strip().lower() for tag in payload.get("tags", [])}
    return "attunement" in tags or "requires_attunement" in tags


def equipment_item_projection(slot: str, item: "ItemStack") -> dict[str, Any]:
    payload = dict(getattr(item, "payload", {}) or {})
    canonical_slot = canonical_slot_for_item_payload(payload, explicit_slot=slot)
    projection = {
        "id": str(item.item_def_id),
        "item_def_id": str(item.item_def_id),
        "instance_id": str(item.instance_id),
        "name": str(payload.get("name", item.item_def_id.replace("_", " ").title())),
        "canonical_slot": canonical_slot,
        "coverage_zones": coverage_zones_for_item(item, slot),
        "armor_weight_class": armor_weight_class_for_item(item, slot),
        "movement_penalty": movement_penalty_for_item(item, slot),
        "stealth_noise": stealth_noise_for_item(item, slot),
        "spell_interference": spell_interference_for_item(item, slot),
        "attunement_required": attunement_required_for_item(item),
    }
    if _normalize_slot_token(slot) != _normalize_slot_token(canonical_slot):
        projection["legacy_slot"] = str(slot)
    return projection


def build_equipment_topology_payload(loadout: "EquipmentLoadout") -> dict[str, Any]:
    canonical_slots = {slot: None for slot in CANONICAL_EQUIPMENT_SLOTS}
    coverage_summary = {zone: [] for zone in BODY_ZONE_ORDER}
    attuned_item_ids: list[str] = []
    for storage_slot, items in loadout.slots.items():
        if is_nonwearable_slot(storage_slot):
            continue
        if not items:
            continue
        for item in items:
            projection = equipment_item_projection(storage_slot, item)
            canonical_slot = str(projection.get("canonical_slot") or "").strip()
            if canonical_slot and canonical_slot in canonical_slots and canonical_slots[canonical_slot] is None:
                canonical_slots[canonical_slot] = projection
            for zone in projection["coverage_zones"]:
                if zone in coverage_summary:
                    coverage_summary[zone].append(str(item.item_def_id))
            if canonical_slot.startswith("attunement_"):
                attuned_item_ids.append(str(item.item_def_id))
    return {
        "slots": canonical_slots,
        "legacy_slot_aliases": {
            legacy_slot: canonical_slot
            for legacy_slot, canonical_slot in sorted(LEGACY_SLOT_ALIASES.items())
            if legacy_slot != canonical_slot
        },
        "coverage_summary": coverage_summary,
        "modifiers": equipment_modifier_totals(loadout),
        "attunement": equipment_attunement_summary(loadout, attuned_item_ids=attuned_item_ids),
    }


def equipment_modifier_totals(loadout: "EquipmentLoadout") -> dict[str, int]:
    total_movement_penalty = 0
    total_stealth_noise = 0
    total_spell_interference = 0
    for slot, items in loadout.slots.items():
        if is_nonwearable_slot(slot):
            continue
        for item in items:
            total_movement_penalty += movement_penalty_for_item(item, slot)
            total_stealth_noise += stealth_noise_for_item(item, slot)
            total_spell_interference += spell_interference_for_item(item, slot)
    return {
        "total_movement_penalty": int(total_movement_penalty),
        "total_stealth_noise": int(total_stealth_noise),
        "total_spell_interference": int(total_spell_interference),
    }


def equipment_attunement_summary(
    loadout: "EquipmentLoadout",
    *,
    attuned_item_ids: list[str] | None = None,
) -> dict[str, Any]:
    attuned = list(attuned_item_ids or [])
    if not attuned:
        for slot, items in loadout.slots.items():
            if canonical_equipment_slot(slot) not in {"attunement_1", "attunement_2", "attunement_3"}:
                continue
            for item in items:
                attuned.append(str(item.item_def_id))
    slot_count = 3
    available_slots = max(0, slot_count - len(attuned))
    return {
        "slot_count": slot_count,
        "attuned_item_ids": attuned,
        "available_slots": available_slots,
    }


@dataclass
class MaterialDef:
    material_id: str
    label: str
    category: str
    density: int = 0
    impact_yield: int = 0
    impact_fracture: int = 0
    shear_yield: int = 0
    shear_fracture: int = 0
    max_edge: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialDef":
        return cls(**data)


@dataclass
class ItemDef:
    item_id: str
    label: str
    category: str
    slot: str | None = None
    coverage: list[str] = field(default_factory=list)
    default_material_id: str | None = None
    attack_profile: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemDef":
        return cls(**data)


@dataclass
class ItemStack:
    instance_id: str
    item_def_id: str
    quantity: int = 1
    material_id: str | None = None
    quality: int = 0
    wear: int = 0
    sharpness: int = 100
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemStack":
        return cls(**data)


@dataclass
class EquipmentLoadout:
    slots: dict[str, list[ItemStack]] = field(default_factory=dict)

    def add_item(self, slot: str, item: ItemStack) -> None:
        canonical_slot = canonical_slot_for_item_payload(getattr(item, "payload", {}) or {}, explicit_slot=slot)
        if canonical_slot is not None:
            item.payload.setdefault("canonical_slot", canonical_slot)
            if _normalize_slot_token(slot) != canonical_slot:
                item.payload.setdefault("legacy_slot", str(slot))
        self.slots.setdefault(slot, []).append(item)

    def covered_parts(self) -> set[str]:
        covered: set[str] = set()
        for slot, items in self.slots.items():
            for item in items:
                for part_id in coverage_zones_for_item(item, slot):
                    covered.add(str(part_id))
        return covered

    def covering_items(self, part_id: str) -> list[tuple[str, ItemStack]]:
        matches: list[tuple[str, ItemStack]] = []
        for slot, items in self.slots.items():
            for item in items:
                coverage = set(coverage_zones_for_item(item, slot))
                if part_id in coverage:
                    matches.append((slot, item))
        matches.sort(key=lambda pair: equipment_layer_order(pair[0]))
        return matches

    def to_dict(self) -> dict[str, Any]:
        payload = {"slots": serialize_value(self.slots)}
        topology = build_equipment_topology_payload(self)
        payload["equipment_topology"] = {
            "slots": topology["slots"],
            "legacy_slot_aliases": topology["legacy_slot_aliases"],
            "coverage_summary": topology["coverage_summary"],
        }
        payload["equipment_modifiers"] = topology["modifiers"]
        payload["canonical_slots"] = topology["slots"]
        payload["legacy_slot_aliases"] = topology["legacy_slot_aliases"]
        payload["coverage_summary"] = topology["coverage_summary"]
        payload["modifier_totals"] = topology["modifiers"]
        payload["attunement"] = topology["attunement"]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EquipmentLoadout":
        payload = dict(data)
        slots = {
            key: [ItemStack.from_dict(item) for item in items]
            for key, items in payload.get("slots", {}).items()
        }
        return cls(slots=slots)


def item_stack_from_legacy_payload(payload: dict[str, Any], *, index: int = 0) -> ItemStack:
    normalized_payload = dict(payload)
    item_name = str(normalized_payload.get("name", normalized_payload.get("id", f"item_{index}"))).strip() or f"item_{index}"
    instance_id = str(normalized_payload.get("instance_id", normalized_payload.get("id", f"legacy_item_{index}")))
    item_def_id = str(normalized_payload.get("item_def_id", item_name.lower().replace(" ", "_")))
    quantity = max(1, int(normalized_payload.get("quantity", normalized_payload.get("count", 1))))
    material_id = normalized_payload.get("material_id") or normalized_payload.get("material") or normalized_payload.get("weapon_material")
    sharpness = int(normalized_payload.get("sharpness", 100))
    canonical_slot = canonical_slot_for_item_payload(normalized_payload)
    if canonical_slot is not None:
        normalized_payload.setdefault("canonical_slot", canonical_slot)
        explicit_slot = (
            normalized_payload.get("equipped_slot")
            or normalized_payload.get("equip_slot")
            or normalized_payload.get("slot")
        )
        if explicit_slot and _normalize_slot_token(explicit_slot) != canonical_slot:
            normalized_payload.setdefault("legacy_slot", str(explicit_slot))
    return ItemStack(
        instance_id=instance_id,
        item_def_id=item_def_id,
        quantity=quantity,
        material_id=str(material_id) if material_id else None,
        quality=int(normalized_payload.get("quality", 0)),
        wear=int(normalized_payload.get("wear", 0)),
        sharpness=sharpness,
        tags=[str(tag) for tag in normalized_payload.get("tags", [])],
        payload=normalized_payload,
    )


def equipment_layer_order(slot: str) -> int:
    order = {
        "under": 0,
        "underlayer": 0,
        "clothes": 1,
        "over": 1,
        "armor": 2,
        "head": 2,
        "face": 2,
        "neck": 2,
        "shoulders": 3,
        "chest": 2,
        "arms": 2,
        "hands": 2,
        "belt": 2,
        "legs": 2,
        "feet": 2,
        "cover": 3,
        "main_hand": 4,
        "off_hand": 4,
        "weapon": 4,
    }
    return order.get(str(slot).lower(), 5)


__all__ = [
    "EquipmentLoadout",
    "ItemDef",
    "ItemStack",
    "BODY_ZONE_ORDER",
    "CANONICAL_EQUIPMENT_SLOTS",
    "LEGACY_SLOT_ALIASES",
    "MaterialDef",
    "armor_weight_class_for_item",
    "attunement_required_for_item",
    "build_equipment_topology_payload",
    "candidate_canonical_slots_for_item_payload",
    "canonical_equipment_slot",
    "canonical_slot_for_item_payload",
    "canonical_slot_query_aliases",
    "coverage_zones_for_item",
    "equipment_attunement_summary",
    "equipment_item_projection",
    "equipment_layer_order",
    "equipment_modifier_totals",
    "is_nonwearable_slot",
    "item_stack_from_legacy_payload",
    "movement_penalty_for_item",
    "preferred_storage_slot_for_item",
    "spell_interference_for_item",
    "stealth_noise_for_item",
    "storage_slots_for_canonical_slot",
]
