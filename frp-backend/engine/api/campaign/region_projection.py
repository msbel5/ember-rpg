"""Campaign context projection helpers for campaign runtime."""
from __future__ import annotations

import copy
import hashlib
import re
from collections import defaultdict
from typing import Any

from engine.api.campaign.context import CampaignContext
from engine.kernel.dialog import compute_npc_reaction
from engine.kernel.game_state import FORMATIONS, normalize_party_state, party_tactic_mode
from engine.kernel.scene_types import SceneType
from engine.map import MapData, Room, TileType
from engine.world.interactions_catalog import load_interaction_rules
from engine.world.interactions_types import InteractionType
from engine.world.behavior_tree_leaves import build_default_ambient_tree
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.worldgen.npc_authored import is_ambient_life_enabled
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
_SERVICE_NPC_ROLES = {
    "merchant",
    "innkeeper",
    "blacksmith",
    "smith",
    "healer",
    "priest",
    "alchemist",
    "scribe",
    "quartermaster",
    "stablehand",
    "bard",
}
_SERVICE_FURNITURE_KINDS = {
    "altar",
    "anvil",
    "bar_counter",
    "bookshelf",
    "display_table",
    "forge",
    "loom",
    "map_table",
    "press",
    "table",
    "well",
    "workbench",
}
_LANDMARK_FURNITURE_KINDS = {
    "campfire",
    "door",
    "fountain",
    "shrine",
    "sign",
    "well",
}
_PARTY_CAPABLE_ACTOR_TYPES = {"npc", "creature"}
_NON_PARTY_ROLE_HINTS = {"cabinet", "cauldron", "table", "oven", "bench", "chair", "bed", "pew", "sack"}
_INTERACTION_HINT_ALIASES: dict[str, str] = {
    "attack": "attack",
    "bury": "bury",
    "chop": "chop",
    "climb": "climb",
    "close": "close",
    "craft": "craft",
    "disarm": "disarm_trap",
    "disarm_trap": "disarm_trap",
    "drink": "drink",
    "examine": "examine",
    "fill": "fill",
    "fish": "fish",
    "flee": "flee",
    "follow": "follow",
    "force": "force_open",
    "force_open": "force_open",
    "hire": "hire",
    "intimidate": "intimidate",
    "kick": "kick",
    "lock_pick": "lock_pick",
    "loot": "loot",
    "mine": "mine",
    "open": "open",
    "persuade": "persuade",
    "pick_up": "pickup",
    "pickup": "pickup",
    "pray": "pray",
    "pull": "pull",
    "push": "push",
    "read": "read",
    "rest": "rest",
    "search": "search",
    "set_trap": "set_trap",
    "sneak": "sneak",
    "steal": "steal",
    "swim": "swim",
    "talk": "talk",
    "trade": "trade",
    "use": "use",
}
_INTERACTION_LABEL_OVERRIDES: dict[str, str] = {
    "disarm_trap": "Disarm Trap",
    "force_open": "Force Open",
    "lock_pick": "Lockpick",
    "pickup": "Pickup",
    "set_trap": "Set Trap",
}
_FURNITURE_TARGET_KIND_ALIASES: dict[str, str] = {
    "anvil": "workstation",
    "altar": "altar",
    "barrel": "barrel",
    "bed": "bed",
    "bookshelf": "bookshelf",
    "campfire": "campfire",
    "chest": "chest",
    "crate": "chest",
    "door": "door",
    "fixture": "fixture",
    "lever": "lever",
    "ore_vein": "ore_vein",
    "shrine": "shrine",
    "sign": "sign",
    "trap": "trap",
    "well": "well",
    "workstation": "workstation",
    "bar_counter": "fixture",
    "bench": "fixture",
    "chair": "fixture",
    "desk": "fixture",
    "display_table": "fixture",
    "map_table": "fixture",
    "stool": "fixture",
    "table": "fixture",
    "trough": "fixture",
}
_RULES_BY_TARGET_TYPE: dict[str, list[tuple[InteractionType, dict[str, Any]]]] = defaultdict(list)
for (_target_type, _interaction_type), _rule in load_interaction_rules().items():
    _RULES_BY_TARGET_TYPE[_target_type].append((_interaction_type, dict(_rule)))


def _entity_kind_from_payload(entity_type: str, disposition: str = "") -> str:
    normalized_type = str(entity_type).strip().lower()
    normalized_disposition = str(disposition).strip().lower()
    if normalized_type == "item":
        return "item"
    if normalized_type == "furniture":
        return "furniture"
    if normalized_type == "creature":
        return "hostile" if normalized_disposition == "hostile" else "creature"
    if normalized_type == "npc":
        return "hostile" if normalized_disposition == "hostile" else "npc"
    if normalized_type in {"object", "fixture"}:
        return "furniture"
    return normalized_type or "object"


def _is_party_capable_actor(actor: Any) -> bool:
    if actor is None:
        return False
    actor_id = str(getattr(getattr(actor, "identity", None), "actor_id", "")).strip()
    if not actor_id or actor_id == "player":
        return False
    actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip()
    if actor_type not in _PARTY_CAPABLE_ACTOR_TYPES:
        return False
    role_hint = str(getattr(actor, "raw_payload", {}).get("role", getattr(actor, "raw_payload", {}).get("template", ""))).lower().strip()
    if role_hint in _NON_PARTY_ROLE_HINTS:
        return False
    if any(
        bool(getattr(actor, "raw_payload", {}).get(key))
        for key in ("companion_roster", "party_member", "active_party_member", "reserve_party_member")
    ):
        return True
    return str(getattr(actor, "raw_payload", {}).get("source", "")).lower().strip() != "campaign_entity"


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
    if not _is_party_capable_actor(actor):
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


def _waypoint_name_for_building(building: dict[str, Any]) -> str:
    building_id = str(building.get("id", "building")).strip() or "building"
    kind = str(building.get("kind", "building")).strip().lower()
    if any(token in kind for token in ("inn", "tavern")):
        return "tavern_counter"
    if any(token in kind for token in ("market", "shop", "merchant", "trader", "stall")):
        return "market_stall"
    if any(token in kind for token in ("temple", "shrine", "chapel")):
        return "temple_door"
    if any(token in kind for token in ("house", "home", "residence")):
        return f"home_{building_id}"
    return f"building_{building_id}"


def _anchor_from_building(building: dict[str, Any]) -> tuple[int, int]:
    x = int(building.get("x", 0))
    y = int(building.get("y", 0))
    width = max(1, int(building.get("width", 1)))
    height = max(1, int(building.get("height", 1)))
    doors = list(building.get("doors", [])) if isinstance(building.get("doors", []), list) else []
    if doors:
        door = doors[0]
        if isinstance(door, dict):
            return (int(door.get("x", x)), int(door.get("y", y)))
    return (x + width // 2, y + height // 2)


def _derive_region_waypoints(context: CampaignContext, region_snapshot: RegionSnapshot) -> dict[str, tuple[int, int]]:
    waypoints: dict[str, tuple[int, int]] = {
        "settlement_square": (int(context.position[0]), int(context.position[1])) if len(context.position) >= 2 else choose_spawn_point(region_snapshot)
    }
    for building in list(region_snapshot.layout.buildings):
        if not isinstance(building, dict):
            continue
        name = _waypoint_name_for_building(building)
        candidate = _valid_schedule_position(context, _anchor_from_building(building))
        if candidate is not None and name not in waypoints:
            waypoints[name] = candidate
    for furniture in list(region_snapshot.layout.furniture):
        if not isinstance(furniture, dict):
            continue
        kind = str(furniture.get("kind", "")).strip().lower()
        if kind == "bar_counter":
            name = "tavern_counter"
        elif kind in {"display_table", "rack", "desk"}:
            name = "market_stall"
        elif kind in {"altar", "pew", "ward_totem"}:
            name = "temple_door"
        elif kind == "bed":
            name = "bed_home"
        else:
            continue
        candidate = _valid_schedule_position(context, (int(furniture.get("x", 0)), int(furniture.get("y", 0))))
        if candidate is not None and name not in waypoints:
            waypoints[name] = candidate
    if len(waypoints) < 3:
        for spawn in list(region_snapshot.layout.npc_spawns):
            candidate = _valid_schedule_position(context, (int(spawn.get("x", 0)), int(spawn.get("y", 0))))
            if candidate is None:
                continue
            name = f"anchor_{len(waypoints)}"
            waypoints.setdefault(name, candidate)
            if len(waypoints) >= 3:
                break
    return waypoints


def _nearest_waypoint_name(position: tuple[int, int], waypoints: dict[str, tuple[int, int]]) -> str | None:
    if not waypoints:
        return None
    return min(
        waypoints.keys(),
        key=lambda name: max(
            abs(int(waypoints[name][0]) - int(position[0])),
            abs(int(waypoints[name][1]) - int(position[1])),
        ),
    )


def _ambient_profile_for_spawn(
    spawn: dict[str, Any],
    *,
    settlement_id: str,
    waypoints: dict[str, tuple[int, int]],
) -> dict[str, Any]:
    ambient_waypoints = {str(name): (int(pos[0]), int(pos[1])) for name, pos in dict(waypoints).items()}
    schedule_map: dict[int, str] = {}
    schedule_entries = [dict(item) for item in list(spawn.get("schedule", [])) if isinstance(item, dict)]
    home_tile = (int(spawn.get("x", 0)), int(spawn.get("y", 0)))
    wander_center = home_tile
    for entry in schedule_entries:
        position = (int(entry.get("position", [home_tile[0], home_tile[1]])[0]), int(entry.get("position", [home_tile[0], home_tile[1]])[1]))
        waypoint_name = _nearest_waypoint_name(position, ambient_waypoints)
        if waypoint_name is None or ambient_waypoints.get(waypoint_name) != position:
            waypoint_name = f"schedule_{int(entry.get('hour', 0))}"
            ambient_waypoints[waypoint_name] = position
        schedule_map[int(entry.get("hour", 0)) % 24] = waypoint_name
        if str(entry.get("building_kind", "")).strip().lower() == "home" or str(entry.get("activity", "")).strip().lower() in {"sleep", "rest", "wake"}:
            home_tile = position
        if str(entry.get("building_kind", "")).strip().lower() in {"work", "leisure"}:
            wander_center = position
    ambient_enabled = is_ambient_life_enabled(spawn, settlement_id=settlement_id)
    ambient_seed = int(hashlib.sha1(f"{settlement_id}:{spawn.get('id', '')}".encode("utf-8")).hexdigest()[:8], 16)
    return {
        "ambient_life": ambient_enabled,
        "home_tile": home_tile,
        "wander_center": wander_center,
        "wander_radius": 4 + ambient_seed % 5,
        "schedule": schedule_map,
        "default_waypoint": _nearest_waypoint_name(wander_center, ambient_waypoints) or "settlement_square",
        "waypoints": ambient_waypoints,
        "night_hours": range(0, 7),
        "state": str(spawn.get("state", "stand") or "stand"),
        "facing": str(spawn.get("facing", "south") or "south"),
    }


def _write_schedule_state(record: dict[str, Any], entry: dict[str, Any], *, activity: str) -> None:
    record["activity"] = activity
    record["assignment"] = activity
    record["building_kind"] = str(entry.get("building_kind", record.get("building_kind", "")))
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


def _live_region_npc_entry(context: CampaignContext, actor_id: str) -> dict[str, Any] | None:
    for entry in _live_region_npcs(context):
        if isinstance(entry, dict) and str(entry.get("id", "")) == actor_id:
            return entry
    return None


def _ambient_npc_position(context: CampaignContext, actor_id: str, fallback: tuple[int, int]) -> tuple[int, int]:
    entry = _live_region_npc_entry(context, actor_id)
    if entry is None:
        return fallback
    try:
        return _clamp_party_position(context, int(entry.get("x", fallback[0])), int(entry.get("y", fallback[1])))
    except Exception:
        return fallback


def _set_live_party_projection_state(context: CampaignContext, actor_id: str, *, active: bool) -> None:
    entry = _live_region_npc_entry(context, actor_id)
    if entry is None:
        return
    if active:
        entry["party_member_active"] = True
        entry["disposition"] = "ally"
        entry["context_actions"] = ["examine"]
        return
    entry.pop("party_member_active", None)
    entry["disposition"] = str(entry.get("disposition", "friendly") or "friendly")
    entry["context_actions"] = list(entry.get("context_actions", ["talk", "examine"])) or ["talk", "examine"]


def persist_projected_npc_state(context: CampaignContext) -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    normalize_party_state(game_state) if game_state is not None else None
    active_party_ids = {str(actor_id) for actor_id in list(getattr(game_state, "party", [])) if str(actor_id) and str(actor_id) != "player"}
    npc_state = {
        str(entry.get("id", "")): entry
        for entry in _live_region_npcs(context)
        if isinstance(entry, dict) and str(entry.get("id", ""))
    }
    for entity_id, record in list(context.entities.items()):
        if not isinstance(record, dict) or str(record.get("type", "")) != "npc":
            continue
        if entity_id in active_party_ids:
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


def _active_combat_payload(context: CampaignContext) -> dict[str, Any] | None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
    combat = raw_payload.get("combat")
    if not isinstance(combat, dict) or not combat.get("combatants"):
        return None
    if str(combat.get("phase", "active")).lower().strip() == "resolved":
        return None
    return combat


def _active_combat_actor_ids(context: CampaignContext) -> set[str]:
    combat = _active_combat_payload(context)
    if combat is None:
        return set()
    return {
        str(entry.get("actor_id", "")).strip()
        for entry in list(combat.get("combatants", []))
        if isinstance(entry, dict) and str(entry.get("actor_id", "")).strip()
    }


def _combat_position_for_actor(context: CampaignContext, actor: Any, actor_id: str) -> tuple[int, int]:
    if actor_id == "player":
        player_entity = getattr(context, "player_entity", None)
        player_position = getattr(player_entity, "position", None)
        if isinstance(player_position, (list, tuple)) and len(player_position) >= 2:
            return _clamp_party_position(context, int(player_position[0]), int(player_position[1]))
        context_position = getattr(context, "position", None)
        if isinstance(context_position, (list, tuple)) and len(context_position) >= 2:
            return _clamp_party_position(context, int(context_position[0]), int(context_position[1]))
    actor_position = getattr(actor, "position", None)
    if actor_position is not None:
        return _clamp_party_position(context, int(actor_position.x), int(actor_position.y))
    record = context.entities.get(actor_id)
    if isinstance(record, dict):
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            return _clamp_party_position(context, int(position[0]), int(position[1]))
    return _clamp_party_position(context, int(context.position[0]), int(context.position[1]))


def _ensure_projected_combat_entity(
    context: CampaignContext,
    actor_id: str,
    actor: Any,
    *,
    is_player_side: bool,
) -> dict[str, Any]:
    existing = context.entities.get(actor_id)
    if isinstance(existing, dict):
        return existing
    if is_player_side and _is_party_capable_actor(actor):
        party_record = _ensure_projected_party_entity(context, actor_id)
        if party_record is not None:
            return party_record
    position = _combat_position_for_actor(context, actor, actor_id)
    disposition = "ally" if is_player_side else "hostile"
    role = str(getattr(actor, "raw_payload", {}).get("role", "combatant"))
    entity = Entity(
        id=actor_id,
        entity_type=EntityType.NPC,
        name=actor.identity.display_name,
        position=position,
        glyph="A" if is_player_side else "!",
        color="light_blue" if is_player_side else "red",
        blocking=True,
        hp=int(actor.stats.get("hp", 1)),
        max_hp=int(actor.stats.get("max_hp", actor.stats.get("hp", 1))),
        disposition=disposition,
        attitude=disposition,
        faction=getattr(actor.identity, "faction_id", None),
        job=role,
    )
    if context.spatial_index.get_position(actor_id) is None:
        context.spatial_index.add(entity)
    record = {
        "name": actor.identity.display_name,
        "type": "npc",
        "position": [int(position[0]), int(position[1])],
        "faction": getattr(actor.identity, "faction_id", None),
        "role": role,
        "attitude": disposition,
        "disposition": disposition,
        "template": str(getattr(actor, "raw_payload", {}).get("template", role)),
        "context_actions": ["examine"] if is_player_side else ["attack", "examine"],
        "blocking": True,
        "entity_ref": entity,
    }
    context.entities[actor_id] = record
    return record


def sync_combat_projection(context: CampaignContext) -> None:
    combat = _active_combat_payload(context)
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors") or {}
    if combat is None or getattr(context, "spatial_index", None) is None:
        return
    if context.player_entity is not None and context.spatial_index.get_position("player") is None:
        context.spatial_index.add(context.player_entity)
    for entry in list(combat.get("combatants", [])):
        if not isinstance(entry, dict):
            continue
        actor_id = str(entry.get("actor_id", "")).strip()
        if not actor_id:
            continue
        actor = actors.get(actor_id)
        if actor is None:
            continue
        position = _combat_position_for_actor(context, actor, actor_id)
        if actor_id == "player":
            context.position = [int(position[0]), int(position[1])]
            if context.player_entity is not None:
                context.player_entity.position = (int(position[0]), int(position[1]))
                if context.spatial_index.get_position("player") is None:
                    context.spatial_index.add(context.player_entity)
                else:
                    context.spatial_index.move(context.player_entity, int(position[0]), int(position[1]))
            continue
        is_player_side = bool(entry.get("is_player", False))
        record = _ensure_projected_combat_entity(context, actor_id, actor, is_player_side=is_player_side)
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            entity_ref.position = (int(position[0]), int(position[1]))
            entity_ref.blocking = True
            entity_ref.attitude = "ally" if is_player_side else "hostile"
            entity_ref.disposition = entity_ref.attitude
            if context.spatial_index.get_position(actor_id) is None:
                context.spatial_index.add(entity_ref)
            else:
                context.spatial_index.move(entity_ref, int(position[0]), int(position[1]))
        record["position"] = [int(position[0]), int(position[1])]
        record["blocking"] = True
        record["attitude"] = "ally" if is_player_side else "hostile"
        record["disposition"] = record["attitude"]
        record["context_actions"] = ["examine"] if is_player_side else ["attack", "examine"]
        live_entry = _live_region_npc_entry(context, actor_id)
        if live_entry is not None:
            live_entry["x"] = int(position[0])
            live_entry["y"] = int(position[1])
        if is_player_side:
            _set_live_party_projection_state(context, actor_id, active=True)


def sync_schedule_projection(context: CampaignContext, *, current_hour: int | None = None) -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if getattr(context, "spatial_index", None) is None:
        return
    normalize_party_state(game_state) if game_state is not None else None
    active_party_ids = set(getattr(game_state, "party", [])) if game_state is not None else {"player"}
    combat_actor_ids = _active_combat_actor_ids(context)
    hour = int(current_hour if current_hour is not None else getattr(getattr(context, "game_time", None), "hour", 0)) % 24
    actor_map = runtime.get("actors") or {}
    npc_state = {
        str(entry.get("id", "")): entry
        for entry in _live_region_npcs(context)
        if isinstance(entry, dict) and str(entry.get("id", ""))
    }

    for entity_id, record in list(context.entities.items()):
        if not isinstance(record, dict) or entity_id == "player" or entity_id in active_party_ids or entity_id in combat_actor_ids:
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
    player_x, player_y = int(context.position[0]), int(context.position[1])
    actors = runtime.get("actors") or {}
    combat_actor_ids = _active_combat_actor_ids(context)
    active_ids = [
        actor_id
        for actor_id in list(getattr(game_state, "party", []))
        if actor_id and actor_id != "player" and _is_party_capable_actor(actors.get(actor_id))
    ]
    reserve_ids = [
        actor_id
        for actor_id in list(getattr(game_state, "inactive_npcs", []))
        if actor_id and _is_party_capable_actor(actors.get(actor_id))
    ]
    if list(getattr(game_state, "party", [])) != (["player"] if "player" in getattr(game_state, "party", []) else []) + active_ids:
        game_state.party = (["player"] if "player" in getattr(game_state, "party", []) else []) + active_ids
    if list(getattr(game_state, "inactive_npcs", [])) != reserve_ids:
        game_state.inactive_npcs = reserve_ids

    for index, actor_id in enumerate(active_ids, start=1):
        record = _ensure_projected_party_entity(context, actor_id)
        if record is None:
            continue
        tactic_mode = party_tactic_mode(game_state, actor_id)
        if actor_id in combat_actor_ids and actors.get(actor_id) is not None:
            slot_position = _combat_position_for_actor(context, actors.get(actor_id), actor_id)
        else:
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
        record["context_actions"] = ["examine"]
        record["tactic_mode"] = tactic_mode
        actor = actors.get(actor_id)
        if actor is not None:
            actor.position.x = slot_position[0]
            actor.position.y = slot_position[1]
            actor.raw_payload["party_member"] = True
            actor.raw_payload["active_party_member"] = True
            actor.raw_payload["reserve_party_member"] = False
            actor.raw_payload["companion_roster"] = True
            actor.raw_payload["party_tactic_mode"] = tactic_mode
        _set_live_party_projection_state(context, actor_id, active=True)

    for actor_id in reserve_ids:
        record = context.entities.get(actor_id)
        actor = actors.get(actor_id)
        live_entry = _live_region_npc_entry(context, actor_id)
        if actor is not None:
            actor.raw_payload["party_member"] = False
            actor.raw_payload["active_party_member"] = False
            actor.raw_payload["reserve_party_member"] = True
            actor.raw_payload["companion_roster"] = True
            actor.raw_payload["party_tactic_mode"] = party_tactic_mode(game_state, actor_id)
        _set_live_party_projection_state(context, actor_id, active=False)
        if live_entry is None and isinstance(record, dict):
            entity_ref = record.get("entity_ref")
            if entity_ref is not None and context.spatial_index.get_position(actor_id) is not None:
                context.spatial_index.remove(entity_ref)
            context.entities.pop(actor_id, None)
            continue
        if not isinstance(record, dict):
            continue
        reserve_position = tuple(record.get("position", list(context.position)))
        if actor is not None:
            reserve_position = _ambient_npc_position(context, actor_id, (int(actor.position.x), int(actor.position.y)))
            actor.position.x = reserve_position[0]
            actor.position.y = reserve_position[1]
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
        record["context_actions"] = list(record.get("context_actions", ["talk", "examine"])) or ["talk", "examine"]
        record["tactic_mode"] = party_tactic_mode(game_state, actor_id)


def _tile_passable(context: CampaignContext, x: int, y: int) -> bool:
    map_data = getattr(context, "map_data", None)
    if map_data is None:
        return True
    width = int(getattr(map_data, "width", 0))
    height = int(getattr(map_data, "height", 0))
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    tile = map_data.tiles[y][x]
    return tile not in {TileType.WALL, TileType.WATER, TileType.TREE}


def _nearest_open_tile(context: CampaignContext, origin: tuple[int, int]) -> tuple[int, int]:
    ox, oy = int(origin[0]), int(origin[1])
    spatial_index = getattr(context, "spatial_index", None)
    for radius in range(0, 5):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x = ox + dx
                y = oy + dy
                if not _tile_passable(context, x, y):
                    continue
                if spatial_index is not None and spatial_index.blocking_at(x, y):
                    continue
                return (x, y)
    return (ox, oy)


def _placement_projection_fields(payload: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(payload.get("entity_type", payload.get("type", ""))).strip().lower()
    role = str(payload.get("role", payload.get("template", ""))).strip().lower()
    building_id = str(
        payload.get("building_id")
        or payload.get("work_building_id")
        or payload.get("home_building_id")
        or ""
    ).strip()
    activity = str(payload.get("activity", "")).strip().lower()
    if entity_type == "npc":
        anchor_kind = "resident"
        placement_priority = 55
        if "meal" in activity or "social" in activity:
            anchor_kind = "plaza"
            placement_priority = 72
        elif activity in {"sleep", "rest", "wake"}:
            anchor_kind = "home"
            placement_priority = 45
        elif role in {"guard", "warden", "scout", "jailer"}:
            anchor_kind = "road"
            placement_priority = 84
        elif role in _SERVICE_NPC_ROLES:
            anchor_kind = "service"
            placement_priority = 96
        return {
            "site_anchor_id": f"{building_id or 'site'}:{anchor_kind}:{payload.get('id', '')}",
            "anchor_kind": anchor_kind,
            "site_role": role or "resident",
            "placement_priority": placement_priority,
        }
    if entity_type in {"furniture", "object", "fixture"}:
        template = str(payload.get("template", role)).strip().lower()
        anchor_kind = "interior"
        placement_priority = 38
        if template in _LANDMARK_FURNITURE_KINDS:
            anchor_kind = "landmark"
            placement_priority = 82
        elif template in _SERVICE_FURNITURE_KINDS:
            anchor_kind = "service"
            placement_priority = 74
        return {
            "site_anchor_id": f"{building_id or 'site'}:{anchor_kind}:{payload.get('id', '')}",
            "anchor_kind": anchor_kind,
            "site_role": template or role or "fixture",
            "placement_priority": placement_priority,
        }
    if entity_type in {"creature", "enemy"}:
        return {
            "site_anchor_id": f"{building_id or 'site'}:threat:{payload.get('id', '')}",
            "anchor_kind": "threat",
            "site_role": role or str(payload.get("template", "")).strip().lower() or "hostile",
            "placement_priority": 88,
        }
    if entity_type == "item":
        return {
            "site_anchor_id": f"{building_id or 'site'}:loot:{payload.get('id', '')}",
            "anchor_kind": "loot",
            "site_role": role or str(payload.get("template", "")).strip().lower() or "item",
            "placement_priority": 26,
        }
    return {
        "site_anchor_id": f"{building_id or 'site'}:ambient:{payload.get('id', '')}",
        "anchor_kind": "ambient",
        "site_role": role or entity_type or "object",
        "placement_priority": 20,
    }


def _semantic_spawn_position(context: CampaignContext, fallback: tuple[int, int]) -> tuple[int, int]:
    building_scores: dict[str, int] = {}
    building_focus_tiles: dict[str, list[tuple[int, int]]] = {}
    for record in context.entities.values():
        if not isinstance(record, dict):
            continue
        entity_type = str(record.get("type", "")).strip().lower()
        position = record.get("position", fallback)
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            continue
        building_id = str(
            record.get("building_id")
            or record.get("work_building_id")
            or record.get("home_building_id")
            or ""
        ).strip()
        if building_id:
            building_focus_tiles.setdefault(building_id, []).append((int(position[0]), int(position[1])))
        if entity_type == "npc":
            role = str(record.get("role", "")).strip().lower()
            score = 70
            if role in _SERVICE_NPC_ROLES:
                score += 55
            if "talk" in [str(item).strip().lower() for item in list(record.get("context_actions", []))]:
                score += 25
            if building_id:
                building_scores[building_id] = building_scores.get(building_id, 0) + score
        elif entity_type == "furniture":
            template = str(record.get("template", record.get("role", ""))).strip().lower()
            score = 12
            if template in _SERVICE_FURNITURE_KINDS:
                score += 42
            elif template in _LANDMARK_FURNITURE_KINDS:
                score += 28
            if building_id:
                building_scores[building_id] = building_scores.get(building_id, 0) + score
    if not building_scores:
        return _nearest_open_tile(context, fallback)
    best_building_id = max(
        building_scores.keys(),
        key=lambda building_id: (building_scores.get(building_id, 0), building_id),
    )
    focus_tiles = building_focus_tiles.get(best_building_id, [])
    if not focus_tiles:
        return _nearest_open_tile(context, fallback)
    focus_tiles.sort(key=lambda item: abs(int(item[0]) - int(fallback[0])) + abs(int(item[1]) - int(fallback[1])))
    return _nearest_open_tile(context, focus_tiles[0])


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
    context.campaign_state["area_waypoints"] = {}
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
    if not preserve_position:
        from .state_sync import sync_player_position

        semantic_spawn = _semantic_spawn_position(context, (int(context.position[0]), int(context.position[1])))
        sync_player_position(context, semantic_spawn[0], semantic_spawn[1], center_viewport=False)
    sync_combat_projection(context)
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


def _build_region_world_entities(world: WorldBlueprint, region_snapshot: RegionSnapshot) -> list[dict[str, Any]]:
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    settlement_waypoints = {"settlement_square": choose_spawn_point(region_snapshot)}
    entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for npc in runtime_state.get("npcs", region_snapshot.layout.npc_spawns):
        npc_id = str(npc["id"])
        if npc_id in seen_ids or bool(npc.get("party_member_active")):
            continue
        seen_ids.add(npc_id)
        ambient_profile = _ambient_profile_for_spawn(
            dict(npc),
            settlement_id=region_snapshot.region_id,
            waypoints=settlement_waypoints,
        )
        entities.append(
            {
                "id": npc_id,
                "entity_type": "npc",
                "entity_kind": "npc",
                "name": str(npc.get("name", str(npc.get("role", "Resident")).replace("_", " ").title())),
                "position": [int(npc["x"]), int(npc["y"])],
                "role": str(npc.get("role", "resident")),
                "template": str(npc.get("template", npc.get("role", "merchant"))),
                "template_id": str(npc.get("template", npc.get("role", "merchant"))),
                "activity": str(npc.get("activity", "")),
                "building_kind": str(npc.get("building_kind", "")),
                "building_id": npc.get("building_id"),
                "home_building_id": npc.get("home_building_id"),
                "work_building_id": npc.get("work_building_id"),
                "disposition": str(npc.get("disposition", "friendly")),
                "ambient_life": bool(ambient_profile.get("ambient_life", False)),
                "facing": str(npc.get("facing", ambient_profile.get("facing", "south"))),
                "state": str(npc.get("state", ambient_profile.get("state", "stand"))),
                "context_actions": list(npc.get("context_actions", ["talk", "examine"])),
            }
        )
    for furniture in region_snapshot.layout.furniture:
        entities.append(
            {
                "id": str(furniture.get("id", f"{furniture['kind']}_{furniture['x']}_{furniture['y']}")),
                "entity_type": "furniture",
                "entity_kind": "furniture",
                "name": str(furniture["kind"]).replace("_", " ").title(),
                "position": [int(furniture["x"]), int(furniture["y"])],
                "template": furniture_template(str(furniture["kind"])),
                "template_id": furniture_template(str(furniture["kind"])),
                "building_id": furniture.get("building_id"),
                "context_actions": furniture_actions(str(furniture["kind"])),
            }
        )
    region = next(region for region in world.regions if region["id"] == region_snapshot.region_id)
    if region.get("fauna"):
        entities.append(
            {
                "id": f"{region_snapshot.region_id}_fauna_0",
                "entity_type": "creature",
                "entity_kind": "hostile",
                "name": str(region["fauna"][0]).replace("_", " ").title(),
                "position": [region_snapshot.width - 5, region_snapshot.height - 5],
                "template": str(region["fauna"][0]).lower(),
                "template_id": str(region["fauna"][0]).lower(),
                "disposition": "hostile",
                "context_actions": ["attack", "examine"],
            }
        )
    return entities


def build_world_entities(
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
    *,
    context: CampaignContext | None = None,
) -> list[dict[str, Any]]:
    del adapter_id
    if context is not None:
        return _augment_world_entities(_build_context_world_entities(context), context=context)
    return _augment_world_entities(_build_region_world_entities(world, region_snapshot), context=None)


def _build_context_world_entities(context: CampaignContext) -> list[dict[str, Any]]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    normalize_party_state(game_state) if game_state is not None else None
    active_party_ids = {
        str(actor_id)
        for actor_id in list(getattr(game_state, "party", []))
        if str(actor_id) and str(actor_id) != "player"
    }
    entities: list[dict[str, Any]] = []
    for entity_id, record in list(context.entities.items()):
        if entity_id == "player" or entity_id in active_party_ids or not isinstance(record, dict):
            continue
        position = record.get("position")
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            entity_ref = record.get("entity_ref")
            position = list(getattr(entity_ref, "position", tuple(context.position)))
        entity_type = str(record.get("type", "")).strip().lower() or str(
            getattr(getattr(record.get("entity_ref"), "entity_type", None), "value", "")
        ).strip().lower()
        payload: dict[str, Any] = {
            "id": str(entity_id),
            "entity_type": entity_type or "object",
            "name": str(record.get("name", entity_id)),
            "position": [int(position[0]), int(position[1])],
            "role": str(record.get("role", "")),
            "activity": str(record.get("activity", "")),
            "building_kind": str(record.get("building_kind", "")),
            "ambient_life": bool(record.get("ambient_life", False)),
            "facing": str(record.get("facing", "south") or "south"),
            "state": str(record.get("state", "stand") or "stand"),
            "context_actions": list(record.get("context_actions", [])),
        }
        disposition = str(record.get("disposition", record.get("attitude", ""))).strip().lower()
        payload["entity_kind"] = str(record.get("entity_kind", _entity_kind_from_payload(entity_type, disposition)))
        template_id = str(
            record.get(
                "template_id",
                record.get("template", record.get("role", entity_type or "object")),
            )
        ).strip()
        if template_id:
            payload["template_id"] = template_id
            payload["template"] = str(record.get("template", template_id))
        if record.get("faction") is not None:
            payload["faction"] = record.get("faction")
        for field_name in ("building_id", "home_building_id", "work_building_id"):
            if record.get(field_name) is not None:
                payload[field_name] = record.get(field_name)
        if disposition:
            payload["disposition"] = disposition
        locked = _record_flag(record, "locked")
        trapped = _record_flag(record, "trapped")
        if locked is not None:
            payload["locked"] = locked
        if trapped is not None:
            payload["trapped"] = trapped
        entities.append(payload)
    return entities


def _augment_world_entities(
    entities: list[dict[str, Any]],
    *,
    context: CampaignContext | None,
) -> list[dict[str, Any]]:
    augmented: list[dict[str, Any]] = []
    for entity in entities:
        payload = dict(entity)
        normalized_context_actions = _normalize_context_actions(payload.get("context_actions", []))
        payload["context_actions"] = list(normalized_context_actions)
        target_kind = _target_kind_for_payload(payload)
        interaction_target_type = _interaction_target_type_for_payload(payload, target_kind=target_kind)
        descriptors = _interaction_descriptors_for_payload(
            payload,
            interaction_target_type=interaction_target_type,
            target_kind=target_kind,
            context=context,
            normalized_context_actions=normalized_context_actions,
        )
        payload["interaction_target_type"] = interaction_target_type
        payload["available_interactions"] = descriptors
        payload["primary_interaction_id"] = _primary_interaction_id(descriptors, normalized_context_actions)
        payload["target_kind"] = target_kind
        if not str(payload.get("entity_kind", "")).strip():
            payload["entity_kind"] = _entity_kind_from_payload(
                str(payload.get("entity_type", "")),
                str(payload.get("disposition", payload.get("attitude", ""))),
            )
        if not str(payload.get("template_id", "")).strip() and str(payload.get("template", "")).strip():
            payload["template_id"] = str(payload.get("template", "")).strip()
        payload.update(_placement_projection_fields(payload))
        payload.update(
            _social_projection_fields(
                payload,
                context=context,
                interaction_target_type=interaction_target_type,
                target_kind=target_kind,
            )
        )
        augmented.append(payload)
    return augmented


def _social_projection_fields(
    payload: dict[str, Any],
    *,
    context: CampaignContext | None,
    interaction_target_type: str | None,
    target_kind: str,
) -> dict[str, Any]:
    if context is None or target_kind != "npc" or interaction_target_type != "npc_friendly":
        return {}
    runtime = context.kernel_runtime or {}
    actor_id = str(payload.get("id", "")).strip()
    actor = (runtime.get("actors") or {}).get(actor_id)
    if actor is None or str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip() != "npc":
        return {}
    raw_payload = getattr(actor, "raw_payload", {})
    named_npc_id_raw = raw_payload.get("named_npc_id")
    named_npc_id = str(named_npc_id_raw).strip() if named_npc_id_raw is not None else ""
    named_npc_id = named_npc_id or None
    identity_source = str(raw_payload.get("identity_source", "")).strip().lower() or ("authored" if named_npc_id else "generated")
    memory_id = str(raw_payload.get("memory_id", "")).strip() or named_npc_id or actor_id
    relationship_score = max(-100, min(100, int(raw_payload.get("relationship_score", 0) or 0)))
    memory = _memory_entry_for_actor(context, actor_id=actor_id, memory_id=memory_id)
    relationship_label = _relationship_label_from_memory(memory, relationship_score)
    last_interaction = _normalized_optional_text(getattr(memory, "last_interaction", None))
    recent_conversation_count = len(list(getattr(memory, "conversations", []) or [])) if memory is not None else 0
    known_facts_count = len(list(getattr(memory, "known_facts", []) or [])) if memory is not None else 0
    known_topic_ids = _known_topic_ids_for_actor(
        context,
        actor_id=actor_id,
        memory_id=memory_id,
        named_npc_id=named_npc_id,
    )
    ask_about_topic_ids = _ask_about_topic_ids_for_actor(
        context,
        actor_id=actor_id,
        actor=actor,
        known_topic_ids=known_topic_ids,
    )
    has_met_player = any(
        (
            last_interaction,
            recent_conversation_count > 0,
            known_facts_count > 0,
            _normalized_optional_text(getattr(memory, "long_term_memory", None)),
        )
    )
    reaction_score = _reaction_score(context, actor)
    return {
        "identity_source": identity_source,
        "named_npc_id": named_npc_id,
        "memory_id": memory_id,
        "recruitable_companion": bool(raw_payload.get("recruitable_companion", False)),
        "relationship_score": relationship_score,
        "relationship_label": relationship_label,
        "reaction_score": reaction_score,
        "has_met_player": has_met_player,
        "last_interaction": last_interaction,
        "recent_conversation_count": recent_conversation_count,
        "known_facts_count": known_facts_count,
        "ask_about_topic_ids": ask_about_topic_ids,
        "ask_about_topics_count": len(ask_about_topic_ids),
        "known_topic_ids": known_topic_ids,
        "known_topics_count": len(known_topic_ids),
        "memory_summary": _memory_summary(memory),
    }


def build_canonical_knowledge_topics(context: CampaignContext | None) -> list[dict[str, Any]]:
    cache = _knowledge_topic_cache(context)
    return [copy.deepcopy(topic) for topic in cache["topics"]]


def _knowledge_topic_cache(context: CampaignContext | None) -> dict[str, Any]:
    if context is None:
        return {"topics": [], "owners_by_topic_id": {}}
    cached = getattr(context, "_knowledge_topic_cache", None)
    if isinstance(cached, dict) and "topics" in cached and "owners_by_topic_id" in cached:
        return cached

    topics_by_id: dict[str, dict[str, Any]] = {}
    manager = getattr(context, "npc_memory", None)
    memories = getattr(manager, "memories", {}) if manager is not None else {}
    for memory_id, memory in sorted(dict(memories).items(), key=lambda item: str(item[0])):
        for fact in list(getattr(memory, "known_facts", []) or []):
            label = _normalized_knowledge_label(fact)
            if label is None:
                continue
            topic_id = _knowledge_topic_id(label)
            topic_entry = topics_by_id.setdefault(
                topic_id,
                {
                    "topic_id": topic_id,
                    "label": label,
                    "source_types": set(),
                    "owner_ids": set(),
                },
            )
            topic_entry["source_types"].add("memory_fact")
            topic_entry["owner_ids"].add(str(memory_id))

    rumor_network = getattr(context, "rumor_network", None)
    active_rumors = rumor_network.get_all_active() if rumor_network is not None else []
    for rumor in sorted(active_rumors, key=lambda item: (_normalized_knowledge_label(getattr(item, "fact", "")) or "", str(getattr(item, "rumor_id", "")))):
        label = _normalized_knowledge_label(getattr(rumor, "fact", ""))
        if label is None:
            continue
        topic_id = _knowledge_topic_id(label)
        topic_entry = topics_by_id.setdefault(
            topic_id,
            {
                "topic_id": topic_id,
                "label": label,
                "source_types": set(),
                "owner_ids": set(),
            },
        )
        topic_entry["source_types"].add("rumor")
        topic_entry["owner_ids"].update(
            str(owner_id).strip()
            for owner_id in list(getattr(rumor, "heard_by", set()) or set())
            if str(owner_id).strip()
        )
        source_npc = str(getattr(rumor, "source_npc", "") or "").strip()
        if source_npc:
            topic_entry["owner_ids"].add(source_npc)

    topics: list[dict[str, Any]] = []
    owners_by_topic_id: dict[str, list[str]] = {}
    for topic_id, topic_entry in sorted(topics_by_id.items(), key=lambda item: (str(item[1]["label"]).lower(), str(item[0]))):
        source_types = sorted({str(source_type) for source_type in topic_entry["source_types"] if str(source_type).strip()})
        owners_by_topic_id[topic_id] = sorted({str(owner_id) for owner_id in topic_entry["owner_ids"] if str(owner_id).strip()})
        topics.append(
            {
                "topic_id": topic_id,
                "label": str(topic_entry["label"]),
                "category": _knowledge_category(source_types),
                "source_types": source_types,
            }
        )

    cache = {
        "topics": topics,
        "owners_by_topic_id": owners_by_topic_id,
    }
    setattr(context, "_knowledge_topic_cache", cache)
    return cache


def _known_topic_ids_for_actor(
    context: CampaignContext,
    *,
    actor_id: str,
    memory_id: str,
    named_npc_id: str | None,
) -> list[str]:
    candidate_ids = {
        str(value).strip()
        for value in (actor_id, memory_id, named_npc_id)
        if str(value or "").strip()
    }
    if not candidate_ids:
        return []
    known_topic_ids: list[str] = []
    seen: set[str] = set()

    memory = _memory_entry_for_actor(context, actor_id=actor_id, memory_id=memory_id)
    for fact in sorted({str(fact).strip() for fact in list(getattr(memory, "known_facts", []) or []) if str(fact).strip()}):
        topic_id = f"fact.{_topic_slug_fragment(fact)}"
        if topic_id in seen:
            continue
        seen.add(topic_id)
        known_topic_ids.append(topic_id)

    rumor_network = getattr(context, "rumor_network", None)
    active_rumors = rumor_network.get_all_active() if rumor_network is not None else []
    for rumor in sorted(active_rumors, key=lambda item: str(getattr(item, "rumor_id", ""))):
        rumor_id = str(getattr(rumor, "rumor_id", "")).strip()
        if not rumor_id:
            continue
        owner_ids = {
            str(owner_id).strip()
            for owner_id in list(getattr(rumor, "heard_by", set()) or set())
            if str(owner_id).strip()
        }
        source_npc = str(getattr(rumor, "source_npc", "") or "").strip()
        if source_npc:
            owner_ids.add(source_npc)
        if not owner_ids.intersection(candidate_ids):
            continue
        topic_id = f"rumor.{rumor_id}"
        if topic_id in seen:
            continue
        seen.add(topic_id)
        known_topic_ids.append(topic_id)
    return known_topic_ids


def _ask_about_topic_ids_for_actor(
    context: CampaignContext,
    *,
    actor_id: str,
    actor: Any,
    known_topic_ids: list[str],
) -> list[str]:
    from .knowledge import related_discovered_topic_ids_for_actor

    faction_id = str(getattr(getattr(actor, "identity", None), "faction_id", "") or "").strip()
    ask_about_topic_ids: list[str] = []
    seen: set[str] = set()

    for topic_id in related_discovered_topic_ids_for_actor(context, actor_id, faction_id):
        normalized = str(topic_id).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ask_about_topic_ids.append(normalized)

    for topic_id in list(known_topic_ids or []):
        normalized = str(topic_id).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ask_about_topic_ids.append(normalized)

    return ask_about_topic_ids


def _topic_slug_fragment(value: Any) -> str:
    normalized = str(_normalized_knowledge_label(value) or "topic").lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_") or "topic"


def _normalized_knowledge_label(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _knowledge_topic_id(label: str) -> str:
    normalized = str(_normalized_knowledge_label(label) or "topic")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")[:48] or "topic"
    digest = hashlib.sha1(normalized.lower().encode("utf-8")).hexdigest()[:12]
    return f"topic_{slug}_{digest}"


def _knowledge_category(source_types: list[str]) -> str:
    normalized = sorted({str(source_type).strip() for source_type in source_types if str(source_type).strip()})
    if normalized == ["rumor"]:
        return "rumor"
    if normalized == ["memory_fact"]:
        return "fact"
    return "mixed"


def sync_combat_projection_state(context: CampaignContext) -> None:
    """Mirror live combat actor positions into projected entities and spatial truth."""
    sync_combat_projection(context)


def _memory_entry_for_actor(context: CampaignContext, *, actor_id: str, memory_id: str):
    manager = getattr(context, "npc_memory", None)
    if manager is None:
        return None
    memories = getattr(manager, "memories", {})
    if memory_id in memories:
        return memories[memory_id]
    if actor_id in memories:
        return memories[actor_id]
    return None


def _relationship_label_from_memory(memory: Any, relationship_score: int) -> str:
    label = _normalized_optional_text(getattr(memory, "relationship_label", None)) if memory is not None else None
    if label:
        return label
    if relationship_score >= 60:
        return "ally"
    if relationship_score >= 30:
        return "friend"
    if relationship_score >= 10:
        return "acquaintance"
    if relationship_score > -20:
        return "stranger"
    if relationship_score > -50:
        return "unfriendly"
    return "enemy"


def _memory_summary(memory: Any) -> str | None:
    if memory is None:
        return None
    long_term = _normalized_optional_text(getattr(memory, "long_term_memory", None))
    if long_term:
        return long_term
    conversations = list(getattr(memory, "conversations", []) or [])
    if conversations:
        last_summary = _normalized_optional_text(conversations[-1].get("summary")) if isinstance(conversations[-1], dict) else None
        if last_summary:
            return last_summary
    return None


def _normalized_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _reaction_score(context: CampaignContext, npc_actor: Any) -> int | None:
    runtime = context.kernel_runtime or {}
    player = (runtime.get("actors") or {}).get("player") or context.player
    if player is None or npc_actor is None:
        return None
    game_state = runtime.get("game_state")
    global_variables = getattr(game_state, "global_variables", {}) if game_state is not None else {}
    reputation = int(global_variables.get("reputation", 0) or 0) if isinstance(global_variables, dict) else 0
    return int(compute_npc_reaction(player, npc_actor, reputation))


def _record_flag(record: dict[str, Any], key: str) -> bool | None:
    if key in record:
        return bool(record.get(key))
    entity_ref = record.get("entity_ref")
    if entity_ref is not None and hasattr(entity_ref, key):
        return bool(getattr(entity_ref, key))
    return None


def _normalize_context_actions(raw_actions: Any) -> list[str]:
    normalized: list[str] = []
    for action in list(raw_actions or []):
        canonical = _INTERACTION_HINT_ALIASES.get(str(action).strip().lower())
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _target_kind_for_payload(payload: dict[str, Any]) -> str:
    entity_type = str(payload.get("entity_type", "object")).strip().lower()
    disposition = str(payload.get("disposition", payload.get("attitude", "friendly"))).strip().lower()
    if not bool(payload.get("alive", True)):
        return "enemy"
    if entity_type == "npc":
        return "enemy" if disposition == "hostile" else "npc"
    if entity_type == "creature":
        return "enemy"
    if entity_type == "furniture":
        return "furniture"
    if entity_type == "item":
        return "item"
    return "tile"


def _canonical_furniture_target_kind(base: str, role: str) -> str:
    for candidate in (base, role):
        if candidate in _FURNITURE_TARGET_KIND_ALIASES:
            return _FURNITURE_TARGET_KIND_ALIASES[candidate]
        if any(token in candidate for token in ("forge", "anvil", "workbench", "loom", "press")):
            return "workstation"
        if "door" in candidate:
            return "door"
        if "bed" in candidate:
            return "bed"
        if any(token in candidate for token in ("bookshelf", "bookcase", "shelf", "cabinet")):
            return "bookshelf"
        if any(token in candidate for token in ("altar", "shrine", "totem", "cauldron", "oven", "lantern")):
            return "altar"
        if "well" in candidate:
            return "well"
        if any(token in candidate for token in ("barrel", "cask")):
            return "barrel"
        if any(token in candidate for token in ("crate", "rack", "chest", "keys")):
            return "chest"
        if "lever" in candidate:
            return "lever"
        if "trap" in candidate:
            return "trap"
        if "campfire" in candidate or "firepit" in candidate:
            return "campfire"
        if any(token in candidate for token in ("sign", "book")):
            return "sign"
        if any(token in candidate for token in ("bench", "chair", "table", "desk", "counter", "stool", "trough")):
            return "fixture"
    return "fixture" if (base or role) else "furniture"


def _interaction_target_type_for_payload(payload: dict[str, Any], *, target_kind: str) -> str | None:
    entity_type = str(payload.get("entity_type", "object")).strip().lower()
    disposition = str(payload.get("disposition", payload.get("attitude", "friendly"))).strip().lower()
    if not bool(payload.get("alive", True)) and entity_type in {"npc", "creature"}:
        return "corpse"
    if entity_type in {"npc", "creature"}:
        return "npc_hostile" if disposition == "hostile" else "npc_friendly"
    if entity_type == "furniture":
        template = str(payload.get("template", "")).strip().lower()
        role = str(payload.get("role", "")).strip().lower()
        base = template or furniture_template(role) or role
        canonical_kind = _canonical_furniture_target_kind(base, role)
        if canonical_kind == "door":
            return "door_locked" if bool(payload.get("locked")) else "door_unlocked"
        if canonical_kind == "chest":
            if bool(payload.get("trapped")):
                return "chest_trapped"
            if bool(payload.get("locked")):
                return "chest_locked"
            return "chest"
        return canonical_kind if canonical_kind in _RULES_BY_TARGET_TYPE else None
    if entity_type == "item":
        return "item"
    return target_kind if target_kind in _RULES_BY_TARGET_TYPE else None


def _interaction_descriptors_for_payload(
    payload: dict[str, Any],
    *,
    interaction_target_type: str | None,
    target_kind: str,
    context: CampaignContext | None,
    normalized_context_actions: list[str],
) -> list[dict[str, Any]]:
    if not interaction_target_type:
        return []
    rules = list(_RULES_BY_TARGET_TYPE.get(interaction_target_type, []))
    if not rules:
        return []
    hint_order = {action_id: index for index, action_id in enumerate(normalized_context_actions)}
    descriptors: list[dict[str, Any]] = []
    for rule_index, (interaction_type, rule) in enumerate(rules):
        interaction_id = _interaction_id(interaction_type)
        available, blocked_reason = _interaction_availability(
            context,
            interaction_target_type=interaction_target_type,
            interaction_id=interaction_id,
            requirements=list(rule.get("requirements", [])),
        )
        descriptors.append(
            {
                "id": f"{payload.get('id', target_kind)}:{interaction_id}",
                "label": _interaction_label(interaction_id),
                "interaction_id": interaction_id,
                "governing_check": _governing_check_payload(rule),
                "requirements": list(rule.get("requirements", [])),
                "ap_cost": int(rule.get("ap_cost", 0)),
                "available": bool(available),
                "blocked_reason": blocked_reason,
                "_sort_hint": hint_order.get(interaction_id, len(hint_order) + rule_index),
                "_sort_rule": rule_index,
            }
        )
    descriptors.sort(key=lambda item: (int(item.pop("_sort_hint")), int(item.pop("_sort_rule")), str(item["interaction_id"])))
    return descriptors


def _interaction_availability(
    context: CampaignContext | None,
    *,
    interaction_target_type: str,
    interaction_id: str,
    requirements: list[Any],
) -> tuple[bool, str | None]:
    del interaction_target_type, interaction_id
    if context is None:
        return True, None
    player = (context.kernel_runtime or {}).get("actors", {}).get("player") or context.player
    if player is None:
        return True, None
    inventory_ids: set[str] = set()
    for item in list(getattr(player, "inventory", []) or []):
        item_def_id = str(getattr(item, "item_def_id", "")).strip().lower()
        if item_def_id:
            inventory_ids.add(item_def_id)
    gold = int(getattr(player, "raw_payload", {}).get("gold", 0) or 0)
    for requirement in [str(item).strip().lower() for item in requirements if str(item).strip()]:
        if requirement == "gold" and gold <= 0:
            return False, "Requires gold."
        if requirement == "ingredients":
            if not inventory_ids:
                return False, "Requires ingredients."
            continue
        if requirement == "matching_key":
            if not any("key" in item_id for item_id in inventory_ids):
                return False, "Requires matching key."
            continue
        aliases = {
            "lockpick": {"lockpick", "lockpick_set"},
            "pickaxe": {"pickaxe", "mining_pick", "miner_pick"},
            "axe": {"axe", "hand_axe", "wood_axe"},
            "fishing_rod": {"fishing_rod", "fishing_hook"},
            "waterskin": {"waterskin"},
            "trap_kit": {"trap_kit"},
        }.get(requirement, {requirement})
        if inventory_ids.isdisjoint(aliases):
            return False, f"Requires {requirement.replace('_', ' ')}."
    return True, None


def _governing_check_payload(rule: dict[str, Any]) -> str | None:
    skill = rule.get("skill")
    return str(skill) if skill is not None else None


def _interaction_id(interaction_type: InteractionType) -> str:
    raw = str(interaction_type.name).strip().lower()
    return "pickup" if raw == "pick_up" else raw


def _interaction_label(interaction_id: str) -> str:
    if interaction_id in _INTERACTION_LABEL_OVERRIDES:
        return _INTERACTION_LABEL_OVERRIDES[interaction_id]
    return interaction_id.replace("_", " ").title()


def _primary_interaction_id(descriptors: list[dict[str, Any]], normalized_context_actions: list[str]) -> str | None:
    if not descriptors:
        return None
    descriptor_ids = {str(item.get("interaction_id", "")) for item in descriptors}
    for action_id in normalized_context_actions:
        if action_id in descriptor_ids:
            return action_id
    for descriptor in descriptors:
        if bool(descriptor.get("available")):
            return str(descriptor.get("interaction_id", "")) or None
    return str(descriptors[0].get("interaction_id", "")) or None


def seed_region_entities(
    context: CampaignContext,
    world: WorldBlueprint,
    region_snapshot: RegionSnapshot,
    adapter_id: str,
) -> None:
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    settlement_waypoints = _derive_region_waypoints(context, region_snapshot)
    context.campaign_state["area_waypoints"] = {
        str(name): [int(position[0]), int(position[1])]
        for name, position in settlement_waypoints.items()
    }
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
        ambient_profile = _ambient_profile_for_spawn(
            dict(spawn),
            settlement_id=region_snapshot.region_id,
            waypoints=settlement_waypoints,
        )
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
        setattr(entity, "facing", str(ambient_profile.get("facing", "south")))
        setattr(entity, "state", str(ambient_profile.get("state", "stand")))
        context.spatial_index.add(entity)
        ambient_enabled = bool(ambient_profile.get("ambient_life", False))
        context.entities[entity.id] = {
            "name": entity.name,
            "type": "npc",
            "entity_kind": "npc",
            "position": [entity.position[0], entity.position[1]],
            "faction": controller,
            "role": role,
            "attitude": "friendly",
            "template": str(spawn.get("template", role)),
            "template_id": str(spawn.get("template", role)),
            "activity": str(spawn.get("activity", "")),
            "building_kind": str(spawn.get("building_kind", "")),
            "building_id": spawn.get("building_id"),
            "home_building_id": spawn.get("home_building_id"),
            "work_building_id": spawn.get("work_building_id"),
            "ambient_life": ambient_enabled,
            "ambient_profile": ambient_profile,
            "waypoints": dict(ambient_profile.get("waypoints", {})),
            "facing": str(ambient_profile.get("facing", "south")),
            "state": str(ambient_profile.get("state", "stand")),
            "context_actions": list(spawn.get("context_actions", ["talk", "examine"])),
            "named_npc_id": spawn.get("named_npc_id"),
            "identity_source": str(spawn.get("identity_source", "generated")),
            "memory_id": spawn.get("memory_id"),
            "entity_ref": entity,
        }
        if ambient_enabled:
            context.entities[entity.id]["wander_tree"] = build_default_ambient_tree(context.entities[entity.id])
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
            "entity_kind": "furniture",
            "position": [furniture_entity.position[0], furniture_entity.position[1]],
            "role": str(furniture["kind"]),
            "template": furniture_template(str(furniture["kind"])),
            "template_id": furniture_template(str(furniture["kind"])),
            "building_id": furniture.get("building_id"),
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
            "entity_kind": "hostile",
            "position": [hostile.position[0], hostile.position[1]],
            "faction": hostile.faction,
            "role": hostile.job,
            "attitude": "hostile",
            "template": str(region["fauna"][0]).lower(),
            "template_id": str(region["fauna"][0]).lower(),
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
    "sync_combat_projection",
    "sync_schedule_projection",
    "sync_party_projection",
]
