"""Compatibility facade for centralized runtime content/config registries."""
from __future__ import annotations

from engine.data._shared import (
    campaign_runtime_registry,
    campaign_templates_registry,
    classes_registry,
    consequence_rules_registry,
    creation_registry,
    history_tables_registry,
    items_registry,
    load_json_path,
    load_registry_list,
    load_registry_list_from_path,
    load_registry_map,
    load_registry_map_from_path,
    locations_registry,
    loot_tables_registry,
    monsters_registry,
    name_banks_registry,
    npc_templates_registry,
    progression_registry,
    recipes_registry,
    runtime_config_registry,
    schedules_registry,
    social_rules_registry,
    spells_registry,
    worldgen_registry,
)
from engine.data.catalogs import *  # noqa: F401,F403
from engine.data.classes import *  # noqa: F401,F403
from engine.data.runtime import *  # noqa: F401,F403
from engine.data.world import *  # noqa: F401,F403

CLASSES = classes_registry()
ITEMS = items_registry()
MONSTERS = monsters_registry()
NPC_TEMPLATES = npc_templates_registry()
SPELLS = spells_registry()
CAMPAIGN_TEMPLATES = campaign_templates_registry()
RECIPES = recipes_registry()
LOCATIONS = locations_registry()
WORLDGEN = worldgen_registry()
SOCIAL_RULES = social_rules_registry()
PROGRESSION = progression_registry()
LOOT_TABLES = loot_tables_registry()
NAME_BANKS = name_banks_registry()
SCHEDULES = schedules_registry()
CHARACTER_CREATION = creation_registry()
CONSEQUENCE_RULES = consequence_rules_registry()
CAMPAIGN_RUNTIME = campaign_runtime_registry()
HISTORY_TABLES = history_tables_registry()
RUNTIME_CONFIG = runtime_config_registry()
