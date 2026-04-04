"""Combat command bridge for the campaign runtime."""
from __future__ import annotations

import logging
import re
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.api.kernel_adapter import advance_turn, begin_turn, check_combat_end, run_attack, start_fight
from engine.kernel.combat_engine import CombatState
from engine.kernel.combat_math import ability_modifier

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


def _handle_attack(
    context: "CampaignContext",
    actors: dict[str, Any],
    player: "ActorRecord",
    target_name: str,
) -> tuple[str, str, int]:
    target = _resolve_combat_target(actors, target_name)
    if target is None:
        return (f"No target '{target_name}' found to attack.", "combat", 0)
    if not getattr(target, "alive", True):
        return (f"{target.identity.display_name} is already dead.", "combat", 0)
    tick = int(context.campaign_state.get("campaign", {}).get("tick", 0))
    combat_state = _ensure_combat_state(context, actors, player, target, tick)
    state_ready = _ensure_player_turn(context, combat_state, actors, seed=tick)
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
        seed=tick,
    )
    narrative = _apply_attack_result(actors, attack_result)
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed=tick + 1)
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
    state_ready = _ensure_player_turn(context, combat_state, actors, seed=int(context.seed))
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    combat_state.active_combatant.turn_resources.action = False
    player.raw_payload["defensive_stance"] = True
    narrative = f"{player.name} takes a defensive stance."
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed=int(context.seed) + 17)
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
    tick = int(context.campaign_state.get("campaign", {}).get("tick", 0))
    state_ready = _ensure_player_turn(context, combat_state, actors, seed=tick)
    if state_ready["resolved"]:
        return (state_ready["summary"] or "Combat is already over.", "combat", 0)
    if state_ready["blocked"]:
        return (state_ready["summary"], "combat", 0)
    d20 = Random(tick).randint(1, 20)
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
    follow_up = _end_player_turn_and_resolve(context, combat_state, actors, seed=tick + 31)
    if follow_up:
        narrative = f"{narrative} {follow_up}".strip()
    return (narrative, "combat", 0)


def _end_player_turn_and_resolve(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    *,
    seed: int,
) -> str:
    if check_combat_end(combat_state, actors):
        combat_state.phase = "resolved"
        _store_combat_state(context, combat_state)
        return "Combat ends."
    advance_turn(combat_state)
    begin_turn(combat_state, actors)
    events = _resolve_non_player_turns(context, combat_state, actors, seed=seed)
    _store_combat_state(context, combat_state)
    return " ".join(event for event in events if event).strip()


def _ensure_player_turn(
    context: "CampaignContext",
    combat_state: CombatState,
    actors: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    messages = _resolve_non_player_turns(context, combat_state, actors, seed=seed)
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
    seed: int,
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
        target_id = _choose_ai_target_id(combat_state, actors, active)
        if not target_id:
            combat_state.phase = "resolved"
            break
        try:
            attack_result = run_attack(
                combat_state,
                actors,
                active.actor_id,
                target_id,
                weapon=_get_equipped_weapon(actor),
                seed=seed + step,
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


def _resolve_combat_target(actors: dict[str, Any], name: str) -> Optional["ActorRecord"]:
    lower = name.lower().strip()
    normalized = lower.replace(" ", "_")
    for actor_id, actor in actors.items():
        if actor_id == "player":
            continue
        actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower()
        if actor_type not in _VALID_TARGET_TYPES:
            continue
        display_name = str(getattr(getattr(actor, "identity", None), "display_name", "")).lower()
        if lower in display_name or normalized == actor_id.lower():
            return actor
    return None


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

    party_ids = [actor_id for actor_id in party_member_ids(context) if actor_id in actors]
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


def _choose_ai_target_id(combat_state: CombatState, actors: dict[str, Any], active_entry: Any) -> str:
    for entry in combat_state.combatants:
        if entry.actor_id == active_entry.actor_id or entry.is_player == active_entry.is_player:
            continue
        actor = actors.get(entry.actor_id)
        if actor is not None and getattr(actor, "alive", True):
            return entry.actor_id
    return ""


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


__all__ = ["build_combat_payload", "maybe_handle_combat_command"]
