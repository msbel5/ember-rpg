"""Combat action handlers -- kernel-native edition.

All combat uses kernel CombatState / ActorRecord directly.
No engine.core imports. No legacy CombatManager.
"""
from __future__ import annotations

import copy, logging, random
from typing import Any, Optional

from engine.api.campaign.debug_trace import trace_event
from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.api.runtime_constants import HOSTILE_KEYWORDS, XP_REWARDS
from engine.kernel import item_stack_from_legacy_payload, resolve_strike
from engine.kernel.actor_records import ActorRecord
from engine.kernel.combat_engine import (
    CombatState, CombatantEntry, TurnResources,
    execute_attack, end_turn, is_combat_over, start_turn,
)
from engine.kernel.narrator import DMEvent, EventType, SceneType

logger = logging.getLogger(__name__)


def _get_combat(session: GameSession) -> Optional[CombatState]:
    """Read kernel CombatState from campaign_state."""
    return session.campaign_state.get("combat_state")

def _get_actors(session: GameSession) -> dict[str, ActorRecord]:
    """Read kernel combat actors dict from campaign_state."""
    return session.campaign_state.get("combat_actors", {})

def _kernel_in_combat(session: GameSession) -> bool:
    """True when a kernel combat encounter is active."""
    state = _get_combat(session)
    if state is None:
        return False
    return state.phase != "resolved" and not is_combat_over(state, _get_actors(session))

def _extract_damage(attack_result) -> int:
    """Effective damage from an AttackResult's CombatResult strike resolution."""
    sr = attack_result.combat_result.strike_resolution
    return int(sr.effective_damage) if sr is not None else 0

def _weapon_from_equipment(equipment: dict) -> Optional[Any]:
    """Build kernel ItemStack from equipment weapon payload."""
    wp = equipment.get("weapon")
    if not wp:
        return None
    damage = max(1, int(wp.get("damage", 4)))
    payload = {
        "id": wp.get("id"), "name": wp.get("name", "Weapon"),
        "value": int(wp.get("value", 0)), "weight": float(wp.get("weight", 0.0)),
        "item_type": "weapon", "damage_dice": wp.get("damage_dice") or f"1d{damage}",
        "damage_type": wp.get("damage_type", "slashing"), "ac_bonus": int(wp.get("ac_bonus", 0)),
    }
    return item_stack_from_legacy_payload(payload, index=0)

def _sync_entity_dead(session: GameSession, entity_id: str, hp: int, alive: bool) -> None:
    """Push HP/alive state into session.entities for one combatant."""
    if entity_id not in session.entities:
        return
    rec = session.entities[entity_id]
    rec["hp"], rec["alive"], rec["blocking"] = hp, alive, alive
    ref = rec.get("entity_ref")
    if ref is not None:
        ref.hp, ref.alive, ref.blocking = hp, alive, alive
        session.sync_entity_record(entity_id, ref)


class CombatActionsMixin:
    """Handlers for attack, spellcasting, flee, and combat bootstrap."""

    # ── Attack entry point ─────────────────────────────────────────────
    def _handle_attack(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        # Proximity gate for melee outside combat.
        if action.target and not _kernel_in_combat(session):
            prox_fail = self._check_entity_proximity(session, action.target, "attack_melee")
            if prox_fail:
                return prox_fail
        target_lower = (action.target or "").lower()
        in_active = _kernel_in_combat(session) and session.dm_context.scene_type == SceneType.COMBAT
        world_hit = self._find_entity_by_name(session, action.target) if action.target else None

        # Already in combat -- process player attack.
        if _kernel_in_combat(session):
            state, actors = _get_combat(session), _get_actors(session)
            aid = state.active_combatant.actor_id
            aname = (actors.get(aid) or ActorRecord.__new__(ActorRecord)).name if actors.get(aid) else aid
            if aid != "player":
                return ActionResult(narrative=f"It is {aname}'s turn.",
                    scene_type=session.dm_context.scene_type,
                    combat_state=self._combat_state(session), state_changes={"_skip_world_tick": True})
            tidx = self._find_target(state, action.target, exclude="player")
            if tidx is None:
                return ActionResult(narrative="No valid target found.", scene_type=session.dm_context.scene_type)
            return self._execute_attack_round(session, state, actors, tidx)

        # World entity target -- bootstrap combat.
        if not in_active and world_hit is not None:
            wid, wdata = world_hit
            enemy = self._character_from_world_entity(wid, wdata)
            if enemy is not None:
                self._start_combat(session, [enemy])
                sr = self._build_combat_start_result(session, [enemy])
                et = self._advance_combat_until_player_turn(session)
                if et:
                    sr.narrative = f"{sr.narrative}\n" + "\n".join(et)
                    sr.combat_state = self._combat_state(session)
                return sr

        # Absurd attack on non-hostile target.
        if not in_active and action.target and world_hit is None and not any(k in target_lower for k in HOSTILE_KEYWORDS):
            event = DMEvent(type=EventType.EXPLORATION, description=(
                f"The player tries to attack '{action.target}' which is not a hostile creature. "
                f"As DM, react humorously or creatively to this absurd action."),
                data={"raw_input": action.raw_input, "target": action.target, "action": "attack_nonhostile"})
            return ActionResult(narrative=self.dm.narrate(event, session.dm_context, self.llm),
                                scene_type=session.dm_context.scene_type)

        # No target or hostile keyword -- spawn random enemy.
        if not action.target or any(k in target_lower for k in HOSTILE_KEYWORDS):
            enemy = self._spawn_enemy(session.player.level, preferred_name=action.target)
            self._start_combat(session, [enemy])
            sr = self._build_combat_start_result(session, [enemy])
            et = self._advance_combat_until_player_turn(session)
            if et:
                sr.narrative = f"{sr.narrative}\n" + "\n".join(et)
                sr.combat_state = self._combat_state(session)
            return sr

        return ActionResult(narrative=f"There's no '{action.target}' here to attack.",
                            scene_type=session.dm_context.scene_type)

    # ── Core attack round (kernel-only) ────────────────────────────────
    def _execute_attack_round(self, session: GameSession, state: CombatState,
                              actors: dict[str, ActorRecord], target_idx: int):
        from engine.api.game_engine import ActionResult
        weapon = _weapon_from_equipment(session.equipment)
        dentry = state.combatants[target_idx]
        did = dentry.actor_id
        defender = actors.get(did)
        dname = defender.name if defender else did
        seed = state.round_number * 1000 + target_idx

        try:
            result = execute_attack(state, actors, "player", did, weapon=weapon, seed=seed)
        except ValueError as exc:
            return ActionResult(narrative=str(exc), scene_type=session.dm_context.scene_type,
                                combat_state=self._combat_state(session))

        cr = result.combat_result
        hit, crit = cr.hit, cr.critical_confirmed
        fumble = cr.attack_roll.is_natural_one and not hit
        damage = _extract_damage(result)
        killed = cr.incapacitation == "dead" or (defender is not None and not defender.alive)
        sc: dict[str, Any] = {}
        parts: list[str] = []

        # Hit-location annotation.
        hit_part, armor_red, mat_bonus = None, 0, ""
        if hit or crit:
            sr = cr.strike_resolution
            if sr:
                hit_part, armor_red = sr.hit_part_id, int(sr.armor_absorbed)
            raw_wp = dict(session.equipment.get("weapon") or {})
            aw = item_stack_from_legacy_payload(raw_wp, index=0) if raw_wp else None
            if aw and aw.material_id:
                mat_bonus = f" ({aw.material_id})"
            trace_event("combat_resolution",
                campaign_id=str(session.campaign_state.get("campaign_id", "")),
                attacker_id="player", defender_id=did,
                hit_part=hit_part or "unknown", armor_absorbed=armor_red,
                effective_damage=damage, defender_viable=defender.alive if defender else False)
            sc.update(hit_location=hit_part, armor_reduction=armor_red, effective_damage=damage)
            if sr:
                sc["kernel_strike"] = sr.to_dict()

        # Cinematic narrative.
        if defender:
            parts.append(self._build_combat_narrative(
                session, session.player.name, defender, hit=hit or crit,
                damage=damage, crit=crit, fumble=fumble))
            if hit_part and (hit or crit):
                arm = f" (armor absorbed {armor_red})" if armor_red > 0 else ""
                parts.append(f"[Hit: {hit_part}{mat_bonus}{arm}]")
        else:
            if crit:     parts.append(f"CRITICAL! {session.player.name} lands a devastating blow -- {damage} damage!")
            elif fumble:  parts.append(f"{session.player.name} stumbles -- the attack goes wide!")
            elif hit:     parts.append(f"{session.player.name} strikes -- hit! {damage} damage.")
            else:         parts.append(f"{session.player.name} swings but misses.")

        # Kill consequences.
        if killed:
            parts.append(self._build_death_narrative(session, dname))
            qevts = self._update_quest_progress_for_kill(session, dname)
            if qevts:
                sc.setdefault("world_events", []).extend(copy.deepcopy(qevts))
                for q in qevts:
                    parts.append(f"Quest complete: {q.get('title', q.get('quest_id','?'))}. "
                                 f"+{q.get('reward_gold',0)} gold, +{q.get('reward_xp',0)} XP.")
            # Guard reinforcements in towns.
            if defender:
                role = defender.raw_payload.get("role", "")
                loc = (session.dm_context.location or "").lower()
                if any(w in loc for w in ("town","village","city","square","market","tavern","inn")) \
                   and role in {"guard","militia","watchman"}:
                    for b in (self._spawn_guard_backup(session), self._spawn_guard_backup(session)):
                        actors[b.identity.actor_id] = b
                        state.combatants.append(CombatantEntry(
                            actor_id=b.identity.actor_id, initiative=10,
                            is_player=False, turn_resources=TurnResources()))
                    session.campaign_state["combat_actors"] = actors
                    parts.append("Nearby guards heard the commotion! Two more guards rush toward you, weapons drawn!")
            _sync_entity_dead(session, did, 0, False)

        self._sync_all_combat_world_state(session)
        # End player turn and advance enemies.
        if not is_combat_over(state, actors) and state.active_combatant.actor_id == "player":
            end_turn(state)
        parts.extend(self._advance_combat_until_player_turn(session))
        self._sync_all_combat_world_state(session)

        over = is_combat_over(state, actors)
        text = " ".join(parts)
        cs_dict = self._combat_state(session)
        xp_result = None
        if over:
            state.phase = "resolved"
            xp = XP_REWARDS.get(session.player.level, 100)
            if session.player.hp > 0:
                xp_result = self.progression.add_xp(session.player, xp)
                sc["xp_gained"] = xp
                if xp_result:
                    sc["level_up"] = xp_result.new_level
            ev = DMEvent(type=EventType.COMBAT_END, description=text,
                         data={"round": state.round_number, "phase": "resolved"})
            self.dm.transition(session.dm_context, SceneType.EXPLORATION)
            text = self.dm.narrate(ev, session.dm_context, self.llm)
            session.campaign_state.pop("combat_state", None)
            session.campaign_state.pop("combat_actors", None)

        return ActionResult(narrative=text, events=[cr.to_dict()], state_changes=sc,
                            scene_type=session.dm_context.scene_type,
                            combat_state=cs_dict, level_up=xp_result)

    # ── Spell casting (kernel-native) ──────────────────────────────────
    def _handle_spell(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        from engine.kernel.spells import begin_casting, resolve_cast
        caster_record = _get_kernel_player(session)
        if caster_record is None:
            return ActionResult(narrative="No casting ability available.",
                                scene_type=session.dm_context.scene_type)
        spell_name = str(action.spell_name or action.target or "").strip()
        if not spell_name:
            return ActionResult(narrative="What spell do you wish to cast?",
                                scene_type=session.dm_context.scene_type)
        spellbook = _find_spellbook_for_spell(caster_record, spell_name)
        if spellbook is None:
            return ActionResult(narrative=f"You don't know the spell '{spell_name}'.",
                                scene_type=session.dm_context.scene_type)
        spell_def = _lookup_spell_def(spell_name)
        if spell_def is None:
            return ActionResult(narrative=f"Spell '{spell_name}' is not in your repertoire.",
                                scene_type=session.dm_context.scene_type)
        # Bootstrap combat if needed.
        if not _kernel_in_combat(session):
            self._start_combat(session, [self._spawn_enemy(session.player.level)])
        state, actors = _get_combat(session), _get_actors(session)
        if state is None:
            return ActionResult(narrative="Combat failed to start.", scene_type=session.dm_context.scene_type)
        tidx = self._find_target(state, action.target, exclude="player")
        if tidx is None:
            return ActionResult(narrative="No valid target for the spell.", scene_type=session.dm_context.scene_type)
        te = state.combatants[tidx]
        ta = actors.get(te.actor_id)
        if ta is None:
            return ActionResult(narrative="Target has vanished.", scene_type=session.dm_context.scene_type)
        tick = int(session.campaign_state.get("game_tick", 0))
        ok, attempt, reason = begin_casting(caster_record, spellbook, spell_def, te.actor_id, None, tick)
        if not ok:
            return ActionResult(narrative=f"Cannot cast: {reason}.",
                                scene_type=session.dm_context.scene_type)
        cast_result = resolve_cast(attempt, caster_record, ta, random.randint(1, 100), tick)
        resisted = cast_result.get("resisted", False)
        effects = cast_result.get("effects_applied", [])
        if cast_result.get("slot_expended"):
            _expend_spell_slot(spellbook, spell_def)
        if resisted:
            narr = f"{session.player.name} casts {spell_def.label}, but {ta.name} resists the magic!"
        else:
            dmg = _estimate_spell_damage(ta, effects)
            ta.hp = max(0, getattr(ta, "hp", int(ta.stats.get("hp", 0))))
            killed = not ta.alive
            _sync_entity_dead(session, te.actor_id, ta.hp, ta.alive)
            narr = f"{session.player.name} casts {spell_def.label}!"
            if effects:
                narr += f" [{', '.join(effects)} applied to {ta.name}]"
            if dmg > 0:
                narr += f" [{dmg} damage]"
            if killed:
                narr += f" {ta.name} has been slain!"
        return ActionResult(narrative=narr,
                            events=[{"spell": spell_def.label, "resisted": resisted, "effects": effects}],
                            scene_type=session.dm_context.scene_type, combat_state=self._combat_state(session))

    # ── Flee ───────────────────────────────────────────────────────────
    def _handle_flee(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        if not _kernel_in_combat(session):
            return ActionResult(narrative="You're not in combat -- nothing to flee from.",
                                scene_type=session.dm_context.scene_type)
        state, actors = _get_combat(session), _get_actors(session)
        old_pos = tuple(session.position)
        oa: list[str] = []
        pa = actors.get("player")
        if pa and not pa.raw_payload.get("disengaged_until_turn_end", False):
            oa = self._opportunity_attack_messages(session, old_pos, (old_pos[0]+3, old_pos[1]+3))

        fc = self._roll_ability_check(session, "AGI", 10)
        if not fc.success:
            ev = DMEvent(type=EventType.COMBAT, description=(
                f"{session.player.name} tries to flee but stumbles! "
                f"(AGI check: {fc.roll}+{fc.modifier}={fc.total} vs DC 10 -- FAIL)"))
            narr = self.dm.narrate(ev, session.dm_context, self.llm)
            return ActionResult(narrative="\n".join(oa + [narr]) if oa else narr,
                                scene_type=session.dm_context.scene_type)

        state.phase = "resolved"
        session.campaign_state.pop("combat_state", None)
        session.campaign_state.pop("combat_actors", None)
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        ev = DMEvent(type=EventType.EXPLORATION, description=(
            f"{session.player.name} successfully flees from combat! "
            f"(AGI check: {fc.roll}+{fc.modifier}={fc.total} vs DC 10 -- PASS)"))
        narr = self.dm.narrate(ev, session.dm_context, self.llm)
        return ActionResult(narrative="\n".join(oa + [narr]) if oa else narr,
                            scene_type=session.dm_context.scene_type,
                            state_changes={"_skip_world_tick": True})

    # ── Disengage ──────────────────────────────────────────────────────
    def _handle_disengage(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        if not _kernel_in_combat(session):
            return ActionResult(narrative="You are not in combat.", scene_type=session.dm_context.scene_type)
        state, actors = _get_combat(session), _get_actors(session)
        aid = state.active_combatant.actor_id
        aa = actors.get(aid)
        aname = aa.name if aa else aid
        if aid != "player":
            return ActionResult(narrative=f"It is {aname}'s turn.",
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(session), state_changes={"_skip_world_tick": True})
        ae = state.active_combatant
        if not ae.turn_resources.action:
            return ActionResult(narrative="You have already used your action this turn.",
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(session), state_changes={"_skip_world_tick": True})
        ae.turn_resources.action = False
        pa = actors.get("player")
        if pa:
            pa.raw_payload["disengaged_until_turn_end"] = True
        end_turn(state)
        parts = ["You disengage and keep every hostile blade at bay as you retreat."]
        parts.extend(self._advance_combat_until_player_turn(session))
        if pa:
            pa.raw_payload.pop("disengaged_until_turn_end", None)
        return ActionResult(narrative="\n".join(parts), scene_type=session.dm_context.scene_type,
                            combat_state=self._combat_state(session), state_changes={"_skip_world_tick": True})


# ---------------------------------------------------------------------------
# Spell bridge helpers (kernel-native)
# ---------------------------------------------------------------------------

def _get_kernel_player(session: GameSession):
    """Extract player ActorRecord from kernel runtime."""
    return (session.campaign_state.get("kernel_runtime") or {}).get("actors", {}).get("player")


def _find_spellbook_for_spell(caster, spell_name: str):
    """Search all spellbooks on the caster for one that knows the spell."""
    from engine.kernel.spells import Spellbook
    spellbooks = caster.raw_payload.get("spellbooks", {})
    normalized = spell_name.lower().replace(" ", "_")
    for sb in spellbooks.values():
        if not isinstance(sb, Spellbook):
            continue
        for level, spells in sb.known_spells.items():
            if normalized in [s.lower() for s in spells]:
                return sb
    return None


def _lookup_spell_def(spell_name: str):
    """Look up a SpellDef from the spells registry by name or id."""
    from engine.data._shared import spells_registry
    from engine.kernel.spells import SpellDef
    registry = spells_registry()
    normalized = spell_name.lower().replace(" ", "_")
    # Try exact id match.
    if normalized in registry:
        return _spell_def_from_data(registry[normalized])
    # Try name field match.
    for raw in registry.values():
        if str(raw.get("name", "")).lower().replace(" ", "_") == normalized:
            return _spell_def_from_data(raw)
    return None


def _spell_def_from_data(raw: dict):
    """Build a kernel SpellDef from spells.json format."""
    from engine.kernel.spells import SpellDef
    effects = raw.get("effects", [])
    effect_ids = [str(e.get("type", "")) + "_" + str(e.get("damage_type", "")) for e in effects if isinstance(e, dict)]
    return SpellDef(
        spell_id=str(raw.get("id", raw.get("name", "unknown"))).lower().replace(" ", "_"),
        label=str(raw.get("name", "Unknown Spell")),
        spell_type=str(raw.get("spell_type", "wizard")),
        school=str(raw.get("school", "evocation")),
        level=int(raw.get("level", 1)),
        casting_time=int(raw.get("casting_time", 0)),
        range=int(raw.get("range", 30)),
        target_type=str(raw.get("target_type", "single")),
        hostile=str(raw.get("target_type", "single")) != "self",
        effect_def_ids=effect_ids,
    )


def _expend_spell_slot(spellbook, spell_def) -> None:
    """Expend a spell slot from the spellbook."""
    for slot in spellbook.slots.get(spell_def.level, []):
        if slot.memorized and not slot.expended:
            slot.expended = True
            return


def _estimate_spell_damage(target, effects_applied: list[str]) -> int:
    """Estimate damage dealt by checking target HP change from applied effects."""
    # Effects are applied inline by resolve_cast via apply_effect.
    # We can only estimate from the effect names — actual damage was already applied.
    return len(effects_applied) * 4  # Rough estimate; real damage is in effect system
