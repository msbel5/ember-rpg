"""Campaign context projection helpers for campaign runtime."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.campaign.context import CampaignContext
from engine.kernel.game_state import FORMATIONS, normalize_party_state
from engine.kernel.scene_types import SceneType
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


def _preserved_party_entities(context: CampaignContext) -> dict[str, dict[str, Any]]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    raw_party_ids = list(getattr(game_state, "party", [])) if game_state is not None else list(context.campaign_state.get("party", []))
    party_ids = {str(actor_id) for actor_id in raw_party_ids if str(actor_id) and str(actor_id) != "player"}
    preserved: dict[str, dict[str, Any]] = {}
    for actor_id in party_ids:
        record = context.entities.get(actor_id)
        if isinstance(record, dict):
            preserved[actor_id] = copy.deepcopy(record)
    return preserved


def _restore_party_entities(context: CampaignContext, preserved: dict[str, dict[str, Any]]) -> None:
    for actor_id, record in preserved.items():
        live_entity = record.get("entity_ref")
        if live_entity is None:
            entity_type_name = str(record.get("type", "npc")).upper()
            try:
                entity_type = EntityType[entity_type_name]
            except KeyError:
                entity_type = EntityType.NPC
            live_entity = Entity(
                id=actor_id,
                entity_type=entity_type,
                name=record.get("name", actor_id),
                position=tuple(record.get("position", list(context.position))),
                glyph=str(record.get("glyph", "A")),
                color=str(record.get("color", "light_blue")),
                blocking=bool(record.get("blocking", entity_type == EntityType.NPC)),
                hp=int(record.get("hp", 8)),
                max_hp=int(record.get("max_hp", record.get("hp", 8) or 8)),
                faction=record.get("faction"),
                job=record.get("role"),
                disposition=str(record.get("disposition", "ally")),
                attitude=str(record.get("attitude", "ally")),
                needs=record.get("needs"),
                body=record.get("body"),
                schedule=record.get("schedule"),
            )
        if context.spatial_index.get_position(actor_id) is None:
            context.spatial_index.add(live_entity)
        restored_record = dict(record)
        restored_record["attitude"] = "ally"
        restored_record["disposition"] = "ally"
        restored_record["entity_ref"] = live_entity
        live_entity.attitude = "ally"
        live_entity.disposition = "ally"
        context.entities[actor_id] = restored_record


def _clamp_party_position(context: CampaignContext, x: int, y: int) -> tuple[int, int]:
    map_data = getattr(context, "map_data", None)
    if map_data is None:
        return (x, y)
    width = max(1, int(getattr(map_data, "width", 1)))
    height = max(1, int(getattr(map_data, "height", 1)))
    return (max(0, min(width - 1, int(x))), max(0, min(height - 1, int(y))))


def _ensure_projected_party_entity(context: CampaignContext, actor_id: str) -> dict[str, Any] | None:
    record = context.entities.get(actor_id)
    if isinstance(record, dict):
        return record
    runtime = context.kernel_runtime or {}
    actor = (runtime.get("actors") or {}).get(actor_id)
    if actor is None:
        return None
    entity = Entity(
        id=actor_id,
        entity_type=EntityType.NPC,
        name=actor.identity.display_name,
        position=tuple(_clamp_party_position(context, int(context.position[0]), int(context.position[1]))),
        glyph="A",
        color="light_blue",
        blocking=True,
        hp=int(actor.stats.get("hp", 0)),
        max_hp=int(actor.stats.get("max_hp", 1)),
        disposition="ally",
        attitude="ally",
        faction=getattr(actor.identity, "faction_id", None),
        job=str(actor.raw_payload.get("role", "companion")),
    )
    if context.spatial_index.get_position(actor_id) is None:
        context.spatial_index.add(entity)
    record = {
        "name": actor.identity.display_name,
        "type": "npc",
        "position": [entity.position[0], entity.position[1]],
        "faction": getattr(actor.identity, "faction_id", None),
        "role": str(actor.raw_payload.get("role", "companion")),
        "attitude": "ally",
        "disposition": "ally",
        "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", "companion"))),
        "context_actions": ["examine"],
        "entity_ref": entity,
    }
    context.entities[actor_id] = record
    return record


def _schedule_entries_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    schedule = record.get("schedule")
    if hasattr(schedule, "to_dict"):
        schedule = schedule.to_dict()
    if isinstance(schedule, dict):
        entries = schedule.get("entries", [])
        if isinstance(entries, list):
            return [dict(item) for item in entries if isinstance(item, dict)]
    entity_ref = record.get("entity_ref")
    entity_schedule = getattr(entity_ref, "schedule", None)
    if hasattr(entity_schedule, "to_dict"):
        entity_schedule = entity_schedule.to_dict()
    if isinstance(entity_schedule, dict):
        entries = entity_schedule.get("entries", [])
        if isinstance(entries, list):
            return [dict(item) for item in entries if isinstance(item, dict)]
    return []


def _current_schedule_entry(entries: list[dict[str, Any]], hour: int) -> dict[str, Any] | None:
    valid_entries = sorted(
        [dict(item) for item in entries if isinstance(item, dict) and "hour" in item],
        key=lambda item: int(item.get("hour", 0)),
    )
    if not valid_entries:
        return None
    current_hour = int(hour) % 24
    eligible = [item for item in valid_entries if int(item.get("hour", 0)) <= current_hour]
    return dict(eligible[-1] if eligible else valid_entries[-1])


def _valid_schedule_position(context: CampaignContext, position: Any) -> tuple[int, int] | None:
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        return None
    x = int(position[0])
    y = int(position[1])
    map_data = getattr(context, "map_data", None)
    if map_data is None:
        return (x, y)
    width = int(getattr(map_data, "width", 0))
    height = int(getattr(map_data, "height", 0))
    if x < 0 or y < 0 or x >= width or y >= height:
        return None
    tile = map_data.tiles[y][x]
    if tile in {TileType.WALL, TileType.WATER, TileType.TREE}:
        return None
    return (x, y)


def _write_schedule_state(record: dict[str, Any], entry: dict[str, Any], *, activity: str) -> None:
    record["activity"] = activity
    record["assignment"] = activity
    record["schedule_hour"] = int(entry.get("hour", 0))
    entity_ref = record.get("entity_ref")
    if entity_ref is not None:
        entity_ref.job = activity
        schedule = getattr(entity_ref, "schedule", None)
        if hasattr(schedule, "to_dict"):
            record["schedule"] = schedule.to_dict()
        elif isinstance(schedule, dict):
            record["schedule"] = copy.deepcopy(schedule)


def _live_region_npcs(context: CampaignContext) -> list[dict[str, Any]]:
    snapshot = getattr(getattr(context, "world", None), "simulation_snapshot", None)
    region_id = str(getattr(getattr(context, "region_snapshot", None), "region_id", ""))
    if snapshot is None or not region_id:
        return []
    state = snapshot.region_states.get(region_id)
    if not isinstance(state, dict):
        return []
    npcs = state.get("npcs", [])
    return npcs if isinstance(npcs, list) else []


def persist_projected_npc_state(context: CampaignContext) -> None:
    npc_state = {
        str(entry.get("id", "")): entry
        for entry in _live_region_npcs(context)
        if isinstance(entry, dict) and str(entry.get("id", ""))
    }
    for entity_id, record in list(context.entities.items()):
        if not isinstance(record, dict) or str(record.get("type", "")) != "npc":
            continue
        live_entry = npc_state.get(entity_id)
        if live_entry is None:
            continue
        entries = _schedule_entries_from_record(record)
        if entries:
            live_entry["schedule"] = copy.deepcopy(entries)
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            live_entry["x"] = int(position[0])
            live_entry["y"] = int(position[1])
        activity = str(record.get("assignment") or record.get("activity") or live_entry.get("activity", "")).strip()
        if activity:
            live_entry["activity"] = activity


def sync_schedule_projection(context: CampaignContext, *, current_hour: int | None = None) -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if getattr(context, "spatial_index", None) is None:
        return
    normalize_party_state(game_state) if game_state is not None else None
    active_party_ids = set(getattr(game_state, "party", [])) if game_state is not None else {"player"}
    hour = int(current_hour if current_hour is not None else getattr(getattr(context, "game_time", None), "hour", 0)) % 24
    actor_map = runtime.get("actors") or {}
    npc_state = {
        str(entry.get("id", "")): entry
        for entry in _live_region_npcs(context)
        if isinstance(entry, dict) and str(entry.get("id", ""))
    }

    for entity_id, record in list(context.entities.items()):
        if not isinstance(record, dict) or entity_id == "player" or entity_id in active_party_ids:
            continue
        if str(record.get("type", "")) != "npc":
            continue
        entries = _schedule_entries_from_record(record)
        current_entry = _current_schedule_entry(entries, hour)
        if current_entry is None:
            continue
        activity = str(current_entry.get("activity") or current_entry.get("location_id") or record.get("assignment") or record.get("role", "resident"))
        _write_schedule_state(record, current_entry, activity=activity)
        live_entry = npc_state.get(entity_id)
        if live_entry is not None:
            live_entry["schedule"] = copy.deepcopy(entries)
            live_entry["activity"] = activity

        resident_list = context.settlement_state.get("residents", []) if isinstance(getattr(context, "settlement_state", None), dict) else []
        for resident in resident_list:
            if str(resident.get("id", "")) == entity_id:
                resident["assignment"] = activity
                break

        actor = actor_map.get(entity_id)
        if actor is not None:
            actor.raw_payload["assignment"] = activity
            actor.raw_payload["current_activity"] = activity

        next_position = _valid_schedule_position(context, current_entry.get("position"))
        if next_position is None:
            continue
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            if context.spatial_index.get_position(entity_id) is None:
                entity_ref.position = next_position
                context.spatial_index.add(entity_ref)
            else:
                context.spatial_index.move(entity_ref, next_position[0], next_position[1])
        record["position"] = [next_position[0], next_position[1]]
        if live_entry is not None:
            live_entry["x"] = next_position[0]
            live_entry["y"] = next_position[1]
        if actor is not None:
            actor.position.x = next_position[0]
            actor.position.y = next_position[1]


def sync_party_projection(context: CampaignContext) -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None or getattr(context, "spatial_index", None) is None:
        return
    normalize_party_state(game_state)
    formation_offsets = list(FORMATIONS.get(str(getattr(game_state, "formation", "wedge")), FORMATIONS["wedge"]))
    active_ids = [actor_id for actor_id in list(getattr(game_state, "party", [])) if actor_id and actor_id != "player"]
    reserve_ids = [actor_id for actor_id in list(getattr(game_state, "inactive_npcs", [])) if actor_id]
    player_x, player_y = int(context.position[0]), int(context.position[1])
    actors = runtime.get("actors") or {}

    for index, actor_id in enumerate(active_ids, start=1):
        record = _ensure_projected_party_entity(context, actor_id)
        if record is None:
            continue
        dx, dy = formation_offsets[index] if index < len(formation_offsets) else formation_offsets[-1]
        slot_position = _clamp_party_position(context, player_x + int(dx), player_y + int(dy))
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            if context.spatial_index.get_position(actor_id) is not None:
                context.spatial_index.move(entity_ref, slot_position[0], slot_position[1])
            else:
                entity_ref.position = slot_position
                context.spatial_index.add(entity_ref)
            entity_ref.attitude = "ally"
            entity_ref.disposition = "ally"
            entity_ref.faction = getattr(getattr(actors.get(actor_id), "identity", None), "faction_id", record.get("faction"))
        record["position"] = [slot_position[0], slot_position[1]]
        record["attitude"] = "ally"
        record["disposition"] = "ally"

    for actor_id in reserve_ids:
        record = context.entities.get(actor_id)
        if not isinstance(record, dict):
            continue
        actor = actors.get(actor_id)
        reserve_position = tuple(record.get("position", list(context.position)))
        if actor is not None:
            reserve_position = _clamp_party_position(context, int(actor.position.x), int(actor.position.y))
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            if context.spatial_index.get_position(actor_id) is not None:
                context.spatial_index.move(entity_ref, reserve_position[0], reserve_position[1])
            else:
                entity_ref.position = reserve_position
                context.spatial_index.add(entity_ref)
            entity_ref.attitude = "friendly"
            entity_ref.disposition = "friendly"
        record["position"] = [int(reserve_position[0]), int(reserve_position[1])]
        record["attitude"] = "friendly"
        record["disposition"] = "friendly"


def apply_region_to_context(
    *,
    context: CampaignContext,
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    settlement_state: dict[str, Any],
    campaign_id: str,
    adapter_id: str,
    profile_id: str,
    seed: int,
    preserve_position: bool = False,
) -> None:
    preserved_party_entities = _preserved_party_entities(context)
    active_settlement = next(
        (item for item in world.settlements if item.region_id == region_snapshot.region_id),
        world.settlements[0],
    )
    map_data = build_map_data(region_snapshot)
    context.map_data = map_data
    next_position = list(map_data.spawn_point)
    if preserve_position and context.position:
        px = int(context.position[0])
        py = int(context.position[1])
        if 0 <= py < region_snapshot.height and 0 <= px < region_snapshot.width and region_snapshot.typed_tiles[py][px]["passable"]:
            next_position = [px, py]
    context.position = next_position
    context.dm_context.scene_type = SceneType.EXPLORATION
    context.dm_context.location = active_settlement.center_name
    context.entities = {}
    context.spatial_index = SpatialIndex()
    context.player_entity = Entity(
        id="player",
        entity_type=EntityType.NPC,
        name=context.player.name,
        position=tuple(context.position),
        glyph="@",
        color="white",
        blocking=True,
        hp=context.player.hp,
        max_hp=context.player.max_hp,
        disposition="friendly",
    )
    context.spatial_index.add(context.player_entity)
    context.viewport = None
    seed_region_entities(context, world, region_snapshot, adapter_id)
    if preserved_party_entities:
        _restore_party_entities(context, preserved_party_entities)
    sync_party_projection(context)
    sync_schedule_projection(
        context,
        current_hour=int(getattr(getattr(world, "simulation_snapshot", None), "current_hour", 0)),
    )
    context.campaign_state.setdefault("active_quests", [])
    context.campaign_state.setdefault("completed_quests", [])
    context.campaign_state.setdefault("failed_quests", [])
    context.campaign_state.setdefault("completed_quest_ids", [])
    context.campaign_state.setdefault("failed_quest_ids", [])
    context.campaign_state.setdefault("emergent_counter", 0)
    context.campaign_state["active_region_id"] = region_snapshot.region_id
    context.campaign_state["campaign_id"] = campaign_id
    context.campaign_state["adapter_id"] = adapter_id
    context.campaign_state["profile_id"] = profile_id
    context.campaign_state["world_seed"] = seed
    context.campaign_state["settlement_state"] = copy.deepcopy(settlement_state)
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    context.campaign_state["active_quests"] = copy.deepcopy(runtime_state.get("active_quests", []))
    context.campaign_state["quest_offers"] = copy.deepcopy(runtime_state.get("quest_offers", []))
    context.ensure_consistency()


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
    context: CampaignContext,
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
        context.spatial_index.add(entity)
        context.entities[entity.id] = {
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
        context.spatial_index.add(furniture_entity)
        context.entities[furniture_entity.id] = {
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
        context.spatial_index.add(hostile)
        context.entities[hostile.id] = {
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
    "apply_region_to_context",
    "build_map_data",
    "build_world_entities",
    "furniture_actions",
    "furniture_template",
    "persist_projected_npc_state",
    "seed_region_entities",
    "sync_schedule_projection",
    "sync_party_projection",
]
