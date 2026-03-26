"""Resource gathering and system handler methods for GameEngine — mixin class."""
from __future__ import annotations

import random
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.api.game_session import GameSession
from engine.api.action_parser import ParsedAction
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.world.skill_checks import roll_check

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult


class ResourceMixin:
    """Resource gathering (rest, fish, mine, chop, read, steal) and save/load handlers."""

    def _handle_rest(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        return self._handle_short_rest(session, action)

    def _handle_short_rest(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        if session.in_combat():
            return ActionResult(
                narrative="You cannot rest in the middle of a fight!",
                scene_type=session.dm_context.scene_type,
            )

        total_healed = 0
        end_mod = session.player.stat_modifier("END")
        spent_dice = 0
        while session.player.hp < session.player.max_hp and session.player.hit_dice_remaining > 0:
            roll = random.randint(1, session.player.hit_die_size)
            heal = max(1, roll + end_mod)
            session.player.hp = min(session.player.max_hp, session.player.hp + heal)
            total_healed += heal
            session.player.hit_dice_remaining -= 1
            spent_dice += 1
        session.player.spell_points = session.player.max_spell_points
        for part in session.body_tracker.current_hp:
            session.body_tracker.heal(part, max(1, session.body_tracker.max_hp[part] // 6))

        desc = f"{session.player.name} takes a short rest and recovers {total_healed} HP using {spent_dice} hit dice."
        event = DMEvent(type=EventType.REST, description=desc)
        self.dm.transition(session.dm_context, SceneType.REST)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)

        return ActionResult(
            narrative=narrative,
            state_changes={
                "hp_restored": total_healed,
                "hit_dice_spent": spent_dice,
                "_world_minutes": 60,
            },
            scene_type=session.dm_context.scene_type,
        )

    def _handle_long_rest(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        if session.in_combat():
            return ActionResult(
                narrative="You cannot sleep soundly with blades drawn.",
                scene_type=session.dm_context.scene_type,
            )
        current_hour = self._current_game_hour(session)
        last_rest = getattr(session.player, "last_long_rest_hour", None)
        if last_rest is not None and (current_hour - float(last_rest)) < 24.0:
            remaining = max(0, int(round(24.0 - (current_hour - float(last_rest)))))
            return ActionResult(
                narrative=f"You are not ready for another full long rest yet. Try again in about {remaining} more hours.",
                scene_type=session.dm_context.scene_type,
            )
        session.player.hp = session.player.max_hp
        session.player.spell_points = session.player.max_spell_points
        restore = max(1, session.player.hit_dice_total // 2)
        session.player.hit_dice_remaining = min(session.player.hit_dice_total, session.player.hit_dice_remaining + restore)
        session.player.exhaustion_level = max(0, int(session.player.exhaustion_level) - 1)
        session.player.last_long_rest_hour = current_hour + 8.0
        for part in session.body_tracker.current_hp:
            session.body_tracker.heal(part, session.body_tracker.max_hp[part])
        desc = f"{session.player.name} settles in for a long rest and wakes fully restored."
        event = DMEvent(type=EventType.REST, description=desc)
        self.dm.transition(session.dm_context, SceneType.REST)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        self.dm.transition(session.dm_context, SceneType.EXPLORATION)
        return ActionResult(
            narrative=narrative,
            state_changes={
                "hp_restored": session.player.max_hp,
                "hit_dice_restored": restore,
                "exhaustion_level": session.player.exhaustion_level,
                "_world_minutes": 480,
            },
            scene_type=session.dm_context.scene_type,
        )

    def _handle_fish(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Fish with INS check. Requires fishing rod."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "fish")
        if ap_fail:
            return ap_fail

        has_rod = any(
            "fishing" in item.get("id", "").lower() or "fishing" in item.get("name", "").lower()
            or "rod" in item.get("id", "").lower()
            for item in session.inventory
        )
        if not has_rod:
            return ActionResult(
                narrative="You need a fishing rod to fish!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 12
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            dropped = not self._add_or_drop_item(session, {"id": "raw_fish", "name": "Raw Fish", "qty": 1})
            if check_result.critical == "success":
                narrative = "You feel a strong tug and pull out two beautiful fish!"
                dropped = (not self._add_or_drop_item(session, {"id": "raw_fish", "name": "Raw Fish", "qty": 1})) or dropped
            else:
                narrative = "After a patient wait, you catch a fine fish!"
            if dropped:
                narrative += " You have no room for the catch, so it flops onto the ground at your feet."
        else:
            narrative = "You wait patiently, but the fish aren't biting today."

        desc = f"{session.player.name} goes fishing."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "fish", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_mine(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Mine ore with MIG check. Requires pickaxe."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "mine")
        if ap_fail:
            return ap_fail

        has_pickaxe = any(
            "pickaxe" in item.get("id", "").lower() or "pickaxe" in item.get("name", "").lower()
            or "pick" in item.get("id", "").lower()
            for item in session.inventory
        )
        if not has_pickaxe:
            return ActionResult(
                narrative="You need a pickaxe to mine!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 12
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            dropped = not self._add_or_drop_item(session, {"id": "iron_ore", "name": "Iron Ore", "qty": 1})
            if check_result.critical == "success":
                narrative = "You strike a rich vein and extract two chunks of quality ore!"
                dropped = (not self._add_or_drop_item(session, {"id": "iron_ore", "name": "Iron Ore", "qty": 1})) or dropped
            else:
                narrative = "You chip away at the rock and extract some usable ore."
            if dropped:
                narrative += " You cannot carry the ore, so it clatters to the ground."
        else:
            narrative = "You swing your pickaxe but only break off worthless rubble."

        desc = f"{session.player.name} mines for ore."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "mine", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_chop(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Chop a tree for wood with MIG check. Requires axe."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "chop")
        if ap_fail:
            return ap_fail

        target = action.target or "a tree"

        has_axe = any(
            "axe" in item.get("id", "").lower() or "axe" in item.get("name", "").lower()
            for item in session.inventory
        )
        if not has_axe:
            return ActionResult(
                narrative="You need an axe to chop wood!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 10
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            dropped = not self._add_or_drop_item(session, {"id": "wood_plank", "name": "Wood Plank", "qty": 1})
            if check_result.critical == "success":
                narrative = f"You fell {target} with powerful strokes, yielding plenty of timber!"
                dropped = (not self._add_or_drop_item(session, {"id": "wood_plank", "name": "Wood Plank", "qty": 1})) or dropped
            else:
                narrative = f"You chop {target} into usable planks."
            if dropped:
                narrative += " You have no room for the timber, so it falls nearby."
        else:
            narrative = f"You hack at {target} but can't fell it properly. No usable wood."

        desc = f"{session.player.name} chops {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "chop", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_read_item(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Read a book, scroll, sign, or other text."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "read")
        if ap_fail:
            return ap_fail

        target = action.target or "the text"
        desc = f"{session.player.name} carefully reads {target}, studying its contents."
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name, "action": "read", "target": target,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=dm_narrative, scene_type=session.dm_context.scene_type)

    def _handle_steal(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Attempt to steal from an NPC using contested check."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "steal")
        if ap_fail:
            return ap_fail

        target = action.target or "someone"
        prox_fail = self._check_entity_proximity(session, target, "steal")
        if prox_fail:
            return prox_fail

        found = self._find_entity_by_name(session, target)
        npc_ins = 12
        if found:
            _, entity = found
            target = entity.get("name", target)

        # Contested check: player AGI vs NPC INS
        result_a, result_b, winner = self._contested_agi_check(session, npc_ins)
        check_text = self._format_skill_check(result_a, "AGI", result_b.total)

        if winner == "a":
            if result_a.critical == "success":
                narrative = f"With incredible sleight of hand, you deftly steal something valuable from {target}!"
            else:
                narrative = f"Your nimble fingers slip into {target}'s belongings unnoticed."
            self._apply_alignment_shift(session, law_delta=-10, good_delta=-5)
        else:
            if result_a.critical == "failure":
                narrative = f"{target} catches your hand! They shout for the guards!"
            else:
                narrative = f"{target} notices your attempt and pulls away suspiciously."
            if found:
                entity_id, entity = found
                self._set_entity_attitude(session, entity_id, "hostile")
                for witness_id, witness in session.entities.items():
                    if witness_id == entity_id:
                        continue
                    witness_pos = witness.get("position", [0, 0])
                    if max(abs(session.position[0] - witness_pos[0]), abs(session.position[1] - witness_pos[1])) <= 2:
                        if witness.get("role") == "guard":
                            self._set_entity_attitude(session, witness_id, "hostile")
            self._apply_alignment_shift(session, law_delta=-12, good_delta=-8)

        desc = f"{session.player.name} attempts to steal from {target}. {'Success' if winner == 'a' else 'Failure'}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "steal", "target": target,
            "success": winner == "a",
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    # --- Save/Load handlers ---

    def _handle_save_game(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        slot_name = (action.target or "").strip() or (
            session.last_save_slot
            if getattr(session, "last_save_slot", None) and not str(session.last_save_slot).startswith("autosave_")
            else "quicksave"
        )
        try:
            self.save_system.save_game(session, slot_name, player_name=session.player.name)
        except Exception as exc:
            return ActionResult(
                narrative=f"Save failed for slot '{slot_name}': {exc}",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        return ActionResult(
            narrative=f"Game saved to '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"save_slot": slot_name, "_skip_world_tick": True},
        )

    def _handle_load_game(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        slot_name = (action.target or "").strip() or (
            session.last_save_slot
            if getattr(session, "last_save_slot", None) and not str(session.last_save_slot).startswith("autosave_")
            else "quicksave"
        )
        try:
            loaded = self.save_system.load_game(slot_name, strict=True)
        except FileNotFoundError:
            return ActionResult(
                narrative=f"No save slot named '{slot_name}' exists.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        except Exception as exc:
            return ActionResult(
                narrative=f"Could not load '{slot_name}': {exc}",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )

        session.replace_with(loaded, preserve_session_id=True)
        session.last_save_slot = slot_name
        return ActionResult(
            narrative=f"Loaded save slot '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"save_slot": slot_name, "_skip_world_tick": True},
        )

    def _handle_list_saves(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        saves = self.save_system.list_saves()
        if not saves:
            text = "No save slots found."
        else:
            lines = ["Save slots:"]
            for save in saves[:12]:
                lines.append(
                    f"- {save['slot_name']} | {save.get('player_name', 'Unknown')} Lv{save.get('player_level', 1)} | "
                    f"{save.get('location', 'Unknown')} | {save.get('game_time', '')}"
                )
            text = "\n".join(lines)
        return ActionResult(
            narrative=text,
            scene_type=session.dm_context.scene_type,
            state_changes={"_skip_world_tick": True},
        )

    def _handle_delete_save(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        slot_name = (action.target or "").strip()
        if not slot_name:
            return ActionResult(
                narrative="Delete which save slot? Try 'delete save quicksave'.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        if not self.save_system.delete_save(slot_name):
            return ActionResult(
                narrative=f"No save slot named '{slot_name}' exists.",
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )
        return ActionResult(
            narrative=f"Deleted save slot '{slot_name}'.",
            scene_type=session.dm_context.scene_type,
            state_changes={"deleted_slot": slot_name, "_skip_world_tick": True},
        )
