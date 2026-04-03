"""Session projection helpers for campaign runtime."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.game_session import GameSession
from engine.kernel.narrator import SceneType
from engine.map import MapData, Room, TileType
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.worldgen.models import RegionSnapshot, WorldBlueprint

from .world import choose_spawn_point, runtime_region_state

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
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
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
            [_TERRAIN_TILE_MAP.get(str(tile.get("terrain", "floor")), TileType.FLOOR) for tile in row]
        )
    return MapData(
        width=region_snapshot.width,
        height=region_snapshot.height,
        tiles=terrain_tiles,
        rooms=rooms,
        spawn_point=choose_spawn_point(region_snapshot),
        exit_points=[],
        metadata={
            "map_type": "campaign_region",
            "region_id": region_snapshot.region_id,
            "biome_id": region_snapshot.biome_id,
        },
    )


def build_world_entities(world: WorldBlueprint, region_snapshot: RegionSnapshot, adapter_id: str) -> list[dict[str, Any]]:
    del adapter_id
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
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
                "template": furniture_template(str(furniture["kind"])),
                "context_actions": furniture_actions(str(furniture["kind"])),
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
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
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
            "template": furniture_template(str(furniture["kind"])),
            "context_actions": furniture_actions(str(furniture["kind"])),
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


def furniture_template(kind: str) -> str:
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


def furniture_actions(kind: str) -> list[str]:
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


__all__ = [
    "apply_region_to_session",
    "build_map_data",
    "build_world_entities",
    "furniture_actions",
    "furniture_template",
    "seed_region_entities",
]
