"""Combat action handlers."""
from __future__ import annotations

import copy
from typing import Any, Optional

from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.world.body_parts import BodyPartTracker, calculate_armor_reduction
from engine.world.materials import MATERIALS

from engine.api.runtime_constants import HOSTILE_KEYWORDS, XP_REWARDS


class CombatActionsMixin:
    """Focused handlers for attack, spellcasting, flee, and combat bootstrap."""

    def _handle_attack(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        if action.target and not session.in_combat():
            prox_fail = self._check_entity_proximity(session, action.target, "attack_melee")
            if prox_fail:
                return prox_fail

        target_lower = (action.target or "").lower()
        in_active_combat = session.in_combat() and session.dm_context.scene_type == SceneType.COMBAT
        found_world_target = self._find_entity_by_name(session, action.target) if action.target else None

        if session.in_combat() and session.combat:
            combat = session.combat
            if combat.active_combatant.name != session.player.name:
                return ActionResult(
                    narrative=f"It is {combat.active_combatant.name}'s turn.",
                    scene_type=session.dm_context.scene_type,
                    combat_state=self._combat_state(combat),
                    state_changes={"_skip_world_tick": True},
                )
            target_idx = self._find_target(combat, action.target, exclude=session.player.name)
            if target_idx is None:
                return ActionResult(narrative="No valid target found.", scene_type=session.dm_context.scene_type)
            return self._execute_attack_round(session, combat, target_idx)

        if not in_active_combat and found_world_target is not None:
            world_target_id, world_target = found_world_target
            enemy = self._character_from_world_entity(world_target_id, world_target)
            if enemy is not None:
                self._start_combat(session, [enemy])
                start_result = self._build_combat_start_result(session, [enemy])
                enemy_turns = self._advance_combat_until_player_turn(session)
                if enemy_turns:
                    start_result.narrative = f"{start_result.narrative}\n" + "\n".join(enemy_turns)
                    start_result.combat_state = self._combat_state(session.combat)
                return start_result

        if not in_active_combat and action.target and found_world_target is None and not any(keyword in target_lower for keyword in HOSTILE_KEYWORDS):
            target_name = action.target or "something"
            event = DMEvent(
                type=EventType.EXPLORATION,
                description=(
                    f"The player tries to attack '{target_name}' which is not a hostile creature. "
                    f"As DM, react humorously or creatively to this absurd action. "
                    f"Maybe the {target_name} 'fights back' in an absurd way, "
                    f"maybe NPCs nearby react with laughter or alarm, or maybe something funny happens."
                ),
                data={"raw_input": action.raw_input, "target": action.target, "action": "attack_nonhostile"},
            )
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
            return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

        if not action.target or any(keyword in target_lower for keyword in HOSTILE_KEYWORDS):
            enemy = self._spawn_enemy(session.player.level, preferred_name=action.target)
            self._start_combat(session, [enemy])
            start_result = self._build_combat_start_result(session, [enemy])
            enemy_turns = self._advance_combat_until_player_turn(session)
            if enemy_turns:
                start_result.narrative = f"{start_result.narrative}\n" + "\n".join(enemy_turns)
                start_result.combat_state = self._combat_state(session.combat)
            return start_result

        return ActionResult(narrative=f"There's no '{action.target}' here to attack.", scene_type=session.dm_context.scene_type)

    def _execute_attack_round(self, session: GameSession, combat: CombatManager, target_idx: int):
        from engine.api.game_engine import ActionResult

        weapon = self._build_weapon_item(session.equipment.get("weapon"))
        try:
            result = combat.attack(target_idx, weapon=weapon) if weapon else combat.attack(target_idx)
        except TypeError:
            result = combat.attack(target_idx)
        state_changes = {}
        narrative_parts = []

        target_combatant = combat.combatants[target_idx] if 0 <= target_idx < len(combat.combatants) else None
        hit = result.get("hit", False)
        raw_damage = result.get("damage", 0)
        damage = raw_damage
        crit = result.get("crit", False)
        fumble = result.get("fumble", False)

        hit_part = None
        armor_reduction = 0
        material_bonus = ""
        if hit or crit:
            from engine.api.game_engine import roll_hit_location as _roll_hit_location

            hit_part = _roll_hit_location()
            equipped_armor = getattr(target_combatant.character, "equipped_armor", []) if target_combatant else []
            armor_reduction = calculate_armor_reduction(hit_part, equipped_armor)
            weapon_material = getattr(session.player, "weapon_material", "iron")
            if weapon_material in MATERIALS:
                material = MATERIALS[weapon_material]
                damage = max(1, int(raw_damage * material.damage_mult))
                material_bonus = f" ({weapon_material})"
            effective_damage = max(0, damage - armor_reduction)
            if target_combatant is not None:
                corrected_hp = target_combatant.character.hp + raw_damage - effective_damage
                target_combatant.character.hp = max(0, min(target_combatant.character.max_hp, corrected_hp))
                target_combatant.is_dead = target_combatant.character.hp <= 0
                result["killed"] = target_combatant.is_dead
                entity_id = getattr(target_combatant.character, "_entity_id", None)
                if entity_id and entity_id in session.entities:
                    entity_body = session.entities[entity_id].get("body")
                    if isinstance(entity_body, BodyPartTracker) and hit_part:
                        entity_body.apply_damage(hit_part, effective_damage)
                    session.entities[entity_id]["hp"] = target_combatant.character.hp
                    session.entities[entity_id]["alive"] = not target_combatant.is_dead
                    session.entities[entity_id]["blocking"] = not target_combatant.is_dead
                    entity_ref = session.entities[entity_id].get("entity_ref")
                    if entity_ref is not None:
                        entity_ref.hp = target_combatant.character.hp
                        entity_ref.alive = not target_combatant.is_dead
                        entity_ref.blocking = not target_combatant.is_dead
                        if isinstance(getattr(entity_ref, "body", None), BodyPartTracker) and entity_ref.body is not entity_body and hit_part:
                            entity_ref.body.apply_damage(hit_part, effective_damage)
                        session.sync_entity_record(entity_id, entity_ref)
            state_changes["hit_location"] = hit_part
            state_changes["armor_reduction"] = armor_reduction
            state_changes["effective_damage"] = effective_damage
            result["damage"] = effective_damage
            damage = effective_damage

        if target_combatant:
            narrative_parts.append(
                self._build_combat_narrative(
                    session,
                    session.player.name,
                    target_combatant.character,
                    hit=hit or crit,
                    damage=damage,
                    crit=crit,
                    fumble=fumble,
                )
            )
            if hit_part and (hit or crit):
                armor_str = f" (armor absorbed {armor_reduction})" if armor_reduction > 0 else ""
                narrative_parts.append(f"[Hit: {hit_part}{material_bonus}{armor_str}]")
        else:
            if crit:
                narrative_parts.append(f"CRITICAL! {session.player.name} lands a devastating blow — {damage} damage!")
            elif fumble:
                narrative_parts.append(f"{session.player.name} stumbles — the attack goes wide!")
            elif hit:
                narrative_parts.append(f"{session.player.name} strikes — hit! {damage} damage.")
            else:
                narrative_parts.append(f"{session.player.name} swings but misses.")

        if result.get("killed"):
            target_name = result.get("target", "")
            narrative_parts.append(self._build_death_narrative(session, target_name or "the enemy"))
            quest_events = self._update_quest_progress_for_kill(session, target_name or "")
            if quest_events:
                state_changes.setdefault("world_events", []).extend(copy.deepcopy(quest_events))
                for event in quest_events:
                    narrative_parts.append(
                        f"Quest complete: {event.get('title', event.get('quest_id', 'Unknown quest'))}. "
                        f"+{event.get('reward_gold', 0)} gold, +{event.get('reward_xp', 0)} XP."
                    )
            killed_combatant = next((combatant for combatant in combat.combatants if combatant.name == target_name), None)
            if killed_combatant:
                killed_char = killed_combatant.character
                role = getattr(killed_char, "role", "")
                location = (session.dm_context.location or "").lower()
                is_town = any(word in location for word in ["town", "village", "city", "square", "market", "tavern", "inn"])
                if is_town and role in ["guard", "militia", "watchman"]:
                    backup1 = self._spawn_guard_backup(session)
                    backup2 = self._spawn_guard_backup(session)
                    combat.combatants.append(__import__("engine.core.combat", fromlist=["Combatant"]).Combatant(character=backup1, initiative=10))
                    combat.combatants.append(__import__("engine.core.combat", fromlist=["Combatant"]).Combatant(character=backup2, initiative=9))
                    narrative_parts.append("Nearby guards heard the commotion! Two more guards rush toward you, weapons drawn!")

        self._sync_all_combat_world_state(session, combat)
        if not combat.combat_ended and combat.active_combatant.name == session.player.name:
            combat.end_turn()
        narrative_parts.extend(self._advance_combat_until_player_turn(session))
        self._sync_all_combat_world_state(session, combat)

        narrative_text = " ".join(narrative_parts)
        combat_state = self._combat_state(combat)
        xp_result = None
        if combat.combat_ended:
            xp = XP_REWARDS.get(session.player.level, 100)
            if session.player.hp > 0:
                xp_result = self.progression.add_xp(session.player, xp)
                state_changes["xp_gained"] = xp
                if xp_result:
                    state_changes["level_up"] = xp_result.new_level

            event = DMEvent(type=EventType.COMBAT_END, description=narrative_text, data=combat.get_summary())
            self.dm.transition(session.dm_context, SceneType.EXPLORATION)
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
        else:
            narrative = narrative_text

        return ActionResult(
            narrative=narrative,
            events=[result],
            state_changes=state_changes,
            scene_type=session.dm_context.scene_type,
            combat_state=combat_state,
            level_up=xp_result,
        )

    def _handle_spell(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult
        from engine.core.effect import DamageEffect
        from engine.core.spell import Spell, TargetType

        if session.player.spell_points <= 0:
            return ActionResult(
                narrative="Your spell points are exhausted. You need to rest.",
                scene_type=session.dm_context.scene_type,
            )

        spell = Spell(
            name="Magic Missile",
            cost=2,
            range=120,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="2d4+2", damage_type="force")],
        )
        if not session.in_combat():
            enemy = self._spawn_enemy(session.player.level)
            self._start_combat(session, [enemy])

        combat = session.combat
        target_idx = self._find_target(combat, action.target, exclude=session.player.name)
        if target_idx is None:
            return ActionResult(narrative="No valid target for the spell.", scene_type=session.dm_context.scene_type)

        result = combat.cast_spell(spell, target_idx)
        if "error" in result:
            return ActionResult(
                narrative=f"The spell failed: {result['error']}",
                events=[result],
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(combat),
            )

        event = DMEvent(
            type=EventType.ENCOUNTER,
            description=f"{session.player.name} unleashes {spell.name}!",
            data={"player_name": session.player.name, "spell_name": spell.name, "action": "cast_spell"},
        )
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        spell_keywords = ["spell", "magic", "missile", "force", "unleash", "cast", "arcane", "incantation", "surge"]
        if not any(keyword in narrative.lower() for keyword in spell_keywords):
            narrative = f"{session.player.name} unleashes {spell.name} with a surge of magical force!"

        return ActionResult(
            narrative=narrative,
            events=[result],
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(combat),
        )

    def _handle_flee(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        if not session.combat:
            return ActionResult(
                narrative="You're not in combat — nothing to flee from.",
                scene_type=session.dm_context.scene_type,
            )

        old_pos = tuple(session.position)
        oa_messages = []
        if not session.combat.active_combatant.disengaged_until_turn_end:
            oa_messages = self._opportunity_attack_messages(session, old_pos, (session.position[0] + 3, session.position[1] + 3))

        flee_check = self._roll_ability_check(session, "AGI", 10)
        if not flee_check.success:
            event = DMEvent(
                type=EventType.COMBAT,
                description=(
                    f"{session.player.name} tries to flee but stumbles! "
                    f"(AGI check: {flee_check.roll}+{flee_check.modifier}={flee_check.total} vs DC 10 — FAIL)"
                ),
            )
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
            return ActionResult(
                narrative="\n".join(oa_messages + [narrative]) if oa_messages else narrative,
                scene_type=session.dm_context.scene_type,
            )

        session.combat.combat_ended = True
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        event = DMEvent(
            type=EventType.EXPLORATION,
            description=(
                f"{session.player.name} successfully flees from combat! "
                f"(AGI check: {flee_check.roll}+{flee_check.modifier}={flee_check.total} vs DC 10 — PASS)"
            ),
        )
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative="\n".join(oa_messages + [narrative]) if oa_messages else narrative,
            scene_type=session.dm_context.scene_type,
            state_changes={"_skip_world_tick": True},
        )

    def _handle_disengage(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        if not session.combat:
            return ActionResult(narrative="You are not in combat.", scene_type=session.dm_context.scene_type)
        if session.combat.active_combatant.name != session.player.name:
            return ActionResult(
                narrative=f"It is {session.combat.active_combatant.name}'s turn.",
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(session.combat),
                state_changes={"_skip_world_tick": True},
            )
        result = session.combat.disengage()
        if result.get("error"):
            return ActionResult(
                narrative=result["error"],
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(session.combat),
                state_changes={"_skip_world_tick": True},
            )
        session.combat.end_turn()
        narrative_parts = ["You disengage and keep every hostile blade at bay as you retreat."]
        narrative_parts.extend(self._advance_combat_until_player_turn(session))
        return ActionResult(
            narrative="\n".join(narrative_parts),
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(session.combat),
            state_changes={"_skip_world_tick": True},
        )
