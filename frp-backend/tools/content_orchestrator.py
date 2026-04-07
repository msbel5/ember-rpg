"""Content packet generation and sidecar validation for JSON-driven game data."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "frp-backend" / "data"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_WORK_ROOT = REPO_ROOT
EQUIPMENT_TYPES = {"weapon", "armor", "shield", "equipment"}
FAMILY_ORDER = [
    "npc_templates",
    "items_equipment",
    "items_supplies",
    "recipes",
    "spells",
    "worldgen",
    "campaign_history_social",
    "monsters",
    "classes",
    "locations",
    "loot_tables",
    "dialog_defs",
    "institutions",
    "caravans",
    "factions",
    "name_banks",
    "world_biomes",
    "world_species",
    "world_cultures",
    "world_buildings",
    "world_furniture",
    "interaction_rules",
    "progression",
    "colony_config",
    "economy_config",
    "quest_config",
    "character_creation",
    "materials",
    "consequence_rules",
    "schedules",
    "campaign_runtime",
]
WORLDGEN_SECTION_KEYS = {
    "building_templates",
    "entity_templates_by_location",
    "map_generator_room_templates",
    "zone_entity_rules",
    "zone_layouts",
    "zone_tile_palettes",
}


@dataclass(frozen=True)
class FamilySpec:
    name: str
    source_files: tuple[str, ...]
    collection_keys: tuple[str, ...]
    goal: str
    constraints: tuple[str, ...]
    consumers: tuple[str, ...]
    generatable: bool = True  # False = config/balance data, skip during AI generation


FAMILY_SPECS: dict[str, FamilySpec] = {
    "npc_templates": FamilySpec(
        name="npc_templates",
        source_files=("npc_templates.json",),
        collection_keys=("npc_templates",),
        goal="Generate new merchant, guard, priest, innkeeper, quest-giver, outlaw, scholar, and scout variants that strengthen quest flavor and settlement variety.",
        constraints=(
            "Keep role, faction, disposition, speech_style, dialogue buckets, and shop_inventory aligned with current runtime expectations.",
            "Do not add branching behavior fields or unsupported AI metadata.",
        ),
        consumers=(
            "engine.data._shared.npc_templates_registry() normalizes this file for runtime access.",
            "engine.core.npc and engine.worldgen.npc_generator rely on grounded role/faction semantics.",
            "engine.api.handlers.social_actions reads dialogue-facing fields and shop-facing templates.",
        ),
    ),
    "items_equipment": FamilySpec(
        name="items_equipment",
        source_files=("items.json",),
        collection_keys=("items",),
        goal="Generate equipment-side items for loot, progression, and store variety without inflating combat numbers for no reason.",
        constraints=(
            "Candidate item types must stay within weapon, armor, shield, or equipment/tool-like entries.",
            "Do not add exotic effects or unsupported item mechanics.",
        ),
        consumers=(
            "engine.kernel.items and engine.kernel.store consume item rarity, value, weight, and combat fields.",
            "engine.api.handlers.inventory_equipment and inventory_management depend on equip-compatible shapes.",
            "engine.world.crafting references many equipment IDs as tools and outputs.",
        ),
    ),
    "items_supplies": FamilySpec(
        name="items_supplies",
        source_files=("items.json",),
        collection_keys=("items",),
        goal="Generate consumables, materials, misc supplies, treasure, and quest-support items that improve economy and crafting breadth.",
        constraints=(
            "Candidate item types must stay outside the equipment split handled by items_equipment.",
            "Do not introduce fields that current inventory, store, or crafting flows cannot parse.",
        ),
        consumers=(
            "engine.kernel.store and engine.world.economy use these entries for value and stock calculations.",
            "engine.api.handlers.inventory_crafting and resource handlers depend on stable material and consumable shapes.",
            "Quest, loot, and settlement surfaces consume these IDs transitively.",
        ),
    ),
    "recipes": FamilySpec(
        name="recipes",
        source_files=("recipes.json",),
        collection_keys=("recipes",),
        goal="Generate practical recipes that deepen crafting loops without inventing new workstation or skill systems.",
        constraints=(
            "All ingredient and product item_id values must already exist in item references.",
            "Restrict workstations, tools, and skills to existing supported values.",
        ),
        consumers=(
            "engine.data._shared.recipes_registry() exposes this file to runtime loaders.",
            "engine.world.crafting and engine.api.handlers.inventory_crafting depend on workstation, tool, and output consistency.",
            "Crafting-side balance should remain grounded in current AP and XP reward expectations.",
        ),
    ),
    "spells": FamilySpec(
        name="spells",
        source_files=("spells.json",),
        collection_keys=("spells",),
        goal="Generate additional kernel-compatible spells that fit the existing school, target_type, and effects vocabulary.",
        constraints=(
            "The current spell data schema has no id field; preserve that shape and use unique names instead of adding ids.",
            "Do not reference projectile or area semantics absent from the current data/effect vocabulary.",
        ),
        consumers=(
            "engine.data._shared.spells_registry() loads the source shape exactly as-is.",
            "engine.kernel.spells and engine.kernel.effects depend on effect descriptors staying inside supported patterns.",
            "engine.api.handlers.combat_actions is still converging onto kernel spell authority, so conservative shapes matter.",
        ),
    ),
    "worldgen": FamilySpec(
        name="worldgen",
        source_files=("worldgen.json",),
        collection_keys=("worldgen",),
        goal="Generate location, building, and zone content that expands settlement and region variety without changing the worldgen wire format.",
        constraints=(
            "Stay inside supported worldgen sections such as building_templates, zone_entity_rules, entity_templates_by_location, zone_layouts, zone_tile_palettes, and map_generator_room_templates.",
            "Do not invent new top-level worldgen config blocks or scene systems.",
        ),
        consumers=(
            "engine.map.zones and engine.worldgen settlement/map generators rely on these sections directly.",
            "engine.orchestrator and region realization consume generated world/zone entity rules.",
            "Only add content the current runtime can actually place or reference.",
        ),
    ),
    "campaign_history_social": FamilySpec(
        name="campaign_history_social",
        source_files=("campaign_templates.json", "history_tables.json", "social_rules.json"),
        collection_keys=("campaigns", "history_tables", "social_rules"),
        goal="Generate campaigns, history seeds, and social rule additions that strengthen creation-to-worldgen-to-dialog continuity.",
        constraints=(
            "campaign_templates.json currently uses the top-level key `campaigns`; preserve that exact key.",
            "Do not add new root keys to history_tables or social_rules; only add safe entries under existing sections.",
        ),
        consumers=(
            "engine.api.campaign.world and engine.api.campaign.runtime read campaign templates and historical flavor.",
            "engine.world.history and engine.kernel.dialog consume history/social vocabularies downstream.",
            "Quest rewards, enemy references, factions, and social defaults must stay inside current runtime capabilities.",
        ),
    ),
    # ── Generatable content families ──────────────────────────────────
    "monsters": FamilySpec(
        name="monsters",
        source_files=("monsters.json",),
        collection_keys=("monsters",),
        goal="Generate new monster types for encounters, loot variety, and biome flavor.",
        constraints=("Keep stat blocks within existing combat math ranges.", "All loot item_ids must exist in items.json."),
        consumers=("engine.data._shared.monsters_registry()", "engine.worldgen.encounter_generator", "engine.kernel.combat"),
    ),
    "classes": FamilySpec(
        name="classes",
        source_files=("classes.json",),
        collection_keys=("classes",),
        goal="Generate new character classes with balanced HP, SP, abilities, and stat bonuses.",
        constraints=("Follow existing class schema exactly.", "Do not exceed existing stat ranges."),
        consumers=("engine.data.classes", "engine.kernel.creation", "engine.kernel.progression"),
    ),
    "locations": FamilySpec(
        name="locations",
        source_files=("locations.json",),
        collection_keys=("locations",),
        goal="Generate new location definitions for settlements and exploration areas.",
        constraints=("NPC roles and workstation IDs must exist in current data.", "Follow existing location schema."),
        consumers=("engine.data.world", "engine.worldgen"),
    ),
    "loot_tables": FamilySpec(
        name="loot_tables",
        source_files=("loot_tables.json",),
        collection_keys=("loot_tables",),
        goal="Generate loot distribution tables for monsters, chests, and quest rewards.",
        constraints=("All item_ids must exist in items.json.", "Rarity weights must sum sensibly."),
        consumers=("engine.data._shared.loot_tables_registry()", "engine.worldgen"),
    ),
    "dialog_defs": FamilySpec(
        name="dialog_defs",
        source_files=("dialog_defs.json",),
        collection_keys=("dialog_defs",),
        goal="Generate NPC dialog trees with branching options, stat checks, and quest hooks.",
        constraints=("Follow DialogDef schema: states with transitions, conditions, actions.", "Stat names: MIG, AGI, END, MND, INS, PRE."),
        consumers=("engine.data._shared.dialog_defs_registry()", "engine.api.campaign.dialog"),
    ),
    "institutions": FamilySpec(
        name="institutions",
        source_files=("institutions.json",),
        collection_keys=("town_institutions",),
        goal="Generate town institution hierarchies, event response rules, and power structures.",
        constraints=("Role IDs and faction references must match existing data.", "Follow existing nested structure."),
        consumers=("engine.world.institutions_catalog",),
    ),
    "caravans": FamilySpec(
        name="caravans",
        source_files=("caravans.json",),
        collection_keys=("caravans",),
        goal="Generate new trade caravan routes connecting settlements with goods.",
        constraints=("All item_ids in goods must exist in items.json.", "Travel hours and values must be reasonable."),
        consumers=("engine.world.caravans",),
    ),
    "factions": FamilySpec(
        name="factions",
        source_files=("factions.json",),
        collection_keys=("factions",),
        goal="Generate new faction ethics profiles and cultural value sets.",
        constraints=("Action types must stay within existing ACTION_TYPES.", "Reaction levels must use existing severity scale."),
        consumers=("engine.world.ethics", "engine.data._shared.factions_registry()"),
    ),
    "name_banks": FamilySpec(
        name="name_banks",
        source_files=("name_banks.json",),
        collection_keys=("name_banks",),
        goal="Expand NPC name pools for each species/culture with lore-appropriate names.",
        constraints=("Follow existing name_banks structure: species → gender → names list.", "No modern/Earth names."),
        consumers=("engine.data._shared.name_banks_registry()", "engine.worldgen.npc_generator"),
    ),
    "world_biomes": FamilySpec(
        name="world_biomes",
        source_files=("world/biomes.json",),
        collection_keys=("biomes",),
        goal="Generate new biome definitions with terrain, flora, fauna, and encounter tables.",
        constraints=("Follow existing biome schema.", "Species and resource references must be valid."),
        consumers=("engine.worldgen.registries.load_world_biomes()",),
    ),
    "world_species": FamilySpec(
        name="world_species",
        source_files=("world/species_templates.json",),
        collection_keys=("species_templates",),
        goal="Generate new species with habitats, culture hints, and stat modifiers.",
        constraints=("Culture hints must reference existing cultures.", "Follow existing species schema."),
        consumers=("engine.worldgen.registries.load_species_templates()",),
    ),
    "world_cultures": FamilySpec(
        name="world_cultures",
        source_files=("world/cultures.json",),
        collection_keys=("cultures",),
        goal="Generate new cultural templates with naming conventions, values, and traditions.",
        constraints=("Follow existing culture schema.", "Must be compatible with species assignment."),
        consumers=("engine.worldgen.registries.load_culture_templates()",),
    ),
    "world_buildings": FamilySpec(
        name="world_buildings",
        source_files=("world/building_templates.json",),
        collection_keys=("building_templates",),
        goal="Generate new building types for settlement construction.",
        constraints=("Furniture references must exist in furniture.json.", "Follow existing schema."),
        consumers=("engine.worldgen.registries.load_building_templates()",),
    ),
    "world_furniture": FamilySpec(
        name="world_furniture",
        source_files=("world/furniture.json",),
        collection_keys=("furniture",),
        goal="Generate new furniture items for building interiors.",
        constraints=("Follow existing furniture schema.", "Material references must be valid."),
        consumers=("engine.worldgen.registries.load_furniture_templates()",),
    ),
    "world_quests": FamilySpec(
        name="world_quests",
        source_files=("world/quest_templates.json",),
        collection_keys=("quest_templates",),
        goal="Generate new quest template patterns for worldgen quest generation.",
        constraints=("Quest kinds must be fetch/kill/escort/deliver/investigate/defend.", "Follow existing schema."),
        consumers=("engine.worldgen.registries.load_quest_templates()",),
        generatable=False,
    ),
    "interaction_rules": FamilySpec(
        name="interaction_rules",
        source_files=("interaction_rules.json",),
        collection_keys=(),
        goal="Generate new interaction rules for object types, skill checks, and AP costs.",
        constraints=("Skills must use Ember stat names: MIG, AGI, END, MND, INS, PRE.", "DC ranges must be reasonable (5-25)."),
        consumers=("engine.world.interactions_catalog",),
    ),
    # ── Non-generatable config/balance files ─────────────────────────
    "progression": FamilySpec(
        name="progression", source_files=("progression.json",), collection_keys=("progression",),
        goal="Add class abilities for new classes, expand stat_bonus_by_class, add skill_xp_thresholds variety.",
        constraints=("Do not change xp_thresholds or hp_per_level for existing classes.", "New class entries must follow existing schema."),
        consumers=("engine.data._shared.progression_registry()",),
    ),
    "colony_config": FamilySpec(
        name="colony_config", source_files=("colony_config.json",), collection_keys=("colony_config",),
        goal="Add new colony needs (entertainment, trade, exploration), more morale tiers, more room zones, more shortage quest types.",
        constraints=("Keep existing need IDs intact.", "New morale tiers must not overlap existing ranges.", "New room zones need valid furniture IDs."),
        consumers=("engine.kernel.colony_types", "engine.kernel.colony_runtime"),
    ),
    "economy_config": FamilySpec(
        name="economy_config", source_files=("economy_config.json",), collection_keys=("economy_config",),
        goal="Expand trade items, add store service types (repair, enchant, upgrade), add seasonal price modifiers, add merchant tier definitions.",
        constraints=("All item_def_ids must exist in items.json.", "Follow existing schema structure."),
        consumers=("engine.api.handlers.social_actions",),
    ),
    "quest_config": FamilySpec(
        name="quest_config", source_files=("quest_config.json",), collection_keys=("quest_config",),
        goal="Add more quest kinds (gather, smuggle, bounty, rescue, sabotage), more emergent shortage scenarios, seasonal quest triggers.",
        constraints=("New quest kinds need gold and xp in reward_scales.", "emergent_shortages items must exist in items.json."),
        consumers=("engine.worldgen.quest_generator",),
    ),
    "character_creation": FamilySpec(
        name="character_creation", source_files=("character_creation.json",), collection_keys=("character_creation",),
        goal="Add more creation questions, more answer options with diverse weight profiles, more background/origin paths.",
        constraints=("Keep existing question IDs.", "New answers must have class_weights/skill_weights matching existing classes."),
        consumers=("engine.data._shared.creation_registry()",),
    ),
    "materials": FamilySpec(
        name="materials", source_files=("materials.json",), collection_keys=(),
        goal="Add more material types (mythril, adamantine, dragonbone, darkwood, moonsilver, living_wood) with physics properties.",
        constraints=("Follow existing schema: density, impact_yield/fracture, shear_yield/fracture, max_edge, tags.", "Keep categories: metal, organic, stone."),
        consumers=("engine.kernel.data_loader",),
    ),
    "consequence_rules": FamilySpec(
        name="consequence_rules", source_files=("consequence_rules.json",), collection_keys=("consequence_rules",),
        goal="Add more consequence templates for varied actions (arson, poisoning, desertion, heresy, smuggling).",
        constraints=("Follow existing consequence schema.", "Severity levels must be consistent."),
        consumers=("engine.data._shared.consequence_rules_registry()",),
    ),
    "schedules": FamilySpec(
        name="schedules", source_files=("schedules.json",), collection_keys=("schedules",),
        goal="Add role-specific NPC schedules (guard_patrol, merchant_daily, priest_ritual, farmer_seasonal, scholar_library).",
        constraints=("Time periods: dawn, morning, afternoon, evening, night.", "Activities must be valid NPC actions."),
        consumers=("engine.data._shared.schedules_registry()",),
    ),
    "campaign_runtime": FamilySpec(
        name="campaign_runtime", source_files=("campaign_runtime.json",), collection_keys=("campaign_runtime",),
        goal="Add more arc titles, quest templates (bounty, rescue, heist, diplomatic), world events (plague, festival, war, eclipse, famine).",
        constraints=("Follow existing quest/event schema.", "Enemy/item references must exist in source data."),
        consumers=("engine.data._shared.campaign_runtime_registry()",),
    ),
    # ── Truly non-generatable (infrastructure/UI only) ───────────────
    "quality_tiers": FamilySpec(
        name="quality_tiers", source_files=("quality_tiers.json",), collection_keys=(),
        goal="Fixed quality tier set.", constraints=(), consumers=("engine.kernel.data_loader",), generatable=False,
    ),
    "runtime_config": FamilySpec(
        name="runtime_config", source_files=("runtime_config.json",), collection_keys=("runtime_config",),
        goal="Infrastructure config.", constraints=(), consumers=("engine.data._shared.runtime_config_registry()",), generatable=False,
    ),
    "inventory_layouts": FamilySpec(
        name="inventory_layouts", source_files=("inventory_layouts.json",), collection_keys=(),
        goal="UI slot definitions.", constraints=(), consumers=("engine.world.inventory_layouts",), generatable=False,
    ),
    "world_profiles": FamilySpec(
        name="world_profiles", source_files=("world/profiles.json",), collection_keys=("profiles",),
        goal="World gen parameters.", constraints=(), consumers=("engine.worldgen.registries",), generatable=False,
    ),
    "world_adapters": FamilySpec(
        name="world_adapters", source_files=("world/adapters/fantasy_ember.json", "world/adapters/scifi_frontier.json"),
        collection_keys=(), goal="Setting adapters.", constraints=(), consumers=("engine.worldgen.registries",), generatable=False,
    ),
}


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _spread_sample(entries: list[Any], limit: int = 12) -> list[Any]:
    if len(entries) <= limit:
        return entries
    indexes = {round(index * (len(entries) - 1) / (limit - 1)) for index in range(limit)}
    return [entries[index] for index in sorted(indexes)]


def _infer_keys(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    key_sets = [set(entry) for entry in entries if isinstance(entry, dict)]
    if not key_sets:
        return {"required": [], "optional": []}
    required = set.intersection(*key_sets)
    optional = set.union(*key_sets) - required
    return {"required": sorted(required), "optional": sorted(optional)}


def _scalar_tag(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _item_bank() -> dict[str, Any]:
    items = _load_json(DATA_DIR / "items.json")["items"]
    npcs = _load_json(DATA_DIR / "npc_templates.json")["npc_templates"]
    recipes = _load_json(DATA_DIR / "recipes.json")["recipes"]
    spells = _load_json(DATA_DIR / "spells.json")["spells"]
    worldgen = _load_json(DATA_DIR / "worldgen.json")["worldgen"]
    locations = _load_json(DATA_DIR / "locations.json")["locations"]
    history = _load_json(DATA_DIR / "history_tables.json")["history_tables"]
    campaigns = _load_json(DATA_DIR / "campaign_templates.json")["campaigns"]
    social = _load_json(DATA_DIR / "social_rules.json")["social_rules"]
    monsters = _load_json(DATA_DIR / "monsters.json")["monsters"]
    item_ids = sorted(item["id"] for item in items if "id" in item)
    recipe_item_ids = sorted(
        {
            part["item_id"]
            for entry in recipes
            for part in [*entry.get("ingredients", []), *entry.get("products", [])]
            if isinstance(part, dict) and part.get("item_id")
        }
    )
    reward_item_ids = sorted(
        {
            item_id
            for campaign in campaigns
            for quest in campaign.get("quests", [])
            for item_id in (quest.get("rewards") or {}).get("items", [])
        }
    )
    return {
        "item_ids": item_ids,
        "recipe_known_item_ids": sorted(set(item_ids) | set(recipe_item_ids)),
        "reward_item_ids": sorted(set(item_ids) | set(reward_item_ids)),
        "item_types": sorted({item["type"] for item in items}),
        "item_rarities": sorted({item["rarity"] for item in items if "rarity" in item}),
        "npc_roles": sorted({entry["role"] for entry in npcs}),
        "npc_dispositions": sorted({entry["disposition"] for entry in npcs}),
        "speech_styles": sorted({entry["speech_style"] for entry in npcs}),
        "faction_ids": sorted(history.get("all_factions", [])),
        "workstation_ids": sorted((locations.get("workstation_specs") or {}).keys()),
        "recipe_skills": sorted({entry["skill"] for entry in recipes}),
        "recipe_tools": sorted({tool for entry in recipes for tool in entry.get("tools", [])}),
        "recipe_failure_results": sorted({entry["failure_result"] for entry in recipes if entry.get("failure_result")}),
        "spell_schools": sorted({entry["school"] for entry in spells}),
        "spell_target_types": sorted({entry["target_type"] for entry in spells}),
        "spell_effect_types": sorted({effect["type"] for entry in spells for effect in entry.get("effects", []) if "type" in effect}),
        "monster_ids": sorted(entry["id"] for entry in monsters if "id" in entry),
        "campaign_ids": sorted(entry["id"] for entry in campaigns if "id" in entry),
        "campaign_difficulties": sorted({entry["difficulty"] for entry in campaigns if "difficulty" in entry}),
        "social_rule_sections": sorted(social.keys()),
        "worldgen_sections": sorted(worldgen.keys()),
        "zone_rule_ids": sorted((worldgen.get("zone_entity_rules") or {}).keys()),
        "worldgen_npc_roles": sorted({value for values in (worldgen.get("zone_entity_rules") or {}).values() for value in values.get("npcs", [])}),
        "worldgen_item_labels": sorted({value for values in (worldgen.get("zone_entity_rules") or {}).values() for value in values.get("items", [])}),
        "worldgen_enemy_labels": sorted({value for values in (worldgen.get("zone_entity_rules") or {}).values() for value in values.get("enemies", [])}),
        "default_npc_attitudes": sorted(set((social.get("default_npc_attitude") or {}).values())),
        "default_npc_alignments": sorted(set((social.get("default_npc_alignment") or {}).values())),
    }


def _workflow_family_names() -> list[str]:
    return [name for name in FAMILY_ORDER if FAMILY_SPECS[name].generatable]


def _review_assignments() -> dict[str, str]:
    names = _workflow_family_names()
    return {f"reviewer_{index + 1}": names[(index + 1) % len(names)] for index in range(len(names))}


def _packet_paths(work_root: Path, batch_id: str, family: str) -> dict[str, Path]:
    packets = work_root / "tmp" / "content_packets"
    return {
        "packet_json": packets / f"{family}.json",
        "packet_md": packets / f"{family}.md",
        "creator_prompt": packets / f"{family}_creator_prompt.txt",
        "reviewer_prompt": packets / f"{family}_reviewer_prompt.txt",
        "candidate": work_root / "candidates" / family / f"batch_{batch_id}.json",
        "review": work_root / "reviews" / family / f"batch_{batch_id}.md",
    }


def _build_list_packet(spec: FamilySpec, bank: dict[str, Any]) -> dict[str, Any]:
    source_path = DATA_DIR / spec.source_files[0]
    if not source_path.exists():
        return {"exemplars": [], "schema": {"required": [], "optional": []}, "reference_lists": {}, "identity_field": "id", "existing_ids": []}
    raw = _load_json(source_path)
    source = raw[spec.collection_keys[0]] if spec.collection_keys else raw
    if isinstance(source, dict):
        source = list(source.values())
    if not isinstance(source, list):
        source = [source] if source else []
    if spec.name == "items_equipment":
        source = [entry for entry in source if isinstance(entry, dict) and entry.get("type") in EQUIPMENT_TYPES]
    if spec.name == "items_supplies":
        source = [entry for entry in source if isinstance(entry, dict) and entry.get("type") not in EQUIPMENT_TYPES]
    # Reference lists per family — use what's available in bank.
    refs_map = {
        "npc_templates": ("item_ids", "faction_ids", "npc_roles", "npc_dispositions", "speech_styles"),
        "items_equipment": ("item_types", "item_rarities"),
        "items_supplies": ("item_types", "item_rarities"),
        "recipes": ("recipe_known_item_ids", "workstation_ids", "recipe_skills", "recipe_tools", "recipe_failure_results"),
        "spells": ("spell_schools", "spell_target_types", "spell_effect_types"),
        "monsters": ("item_ids", "monster_ids"),
        "classes": ("item_ids",),
        "locations": ("npc_roles", "workstation_ids", "item_ids"),
        "loot_tables": ("item_ids", "monster_ids", "item_rarities"),
        "dialog_defs": ("npc_roles", "item_ids", "faction_ids"),
        "institutions": ("npc_roles", "faction_ids"),
        "caravans": ("item_ids",),
        "factions": ("faction_ids",),
        "name_banks": (),
        "interaction_rules": ("npc_roles",),
    }
    ref_keys = refs_map.get(spec.name, ())
    reference_lists = {key: bank[key] for key in ref_keys if key in bank}
    # Determine identity field and collect existing IDs for duplicate prevention.
    entries = [e for e in source if isinstance(e, dict)]
    id_field = "id" if all("id" in e for e in entries) else ("dialog_id" if all("dialog_id" in e for e in entries) else "name")
    existing_ids = sorted({str(e.get(id_field, "")) for e in entries if e.get(id_field)})
    return {
        "exemplars": _spread_sample(entries, 12),
        "schema": _infer_keys(entries),
        "reference_lists": reference_lists,
        "identity_field": id_field,
        "existing_ids": existing_ids,
    }


def _build_worldgen_packet(bank: dict[str, Any]) -> dict[str, Any]:
    worldgen = _load_json(DATA_DIR / "worldgen.json")["worldgen"]
    sections = {
        "building_templates": dict(list(worldgen["building_templates"].items())[:3]),
        "entity_templates_by_location": worldgen["entity_templates_by_location"],
        "map_generator_room_templates": dict(list(worldgen["map_generator_room_templates"].items())[:2]),
        "zone_entity_rules": dict(list(worldgen["zone_entity_rules"].items())[:4]),
        "zone_layouts": dict(list(worldgen["zone_layouts"].items())[:2]),
        "zone_tile_palettes": dict(list(worldgen["zone_tile_palettes"].items())[:3]),
    }
    return {
        "exemplars": sections,
        "schema": {section: _scalar_tag(worldgen[section]) for section in sections},
        "reference_lists": {key: bank[key] for key in ("worldgen_sections", "zone_rule_ids", "worldgen_npc_roles", "worldgen_item_labels", "worldgen_enemy_labels")},
        "identity_field": "section_key",
    }


def _build_bundle_packet(bank: dict[str, Any]) -> dict[str, Any]:
    campaigns = _load_json(DATA_DIR / "campaign_templates.json")["campaigns"]
    history = _load_json(DATA_DIR / "history_tables.json")["history_tables"]
    social = _load_json(DATA_DIR / "social_rules.json")["social_rules"]
    return {
        "exemplars": {
            "campaigns": _spread_sample(campaigns, 3),
            "history_tables": {key: history[key] for key in list(history)[:6]},
            "social_rules": social,
        },
        "schema": {
            "campaigns": _infer_keys(campaigns),
            "history_tables": {key: _scalar_tag(value) for key, value in history.items()},
            "social_rules": {key: _scalar_tag(value) for key, value in social.items()},
        },
        "reference_lists": {key: bank[key] for key in ("campaign_ids", "campaign_difficulties", "monster_ids", "reward_item_ids", "faction_ids", "social_rule_sections", "npc_roles", "default_npc_attitudes", "default_npc_alignments")},
        "identity_field": "id",
    }


def prepare_packets(batch_id: str | None = None, work_root: Path | None = None) -> dict[str, Any]:
    root = work_root or DEFAULT_WORK_ROOT
    stamp = batch_id or _now_stamp()
    bank = _item_bank()
    assignments = _review_assignments()
    manifest = {"batch_id": stamp, "generated_at": datetime.now().isoformat(), "families": [], "review_assignments": assignments}
    generatable_families = _workflow_family_names()
    for name in generatable_families:
        spec = FAMILY_SPECS[name]
        paths = _packet_paths(root, stamp, name)
        packet = _build_worldgen_packet(bank) if name == "worldgen" else _build_bundle_packet(bank) if name == "campaign_history_social" else _build_list_packet(spec, bank)
        packet.update(
            {
                "family_name": spec.name,
                "source_files": list(spec.source_files),
                "collection_keys": list(spec.collection_keys),
                "candidate_output_file": str(paths["candidate"]),
                "review_output_file": str(paths["review"]),
                "family_goal": spec.goal,
                "family_constraints": list(spec.constraints),
                "consumer_notes": list(spec.consumers),
                "target_entry_range": "25-100",
            }
        )
        _write_json(paths["packet_json"], packet)
        md = [
            f"# {spec.name}",
            "",
            f"- Source files: {', '.join(spec.source_files)}",
            f"- Collection keys: {', '.join(spec.collection_keys)}",
            f"- Candidate output: `{paths['candidate']}`",
            f"- Review output: `{paths['review']}`",
            f"- Target: {spec.goal}",
            "- Constraints:",
            *[f"  - {line}" for line in spec.constraints],
            "- Consumer notes:",
            *[f"  - {line}" for line in spec.consumers],
        ]
        _write_text(paths["packet_md"], "\n".join(md))
        existing_ids = packet.get("existing_ids", [])
        prompt_args = {
            "family_name": spec.name,
            "source_file": ", ".join(spec.source_files),
            "collection_keys": ", ".join(spec.collection_keys),
            "candidate_output_file": str(paths["candidate"]),
            "review_output_file": str(paths["review"]),
            "family_goal": spec.goal,
            "family_constraints": "\n".join(f"- {line}" for line in spec.constraints),
            "examples": json.dumps(packet["exemplars"], indent=2, ensure_ascii=False),
            "reference_lists": json.dumps(packet["reference_lists"], indent=2, ensure_ascii=False),
            "consumer_notes": "\n".join(f"- {line}" for line in spec.consumers),
            "existing_ids": json.dumps(existing_ids) if existing_ids else "(none — this is a new family)",
        }
        _write_text(paths["creator_prompt"], _template("content_creator_prompt.txt").format(**prompt_args))
        _write_text(paths["reviewer_prompt"], _template("content_reviewer_prompt.txt").format(**prompt_args))
        manifest["families"].append({"name": name, **{key: str(value) for key, value in paths.items() if key in {"candidate", "review", "packet_json", "packet_md"}}})
    master_prompt = _template("content_master_prompt.txt").format(
        family_table="\n".join(f"- creator_{index + 1}: {name}" for index, name in enumerate(generatable_families)),
        review_table="\n".join(f"- {reviewer}: reviews `{family}`" for reviewer, family in assignments.items()),
        repo_notes="- `spells.json` currently has no `id` field; preserve the source schema.\n- `campaign_templates.json` currently uses the top-level key `campaigns`.\n- Worldgen expansion should stay inside the existing additive sections listed in the work packets.",
    )
    _write_text(root / "tmp" / "content_packets" / "copilot_master_prompt.txt", master_prompt)
    _write_json(root / "tmp" / "content_packets" / "manifest.json", manifest)
    return manifest


def validate_batches(batch_id: str | None = None, work_root: Path | None = None, strict_missing: bool = True) -> dict[str, Any]:
    from tools.content_validator import validate_batches as _validate_batches

    return _validate_batches(batch_id=batch_id, work_root=work_root, strict_missing=strict_missing)


def run_dry_run(batch_id: str | None = None, work_root: Path | None = None) -> dict[str, Any]:
    from tools.content_validator import run_dry_run as _run_dry_run

    return _run_dry_run(batch_id=batch_id, work_root=work_root)


def generate_content(batch_id: str | None = None, work_root: Path | None = None,
                     model: str = "gpt-4.1", timeout: int = 300) -> dict:
    """Generate candidates for all families using Copilot CLI."""
    from tools.content_executor import generate_all
    root = work_root or DEFAULT_WORK_ROOT
    manifest_path = root / "tmp" / "content_packets" / "manifest.json"
    if not manifest_path.exists():
        prepare_packets(batch_id=batch_id, work_root=root)
    return generate_all(str(manifest_path), model=model, timeout=timeout)


def review_content(batch_id: str | None = None, work_root: Path | None = None,
                   model: str = "gpt-4.1", timeout: int = 300) -> dict:
    """Run reviewer prompts on generated candidates using Copilot CLI."""
    from tools.content_executor import review_all
    root = work_root or DEFAULT_WORK_ROOT
    manifest_path = root / "tmp" / "content_packets" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Run 'prepare' first.")
    return review_all(str(manifest_path), model=model, timeout=timeout)


def merge_content(work_root: Path | None = None, dry_run: bool = False) -> dict:
    """Merge validated candidates into primary data files."""
    from tools.content_merger import merge_all
    root = work_root or DEFAULT_WORK_ROOT
    manifest_path = root / "tmp" / "content_packets" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Run 'prepare' and 'generate' first.")
    return merge_all(str(manifest_path), dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--batch-id")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--batch-id")
    validate.add_argument("--allow-missing", action="store_true")
    dry_run = subparsers.add_parser("dry-run")
    dry_run.add_argument("--batch-id")
    gen = subparsers.add_parser("generate", help="Generate content via GitHub Models API")
    gen.add_argument("--batch-id")
    gen.add_argument("--model", default="gpt-4.1", help="Model name (default: gpt-4o)")
    gen.add_argument("--timeout", type=int, default=180, help="Timeout per family in seconds")
    rev = subparsers.add_parser("review", help="Review generated candidates via AI")
    rev.add_argument("--batch-id")
    rev.add_argument("--model", default="gpt-4.1", help="Model name for review")
    rev.add_argument("--timeout", type=int, default=180)
    merge = subparsers.add_parser("merge", help="Merge validated candidates into data files")
    merge.add_argument("--dry-run", action="store_true", help="Show what would be merged without writing")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare_packets(batch_id=args.batch_id, work_root=args.work_root)
        return 0
    if args.command == "validate":
        result = validate_batches(batch_id=args.batch_id, work_root=args.work_root, strict_missing=not args.allow_missing)
        return 0 if result["overall_status"] in {"pass", "pass_with_warnings"} else 1
    if args.command == "generate":
        results = generate_content(batch_id=args.batch_id, work_root=args.work_root, model=args.model, timeout=args.timeout)
        for name, info in results.items():
            status = "OK" if info["ok"] else "FAIL"
            print(f"  {name}: {status} — {info['message']}")
        return 0 if all(r["ok"] for r in results.values()) else 1
    if args.command == "review":
        results = review_content(batch_id=args.batch_id, work_root=args.work_root, model=args.model, timeout=args.timeout)
        for name, info in results.items():
            status = "OK" if info["ok"] else "FAIL"
            print(f"  {name}: {status} — {info['message']}")
        return 0 if all(r["ok"] for r in results.values()) else 1
    if args.command == "merge":
        import logging as _log
        _log.basicConfig(level=_log.INFO, format="%(message)s")
        results = merge_content(work_root=args.work_root, dry_run=args.dry_run)
        total_added = sum(r["added"] for r in results.values())
        total_skipped = sum(r["skipped"] for r in results.values())
        total_errors = sum(len(r["errors"]) for r in results.values())
        for name, r in results.items():
            status = "OK" if not r["errors"] else "WARN"
            print(f"  {name}: +{r['added']} added, {r['skipped']} skipped {status}")
            for e in r["errors"]:
                print(f"    ERROR: {e}")
        mode = "DRY-RUN" if args.dry_run else "MERGED"
        print(f"\n{mode}: {total_added} added, {total_skipped} skipped, {total_errors} errors")
        return 0 if total_errors == 0 else 1
    run_dry_run(batch_id=args.batch_id, work_root=args.work_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
