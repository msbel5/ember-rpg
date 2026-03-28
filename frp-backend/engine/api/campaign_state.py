"""State builders and session hydration helpers for campaign-first runtime."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.api.game_session import GameSession
from engine.core.dm_agent import SceneType
from engine.map import MapData, Room, TileType
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.worldgen import (
    WorldSeed,
    adapt_species,
    generate_world,
    initialize_simulation,
    load_adapter_pack,
    seed_civilizations,
    seed_species,
    simulate_history,
    snapshot_world,
)
from engine.worldgen.models import RegionSnapshot, WorldBlueprint

if TYPE_CHECKING:
    from engine.api.campaign_runtime import CampaignContext


_TERRAIN_TILE_MAP: dict[str, TileType] = {
    "road": TileType.ROAD,
    "cobble": TileType.ROAD,
    "cobblestone": TileType.ROAD,
    "dirt_path": TileType.ROAD,
    "wall": TileType.WALL,
    "door": TileType.DOOR,
    "floor": TileType.FLOOR,
    "wood_floor": TileType.FLOOR,
    "stone_floor": TileType.FLOOR,
    "marble": TileType.FLOOR,
    "tavern_floor": TileType.FLOOR,
    "sand": TileType.FLOOR,
    "swamp": TileType.FLOOR,
    "grass": TileType.FLOOR,
    "water": TileType.WATER,
    "tree": TileType.TREE,
    "well": TileType.WALL,
    "fountain": TileType.WALL,
}

_ROLE_GLYPHS: dict[str, str] = {
    "smith": "S",
    "innkeeper": "I",
    "bard": "B",
    "priest": "P",
    "merchant": "M",
    "guard": "G",
    "resident": "R",
    "mayor": "M",
    "scribe": "S",
    "alchemist": "A",
    "baker": "B",
    "stablehand": "H",
    "quartermaster": "Q",
    "jailer": "J",
    "scout": "C",
    "warden": "W",
    "researcher": "R",
}

_ROLE_COLORS: dict[str, str] = {
    "smith": "yellow",
    "innkeeper": "magenta",
    "bard": "cyan",
    "priest": "white",
    "merchant": "yellow",
    "guard": "orange",
    "resident": "green",
    "mayor": "light_blue",
    "scribe": "white",
    "alchemist": "purple",
    "baker": "yellow",
    "stablehand": "green",
    "quartermaster": "light_blue",
    "jailer": "orange",
    "scout": "light_blue",
    "warden": "orange",
    "researcher": "purple",
}

_ABILITY_ORDER: list[str] = ["MIG", "AGI", "END", "MND", "INS", "PRE"]


def build_world(*, adapter_id: str, profile_id: str, seed: int) -> WorldBlueprint:
    adapter = load_adapter_pack(adapter_id)
    world = generate_world(int(WorldSeed(seed)), profile_id)
    world = seed_species(world)
    allowed_species = set(adapter.get("allowed_species") or [])
    if allowed_species:
        world.species_lineages = [
            lineage for lineage in world.species_lineages if lineage.species_id in allowed_species
        ]
        world.domestication_pools = {
            role: [species_id for species_id in species_ids if species_id in allowed_species]
            for role, species_ids in world.domestication_pools.items()
        }
    world = adapt_species(world, adapter_id)
    world = seed_civilizations(world)
    world = simulate_history(world)
    world = initialize_simulation(world)
    world.metadata["adapter_id"] = adapter_id
    return world


def region_payload(context: "CampaignContext") -> dict[str, Any]:
    snapshot = context.region_snapshot.to_dict()
    snapshot["metadata"]["explainability"] = copy.deepcopy(
        next(
            (
                region.get("explainability", {})
                for region in context.world.regions
                if region["id"] == context.region_snapshot.region_id
            ),
            {},
        )
    )
    return snapshot


def map_payload_from_region(region_snapshot: RegionSnapshot) -> dict[str, Any]:
    tiles: list[list[str]] = []
    for row in region_snapshot.typed_tiles:
        tiles.append([str(tile.get("terrain", "grass")) for tile in row])
    return {
        "width": region_snapshot.width,
        "height": region_snapshot.height,
        "spawn_point": list(choose_spawn_point(region_snapshot)),
        "tiles": tiles,
        "metadata": {
            "map_type": "campaign_region",
            "region_id": region_snapshot.region_id,
            "biome_id": region_snapshot.biome_id,
        },
    }


def campaign_payload(context: "CampaignContext") -> dict[str, Any]:
    session_data = context.session.to_dict()
    runtime_state = _runtime_region_state(context.world, context.region_snapshot.region_id)
    return {
        "world": {
            "seed": context.world.seed,
            "profile_id": context.world.profile_id,
            "adapter_id": context.adapter_id,
            "active_region_id": context.world.simulation_snapshot.active_region_id,
            "faction_count": len(context.world.factions),
            "settlement_count": len(context.world.settlements),
            "history_end_year": context.world.history_end_year,
            "current_hour": context.world.simulation_snapshot.current_hour if context.world.simulation_snapshot else 0,
            "current_day": context.world.simulation_snapshot.current_day if context.world.simulation_snapshot else 1,
            "season": context.world.simulation_snapshot.season if context.world.simulation_snapshot else "spring",
            "weather": copy.deepcopy(runtime_state.get("weather", {})),
        },
        "player": session_data["player"],
        "scene": session_data["scene"],
        "location": session_data["location"],
        "combat": session_data.get("combat"),
        "conversation_state": session_data.get("conversation_state", {}),
        "region": region_payload(context),
        "map_data": map_payload_from_region(context.region_snapshot),
        "world_entities": build_world_entities(context.world, context.region_snapshot, context.adapter_id),
        "ground_items": copy.deepcopy(session_data.get("ground_items", [])),
        "active_quests": copy.deepcopy(runtime_state.get("active_quests", session_data.get("active_quests", []))),
        "quest_offers": copy.deepcopy(runtime_state.get("quest_offers", session_data.get("quest_offers", []))),
        "settlement": copy.deepcopy(context.settlement_state),
        "character_sheet": build_character_sheet(context.session, context.settlement_state),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-12:]),
    }


def persist_campaign_state(context: "CampaignContext") -> None:
    context.session.campaign_state["campaign_v2"] = {
        "campaign_id": context.campaign_id,
        "adapter_id": context.adapter_id,
        "profile_id": context.profile_id,
        "seed": context.seed,
        "active_region_id": context.region_snapshot.region_id,
        "world_snapshot": snapshot_world(context.world),
        "settlement_state": copy.deepcopy(context.settlement_state),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-20:]),
    }


def apply_region_to_session(
    *,
    session: GameSession,
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    settlement_state: dict[str, Any],
    campaign_id: str,
    adapter_id: str,
    profile_id: str,
    seed: int,
    preserve_position: bool = False,
) -> None:
    active_settlement = next(
        (item for item in world.settlements if item.region_id == region_snapshot.region_id),
        world.settlements[0],
    )
    map_data = build_map_data(region_snapshot)
    session.map_data = map_data
    next_position = list(map_data.spawn_point)
    if preserve_position and session.position:
        px = int(session.position[0])
        py = int(session.position[1])
        if 0 <= py < region_snapshot.height and 0 <= px < region_snapshot.width and region_snapshot.typed_tiles[py][px]["passable"]:
            next_position = [px, py]
    session.position = next_position
    session.dm_context.scene_type = SceneType.EXPLORATION
    session.dm_context.location = active_settlement.center_name
    session.entities = {}
    session.spatial_index = SpatialIndex()
    session.player_entity = Entity(
        id="player",
        entity_type=EntityType.NPC,
        name=session.player.name,
        position=tuple(session.position),
        glyph="@",
        color="white",
        blocking=True,
        hp=session.player.hp,
        max_hp=session.player.max_hp,
        disposition="friendly",
    )
    session.spatial_index.add(session.player_entity)
    session.viewport = None
    seed_region_entities(session, world, region_snapshot, adapter_id)
    session.campaign_state.setdefault("active_quests", [])
    session.campaign_state.setdefault("completed_quests", [])
    session.campaign_state.setdefault("failed_quests", [])
    session.campaign_state.setdefault("completed_quest_ids", [])
    session.campaign_state.setdefault("failed_quest_ids", [])
    session.campaign_state.setdefault("emergent_counter", 0)
    session.campaign_state["active_region_id"] = region_snapshot.region_id
    session.campaign_state["campaign_id"] = campaign_id
    session.campaign_state["adapter_id"] = adapter_id
    session.campaign_state["profile_id"] = profile_id
    session.campaign_state["world_seed"] = seed
    session.campaign_state["settlement_state"] = copy.deepcopy(settlement_state)
    runtime_state = _runtime_region_state(world, region_snapshot.region_id)
    session.campaign_state["active_quests"] = copy.deepcopy(runtime_state.get("active_quests", []))
    session.campaign_state["quest_offers"] = copy.deepcopy(runtime_state.get("quest_offers", []))
    session.ensure_consistency()


def build_map_data(region_snapshot: RegionSnapshot) -> MapData:
    terrain_tiles: list[list[TileType]] = []
    rooms: list[Room] = []
    for building in region_snapshot.layout.buildings:
        rooms.append(
            Room(
                x=int(building["x"]),
                y=int(building["y"]),
                width=int(building["width"]),
                height=int(building["height"]),
                room_type=str(building["kind"]),
            )
        )
    for row in region_snapshot.typed_tiles:
        terrain_tiles.append(
            [
                _TERRAIN_TILE_MAP.get(str(tile.get("terrain", "floor")), TileType.FLOOR)
                for tile in row
            ]
        )
    spawn_point = choose_spawn_point(region_snapshot)
    return MapData(
        width=region_snapshot.width,
        height=region_snapshot.height,
        tiles=terrain_tiles,
        rooms=rooms,
        spawn_point=spawn_point,
        exit_points=[],
        metadata={
            "map_type": "campaign_region",
            "region_id": region_snapshot.region_id,
            "biome_id": region_snapshot.biome_id,
        },
    )


def choose_spawn_point(region_snapshot: RegionSnapshot) -> tuple[int, int]:
    cx = int(region_snapshot.layout.center_feature["x"])
    cy = int(region_snapshot.layout.center_feature["y"]) + 2
    if 0 <= cy < region_snapshot.height and region_snapshot.typed_tiles[cy][cx]["passable"]:
        return (cx, cy)
    for x, y in region_snapshot.layout.road_tiles:
        tile = region_snapshot.typed_tiles[y][x]
        if tile["passable"]:
            return (int(x), int(y))
    return (1, 1)


def _runtime_region_state(world: WorldBlueprint, region_id: str) -> dict[str, Any]:
    if world.simulation_snapshot is None:
        return {}
    return dict(world.simulation_snapshot.region_states.get(region_id, {}))


def _furniture_template(kind: str) -> str:
    return {
        "forge": "anvil",
        "workbench": "table",
        "bar_counter": "bench",
        "display_table": "table",
        "rack": "chest",
        "desk": "table",
        "cabinet": "bookshelf",
        "cauldron": "altar",
        "oven": "altar",
        "sack": "crate",
        "trough": "bench",
        "hay_bale": "crate",
        "cell_door": "door",
        "keys": "chest",
        "well_bucket": "barrel",
        "loom": "table",
        "press": "table",
        "cask": "barrel",
        "lantern": "altar",
        "map_table": "table",
        "stool": "chair",
        "ward_totem": "altar",
    }.get(kind, kind)


def _furniture_actions(kind: str) -> list[str]:
    return {
        "forge": ["examine", "use"],
        "anvil": ["examine", "use"],
        "bar_counter": ["examine", "trade"],
        "altar": ["examine", "pray"],
        "bed": ["examine", "rest"],
        "bookshelf": ["examine", "read"],
        "crate": ["examine", "search"],
        "barrel": ["examine", "search"],
        "bench": ["examine", "sit"],
        "chair": ["examine", "sit"],
    }.get(kind, ["examine"])


def build_world_entities(world: WorldBlueprint, region_snapshot: RegionSnapshot, adapter_id: str) -> list[dict[str, Any]]:
    del adapter_id
    runtime_state = _runtime_region_state(world, region_snapshot.region_id)
    entities: list[dict[str, Any]] = []
    for npc in runtime_state.get("npcs", region_snapshot.layout.npc_spawns):
        entities.append(
            {
                "id": str(npc["id"]),
                "entity_type": "npc",
                "name": str(npc.get("name", str(npc.get("role", "Resident")).replace("_", " ").title())),
                "position": [int(npc["x"]), int(npc["y"])],
                "role": str(npc.get("role", "resident")),
                "template": str(npc.get("template", npc.get("role", "merchant"))),
                "disposition": str(npc.get("disposition", "friendly")),
                "context_actions": list(npc.get("context_actions", ["talk", "examine"])),
            }
        )
    for furniture in region_snapshot.layout.furniture:
        entities.append(
            {
                "id": str(furniture.get("id", f"{furniture['kind']}_{furniture['x']}_{furniture['y']}")),
                "entity_type": "furniture",
                "name": str(furniture["kind"]).replace("_", " ").title(),
                "position": [int(furniture["x"]), int(furniture["y"])],
                "template": _furniture_template(str(furniture["kind"])),
                "context_actions": _furniture_actions(str(furniture["kind"])),
            }
        )
    region = next(region for region in world.regions if region["id"] == region_snapshot.region_id)
    if region.get("fauna"):
        entities.append(
            {
                "id": f"{region_snapshot.region_id}_fauna_0",
                "entity_type": "creature",
                "name": str(region["fauna"][0]).replace("_", " ").title(),
                "position": [region_snapshot.width - 5, region_snapshot.height - 5],
                "template": str(region["fauna"][0]).lower(),
                "disposition": "hostile",
                "context_actions": ["attack", "examine"],
            }
        )
    return entities


def seed_region_entities(
    session: GameSession,
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
) -> None:
    runtime_state = _runtime_region_state(world, region_snapshot.region_id)
    controller = next(
        (
            region.get("controller_faction_id")
            for region in world.regions
            if region["id"] == region_snapshot.region_id
        ),
        "independent",
    )
    for spawn in runtime_state.get("npcs", region_snapshot.layout.npc_spawns):
        role = str(spawn["role"])
        display_name = str(spawn.get("name", role.replace("_", " ").title()))
        entity = Entity(
            id=str(spawn["id"]),
            entity_type=EntityType.NPC,
            name=display_name,
            position=(int(spawn["x"]), int(spawn["y"])),
            glyph=_ROLE_GLYPHS.get(role, role[:1].upper()),
            color=_ROLE_COLORS.get(role, "green"),
            blocking=True,
            hp=12,
            max_hp=12,
            disposition="friendly",
            faction=controller,
            schedule={"npc_id": str(spawn["id"]), "npc_name": display_name, "entries": copy.deepcopy(spawn.get("schedule", []))},
            job=role,
        )
        session.spatial_index.add(entity)
        session.entities[entity.id] = {
            "name": entity.name,
            "type": "npc",
            "position": [entity.position[0], entity.position[1]],
            "faction": controller,
            "role": role,
            "attitude": "friendly",
            "template": str(spawn.get("template", role)),
            "context_actions": list(spawn.get("context_actions", ["talk", "examine"])),
            "entity_ref": entity,
        }
    for furniture in region_snapshot.layout.furniture:
        furniture_entity = Entity(
            id=str(furniture.get("id", f"{furniture['kind']}_{furniture['x']}_{furniture['y']}")),
            entity_type=EntityType.FURNITURE,
            name=str(furniture["kind"]).replace("_", " ").title(),
            position=(int(furniture["x"]), int(furniture["y"])),
            glyph="#",
            color="white",
            blocking=bool(str(furniture["kind"]) not in {"bench", "chair", "bed", "pew", "sack"}),
            disposition="neutral",
            faction=None,
            job=str(furniture["kind"]),
        )
        session.spatial_index.add(furniture_entity)
        session.entities[furniture_entity.id] = {
            "name": furniture_entity.name,
            "type": "furniture",
            "position": [furniture_entity.position[0], furniture_entity.position[1]],
            "role": str(furniture["kind"]),
            "template": _furniture_template(str(furniture["kind"])),
            "context_actions": _furniture_actions(str(furniture["kind"])),
            "entity_ref": furniture_entity,
        }
    region = next(region for region in world.regions if region["id"] == region_snapshot.region_id)
    if region.get("fauna"):
        fauna_name = str(region["fauna"][0]).replace("_", " ").title()
        hostile = Entity(
            id=f"{region_snapshot.region_id}_fauna_0",
            entity_type=EntityType.CREATURE,
            name=fauna_name,
            position=(region_snapshot.width - 5, region_snapshot.height - 5),
            glyph="!",
            color="red",
            blocking=True,
            hp=10,
            max_hp=10,
            disposition="hostile",
            faction=f"{adapter_id}_wilds",
            job="predator",
        )
        session.spatial_index.add(hostile)
        session.entities[hostile.id] = {
            "name": hostile.name,
            "type": "creature",
            "position": [hostile.position[0], hostile.position[1]],
            "faction": hostile.faction,
            "role": hostile.job,
            "attitude": "hostile",
            "entity_ref": hostile,
        }


def build_settlement_state(
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
    player_name: str,
) -> dict[str, Any]:
    settlement = next(item for item in world.settlements if item.region_id == region_snapshot.region_id)
    runtime_state = _runtime_region_state(world, region_snapshot.region_id)
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


def alerts_from_events(events: list[dict[str, Any]]) -> list[str]:
    alerts = []
    for event in events:
        if str(event.get("severity", "warning")).lower() == "info":
            continue
        event_type = str(event.get("event_type", "event"))
        region_id = str(event.get("region_id", "unknown"))
        alerts.append(f"{event_type.replace('_', ' ').title()} in {region_id}")
    return alerts[:4]


def build_character_sheet(session: GameSession, settlement_state: dict[str, Any] | None = None) -> dict[str, Any]:
    player = session.player
    player_data = player.to_dict()
    dominant_class = str(player.dominant_class or "adventurer")
    stats = []
    for ability in _ABILITY_ORDER:
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
        "hp": {"current": int(player.hp), "max": int(player.max_hp)},
        "sp": {"current": int(player.spell_points), "max": int(player.max_spell_points)},
        "ap": {
            "current": int(getattr(session.ap_tracker, "current_ap", 0) or 0),
            "max": int(getattr(session.ap_tracker, "max_ap", 0) or 0),
        },
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
        "stat_source": str(creation_profile.get("stat_source", "default")),
        "rolled_values": list(creation_profile.get("rolled_values", [])),
        "saved_roll": copy.deepcopy(creation_profile.get("saved_roll")),
    }
    return {
        "name": player.name,
        "race": player.race,
        "class_name": dominant_class.capitalize(),
        "level": int(player.level),
        "alignment": player.alignment,
        "stats": stats,
        "skills": skills,
        "resources": resources,
        "armor_class": int(player_data.get("ac", 10)),
        "initiative_bonus": int(player_data.get("initiative_bonus", 0)),
        "gold": int(player.gold),
        "equipment": copy.deepcopy(player.equipment),
        "inventory_count": len(player.inventory),
        "passives": copy.deepcopy(player_data.get("passives", {})),
        "settlement_role": str((settlement_state or {}).get("player_role", "commander")),
        "creation_summary": creation_summary,
    }
