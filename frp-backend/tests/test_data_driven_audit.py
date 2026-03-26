from pathlib import Path

from engine.core.character_creation import (
    ABILITY_ORDER,
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    CLASS_STAT_PRIORITIES,
    CREATION_QUESTIONS,
)
from engine.data_loader import (
    get_building_templates,
    get_context_actions,
    get_creation_ability_order,
    get_creation_class_default_skills,
    get_creation_class_skill_counts,
    get_creation_class_skill_options,
    get_creation_class_stat_priorities,
    get_creation_questions,
    get_location_enemy_templates,
    get_location_item_templates,
    get_location_npc_templates,
    get_map_generator_room_templates,
    get_map_generator_tile_sets,
    get_scene_fallback_narratives,
    get_scene_system_prompt,
    get_zone_entity_rules,
    get_zone_layouts,
    get_zone_tile_palettes,
    list_monsters,
    list_recipes,
)
from engine.map.zones import BUILDING_TEMPLATES, ZONE_ENTITY_RULES, ZONE_LAYOUTS, ZONE_TILE_PALETTES
from engine.orchestrator import DMNarrator, EntityPlacer, MapGenerator
from engine.world.crafting import ALL_RECIPES


def test_crafting_registry_matches_json_loader():
    assert set(ALL_RECIPES.keys()) == {recipe["id"] for recipe in list_recipes()}


def test_zone_registries_match_loader():
    assert set(BUILDING_TEMPLATES.keys()) == set(get_building_templates().keys())
    assert {zone_type.value for zone_type in ZONE_TILE_PALETTES.keys()} == set(get_zone_tile_palettes().keys())
    assert {zone_type.value for zone_type in ZONE_ENTITY_RULES.keys()} == set(get_zone_entity_rules().keys())
    assert set(ZONE_LAYOUTS.keys()) == set(get_zone_layouts().keys())


def test_orchestrator_registries_match_loader():
    assert MapGenerator.TILE_SETS == get_map_generator_tile_sets()
    assert MapGenerator.ROOM_TEMPLATES == get_map_generator_room_templates()
    assert EntityPlacer.NPC_TEMPLATES_BY_LOCATION == get_location_npc_templates()
    assert EntityPlacer.ITEM_TEMPLATES_BY_LOCATION == get_location_item_templates()
    assert EntityPlacer.ENEMY_TEMPLATES_BY_LOCATION == get_location_enemy_templates()
    assert EntityPlacer.CONTEXT_ACTIONS == get_context_actions()
    assert DMNarrator.SCENE_SYSTEM_PROMPT == get_scene_system_prompt()
    assert DMNarrator.FALLBACK_NARRATIVES == get_scene_fallback_narratives()


def test_character_creation_config_matches_loader():
    assert ABILITY_ORDER == get_creation_ability_order()
    assert CLASS_SKILL_OPTIONS == get_creation_class_skill_options()
    assert CLASS_SKILL_COUNTS == get_creation_class_skill_counts()
    assert CLASS_DEFAULT_SKILLS == get_creation_class_default_skills()
    assert CLASS_STAT_PRIORITIES == get_creation_class_stat_priorities()
    assert CREATION_QUESTIONS == get_creation_questions()


def test_monster_spawn_source_data_exists():
    monster_names = {monster["name"] for monster in list_monsters()}
    assert "Goblin" in monster_names
    assert "Skeleton" in monster_names
    assert "Orc" in monster_names


def test_runtime_content_json_loads_are_centralized():
    engine_root = Path(__file__).resolve().parents[1] / "engine"
    allowed = {
        "data_loader.py",
        "llm/__init__.py",
        "api/save_system.py",
        "api/ws_routes.py",
        "save/__init__.py",
    }
    offenders = []
    for path in sorted(engine_root.rglob("*.py")):
        rel = path.relative_to(engine_root).as_posix()
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if "json.load(" in text or "json.loads(" in text:
            offenders.append(rel)
    assert not offenders, f"Direct JSON loading outside data_loader: {offenders}"
