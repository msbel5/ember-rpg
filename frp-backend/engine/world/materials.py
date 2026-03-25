"""
Materials system for Ember RPG.
FR-15..FR-19: Material properties affecting items (damage, weight, value, armor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class MaterialProperties:
    """Immutable property set for a crafting / equipment material."""
    density: float       # kg/m³ relative factor (1.0 = baseline iron)
    hardness: float      # 0‑10 scale (Mohs-inspired)
    value_mult: float    # multiplier on base gold value
    damage_mult: float   # multiplier on base weapon damage
    armor_mult: float    # multiplier on base armor protection


MATERIALS: Dict[str, MaterialProperties] = {
    "iron": MaterialProperties(
        density=1.0, hardness=4.0, value_mult=1.0,
        damage_mult=1.0, armor_mult=1.0,
    ),
    "steel": MaterialProperties(
        density=1.05, hardness=5.5, value_mult=1.8,
        damage_mult=1.3, armor_mult=1.25,
    ),
    "bronze": MaterialProperties(
        density=1.1, hardness=3.5, value_mult=0.9,
        damage_mult=0.85, armor_mult=0.9,
    ),
    "wood": MaterialProperties(
        density=0.4, hardness=2.0, value_mult=0.3,
        damage_mult=0.5, armor_mult=0.4,
    ),
    "leather": MaterialProperties(
        density=0.35, hardness=1.5, value_mult=0.5,
        damage_mult=0.3, armor_mult=0.5,
    ),
    "mithril": MaterialProperties(
        density=0.45, hardness=8.0, value_mult=10.0,
        damage_mult=1.6, armor_mult=1.8,
    ),
    "silver": MaterialProperties(
        density=1.3, hardness=3.0, value_mult=5.0,
        damage_mult=0.9, armor_mult=0.85,
    ),
    "gold": MaterialProperties(
        density=2.4, hardness=2.5, value_mult=15.0,
        damage_mult=0.6, armor_mult=0.6,
    ),
    "bone": MaterialProperties(
        density=0.6, hardness=3.0, value_mult=0.4,
        damage_mult=0.7, armor_mult=0.55,
    ),
    "obsidian": MaterialProperties(
        density=0.9, hardness=6.5, value_mult=3.0,
        damage_mult=1.5, armor_mult=0.7,
    ),
}


def apply_material(
    base_damage: float,
    base_weight: float,
    base_value: float,
    base_armor: float,
    material_name: str,
) -> Dict[str, float]:
    """Return modified item stats after applying *material_name*.

    Raises ``KeyError`` when the material is unknown.

    Returns a dict with keys: damage, weight, value, armor, material.
    """
    mat = MATERIALS[material_name.lower()]
    return {
        "damage": round(base_damage * mat.damage_mult, 2),
        "weight": round(base_weight * mat.density, 2),
        "value": round(base_value * mat.value_mult, 2),
        "armor": round(base_armor * mat.armor_mult, 2),
        "material": material_name.lower(),
    }


def get_item_display_name(item_name: str, material: str) -> str:
    """Return a human-friendly display name such as ``'Steel Longsword'``."""
    return f"{material.capitalize()} {item_name.title()}"
