"""Combat command bridge for the campaign runtime."""
from __future__ import annotations

import logging
import re
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.api.kernel_adapter import advance_turn, begin_turn, check_combat_end, run_attack, start_fight
from engine.api.campaign.actor_query import resolve_live_actor_query
from engine.kernel.combat_engine import CombatState
from engine.kernel.combat_math import ability_modifier
from engine.kernel.game_state import FORMATIONS, party_tactic_for_actor
from engine.map import TileType

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor import ActorRecord, ItemStack

logger = logging.getLogger(__name__)

_ATTACK_RE = re.compile(r"^attack\s+(.+)$", re.IGNORECASE)
_DEFEND_RE = re.compile(r"^defend$", re.IGNORECASE)
_FLEE_RE = re.compile(r"^flee$", re.IGNORECASE)
_VALID_TARGET_TYPES = {"npc", "creature", "monster", "animal"}


def maybe_handle_combat_command(context: "CampaignContext", command_text: str) -> Optional[tuple[str, str, int]]:
    text = command_text.strip()
    runtime = context.kernel_runtime or {}
    actors: dict[str, Any] = runtime.get("actors", {})
    player: Optional[ActorRecord] = actors.get("player")
    if player is None:
        return None
    match = _ATTACK_RE.match(text)
    if match:
        return _handle_attack(context, actors, player, match.group(1).strip())
    if _DEFEND_RE.match(text):
        return None if not context.in_combat() else _handle_defend(context, actors, player)
    if _FLEE_RE.match(text):
        return None if not context.in_combat() else _handle_flee(context, actors, player)
    return None


def handle_attack_target_id(
    context: "CampaignContext",
    target_actor_id: str,
) -> tuple[str, str, int]:
    runtime = context.kernel_runtime or {}
    actors: dict[str, Any] = runtime.get("actors", {})
    player: Optional[ActorRecord] = actors.get("player")
    if player is None:
        return ("No combatant is ready to act.", "combat", 0)
    return _handle_attack(context, actors, player, str(target_actor_id).strip())


def _handle_attack(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    resolved = resolve_live_actor_query(actors, target_name, include_player=False, actor_types=_VALID_TARGET_TYPES)
    if resolved.error:
        return (resolved.error, "combat", 0)
    target = resolved.actor
    if target is None:
        return (f"No target '{target_name}' found to attack.", "combat", 0)
    if not getattr(target, "alive", True):
        return (f"{target.identity.display_name} is already dead.", "combat", 0)
    combat_state = _ensure_combat_state(context, actors, player, target, _combat_seed(context, offset=1))
    state_ready = _ensure_player_turn(context, combat_state, actors)
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    attack_result = run_attack(
        combat_state,
        actors,
        player.identity.actor_id,
        target.identity.actor_id,
        weapon=_get_equipped_weapon(player),
        seed=_combat_seed(context, combat_state, offset=11),
    )
    narrative = _apply_attack_result(actors, attack_result)
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed_offset=17)
    if follow_up:
        narrative = f"{narrative} {follow_up}".strip()
    return (narrative, "combat", 0)


def _handle_defend(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
) -> tuple[str, str, int]:
    combat_state = _combat_state(context)
    if combat_state is None:
        return ("No active combat.", "combat", 0)
    state_ready = _ensure_player_turn(context, combat_state, actors)
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    combat_state.active_combatant.turn_resources.action = False
    player.raw_payload["defensive_stance"] = True
    narrative = f"{player.name} takes a defensive stance."
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed_offset=29)
    if follow_up:
        narrative = f"{narrative} {follow_up}".strip()
    return (narrative, "combat", 0)


def _handle_flee(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
) -> tuple[str, str, int]:
    combat_state = _combat_state(context)
    if combat_state is None:
        return ("No active combat.", "combat", 0)
    state_ready = _ensure_player_turn(context, combat_state, actors)
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    flee_seed = _combat_seed(context, combat_state, offset=23)
    d20 = Random(flee_seed).randint(1, 20)
    agi_mod = ability_modifier(int(player.stats.get("AGI", 10)))
    total = d20 + agi_mod
    dc = 10
    if total >= dc:
        player.raw_payload["fled_combat"] = True
        _clear_combat_state(context)
        return (
            f"{player.name} attempts to flee (d20={d20} + AGI {agi_mod:+d} = {total} vs DC {dc}) and escapes successfully!",
            "combat",
            0,
        )
    combat_state.active_combatant.turn_resources.action = False
    narrative = f"{player.name} attempts to flee (d20={d20} + AGI {agi_mod:+d} = {total} vs DC {dc}) but fails to escape!"
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed_offset=41)
    if follow_up:
        narrative = f"{narrative} {follow_up}".strip()
    return (narrative, "combat", 0)


def _end_player_turn_and_resolve(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    *,
    seed_offset: int,
) -> str:
    if check_combat_end(combat_state, actors):
        combat_state.phase = "resolved"
        _store_combat_state(context, combat_state)
        return "Combat ends."
    advance_turn(combat_state)
    begin_turn(combat_state, actors)
    events = _resolve_non_player_turns(context, combat_state, actors, seed_offset=seed_offset)
    _store_combat_state(context, combat_state)
    return " ".join(event for event in events if event).strip()


def _ensure_player_turn(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
) -> dict[str, Any]:
    messages = _resolve_non_player_turns(context, combat_state, actors, seed_offset=0)
    _store_combat_state(context, combat_state)
    active = combat_state.active_combatant if combat_state.combatants else None
    if combat_state.phase == "resolved" or check_combat_end(combat_state, actors):
        combat_state.phase = "resolved"
        _store_combat_state(context, combat_state)
        return {"resolved": True, "blocked": False, "summary": " ".join(messages).strip()}
    if active is None or active.actor_id != "player":
        summary = " ".join(messages).strip() or "It is not your turn yet."
        return {"resolved": False, "blocked": True, "summary": summary}
    if not active.turn_resources.action:
        begin_turn(combat_state, actors)
    return {"resolved": False, "blocked": False, "summary": " ".join(messages).strip()}


def _resolve_non_player_turns(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    *,
    seed_offset: int,
) -> list[str]:
    messages: list[str] = []
    max_steps = max(1, len(combat_state.combatants) * 4)
    for step in range(max_steps):
        if not combat_state.combatants or check_combat_end(combat_state, actors):
            combat_state.phase = "resolved"
            break
        active = combat_state.active_combatant
        actor = actors.get(active.actor_id)
        if actor is None or not getattr(actor, "alive", True):
            advance_turn(combat_state)
            begin_turn(combat_state, actors)
            continue
        if active.actor_id == "player":
            break
        target_id = _choose_companion_target_id(context, combat_state, actors, active)
        if not target_id:
            if active.is_player:
                tactic_mode = _companion_tactic_mode(context, active.actor_id)
                messages.append(
                    _resolve_companion_turn(
                        context,
                        combat_state,
                        actors,
                        active,
                        "",
                        seed=_combat_seed(context, combat_state, offset=seed_offset + (step * 37) + 3),
                        tactic_mode=tactic_mode,
                    )
                )
                if check_combat_end(combat_state, actors):
                    combat_state.phase = "resolved"
                    break
                advance_turn(combat_state)
                begin_turn(combat_state, actors)
                continue
            combat_state.phase = "resolved"
            break
        if active.is_player:
            tactic_mode = _companion_tactic_mode(context, active.actor_id)
            messages.append(
                _resolve_companion_turn(
                    context,
                    combat_state,
                    actors,
                    active,
                    target_id,
                    seed=_combat_seed(context, combat_state, offset=seed_offset + (step * 37) + 7),
                    tactic_mode=tactic_mode,
                )
            )
        else:
            try:
                attack_result = run_attack(
                    combat_state,
                    actors,
                    active.actor_id,
                    target_id,
                    weapon=_get_equipped_weapon(actor),
                    seed=_combat_seed(context, combat_state, offset=seed_offset + (step * 37) + 11),
                )
            except ValueError as exc:
                logger.debug("Combat auto-turn skipped for %s: %s", active.actor_id, exc)
                active.turn_resources.action = False
                attack_result = None
            if attack_result is not None:
                messages.append(_apply_attack_result(actors, attack_result))
        if check_combat_end(combat_state, actors):
            combat_state.phase = "resolved"
            break
        advance_turn(combat_state)
        begin_turn(combat_state, actors)
    return messages
def _store_combat_state(context: "CampaignContext", combat_state: CombatState) -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return
    if combat_state.phase == "resolved":
        game_state.raw_payload.pop("combat", None)
        if context.dm_context is not None:
            context.dm_context.scene_type_name = "exploration"
        return
    game_state.raw_payload["combat"] = combat_state.to_dict()
    if context.dm_context is not None:
        context.dm_context.scene_type_name = "combat"


def _clear_combat_state(context: "CampaignContext") -> None:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is not None:
        game_state.raw_payload.pop("combat", None)
    if context.dm_context is not None:
        context.dm_context.scene_type_name = "exploration"


def _combat_state(context: "CampaignContext") -> Optional[CombatState]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return None
    combat_payload = (getattr(game_state, "raw_payload", {}) or {}).get("combat")
    if not isinstance(combat_payload, dict) or not combat_payload.get("combatants"):
        return None
    return CombatState.from_dict(dict(combat_payload))


def _combat_seed(
    context: "CampaignContext",
    combat_state: CombatState | None = None,
    *,
    offset: int = 0,
) -> int:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None)
    base_tick = int(getattr(world_time, "game_tick", 0))
    round_number = int(getattr(combat_state, "round_number", 0) or 0)
    turn_index = int(getattr(combat_state, "current_turn_index", 0) or 0)
    return (
        (int(context.seed) * 1_000_003)
        + (base_tick * 1_009)
        + (round_number * 131)
        + (turn_index * 17)
        + int(offset)
    )


def _ensure_combat_state(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
    target: "ActorRecord",
    seed: int,
) -> CombatState:
    combat_state = _combat_state(context)
    if combat_state is not None:
        actor_ids = {entry.actor_id for entry in combat_state.combatants}
        if target.identity.actor_id in actor_ids and player.identity.actor_id in actor_ids:
            return combat_state
    from engine.api.campaign.party_bridge import party_member_ids

    party_ids = _projected_party_combatant_ids(context, actors)
    combatants: list[ActorRecord] = []
    seen: set[str] = set()
    for actor_id in party_ids + [target.identity.actor_id]:
        actor = actors.get(actor_id)
        if actor is None or not getattr(actor, "alive", True) or actor.identity.actor_id in seen:
            continue
        combatants.append(actor)
        seen.add(actor.identity.actor_id)
    combat_state = start_fight(combatants, seed=seed)
    for entry in combat_state.combatants:
        if entry.actor_id in party_ids:
            entry.is_player = True
    _set_active_turn(combat_state, player.identity.actor_id)
    return combat_state


def _set_active_turn(combat_state: CombatState, actor_id: str) -> None:
    for index, entry in enumerate(combat_state.combatants):
        if entry.actor_id == actor_id:
            combat_state.current_turn_index = index
            return


def _choose_ai_target_id(combat_state: CombatState, actors: dict[str, Any], active_entry: Any, *, context: "CampaignContext") -> str:
    del context
    active_actor = actors.get(active_entry.actor_id)
    if active_actor is None:
        return ""
    candidates: list[tuple[int, str]] = []
    for entry in combat_state.combatants:
        if entry.actor_id == active_entry.actor_id or entry.is_player == active_entry.is_player:
            continue
        actor = actors.get(entry.actor_id)
        if actor is None or not getattr(actor, "alive", True):
            continue
        candidates.append((_distance_between(active_actor, actor), entry.actor_id))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def _choose_companion_target_id(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    active_entry: Any,
) -> str:
    tactic_mode = _companion_tactic_mode(context, active_entry.actor_id)
    if tactic_mode == "aggressive":
        return _choose_aggressive_target_id(combat_state, actors, active_entry)
    if tactic_mode == "guard":
        return _choose_guard_target_id(context, combat_state, actors, active_entry)
    return _choose_ai_target_id(combat_state, actors, active_entry, context=context)


def _choose_aggressive_target_id(combat_state: CombatState, actors: dict[str, Any], active_entry: Any) -> str:
    active_actor = actors.get(active_entry.actor_id)
    if active_actor is None:
        return ""
    candidates: list[tuple[int, int, str]] = []
    for entry in combat_state.combatants:
        if entry.actor_id in {active_entry.actor_id, "player"} or entry.is_player == active_entry.is_player:
            continue
        actor = actors.get(entry.actor_id)
        if actor is None or not getattr(actor, "alive", True):
            continue
        distance = _distance_between(active_actor, actor)
        hp = int(getattr(actor, "hp", actor.stats.get("hp", 0)))
        candidates.append((distance, hp, entry.actor_id))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def _choose_guard_target_id(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    active_entry: Any,
) -> str:
    player = actors.get("player")
    if player is None:
        return ""
    candidates: list[tuple[int, int, str]] = []
    for entry in combat_state.combatants:
        if entry.actor_id == "player" or entry.is_player:
            continue
        actor = actors.get(entry.actor_id)
        if actor is None or not getattr(actor, "alive", True):
            continue
        distance = _distance_between(player, actor)
        if distance > 2:
            continue
        hp = int(getattr(actor, "hp", actor.stats.get("hp", 0)))
        candidates.append((distance, hp, entry.actor_id))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def _companion_tactic_mode(context: "CampaignContext", actor_id: str) -> str:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return "balanced"
    return party_tactic_for_actor(game_state, actor_id)


def _formation_anchor_position(context: "CampaignContext", actor_id: str) -> tuple[int, int]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return (int(context.position[0]), int(context.position[1]))
    party_ids = [str(item) for item in list(getattr(game_state, "party", [])) if str(item)]
    offsets = list(FORMATIONS.get(str(getattr(game_state, "formation", "wedge")), FORMATIONS["wedge"]))
    try:
        index = party_ids.index(actor_id)
    except ValueError:
        index = 0
    dx, dy = offsets[min(index, len(offsets) - 1)]
    return (int(context.position[0]) + int(dx), int(context.position[1]) + int(dy))


def _step_toward_position(context: "CampaignContext", actor: Any, goal: tuple[int, int]) -> tuple[int, int] | None:
    current = (int(actor.position.x), int(actor.position.y))
    candidates = [
        (current[0] + 1, current[1]),
        (current[0] - 1, current[1]),
        (current[0], current[1] + 1),
        (current[0], current[1] - 1),
    ]
    valid: list[tuple[int, int, int]] = []
    spatial_index = getattr(context, "spatial_index", None)
    current_distance = abs(goal[0] - current[0]) + abs(goal[1] - current[1])
    for x, y in candidates:
        if not _passable_tile(context, x, y):
            continue
        if spatial_index is not None and spatial_index.blocking_at(x, y) and (x, y) != current:
            continue
        distance = abs(goal[0] - x) + abs(goal[1] - y)
        if distance >= current_distance:
            continue
        valid.append((distance, y, x))
    if not valid:
        return None
    valid.sort()
    _, y, x = valid[0]
    return (x, y)


def _projected_party_combatant_ids(context: "CampaignContext", actors: dict[str, Any]) -> list[str]:
    from engine.api.campaign.party_bridge import party_member_ids

    projected: list[str] = []
    for actor_id in party_member_ids(context):
        if actor_id not in actors:
            continue
        if actor_id == "player":
            projected.append(actor_id)
            continue
        record = context.entities.get(actor_id)
        if not isinstance(record, dict):
            continue
        if str(record.get("attitude", "")) != "ally":
            continue
        projected.append(actor_id)
    return projected


def _distance_between(left: Any, right: Any) -> int:
    return abs(int(left.position.x) - int(right.position.x)) + abs(int(left.position.y) - int(right.position.y))


def _adjacent(left: Any, right: Any) -> bool:
    return _distance_between(left, right) == 1


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


def _move_actor_projection(context: "CampaignContext", actor_id: str, x: int, y: int, actors: dict[str, Any]) -> None:
    actor = actors.get(actor_id)
    if actor is not None:
        actor.position.x = int(x)
        actor.position.y = int(y)
    record = context.entities.get(actor_id)
    if not isinstance(record, dict):
        return
    record["position"] = [int(x), int(y)]
    entity_ref = record.get("entity_ref")
    spatial_index = getattr(context, "spatial_index", None)
    if entity_ref is not None and spatial_index is not None:
        if spatial_index.get_position(actor_id) is None:
            entity_ref.position = (int(x), int(y))
            spatial_index.add(entity_ref)
        else:
            spatial_index.move(entity_ref, int(x), int(y))


def _companion_step_toward(context: "CampaignContext", actor: Any, target: Any) -> tuple[int, int] | None:
    return _step_toward_position(context, actor, (int(target.position.x), int(target.position.y)))


def _resolve_companion_turn(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    active_entry: Any,
    target_id: str,
    *,
    seed: int,
    tactic_mode: str = "balanced",
) -> str:
    actor = actors.get(active_entry.actor_id)
    target = actors.get(target_id)
    if actor is None:
        active_entry.turn_resources.action = False
        return ""
    if target is None:
        if str(tactic_mode).lower() == "guard":
            anchor_position = _formation_anchor_position(context, active_entry.actor_id)
            next_step = _step_toward_position(context, actor, anchor_position)
            if next_step is not None:
                _move_actor_projection(context, active_entry.actor_id, next_step[0], next_step[1], actors)
                active_entry.turn_resources.movement = max(0, int(active_entry.turn_resources.movement) - 1)
                active_entry.turn_resources.action = False
                return f"{actor.name} falls back to guard the party."
        active_entry.turn_resources.action = False
        actor.raw_payload["defensive_stance"] = True
        return f"{actor.name} takes a defensive stance."
    if _adjacent(actor, target):
        try:
            attack_result = run_attack(
                combat_state,
                actors,
                active_entry.actor_id,
                target_id,
                weapon=_get_equipped_weapon(actor),
                seed=seed,
            )
        except ValueError as exc:
            logger.debug("Companion attack fallback for %s: %s", active_entry.actor_id, exc)
        else:
            return _apply_attack_result(actors, attack_result)
    if str(tactic_mode).lower() == "guard":
        player = actors.get("player")
        if player is not None and _distance_between(player, target) > 2:
            anchor_position = _formation_anchor_position(context, active_entry.actor_id)
            next_step = _step_toward_position(context, actor, anchor_position)
            if next_step is not None:
                _move_actor_projection(context, active_entry.actor_id, next_step[0], next_step[1], actors)
                active_entry.turn_resources.movement = max(0, int(active_entry.turn_resources.movement) - 1)
                active_entry.turn_resources.action = False
                return f"{actor.name} falls back to guard the party."
            active_entry.turn_resources.action = False
            actor.raw_payload["defensive_stance"] = True
            return f"{actor.name} holds position near the party."
    next_step = _companion_step_toward(context, actor, target)
    if next_step is not None:
        _move_actor_projection(context, active_entry.actor_id, next_step[0], next_step[1], actors)
        active_entry.turn_resources.movement = max(0, int(active_entry.turn_resources.movement) - 1)
        active_entry.turn_resources.action = False
        return f"{actor.name} advances toward {target.name}."
    active_entry.turn_resources.action = False
    actor.raw_payload["defensive_stance"] = True
    return f"{actor.name} takes a defensive stance."


def _apply_attack_result(actors: dict[str, Any], attack_result: Any) -> str:
    result = attack_result.combat_result
    attacker = actors.get(attack_result.attacker_id)
    defender = actors.get(attack_result.defender_id)
    attacker_name = getattr(attacker, "name", attack_result.attacker_id)
    defender_name = getattr(defender, "name", attack_result.defender_id)
    if not result.hit:
        return (
            f"{attacker_name} attacks {defender_name} but misses "
            f"(roll {result.attack_roll.total} vs AC {result.defense.total})."
        )
    strike = result.strike_resolution
    damage = strike.effective_damage if strike is not None else 0
    wound = strike.wound if strike is not None else None
    killed = False
    if defender is not None:
        defender.stats["hp"] = max(0, int(defender.stats.get("hp", 0)) - damage)
        if wound is not None:
            defender.raw_payload.setdefault("wounds", []).append(wound)
        if result.incapacitation == "dead" or int(defender.stats.get("hp", 0)) <= 0:
            defender.alive = False
            killed = True
    parts = [f"{attacker_name} attacks {defender_name} and hits for {damage} damage"]
    if wound is not None:
        parts.append(f"wounding the {wound.body_part_id}")
    if killed:
        parts.append(f"{defender_name} is slain")
    return ". ".join(parts) + "."


def build_combat_payload(context: "CampaignContext") -> Optional[dict[str, Any]]:
    combat_state = _combat_state(context)
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
            targets.append({
                "actor_id": entry.actor_id,
                "name": actor.name,
                "alive": bool(actor.alive),
                "hp": int(actor.stats.get("hp", 0)),
                "max_hp": int(actor.stats.get("max_hp", 1)),
            })
    return {
        "phase": combat_state.phase,
        "round": int(combat_state.round_number),
        "turn_actor_id": active_actor_id,
        "combatants": combatants,
        "available_actions": ["attack", "defend", "flee", "cast", "use_item"],
        "targets": targets,
    }


def _get_equipped_weapon(actor: "ActorRecord") -> Optional["ItemStack"]:
    equipment = getattr(actor, "equipment", None)
    if equipment is None:
        return None
    for slot_key in ("weapon", "weapon_1", "main_hand"):
        items = getattr(equipment, "slots", {}).get(slot_key)
        if items and isinstance(items, list):
            return items[0]
    return None


__all__ = ["build_combat_payload", "handle_attack_target_id", "maybe_handle_combat_command"]
