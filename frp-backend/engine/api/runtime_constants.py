"""Data-backed runtime constants shared across API orchestration modules."""
from __future__ import annotations

from engine.data_loader import (
    CLASSES,
    get_creation_class_aliases,
    get_creation_default_class,
    get_default_npc_alignment_map,
    get_default_npc_attitude_map,
    get_default_opening_scene,
    get_hostile_keywords,
    get_interaction_hold_turns,
    get_location_stock_baseline,
    get_npc_visuals,
    get_opening_scenes,
    get_role_production_map,
    get_social_attitude_dcs,
    get_think_topic_skills,
    get_workstation_anchors,
    get_workstation_specs,
    get_xp_rewards,
)


def _build_starter_kits() -> dict:
    kits = {}
    for class_id, class_data in CLASSES.items():
        kits[class_id] = class_data.get("starting_equipment", [])
    return kits


XP_REWARDS = get_xp_rewards()
NPC_VISUALS = {role: tuple(spec) for role, spec in get_npc_visuals().items()}
WORKSTATION_SPECS = get_workstation_specs()
WORKSTATION_ANCHORS = get_workstation_anchors()
SOCIAL_ATTITUDE_DCS = get_social_attitude_dcs()
DEFAULT_NPC_ATTITUDE = get_default_npc_attitude_map()
DEFAULT_NPC_ALIGNMENT = get_default_npc_alignment_map()
THINK_TOPIC_SKILLS = {skill: set(keywords) for skill, keywords in get_think_topic_skills().items()}
ROLE_PRODUCTION = {role: tuple(values) for role, values in get_role_production_map().items()}
HOSTILE_KEYWORDS = get_hostile_keywords()
CLASS_ALIASES = get_creation_class_aliases()
DEFAULT_PLAYER_CLASS = get_creation_default_class()
DEFAULT_OPENING_SCENE = get_default_opening_scene()
LOCATION_STOCK_BASELINE = get_location_stock_baseline()
INTERACTION_HOLD_TURNS = get_interaction_hold_turns()
STARTER_KITS = _build_starter_kits()
OPENING_SCENES = [
    (
        scene.get("location", DEFAULT_OPENING_SCENE.get("location", "Stone Bridge Tavern")),
        scene.get("description", DEFAULT_OPENING_SCENE.get("description", "")),
    )
    for scene in get_opening_scenes()
] or [
    (
        DEFAULT_OPENING_SCENE.get("location", "Stone Bridge Tavern"),
        DEFAULT_OPENING_SCENE.get(
            "description",
            "Low rafters, the smell of pipe smoke. A fire crackles in the hearth. The door creaks open - someone has arrived.",
        ),
    ),
]
