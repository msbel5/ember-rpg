"""Exploration command bridge: look, examine, move, and skill-based scene verbs.

Each handler follows the maybe_handle pattern -- returns
(narrative, command_type, hours_advanced) or None when the
command text does not match.
"""
from __future__ import annotations

import logging
import random
import re
from typing import TYPE_CHECKING, Optional

from engine.world.interactions_catalog import load_interaction_rules
from engine.world.interactions_runtime import interaction_target_type_for_tile
from engine.kernel.combat_math import ability_modifier
from engine.api.campaign.state_sync import sync_player_position
from engine.map import TileType

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord

logger = logging.getLogger(__name__)
_INTERACTION_RULES = load_interaction_rules()

_LOOK_AT_RE = re.compile(r"^look\s+at\s+(.+)$", re.IGNORECASE)
_LOOK_RE = re.compile(r"^look(?:\s+around)?$", re.IGNORECASE)
_EXAMINE_RE = re.compile(r"^(?:examine|inspect)\s+(.+)$", re.IGNORECASE)
_MOVE_TO_COORDS_RE = re.compile(r"^(?:move|go)\s+to\s+(\d+)\s*,\s*(\d+)$", re.IGNORECASE)
_MOVE_TO_PLACE_RE = re.compile(r"^go\s+to\s+(.+)$", re.IGNORECASE)
_MOVE_DIR_RE = re.compile(r"^move\s+(north|south|east|west|up|down|n|s|e|w)$", re.IGNORECASE)
_SCENE_VERB_RE = re.compile(
    r"^(search|lockpick|climb|sneak|steal|pray|fish|mine|chop|push|open)(?:\s+(.+))?$",
    re.IGNORECASE,
)

_VERB_STAT: dict[str, str] = {
    "search": "INS", "lockpick": "AGI", "climb": "MIG", "sneak": "AGI",
    "steal": "AGI", "pray": "INS", "fish": "AGI", "mine": "MIG",
    "chop": "MIG", "push": "MIG", "open": "MIG",
}
_DIR_DELTAS: dict[str, tuple[int, int]] = {
    "north": (0, -1), "n": (0, -1), "south": (0, 1), "s": (0, 1),
    "east": (1, 0), "e": (1, 0), "west": (-1, 0), "w": (-1, 0),
    "up": (0, -1), "down": (0, 1),
}

# -- helpers -----------------------------------------------------------------

def _player(ctx: "CampaignContext") -> Optional["ActorRecord"]:
    return (ctx.kernel_runtime or {}).get("actors", {}).get("player")

def _actors(ctx: "CampaignContext") -> dict[str, "ActorRecord"]:
    return (ctx.kernel_runtime or {}).get("actors", {})

def _npc_list(ctx: "CampaignContext") -> list["ActorRecord"]:
    visible_types = {"npc", "creature", "monster", "animal"}
    return [
        actor
        for actor_id, actor in _actors(ctx).items()
        if actor_id != "player"
        and getattr(actor, "alive", True)
        and str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower() in visible_types
    ]

def _time_desc(ctx: "CampaignContext") -> str:
    ss = ctx.settlement_state
    hour, day, season = ss.get("current_hour", 12), ss.get("current_day", 1), ss.get("season", "spring")
    period = "before dawn" if hour < 6 else "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"Day {day}, {period} ({season})"

def _building_summary(ctx: "CampaignContext") -> str:
    rooms = ctx.settlement_state.get("rooms", [])
    if not rooms:
        return ""
    labels = [r.get("label", r.get("kind", "building")) for r in rooms[:6]]
    extra = f" and {len(rooms) - 6} more" if len(rooms) > 6 else ""
    return "Nearby buildings: " + ", ".join(labels) + extra + "."

def _furniture_summary(ctx: "CampaignContext") -> str:
    furniture = [entity for entity in ctx.world_entities if entity.get("entity_type") == "furniture"] if hasattr(ctx, "world_entities") else []
    if not furniture:
        furniture = [
            value for value in ctx.entities.values()
            if isinstance(value, dict) and str(value.get("type", "")).lower() == "furniture"
        ]
    if not furniture:
        return ""
    labels = [str(item.get("name", "Fixture")) for item in furniture[:5]]
    extra = f" and {len(furniture) - 5} more" if len(furniture) > 5 else ""
    return "Nearby fixtures: " + ", ".join(labels) + extra + "."

def _npc_summary(ctx: "CampaignContext") -> str:
    npcs = _npc_list(ctx)
    if not npcs:
        return "No one else is around."
    parts = [f"{n.identity.display_name} ({getattr(n.identity, 'actor_type', 'npc')})" for n in npcs[:8]]
    extra = f" and {len(npcs) - 8} others" if len(npcs) > 8 else ""
    return "You see: " + ", ".join(parts) + extra + "."

def _find_actor(ctx: "CampaignContext", target: str) -> Optional["ActorRecord"]:
    tl = target.lower().strip()
    for aid, a in _actors(ctx).items():
        if aid != "player" and tl in a.identity.display_name.lower():
            return a
    return None

def _find_room(ctx: "CampaignContext", target: str) -> Optional[dict]:
    tl = target.lower().strip()
    for room in ctx.settlement_state.get("rooms", []):
        label = room.get("label", room.get("kind", "")).lower()
        if tl in label or label in tl:
            return room
    return None

# -- handlers ----------------------------------------------------------------

def maybe_handle_look_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle 'look', 'look around', 'look at <target>'."""
    text = command_text.strip()
    m = _LOOK_AT_RE.match(text)
    if m:
        return maybe_handle_examine_command(context, f"examine {m.group(1)}")
    if not _LOOK_RE.match(text):
        return None
    if _player(context) is None:
        return ("You look around but cannot make sense of your surroundings.", "exploration", 0)
    if hasattr(context, "refresh_fog_state"):
        context.refresh_fog_state()
    ss = context.settlement_state
    name = ss.get("name", "this settlement")
    weather = ss.get("weather", {}).get("description", "")
    lines = [f"You are in {name}. {_time_desc(context)}.{' ' + weather if weather else ''}",
             _npc_summary(context)]
    bld = _building_summary(context)
    if bld:
        lines.append(bld)
    fixtures = _furniture_summary(context)
    if fixtures:
        lines.append(fixtures)
    return ("\n".join(lines), "exploration", 0)


def maybe_handle_examine_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle 'examine <target>', 'inspect <target>'."""
    m = _EXAMINE_RE.match(command_text.strip())
    if not m:
        return None
    target = m.group(1).strip()
    actor = _find_actor(context, target)
    if actor is not None:
        parts = [f"{actor.identity.display_name} ({getattr(actor.identity, 'actor_type', '')})"]
        desc = actor.raw_payload.get("description", "")
        if desc:
            parts.append(desc)
        stats = [f"{k} {actor.stats[k]}" for k in ("MIG","AGI","VIT","INS","CHA","ARC") if k in actor.stats]
        if stats:
            parts.append("Stats: " + ", ".join(stats))
        if actor.equipment and actor.equipment.slots:
            eq = [f"{it.name} ({sl})" for sl, items in actor.equipment.slots.items() for it in items]
            if eq:
                parts.append("Equipped: " + ", ".join(eq))
        if actor.max_hp:
            parts.append(f"HP: {actor.hp}/{actor.max_hp}")
        return ("\n".join(parts), "exploration", 0)
    room = _find_room(context, target)
    if room is not None:
        label = room.get("label", room.get("kind", "building"))
        ws = room.get("workstations", [])
        ws_t = f" Workstations: {', '.join(ws)}." if ws else ""
        beds = room.get("beds", 0)
        bed_t = f" Beds: {beds}." if beds else ""
        return (f"{label} -- {room.get('doors', 0)} door(s).{ws_t}{bed_t}", "exploration", 0)
    return (f"You look closely at '{target}' but find nothing remarkable.", "exploration", 0)


def build_structured_tile_payload(
    context: "CampaignContext",
    *,
    target_position: tuple[int, int] | None,
    tile_name: str | None = None,
    interaction_id: str | None = None,
) -> dict[str, object] | None:
    if target_position is None or len(target_position) < 2:
        return None
    x, y = int(target_position[0]), int(target_position[1])
    map_data = getattr(context, "map_data", None)
    if map_data is None:
        return None
    if x < 0 or y < 0 or x >= int(map_data.width) or y >= int(map_data.height):
        return None
    tile = map_data.tiles[y][x]
    terrain = "floor"
    flags: set[str] = set()
    if tile == TileType.WATER:
        terrain = "shallow_water"
        flags.add("WATER")
    elif tile == TileType.TREE:
        terrain = "tree"
        flags.add("TREE")
    elif tile == TileType.WALL:
        terrain = "stone_wall"
    elif tile == TileType.ROAD:
        terrain = "road"
    normalized_tile_name = str(tile_name or "").strip().lower().replace(" ", "_")
    if normalized_tile_name == "bridge":
        terrain = "bridge"
        flags.add("BRIDGE")
    elif normalized_tile_name in {"ore", "ore_vein"}:
        terrain = "ore_vein"
        flags.add("ORE")
    elif normalized_tile_name == "narrow_gap":
        terrain = "narrow_gap"
        flags.add("NARROW")
    elif normalized_tile_name == "boulder":
        terrain = "boulder"
        flags.add("BOULDER")
    preferred = None
    if interaction_id:
        from engine.world.interactions_runtime import parse_interaction_type

        preferred = parse_interaction_type(interaction_id)
    return {
        "name": str(tile_name or terrain).replace("_", " ").title(),
        "target_type": interaction_target_type_for_tile(
            {"terrain": terrain, "flags": flags, "items": []},
            preferred_interaction=preferred,
            rules=_INTERACTION_RULES,
            tile_name=tile_name,
        ),
        "tile": {"terrain": terrain, "flags": flags, "items": []},
        "position": [x, y],
    }


def handle_structured_examine(
    context: "CampaignContext",
    *,
    target_id: str | None = None,
    target_kind: str | None = None,
    target_position: tuple[int, int] | None = None,
    tile_name: str | None = None,
) -> tuple[str, str, int]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    if target_id:
        actor = actors.get(str(target_id))
        if actor is not None and str(target_kind or "").strip().lower() in {"", "npc", "enemy"}:
            parts = [f"{actor.identity.display_name} ({getattr(actor.identity, 'actor_type', '')})"]
            desc = actor.raw_payload.get("description", "")
            if desc:
                parts.append(desc)
            if actor.max_hp:
                parts.append(f"HP: {actor.hp}/{actor.max_hp}")
            return ("\n".join(parts), "exploration", 0)
        record = context.entities.get(str(target_id))
        if isinstance(record, dict):
            name = str(record.get("name", target_id))
            role = str(record.get("role", record.get("template", ""))).replace("_", " ").strip()
            position = record.get("position", list(context.position))
            detail = f" at ({int(position[0])},{int(position[1])})" if isinstance(position, (list, tuple)) and len(position) >= 2 else ""
            role_text = f" [{role}]" if role else ""
            return (f"You examine {name}{role_text}{detail}.", "exploration", 0)
        live_entity = getattr(context, "spatial_index", None).get_entity(str(target_id)) if getattr(context, "spatial_index", None) is not None else None
        if live_entity is not None:
            return (f"You examine {live_entity.name}.", "exploration", 0)
    tile_payload = build_structured_tile_payload(
        context,
        target_position=target_position,
        tile_name=tile_name,
    )
    if tile_payload is not None:
        name = str(tile_payload.get("name", "the ground"))
        position = list(tile_payload.get("position", list(context.position)))
        return (f"You examine {name} at ({int(position[0])},{int(position[1])}).", "exploration", 0)
    return ("You look closely but find nothing remarkable.", "exploration", 0)


def maybe_handle_move_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle 'move <direction>', 'move to <x>,<y>', 'go to <location>'."""
    text = command_text.strip()
    no_player = ("You cannot move -- no player record found.", "exploration", 0)
    # "move to X,Y"
    m = _MOVE_TO_COORDS_RE.match(text)
    if m:
        player = _player(context)
        if player is None:
            return no_player
        old_x, old_y = player.position.x, player.position.y
        new_x, new_y = int(m.group(1)), int(m.group(2))
        sync_player_position(context, new_x, new_y)
        if hasattr(context, "refresh_fog_state"):
            context.refresh_fog_state()
        return ("", "exploration", 0)  # silent move — player sees the movement on the map
    # "move <direction>"
    m = _MOVE_DIR_RE.match(text)
    if m:
        player = _player(context)
        if player is None:
            return no_player
        d = m.group(1).lower()
        dx, dy = _DIR_DELTAS.get(d, (0, 0))
        new_x = int(player.position.x) + dx
        new_y = int(player.position.y) + dy
        sync_player_position(context, new_x, new_y)
        if hasattr(context, "refresh_fog_state"):
            context.refresh_fog_state()
        return ("", "exploration", 0)  # silent move
    # "go to <location>"
    m = _MOVE_TO_PLACE_RE.match(text)
    if m:
        loc = m.group(1).strip()
        if _player(context) is None:
            return no_player
        room = _find_room(context, loc)
        label = room.get("label", room.get("kind", "building")) if room else loc
        if hasattr(context, "refresh_fog_state"):
            context.refresh_fog_state()
        return (f"You head towards {label}.", "exploration", 0)
    return None


def maybe_handle_scene_verb_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle skill-check scene verbs: search, open, lockpick, climb, etc."""
    from engine.api.campaign.crime import maybe_record_trespass

    m = _SCENE_VERB_RE.match(command_text.strip())
    if not m:
        return None
    verb, target = m.group(1).lower(), (m.group(2) or "").strip()
    player = _player(context)
    if player is None:
        return ("You try but cannot act -- no player record found.", "exploration", 1)
    stat_name = _VERB_STAT.get(verb, "MIG")
    dc = 15
    mod = ability_modifier(int(player.stats.get(stat_name, 10)))
    roll = random.randint(1, 20)
    total = roll + mod
    success = total >= dc
    tgt = f" {target}" if target else ""
    detail = f"[{stat_name} check: d20({roll}) + {mod} = {total} vs DC {dc}]"
    narrative = _VERB_NARRATIVES[verb][0 if success else 1].format(target=tgt, detail=detail, verb=verb)
    incident = maybe_record_trespass(
        context,
        verb=verb,
        target_query=target,
        success=success,
    )
    if incident is not None and isinstance(incident.get("last_incident"), dict):
        narrative = f"{narrative} Trespass recorded.".strip()
    return (narrative, "exploration", 1)

# success/failure narrative pairs per verb
_VERB_NARRATIVES: dict[str, tuple[str, str]] = {
    "search": ("You search{target} carefully and notice something interesting. {detail}",
               "You search{target} but find nothing of interest. {detail}"),
    "lockpick": ("You deftly pick the lock on{target}. The mechanism clicks open. {detail}",
                 "You fumble with the lock on{target}. It refuses to budge. {detail}"),
    "climb": ("You scale{target} with practiced ease. {detail}",
              "You attempt to climb{target} but lose your grip. {detail}"),
    "sneak": ("You move silently, blending into the shadows. {detail}",
              "You try to move quietly but stumble, making noise. {detail}"),
    "steal": ("You deftly lift something from{target}. {detail}",
              "You reach for{target} but are noticed and pull back. {detail}"),
    "pray": ("You kneel and pray. A sense of calm washes over you. {detail}",
             "You attempt to pray but your mind wanders. {detail}"),
    "fish": ("You cast your line and feel a tug. A fine catch! {detail}",
             "You cast your line but the fish elude you today. {detail}"),
    "mine": ("You swing your pick and find a vein of ore. {detail}",
             "You swing your pick but only chip away at barren rock. {detail}"),
    "chop": ("You chop steadily and gather a bundle of wood. {detail}",
             "You swing at the wood but your blade glances off. {detail}"),
    "push": ("You push{target} with all your might and it moves. {detail}",
             "You push{target} but it won't budge. {detail}"),
    "open": ("You open{target} without difficulty. {detail}",
             "You try to open{target} but it resists your effort. {detail}"),
}

__all__ = [
    "build_structured_tile_payload",
    "handle_structured_examine",
    "maybe_handle_examine_command",
    "maybe_handle_look_command",
    "maybe_handle_move_command",
    "maybe_handle_scene_verb_command",
]
