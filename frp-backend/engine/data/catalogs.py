"""Item, monster, NPC, spell, and recipe accessors."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.data._shared import (
    items_registry,
    monsters_registry,
    npc_templates_registry,
    recipes_registry,
    spells_registry,
)


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    item = items_registry().get(str(item_id or ""))
    return dict(item) if item else None


def list_items() -> List[Dict[str, Any]]:
    return [dict(item) for item in items_registry().values()]


def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
    monster = monsters_registry().get(str(monster_id or ""))
    return dict(monster) if monster else None


def list_monsters() -> List[Dict[str, Any]]:
    return [dict(monster) for monster in monsters_registry().values()]


def get_npc_template(template_id: str) -> Optional[Dict[str, Any]]:
    npc = npc_templates_registry().get(str(template_id or ""))
    return dict(npc) if npc else None


def list_npc_templates() -> List[Dict[str, Any]]:
    return [dict(template) for template in npc_templates_registry().values()]


def get_spell(spell_id_or_name: str) -> Optional[Dict[str, Any]]:
    query = str(spell_id_or_name or "").lower()
    if not query:
        return None
    for spell in spells_registry().values():
        if query == str(spell.get("id", "")).lower() or query == str(spell.get("name", "")).lower():
            return dict(spell)
    return None


def list_spells() -> List[Dict[str, Any]]:
    return [dict(spell) for spell in spells_registry().values()]


def get_recipe(recipe_id: str) -> Optional[Dict[str, Any]]:
    recipe = recipes_registry().get(str(recipe_id or ""))
    return dict(recipe) if recipe else None


def list_recipes() -> List[Dict[str, Any]]:
    return [dict(recipe) for recipe in recipes_registry().values()]


def recipes_by_skill(skill: str) -> List[Dict[str, Any]]:
    skill_lower = str(skill or "").lower()
    return [dict(recipe) for recipe in recipes_registry().values() if str(recipe.get("skill", "")).lower() == skill_lower]

