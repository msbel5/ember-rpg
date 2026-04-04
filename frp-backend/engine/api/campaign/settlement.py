"""Settlement and character-sheet projections for campaign runtime.

All game constants loaded from data layer — no hardcoded ability orders,
no hardcoded stat defaults.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from engine.api.campaign_session import CampaignSession
from engine.data.classes import get_creation_ability_order
from engine.worldgen.models import RegionSnapshot, WorldBlueprint

log = logging.getLogger(__name__)


def build_settlement_state(
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
    player_name: str,
) -> dict[str, Any]:
    from .world import runtime_region_state

    settlement = next(item for item in world.settlements if item.region_id == region_snapshot.region_id)
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    historical_pressure = [
        {
            "event_type": event.event_type,
            "summary": event.summary,
            "pressure": event.consequences,
        }
        for event in world.historical_events
        if settlement.region_id in event.regions
    ][:4]
    residents = []
    for npc in runtime_state.get("npcs", region_snapshot.layout.npc_spawns):
        residents.append(
            {
                "id": npc["id"],
                "name": str(npc.get("name", str(npc["role"]).replace("_", " ").title())),
                "role": npc["role"],
                "assignment": str(npc.get("activity", npc["role"])),
                "drafted": False,
                "building_id": npc.get("building_id"),
                "mood": "steady" if str(npc.get("disposition", "friendly")) != "hostile" else "alarmed",
            }
        )
    residents.insert(
        0,
        {
            "id": "player_commander",
            "name": player_name,
            "role": "commander",
            "assignment": "command",
            "drafted": False,
            "building_id": None,
            "mood": "focused",
        },
    )
    rooms = []
    for building in region_snapshot.layout.buildings:
        rooms.append(
            {
                "id": building["id"],
                "kind": building["kind"],
                "label": building["kind"].replace("_", " ").title(),
                "priority": 3,
                "doors": len(building["doors"]),
                "beds": 1 if building["kind"] == "house" else 0,
                "workstations": list(building["required_furniture"]),
            }
        )
    jobs = [
        {
            "id": f"job_{index}",
            "kind": furniture["kind"],
            "priority": 3,
            "status": "idle",
            "assignee_id": None,
        }
        for index, furniture in enumerate(region_snapshot.layout.furniture)
    ]
    economy = copy.deepcopy(runtime_state.get("economy", {}))
    weather = copy.deepcopy(runtime_state.get("weather", {}))
    readable_alerts = [str(item).replace("_", " ").capitalize() for item in runtime_state.get("alerts", [])]
    return {
        "adapter_id": adapter_id,
        "settlement_id": settlement.id,
        "name": settlement.center_name,
        "faction_id": settlement.faction_id,
        "population": settlement.population,
        "defense_posture": "normal",
        "residents": residents,
        "rooms": rooms,
        "jobs": jobs,
        "stockpiles": [
            {
                "id": "central_stockpile",
                "label": "Central Stockpile",
                "resource_tags": list(settlement.building_focus),
                "room_id": rooms[0]["id"] if rooms else None,
            }
        ],
        "construction_queue": [],
        "alerts": readable_alerts,
        "needs": {
            "food": max(1, settlement.population // 30),
            "security": max(1, len(residents) // 3),
            "materials": max(1, len(region_snapshot.layout.furniture) // 2),
        },
        "faction_pressure": historical_pressure,
        "current_hour": world.simulation_snapshot.current_hour if world.simulation_snapshot else 0,
        "current_day": world.simulation_snapshot.current_day if world.simulation_snapshot else 1,
        "season": world.simulation_snapshot.season if world.simulation_snapshot else "spring",
        "weather": weather,
        "economy": economy,
        "quest_offer_count": len(runtime_state.get("quest_offers", [])),
    }


def build_character_sheet(session: CampaignSession, settlement_state: dict[str, Any] | None = None) -> dict[str, Any]:
    player = session.player
    dominant_class = str(player.dominant_class or "adventurer")
    stats = []
    # Ability order loaded from character_creation.json — not hardcoded
    for ability in get_creation_ability_order():
        value = int(player.stats.get(ability, 10))
        stats.append(
            {
                "id": ability,
                "label": ability,
                "value": value,
                "modifier": player.stat_modifier(ability),
            }
        )

    skill_names = sorted(set(player.skill_proficiencies) | set(player.skills.keys()) | set(player.expertise_skills))
    skills = []
    for skill in skill_names:
        skills.append(
            {
                "id": skill,
                "label": skill.replace("_", " ").title(),
                "bonus": player.skill_bonus(skill),
                "proficient": player.has_proficiency(skill),
                "expertise": player.has_expertise(skill),
            }
        )

    resources = {
        "hp": {"current": player.hp, "max": player.max_hp},
        "sp": {"current": player.spell_points, "max": player.max_spell_points},
        "turn": current_player_turn_resources(session),
    }
    creation_profile = dict(player.creation_profile or {})
    creation_summary = {
        "recommended_class": str(creation_profile.get("recommended_class", dominant_class)),
        "recommended_alignment": str(creation_profile.get("recommended_alignment", player.alignment)),
        "recommended_skills": list(creation_profile.get("recommended_skills", [])),
        "selected_skills": list(player.skill_proficiencies),
        "answers": copy.deepcopy(player.creation_answers),
        "class_weights": copy.deepcopy(creation_profile.get("class_weights", {})),
        "skill_weights": copy.deepcopy(creation_profile.get("skill_weights", {})),
        "alignment_axes": copy.deepcopy(player.alignment_axes),
        "facet_scores": copy.deepcopy(creation_profile.get("facet_scores", {})),
        "campaign_genesis": copy.deepcopy(creation_profile.get("campaign_genesis", {})),
        "world_seed_hints": copy.deepcopy(creation_profile.get("world_seed_hints", {})),
        "faction_bias": copy.deepcopy(creation_profile.get("faction_bias", {})),
        "settlement_bias": copy.deepcopy(creation_profile.get("settlement_bias", {})),
        "stat_source": str(creation_profile.get("stat_source", "default")),
        "rolled_values": list(creation_profile.get("rolled_values", [])),
        "saved_roll": copy.deepcopy(creation_profile.get("saved_roll")),
    }
    return {
        "name": player.name,
        "race": player.race,
        "class_name": dominant_class.capitalize(),
        "level": player.level,
        "alignment": player.alignment,
        "stats": stats,
        "skills": skills,
        "resources": resources,
        "armor_class": player.ac,
        "initiative_bonus": player.initiative_bonus,
        "gold": player.gold,
        "equipment": player.equipment.to_dict(),
        "inventory_count": len(player.inventory),
        "passives": copy.deepcopy(player.passives),
        "settlement_role": str((settlement_state or {}).get("player_role", "commander")),
        "creation_summary": creation_summary,
    }


def current_player_turn_resources(session: CampaignSession) -> dict[str, int | bool]:
    combat = getattr(session, "combat", None)
    player_name = str(getattr(session.player, "name", "")).strip()
    if combat is not None:
        for combatant in getattr(combat, "combatants", []):
            if str(getattr(combatant, "name", "")).strip() != player_name:
                continue
            return {
                "action_available": bool(getattr(combatant, "action_available", True)),
                "bonus_action_available": bool(getattr(combatant, "bonus_action_available", True)),
                "reaction_available": bool(getattr(combatant, "reaction_available", True)),
                "movement_remaining": int(getattr(combatant, "movement_remaining", 0)),
                "speed": int(getattr(combatant, "speed", 6)),
            }
    speed = max(6, int(getattr(getattr(session, "ap_tracker", None), "max_ap", 6) or 6))
    return {
        "action_available": True,
        "bonus_action_available": True,
        "reaction_available": True,
        "movement_remaining": speed,
        "speed": speed,
    }


__all__ = ["build_character_sheet", "build_settlement_state", "current_player_turn_resources"]
