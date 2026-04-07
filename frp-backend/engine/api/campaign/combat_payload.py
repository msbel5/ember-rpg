"""Combat payload shaping and read-only combat legality helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.kernel.gameplay import actor_can_cast_registry_spells
from engine.map import TileType
from engine.world.proximity import combat_targeting_check

from .called_shot import _called_shot_zones

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord, ItemStack
    from engine.kernel.combat_engine import CombatState


_DIRECTION_DELTAS: dict[str, tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
_RANGED_ATTACK_TYPES = {"ranged", "launcher", "thrown", "projectile", "beam"}
_LOS_PROJECTILE_TYPES = {"arrow", "fireball", "cone", "bouncing", "traveling", "beam", "laser"}
_SUPPORTED_ACTIONS = ["attack", "defend", "flee", "move", "end_turn"]


def _passable_tile(context: "CampaignContext", x: int, y: int) -> bool:
    map_data = getattr(context, "map_data", None)
    if map_data is None:
        return True
    width = int(getattr(map_data, "width", 0))
    height = int(getattr(map_data, "height", 0))
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    tile = map_data.tiles[y][x]
    return tile not in {TileType.WALL, TileType.WATER, TileType.TREE}


def _movement_block_reason(
    context: "CampaignContext",
    actor_id: str,
    x: int,
    y: int,
    *,
    movement_remaining: int,
) -> str | None:
    if movement_remaining <= 0:
        return "no_movement_remaining"
    map_data = getattr(context, "map_data", None)
    if map_data is not None:
        width = int(getattr(map_data, "width", 0))
        height = int(getattr(map_data, "height", 0))
        if x < 0 or y < 0 or x >= width or y >= height:
            return "edge_of_map"
        if not _passable_tile(context, x, y):
            return "blocked_terrain"
    spatial_index = getattr(context, "spatial_index", None)
    if spatial_index is not None:
        for entity in spatial_index.at(int(x), int(y)):
            if entity.id == actor_id or not bool(getattr(entity, "blocking", False)):
                continue
            return "occupied"
    return None


def _movement_failure_message(direction: str, blocked_reason: str) -> str:
    if blocked_reason == "no_movement_remaining":
        return "You have no movement remaining this turn."
    if blocked_reason == "edge_of_map":
        return f"You can't move {direction} - edge of the map."
    if blocked_reason == "blocked_terrain":
        return f"You can't move {direction} - blocked by terrain."
    if blocked_reason == "occupied":
        return f"You can't move {direction} - the tile is occupied."
    return f"You can't move {direction} right now."


def _build_move_options(
    context: "CampaignContext",
    combat_state: "CombatState",
    actors: dict[str, Any],
) -> list[dict[str, Any]]:
    if not combat_state.combatants:
        return []
    active = combat_state.active_combatant
    if active.actor_id != "player":
        return []
    actor = actors.get(active.actor_id)
    if actor is None or not getattr(actor, "alive", True):
        return []
    current = (int(actor.position.x), int(actor.position.y))
    movement_remaining = int(active.turn_resources.movement)
    options: list[dict[str, Any]] = []
    for direction, (dx, dy) in _DIRECTION_DELTAS.items():
        next_x, next_y = current[0] + dx, current[1] + dy
        blocked_reason = _movement_block_reason(
            context,
            active.actor_id,
            next_x,
            next_y,
            movement_remaining=movement_remaining,
        )
        options.append(
            {
                "direction": direction,
                "position": [int(next_x), int(next_y)],
                "available": blocked_reason is None,
                "blocked_reason": blocked_reason,
            }
        )
    return options


def _weapon_attack_profile(weapon: "ItemStack" | None) -> dict[str, Any]:
    payload = dict(getattr(weapon, "payload", {}) or {}) if weapon is not None else {}
    profile: dict[str, Any] = dict(payload.get("attack_profile", {}) or {})
    combat_headers = payload.get("combat_headers")
    if not profile and isinstance(combat_headers, list) and combat_headers:
        first_header = combat_headers[0]
        if isinstance(first_header, dict):
            profile.update(first_header)
    for key in ("range", "max_range"):
        value = profile.get(key, payload.get(key))
        if value not in (None, ""):
            profile["range"] = int(value)
            break
    attack_type = str(profile.get("attack_type", payload.get("attack_type", ""))).strip().lower()
    projectile_type = str(profile.get("projectile_type", payload.get("projectile_type", "none"))).strip().lower() or "none"
    max_range = max(1, int(profile.get("range", 1)))
    if attack_type in _RANGED_ATTACK_TYPES or projectile_type in _LOS_PROJECTILE_TYPES or max_range > 1:
        return {
            "attack_mode": "ranged",
            "geometry": projectile_type if projectile_type != "none" else "line",
            "max_range": max_range,
            "requires_line_of_sight": True,
            "projectile_type": projectile_type,
        }
    return {
        "attack_mode": "melee",
        "geometry": "contact",
        "max_range": 1,
        "requires_line_of_sight": False,
        "projectile_type": projectile_type,
    }


def _combat_attack_legality(
    context: "CampaignContext",
    attacker: Any,
    target: Any,
    *,
    weapon: "ItemStack" | None,
) -> dict[str, Any]:
    targeting = _weapon_attack_profile(weapon)
    legality = combat_targeting_check(
        [int(attacker.position.x), int(attacker.position.y)],
        [int(target.position.x), int(target.position.y)],
        max_range=int(targeting["max_range"]),
        map_data=getattr(context, "map_data", None),
        requires_line_of_sight=bool(targeting["requires_line_of_sight"]),
        adjacency_only=str(targeting["attack_mode"]) == "melee",
    )
    legality["targeting"] = targeting
    return legality


def _attack_blocked_message(target: Any, legality: dict[str, Any], *, combat_started: bool) -> str:
    target_name = getattr(target, "name", target.identity.display_name)
    prefix = "Combat begins. " if combat_started else ""
    if legality.get("reason") == "no_line_of_sight":
        return f"{prefix}You do not have a clear line of sight to {target_name}."
    max_range = int(legality.get("max_range", 1))
    distance = int(legality.get("distance", 0))
    attack_mode = str((legality.get("targeting") or {}).get("attack_mode", "attack"))
    return f"{prefix}{target_name} is out of range for your {attack_mode} attack ({distance} tiles vs {max_range})."


def _get_equipped_weapon(actor: "ActorRecord") -> Optional["ItemStack"]:
    equipment = getattr(actor, "equipment", None)
    if equipment is None:
        return None
    items = getattr(equipment, "slots", {}).get("main_hand")
    if items and isinstance(items, list):
        return items[0]
    return None


def _combat_spell_tick(context: "CampaignContext", combat_state: "CombatState") -> int:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None)
    base_tick = int(getattr(world_time, "game_tick", 0))
    return base_tick + (int(combat_state.round_number) * 10) + int(combat_state.current_turn_index)


def build_combat_payload(
    context: "CampaignContext",
    combat_state: "CombatState" | None,
) -> Optional[dict[str, Any]]:
    if combat_state is None or combat_state.phase == "resolved":
        return None
    actors = (context.kernel_runtime or {}).get("actors", {})
    active_actor_id = combat_state.active_combatant.actor_id if combat_state.combatants else ""
    combatants: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for entry in combat_state.combatants:
        actor = actors.get(entry.actor_id)
        if actor is None:
            continue
        payload = {
            "actor_id": entry.actor_id,
            "name": actor.name,
            "is_player": entry.is_player,
            "initiative": entry.initiative,
            "alive": bool(actor.alive),
            "hp": int(actor.stats.get("hp", 0)),
            "max_hp": int(actor.stats.get("max_hp", 1)),
            "position": [int(actor.position.x), int(actor.position.y)],
            "turn_resources": {
                "action_available": bool(entry.turn_resources.action),
                "bonus_action_available": bool(entry.turn_resources.bonus_action),
                "reaction_available": bool(entry.turn_resources.reaction),
                "movement_remaining": int(entry.turn_resources.movement),
                "speed": int(entry.turn_resources.max_movement),
            },
        }
        combatants.append(payload)
        if not entry.is_player:
            target_payload = {
                "actor_id": entry.actor_id,
                "name": actor.name,
                "alive": bool(actor.alive),
                "hp": int(actor.stats.get("hp", 0)),
                "max_hp": int(actor.stats.get("max_hp", 1)),
                "position": [int(actor.position.x), int(actor.position.y)],
                "called_shot_zones": _called_shot_zones(actor),
            }
            if active_actor_id == "player":
                player_actor = actors.get("player")
                if player_actor is not None:
                    legality = _combat_attack_legality(context, player_actor, actor, weapon=_get_equipped_weapon(player_actor))
                    target_payload.update(
                        {
                            "attackable": bool(legality["allowed"]),
                            "attack_blocked_reason": legality["reason"],
                            "distance": int(legality["distance"]),
                            "targeting": legality["targeting"],
                        }
                    )
            targets.append(target_payload)
    available_actions = list(_SUPPORTED_ACTIONS) if active_actor_id == "player" else []
    if active_actor_id == "player":
        active_actor = actors.get("player")
        active_entry = combat_state.active_combatant if combat_state.combatants else None
        if active_actor is not None and actor_can_cast_registry_spells(
            active_actor,
            current_tick=_combat_spell_tick(context, combat_state),
        ):
            available_actions.append("cast")
        if (
            active_actor is not None
            and active_entry is not None
            and bool(active_entry.turn_resources.action)
        ):
            from engine.api.gameplay_bridge import actor_has_usable_runtime_item

            if actor_has_usable_runtime_item(active_actor):
                available_actions.append("use_item")
    return {
        "phase": combat_state.phase,
        "round": int(combat_state.round_number),
        "turn_actor_id": active_actor_id,
        "combatants": combatants,
        "available_actions": available_actions,
        "move_options": _build_move_options(context, combat_state, actors),
        "targets": targets,
    }


__all__ = [
    "_DIRECTION_DELTAS",
    "_attack_blocked_message",
    "_combat_attack_legality",
    "_combat_spell_tick",
    "_get_equipped_weapon",
    "_movement_block_reason",
    "_movement_failure_message",
    "_passable_tile",
    "build_combat_payload",
]
