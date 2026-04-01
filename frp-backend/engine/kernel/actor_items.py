from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value


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
        self.slots.setdefault(slot, []).append(item)

    def covered_parts(self) -> set[str]:
        covered: set[str] = set()
        for items in self.slots.values():
            for item in items:
                coverage = item.payload.get("coverage", []) or item.payload.get("covers", [])
                for part_id in coverage:
                    covered.add(str(part_id))
        return covered

    def covering_items(self, part_id: str) -> list[tuple[str, ItemStack]]:
        matches: list[tuple[str, ItemStack]] = []
        for slot, items in self.slots.items():
            for item in items:
                coverage = set(str(entry) for entry in item.payload.get("coverage", []))
                coverage.update(str(entry) for entry in item.payload.get("covers", []))
                if part_id in coverage:
                    matches.append((slot, item))
        matches.sort(key=lambda pair: equipment_layer_order(pair[0]))
        return matches

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EquipmentLoadout":
        payload = dict(data)
        payload["slots"] = {
            key: [ItemStack.from_dict(item) for item in items]
            for key, items in payload.get("slots", {}).items()
        }
        return cls(**payload)


def item_stack_from_legacy_payload(payload: dict[str, Any], *, index: int = 0) -> ItemStack:
    item_name = str(payload.get("name", payload.get("id", f"item_{index}"))).strip() or f"item_{index}"
    instance_id = str(payload.get("instance_id", payload.get("id", f"legacy_item_{index}")))
    item_def_id = str(payload.get("item_def_id", item_name.lower().replace(" ", "_")))
    quantity = max(1, int(payload.get("quantity", payload.get("count", 1))))
    material_id = payload.get("material_id") or payload.get("material") or payload.get("weapon_material")
    sharpness = int(payload.get("sharpness", 100))
    return ItemStack(
        instance_id=instance_id,
        item_def_id=item_def_id,
        quantity=quantity,
        material_id=str(material_id) if material_id else None,
        quality=int(payload.get("quality", 0)),
        wear=int(payload.get("wear", 0)),
        sharpness=sharpness,
        tags=[str(tag) for tag in payload.get("tags", [])],
        payload=dict(payload),
    )


def equipment_layer_order(slot: str) -> int:
    order = {
        "under": 0,
        "underlayer": 0,
        "clothes": 1,
        "over": 1,
        "armor": 2,
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
    "MaterialDef",
    "equipment_layer_order",
    "item_stack_from_legacy_payload",
]
