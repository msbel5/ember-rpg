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
    "wall": TileType.WALL,
    "door": TileType.DOOR,
    "floor": TileType.FLOOR,
    "wood_floor": TileType.FLOOR,
    "stone_floor": TileType.FLOOR,
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
    "resident": "R",
    "scout": "C",
    "warden": "W",
    "researcher": "R",
}

_ROLE_COLORS: dict[str, str] = {
    "smith": "yellow",
    "innkeeper": "magenta",
    "bard": "cyan",
    "priest": "white",
    "resident": "green",
    "scout": "light_blue",
    "warden": "orange",
    "researcher": "purple",
}


def build_world(*, adapter_id: str, profile_id: str, seed: int) -> WorldBlueprint:
    adapter = load_adapter_pack(adapter_id)
    world = generate_world(seed, profile_id)
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


def campaign_payload(context: "CampaignContext") -> dict[str, Any]:
    session_data = context.session.to_dict()
    return {
        "world": {
            "seed": context.world.seed,
            "profile_id": context.world.profile_id,
            "adapter_id": context.adapter_id,
            "active_region_id": context.world.simulation_snapshot.active_region_id,
            "faction_count": len(context.world.factions),
            "settlement_count": len(context.world.settlements),
            "history_end_year": context.world.history_end_year,
        },
        "player": session_data["player"],
        "scene": session_data["scene"],
        "location": session_data["location"],
        "combat": session_data.get("combat"),
        "conversation_state": session_data.get("conversation_state", {}),
        "region": region_payload(context),
        "settlement": copy.deepcopy(context.settlement_state),
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
) -> None:
    active_settlement = next(
        (item for item in world.settlements if item.region_id == region_snapshot.region_id),
        world.settlements[0],
    )
    map_data = build_map_data(region_snapshot)
    session.map_data = map_data
    session.position = list(map_data.spawn_point)
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


def seed_region_entities(
    session: GameSession,
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
) -> None:
    controller = next(
        (
            region.get("controller_faction_id")
            for region in world.regions
            if region["id"] == region_snapshot.region_id
        ),
        "independent",
    )
    for spawn in region_snapshot.layout.npc_spawns:
        role = str(spawn["role"])
        display_name = "%s %s" % (role.replace("_", " ").title(), spawn["id"].split("_")[-1].title())
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
            "entity_ref": entity,
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
    for npc in region_snapshot.layout.npc_spawns:
        residents.append(
            {
                "id": npc["id"],
                "name": str(npc["role"]).replace("_", " ").title(),
                "role": npc["role"],
                "assignment": npc["role"],
                "drafted": False,
                "building_id": npc["building_id"],
                "mood": "steady",
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
        "alerts": [],
        "needs": {
            "food": max(1, settlement.population // 30),
            "security": max(1, len(residents) // 3),
            "materials": max(1, len(region_snapshot.layout.furniture) // 2),
        },
        "faction_pressure": historical_pressure,
        "current_hour": world.simulation_snapshot.current_hour if world.simulation_snapshot else 0,
    }


def alerts_from_events(events: list[dict[str, Any]]) -> list[str]:
    alerts = []
    for event in events:
        event_type = str(event.get("event_type", "event"))
        region_id = str(event.get("region_id", "unknown"))
        alerts.append(f"{event_type.replace('_', ' ').title()} in {region_id}")
    return alerts[:4]
