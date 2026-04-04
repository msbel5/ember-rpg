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

from engine.kernel.combat_math import ability_modifier
from engine.api.campaign.state_sync import sync_player_position

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord

logger = logging.getLogger(__name__)

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
        return (f"You move from ({old_x},{old_y}) to ({new_x},{new_y}).",
                "exploration", 0)
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
        return (f"You move {d} to ({new_x},{new_y}).", "exploration", 0)
    # "go to <location>"
    m = _MOVE_TO_PLACE_RE.match(text)
    if m:
        loc = m.group(1).strip()
        if _player(context) is None:
            return no_player
        room = _find_room(context, loc)
        label = room.get("label", room.get("kind", "building")) if room else loc
        return (f"You head towards {label}.", "exploration", 0)
    return None


def maybe_handle_scene_verb_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle skill-check scene verbs: search, open, lockpick, climb, etc."""
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
    "maybe_handle_examine_command",
    "maybe_handle_look_command",
    "maybe_handle_move_command",
    "maybe_handle_scene_verb_command",
]
