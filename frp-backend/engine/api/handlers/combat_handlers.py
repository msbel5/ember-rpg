"""Combat handler methods for GameEngine — mixin class."""
from __future__ import annotations

import copy
import random
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.item import Item, ItemType
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.api.game_session import GameSession
from engine.api.action_parser import ParsedAction
from engine.world.entity import Entity, EntityType
from engine.world.body_parts import BodyPartTracker, calculate_armor_reduction
from engine.world.materials import MATERIALS

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult

from engine.api.game_engine import XP_REWARDS


class CombatMixin:
    """All combat-related handler methods."""

    def _handle_attack(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        # Proximity check for attack (melee range)
        if action.target and not session.in_combat():
            prox_fail = self._check_entity_proximity(session, action.target, "attack_melee")
            if prox_fail:
                return prox_fail

        hostile_keywords = ["goblin", "orc", "bandit", "wolf", "skeleton", "zombie",
                            "enemy", "monster", "troll", "guard", "militia", "watchman",
                            "ogre", "dragon", "rat", "spider", "cultist", "thug"]
        target_lower = (action.target or "").lower()
        in_active_combat = session.in_combat() and session.dm_context.scene_type == SceneType.COMBAT
        found_world_target = self._find_entity_by_name(session, action.target) if action.target else None

        # If already in combat, target existing enemy instead of spawning new.
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
                return ActionResult(
                    narrative="No valid target found.",
                    scene_type=session.dm_context.scene_type,
                )
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

        if not in_active_combat and action.target and found_world_target is None and not any(kw in target_lower for kw in hostile_keywords):
            # Non-hostile target -> creative DM response
            target_name = action.target or "something"
            desc = (
                f"The player tries to attack '{target_name}' which is not a hostile creature. "
                f"As DM, react humorously or creatively to this absurd action. "
                f"Maybe the {target_name} 'fights back' in an absurd way, "
                f"maybe NPCs nearby react with laughter or alarm, or maybe something funny happens."
            )
            event = DMEvent(
                type=EventType.EXPLORATION,
                description=desc,
                data={
                    "raw_input": action.raw_input,
                    "target": action.target,
                    "action": "attack_nonhostile",
                },
            )
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
            return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

        # Spawn random enemy if no target specified (bare "attack") or target matches hostile keyword
        if not action.target or any(kw in target_lower for kw in hostile_keywords):
            enemy = self._spawn_enemy(session.player.level, preferred_name=action.target)
            self._start_combat(session, [enemy])
            start_result = self._build_combat_start_result(session, [enemy])
            enemy_turns = self._advance_combat_until_player_turn(session)
            if enemy_turns:
                start_result.narrative = f"{start_result.narrative}\n" + "\n".join(enemy_turns)
                start_result.combat_state = self._combat_state(session.combat)
            return start_result

        return ActionResult(
            narrative=f"There's no '{action.target}' here to attack.",
            scene_type=session.dm_context.scene_type,
        )

    def _execute_attack_round(self, session: GameSession, combat: CombatManager, target_idx: int) -> "ActionResult":
        """Execute the player's attack, then advance combat until the player's next turn."""
        from engine.api.game_engine import ActionResult
        weapon = self._build_weapon_item(session.equipment.get("weapon"))
        try:
            result = combat.attack(target_idx, weapon=weapon) if weapon else combat.attack(target_idx)
        except TypeError:
            result = combat.attack(target_idx)
        state_changes = {}
        narrative_parts = []

        # Identify target for narrative
        target_combatant = None
        if 0 <= target_idx < len(combat.combatants):
            target_combatant = combat.combatants[target_idx]

        hit = result.get("hit", False)
        raw_damage = result.get("damage", 0)
        damage = raw_damage
        crit = result.get("crit", False)
        fumble = result.get("fumble", False)

        # --- Body part + material system ---
        hit_part = None
        armor_reduction = 0
        material_bonus = ""
        if hit or crit:
            # Roll hit location
            # Import from game_engine module so test patches on that module work
            from engine.api.game_engine import roll_hit_location as _roll_hit_location
            hit_part = _roll_hit_location()
            equipped_armor = getattr(target_combatant.character, 'equipped_armor', []) if target_combatant else []
            armor_reduction = calculate_armor_reduction(hit_part, equipped_armor)
            # Apply weapon material bonus (default iron)
            weapon_material = getattr(session.player, 'weapon_material', 'iron')
            if weapon_material in MATERIALS:
                mat = MATERIALS[weapon_material]
                damage = max(1, int(raw_damage * mat.damage_mult))
                material_bonus = f" ({weapon_material})"
            # Reduce damage by armor
            effective_damage = max(0, damage - armor_reduction)
            if target_combatant is not None:
                corrected_hp = target_combatant.character.hp + raw_damage - effective_damage
                target_combatant.character.hp = max(0, min(target_combatant.character.max_hp, corrected_hp))
                if target_combatant.character.hp <= 0:
                    target_combatant.is_dead = True
                    result["killed"] = True
                else:
                    target_combatant.is_dead = False
                    result["killed"] = False
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
            # Apply body part damage to tracker (for the target if it's an enemy)
            state_changes["hit_location"] = hit_part
            state_changes["armor_reduction"] = armor_reduction
            state_changes["effective_damage"] = effective_damage
            # Update the result damage
            result["damage"] = effective_damage
            damage = effective_damage

        if target_combatant:
            hit_part_str = f" in the {hit_part}" if hit_part else ""
            narrative_parts.append(
                self._build_combat_narrative(
                    session, session.player.name, target_combatant.character,
                    hit=hit or crit, damage=damage, crit=crit, fumble=fumble
                )
            )
            if hit_part and (hit or crit):
                armor_str = f" (armor absorbed {armor_reduction})" if armor_reduction > 0 else ""
                narrative_parts.append(f"[Hit: {hit_part}{material_bonus}{armor_str}]")
        else:
            # Fallback if no target
            if crit:
                narrative_parts.append(f"CRITICAL! {session.player.name} lands a devastating blow — {damage} damage!")
            elif fumble:
                narrative_parts.append(f"{session.player.name} stumbles — the attack goes wide!")
            elif hit:
                narrative_parts.append(f"{session.player.name} strikes — hit! {damage} damage.")
            else:
                narrative_parts.append(f"{session.player.name} swings but misses.")

        # --- Bug 5: Guard backup in town ---
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
            killed_combatant = next(
                (c for c in combat.combatants if c.name == target_name), None
            )
            if killed_combatant:
                killed_char = killed_combatant.character
                role = getattr(killed_char, "role", "")
                location = (session.dm_context.location or "").lower()
                is_town = any(w in location for w in ["town", "village", "city", "square", "market", "tavern", "inn"])
                if is_town and role in ["guard", "militia", "watchman"]:
                    backup1 = self._spawn_guard_backup(session)
                    backup2 = self._spawn_guard_backup(session)
                    combat.combatants.append(
                        __import__("engine.core.combat", fromlist=["Combatant"]).Combatant(
                            character=backup1, initiative=10
                        )
                    )
                    combat.combatants.append(
                        __import__("engine.core.combat", fromlist=["Combatant"]).Combatant(
                            character=backup2, initiative=9
                        )
                    )
                    narrative_parts.append(
                        "Nearby guards heard the commotion! Two more guards rush toward you, weapons drawn!"
                    )

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

            event = DMEvent(
                type=EventType.COMBAT_END,
                description=narrative_text,
                data=combat.get_summary(),
            )
            self.dm.transition(session.dm_context, SceneType.EXPLORATION)
            # For combat end, do a final narrate to wrap up the battle
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
        else:
            # Individual parts are already LLM-narrated; return them directly
            narrative = narrative_text

        return ActionResult(
            narrative=narrative,
            events=[result],
            state_changes=state_changes,
            scene_type=session.dm_context.scene_type,
            combat_state=combat_state,
            level_up=xp_result,
        )

    def _build_combat_narrative(self, session, attacker_name, target, hit, damage, crit=False, fumble=False):
        """Generate LLM narrative for a player attack. Falls back to template on failure."""
        # Template fallback strings
        if crit:
            fallback = f"CRITICAL! {attacker_name} lands a devastating blow — {damage} damage!"
        elif fumble:
            fallback = f"{attacker_name} stumbles — the attack goes wide!"
        elif hit:
            fallback = f"{attacker_name} strikes — hit! {damage} damage."
        else:
            fallback = f"{attacker_name} swings but misses."
        if self.llm is None:
            return fallback
        try:
            if hit:
                desc = (
                    f"{attacker_name} attacks {target.name}. "
                    f"{'Critical hit! ' if crit else ''}Dealt {damage} damage. "
                    f"{target.name} has {target.hp} HP remaining. "
                    f"Describe the attack {'critically ' if crit else ''}hitting cinematically in 1-2 sentences."
                )
            else:
                desc = (
                    f"{attacker_name} attacks {target.name} but {'fumbles and ' if fumble else ''}misses. "
                    f"Describe the miss dramatically in 1 sentence."
                )
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "player_name": session.player.name,
                "target_name": target.name,
                "hit": hit,
                "damage": damage,
                "player_hp": session.player.hp,
                "player_max_hp": session.player.max_hp,
                "target_hp": target.hp,
                "action": "attack",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_enemy_combat_narrative(self, session, enemy, hit, damage):
        """Generate LLM narrative for an enemy counterattack. Falls back to template on failure."""
        if hit:
            fallback = f"{enemy.name} hits you for {damage} damage! (HP: {session.player.hp}/{session.player.max_hp})"
        else:
            fallback = f"{enemy.name} swings at you but misses!"
        if self.llm is None:
            return fallback
        try:
            desc = (
                f"{enemy.name} counterattacks {session.player.name}. "
                f"{'Hit for ' + str(damage) + ' damage' if hit else 'Miss'}. "
                f"Player has {session.player.hp}/{session.player.max_hp} HP. "
                f"Describe in 1 sentence."
            )
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "attacker_name": enemy.name,
                "player_name": session.player.name,
                "hit": hit,
                "damage": damage,
                "player_hp": session.player.hp,
                "player_max_hp": session.player.max_hp,
                "action": "enemy_attack",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_death_narrative(self, session, enemy_name):
        """Generate LLM narrative for enemy death. Falls back to template on failure."""
        fallback = f"{enemy_name} has been defeated!"
        if self.llm is None:
            return fallback
        try:
            desc = f"{enemy_name} has been defeated! Describe their death dramatically in 1-2 sentences."
            event = DMEvent(type=EventType.COMBAT, description=desc, data={
                "enemy_name": enemy_name,
                "action": "enemy_death",
            })
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_combat_start_result(self, session: GameSession, enemies: List[Character]) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        enemy_names = ", ".join(enemy.name for enemy in enemies) or "an enemy"
        active_name = session.combat.active_combatant.name if session.combat and not session.combat.combat_ended else session.player.name
        fallback = f"Combat begins against {enemy_names}. Initiative is rolled; {active_name} acts first."
        try:
            desc = (
                f"{session.player.name} enters combat with {enemy_names} in {session.dm_context.location}. "
                f"The fight starts now. Initiative is rolled and {active_name} has the first turn."
            )
            event = DMEvent(
                type=EventType.COMBAT_START,
                description=desc,
                data={
                    "player_name": session.player.name,
                    "enemy_name": enemy_names,
                    "location": session.dm_context.location,
                    "action": "combat_start",
                },
            )
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            narrative = fallback
        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(session.combat),
            state_changes={"_skip_world_tick": True},
        )

    def _spawn_guard_backup(self, session: GameSession) -> Character:
        """Spawn a backup town guard."""
        guard = Character(
            name="Town Guard",
            hp=12, max_hp=12,
            stats={"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 12},
        )
        guard.role = "guard"
        return guard

    def _handle_spell(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        if session.player.spell_points <= 0:
            return ActionResult(
                narrative="Your spell points are exhausted. You need to rest.",
                scene_type=session.dm_context.scene_type,
            )

        from engine.core.spell import Spell, TargetType
        from engine.core.effect import DamageEffect
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
            return ActionResult(
                narrative="No valid target for the spell.",
                scene_type=session.dm_context.scene_type,
            )

        result = combat.cast_spell(spell, target_idx)

        if "error" in result:
            # Spell failed -- return error narrative directly, skip LLM
            return ActionResult(
                narrative=f"The spell failed: {result['error']}",
                events=[result],
                scene_type=session.dm_context.scene_type,
                combat_state=self._combat_state(combat),
            )

        desc = f"{session.player.name} unleashes {spell.name}!"
        fallback_narrative = f"{session.player.name} unleashes {spell.name} with a surge of magical force!"

        event = DMEvent(type=EventType.ENCOUNTER, description=desc, data={
            "player_name": session.player.name,
            "spell_name": spell.name,
            "action": "cast_spell",
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        # If LLM returned a generic template without spell keywords, use specific fallback
        spell_keywords = ["spell", "magic", "missile", "force", "unleash", "cast", "arcane", "incantation", "surge"]
        if not any(kw in narrative.lower() for kw in spell_keywords):
            narrative = fallback_narrative

        return ActionResult(
            narrative=narrative,
            events=[result],
            scene_type=session.dm_context.scene_type,
            combat_state=self._combat_state(combat),
        )

    def _handle_flee(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Handle fleeing from combat with AGI check."""
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

        # AGI check to escape (DC 10)
        flee_check = self._roll_ability_check(session, "AGI", 10)

        if not flee_check.success:
            # Failed flee -- player stays in combat
            desc = (
                f"{session.player.name} tries to flee but stumbles! "
                f"(AGI check: {flee_check.roll}+{flee_check.modifier}={flee_check.total} vs DC 10 — FAIL)"
            )
            event = DMEvent(type=EventType.COMBAT, description=desc)
            narrative = self.dm.narrate(event, session.dm_context, self.llm)
            return ActionResult(
                narrative="\n".join(oa_messages + [narrative]) if oa_messages else narrative,
                scene_type=session.dm_context.scene_type,
            )

        # Success -- escape combat
        session.combat.combat_ended = True
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        desc = (
            f"{session.player.name} successfully flees from combat! "
            f"(AGI check: {flee_check.roll}+{flee_check.modifier}={flee_check.total} vs DC 10 — PASS)"
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative="\n".join(oa_messages + [narrative]) if oa_messages else narrative,
            scene_type=session.dm_context.scene_type,
            state_changes={"_skip_world_tick": True},
        )

    def _handle_disengage(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        if not session.combat:
            return ActionResult(
                narrative="You are not in combat.",
                scene_type=session.dm_context.scene_type,
            )
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

    def _start_combat(self, session: GameSession, enemies: List[Character]) -> None:
        """Initialize a combat encounter."""
        combatants = [session.player]
        adjacent_positions = [
            (session.position[0] + 1, session.position[1]),
            (session.position[0] - 1, session.position[1]),
            (session.position[0], session.position[1] + 1),
            (session.position[0], session.position[1] - 1),
        ]
        for enemy in enemies:
            entity_id = getattr(enemy, "_entity_id", None)
            if not entity_id:
                entity_id = f"combat_enemy_{len(session.entities) + 1}"
                enemy._entity_id = entity_id
            if entity_id not in session.entities:
                spawn_pos = list(session.position)
                for candidate in adjacent_positions:
                    if session.map_data is not None and not session.map_data.is_walkable(*candidate):
                        continue
                    blockers = session.spatial_index.at(*candidate) if session.spatial_index is not None else []
                    if any(getattr(blocker, "blocking", False) for blocker in blockers):
                        continue
                    spawn_pos = [candidate[0], candidate[1]]
                    break
                live_entity = Entity(
                    id=entity_id,
                    entity_type=EntityType.NPC,
                    name=enemy.name,
                    position=tuple(spawn_pos),
                    glyph="g",
                    color="red",
                    blocking=True,
                    hp=enemy.hp,
                    max_hp=enemy.max_hp,
                    disposition="hostile",
                    attitude="hostile",
                    alignment="CE",
                )
                if session.spatial_index is not None and session.spatial_index.get_position(entity_id) is None:
                    session.spatial_index.add(live_entity)
                session.entities[entity_id] = {
                    "name": enemy.name,
                    "type": "npc",
                    "position": list(spawn_pos),
                    "role": getattr(enemy, "role", "monster"),
                    "faction": "hostile",
                    "hp": enemy.hp,
                    "max_hp": enemy.max_hp,
                    "alive": True,
                    "blocking": True,
                    "attitude": "hostile",
                    "alignment": "CE",
                    "alignment_axes": {"law_chaos": -40, "good_evil": -40},
                    "entity_ref": live_entity,
                }
            combatants.append(enemy)
        session.combat = CombatManager(combatants, seed=random.randint(0, 9999))
        session.combat.start_turn()
        session.clear_conversation_target()
        self.dm.transition(session.dm_context, SceneType.COMBAT)

    def _spawn_enemy(self, player_level: int, preferred_name: Optional[str] = None) -> Character:
        """Spawn a level-appropriate enemy."""
        enemies = [
            Character(name="Goblin",   hp=8,  max_hp=8,
                      stats={"MIG": 8,  "AGI": 14, "END": 8,  "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Orc",      hp=15, max_hp=15,
                      stats={"MIG": 14, "AGI": 8,  "END": 12, "MND": 6, "INS": 8, "PRE": 6}),
            Character(name="Skeleton", hp=10, max_hp=10,
                      stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 4, "INS": 6, "PRE": 4}),
        ]
        target_lower = (preferred_name or "").strip().lower()
        if target_lower:
            for enemy in enemies:
                if target_lower in enemy.name.lower():
                    return enemy
        return random.choice(enemies)

    def _combat_state(self, combat: Optional[CombatManager]) -> Optional[dict]:
        """Serialize combat state for API response."""
        if combat is None:
            return None
        return {
            "round": combat.round,
            "active": combat.active_combatant.name if not combat.combat_ended else None,
            "ended": combat.combat_ended,
            "combatants": [
                {
                    "name": c.name,
                    "hp": c.character.hp,
                    "max_hp": c.character.max_hp,
                    "ap": c.ap,
                    "dead": c.is_dead,
                    "initiative": c.initiative,
                    "conditions": list(getattr(c.character, "conditions", [])),
                    "resources": {
                        "action_available": bool(getattr(c, "action_available", True)),
                        "bonus_action_available": bool(getattr(c, "bonus_action_available", True)),
                        "reaction_available": bool(getattr(c, "reaction_available", True)),
                        "movement_remaining": int(getattr(c, "movement_remaining", 0)),
                        "speed": int(getattr(c, "speed", 0)),
                        "disengaged_until_turn_end": bool(getattr(c, "disengaged_until_turn_end", False)),
                    },
                    "death_saves": {
                        "successes": int(getattr(c.character, "death_save_successes", 0)),
                        "failures": int(getattr(c.character, "death_save_failures", 0)),
                    },
                    "stable": bool(getattr(c.character, "is_stable", False)),
                }
                for c in combat.combatants
            ],
        }

    def _combat_player_index(self, combat: CombatManager, player_name: str) -> Optional[int]:
        return next((i for i, c in enumerate(combat.combatants) if c.name == player_name), None)

    def _combat_entity_id(self, combatant) -> Optional[str]:
        return getattr(combatant.character, "_entity_id", None)

    def _sync_combatant_world_state(self, session: GameSession, combatant) -> None:
        entity_id = self._combat_entity_id(combatant)
        if entity_id and entity_id in session.entities:
            session.entities[entity_id]["hp"] = combatant.character.hp
            session.entities[entity_id]["alive"] = not combatant.is_dead
            session.entities[entity_id]["blocking"] = not combatant.is_dead
            entity_ref = session.entities[entity_id].get("entity_ref")
            if entity_ref is not None:
                entity_ref.hp = combatant.character.hp
                entity_ref.alive = not combatant.is_dead
                entity_ref.blocking = not combatant.is_dead
                session.sync_entity_record(entity_id, entity_ref)

    def _sync_all_combat_world_state(self, session: GameSession, combat: Optional[CombatManager]) -> None:
        if combat is None:
            return
        for combatant in combat.combatants:
            self._sync_combatant_world_state(session, combatant)

    def _advance_combat_until_player_turn(self, session: GameSession) -> List[str]:
        messages: List[str] = []
        if session.combat is None:
            return messages
        combat = session.combat
        max_iterations = len(combat.combatants) * 2
        for _ in range(max_iterations):
            if combat.combat_ended:
                break
            if combat.active_combatant.name == session.player.name:
                break
            active = combat.active_combatant
            if active.is_dead:
                combat.end_turn()
                continue
            player_idx = self._combat_player_index(combat, session.player.name)
            if player_idx is not None:
                result = combat.attack(player_idx)
                hit = result.get("hit", False)
                damage = result.get("damage", 0)
                messages.append(self._build_enemy_combat_narrative(session, active.character, hit, damage))
            combat.end_turn()
        self._sync_all_combat_world_state(session, combat)
        return messages

    def _combatant_position(self, session: GameSession, combatant) -> tuple[int, int]:
        entity_id = self._combat_entity_id(combatant)
        if entity_id and entity_id in session.entities:
            pos = session.entities[entity_id].get("position", list(session.position))
            return (pos[0], pos[1])
        return tuple(session.position)

    def _opportunity_attack_messages(self, session: GameSession, old_pos: tuple[int, int], new_pos: tuple[int, int]) -> List[str]:
        if not session.combat:
            return []
        combat = session.combat
        player_idx = self._combat_player_index(combat, session.player.name)
        if player_idx is None:
            return []
        messages: List[str] = []
        for combatant in combat.combatants:
            if combatant.name == session.player.name or combatant.is_dead:
                continue
            if not getattr(combatant, "reaction_available", True):
                continue
            if getattr(combat.active_combatant, "disengaged_until_turn_end", False):
                continue
            cpos = self._combatant_position(session, combatant)
            old_adj = max(abs(old_pos[0] - cpos[0]), abs(old_pos[1] - cpos[1])) <= 1
            new_adj = max(abs(new_pos[0] - cpos[0]), abs(new_pos[1] - cpos[1])) <= 1
            if old_adj and not new_adj:
                combatant.reaction_available = False
                saved_turn = combat.current_turn
                combat.current_turn = combat.combatants.index(combatant)
                result = combat.attack(player_idx)
                combat.current_turn = saved_turn
                if result.get("hit"):
                    messages.append(f"{combatant.name} lashes out with an opportunity attack for {result.get('damage', 0)} damage.")
                else:
                    messages.append(f"{combatant.name} swings as you withdraw, but misses.")
        self._sync_all_combat_world_state(session, combat)
        return messages

    def _character_from_world_entity(self, entity_id: str, entity: Dict[str, Any]) -> Optional[Character]:
        entity_ref = entity.get("entity_ref")
        role = entity.get("role") or entity.get("job") or getattr(entity_ref, "job", None)
        if not role and entity.get("type") != "npc":
            return None

        stat_presets = {
            "guard": {"MIG": 12, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 11},
            "merchant": {"MIG": 8, "AGI": 10, "END": 10, "MND": 10, "INS": 12, "PRE": 13},
            "blacksmith": {"MIG": 14, "AGI": 10, "END": 12, "MND": 9, "INS": 11, "PRE": 10},
            "innkeeper": {"MIG": 10, "AGI": 9, "END": 11, "MND": 10, "INS": 12, "PRE": 12},
            "quest_giver": {"MIG": 9, "AGI": 9, "END": 10, "MND": 12, "INS": 12, "PRE": 13},
            "spy": {"MIG": 9, "AGI": 13, "END": 9, "MND": 11, "INS": 13, "PRE": 11},
        }
        hp = int(getattr(entity_ref, "hp", entity.get("hp", 10)))
        max_hp = int(getattr(entity_ref, "max_hp", entity.get("max_hp", hp)))
        character = Character(
            name=entity.get("name", entity_id),
            hp=hp,
            max_hp=max_hp,
            stats=stat_presets.get(role, {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10}),
        )
        character.role = role or "npc"
        character._entity_id = entity_id
        character.equipped_armor = ["shield"] if role == "guard" else []
        character.weapon_material = "iron" if role in {"guard", "blacksmith"} else "wood"
        return character

    def _build_weapon_item(self, item_data: Optional[Dict[str, Any]]) -> Optional[Item]:
        if not item_data:
            return None
        damage = max(1, int(item_data.get("damage", 4)))
        damage_dice = item_data.get("damage_dice") or f"1d{damage}"
        return Item(
            id=item_data.get("id"),
            name=item_data.get("name", "Weapon"),
            value=int(item_data.get("value", 0)),
            weight=float(item_data.get("weight", 0.0)),
            item_type=ItemType.WEAPON,
            damage_dice=damage_dice,
            damage_type=item_data.get("damage_type", "slashing"),
            armor_bonus=int(item_data.get("ac_bonus", 0)),
        )

    def _find_target(
        self,
        combat: CombatManager,
        target_name: Optional[str],
        exclude: str,
    ) -> Optional[int]:
        """Find target combatant index by name, or first living non-player."""
        if target_name:
            for i, c in enumerate(combat.combatants):
                if (target_name.lower() in c.name.lower()
                        and not c.is_dead
                        and c.name != exclude):
                    return i

        for i, c in enumerate(combat.combatants):
            if c.name != exclude and not c.is_dead:
                return i

        return None
