"""Campaign context projection helpers for campaign runtime."""
from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from engine.api.campaign.context import CampaignContext
from engine.kernel.game_state import FORMATIONS, normalize_party_state, party_tactic_mode
from engine.kernel.scene_types import SceneType
from engine.map import MapData, Room, TileType
from engine.world.interactions_catalog import load_interaction_rules
from engine.world.interactions_types import InteractionType
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
    player_x, player_y = int(context.position[0]), int(context.position[1])
    actors = runtime.get("actors") or {}
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


def _build_region_world_entities(world: WorldBlueprint, region_snapshot: RegionSnapshot) -> list[dict[str, Any]]:
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    entities: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for npc in runtime_state.get("npcs", region_snapshot.layout.npc_spawns):
        npc_id = str(npc["id"])
        if npc_id in seen_ids or bool(npc.get("party_member_active")):
            continue
        seen_ids.add(npc_id)
        entities.append(
            {
                "id": npc_id,
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
            "context_actions": list(record.get("context_actions", [])),
        }
        if record.get("template") is not None:
            payload["template"] = str(record.get("template", ""))
        if record.get("faction") is not None:
            payload["faction"] = record.get("faction")
        disposition = str(record.get("disposition", record.get("attitude", ""))).strip().lower()
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
        augmented.append(payload)
    return augmented


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
