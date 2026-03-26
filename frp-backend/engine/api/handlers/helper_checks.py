"""Skill, AP, and time helper methods for GameEngine mixins."""
from __future__ import annotations

from typing import Optional

from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.world.action_points import ACTION_COSTS
from engine.world.skill_checks import SkillCheckResult, ability_modifier, contested_check


class HelperChecksMixin:
    """Focused helpers for skill checks, AP, and long-action timing."""

    def _encumbrance_penalty(self, session: GameSession) -> int:
        """Get current encumbrance AP penalty from physical inventory."""
        if session.physical_inventory is None:
            return 0
        str_mod = session._get_strength_modifier()
        base_penalty = session.physical_inventory.encumbrance_ap_penalty(str_mod)
        if base_penalty >= 999:
            return 999
        return base_penalty + session.movement_ap_penalty()

    def _current_game_hour(self, session: GameSession) -> float:
        if not getattr(session, "game_time", None):
            return 0.0
        return ((session.game_time.day - 1) * 24) + session.game_time.hour + (session.game_time.minute / 60.0)

    def _player_skill_bonus(self, session: GameSession, skill: str) -> int:
        try:
            return session.player.skill_bonus(skill)
        except Exception:
            fallback_ability = Character.SKILL_STATS.get(skill, "MIG")
            return ability_modifier(session.player.stats.get(fallback_ability, 10))

    def _roll_player_skill_check(
        self,
        session: GameSession,
        skill: str,
        dc: int,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> SkillCheckResult:
        import engine.api.game_engine as _ge

        governing_stat = Character.SKILL_STATS.get(skill, "MIG")
        ability_score = session.player.stats.get(governing_stat, 10)
        legacy_bonus = int((session.player.skills or {}).get(skill, 0))
        proficient = session.player.has_proficiency(skill)
        expertise = session.player.has_expertise(skill)
        modifier_bonus = legacy_bonus if skill in Character.DND_SKILL_STATS else 0
        result = _ge.roll_check(
            ability_score,
            dc,
            proficiency_bonus=session.player.proficiency_bonus if proficient or expertise else 0,
            expertise=expertise,
            modifier_bonus=modifier_bonus,
            advantage=advantage,
            disadvantage=disadvantage,
        )
        if governing_stat == "AGI":
            result = self._apply_check_penalty(result, session.agi_check_penalty())
        if session.player.exhaustion_level >= 1 and result.critical not in {"success", "failure"}:
            result = _ge.roll_check(
                ability_score,
                dc,
                proficiency_bonus=session.player.proficiency_bonus if proficient or expertise else 0,
                expertise=expertise,
                modifier_bonus=modifier_bonus,
                advantage=False,
                disadvantage=True,
            )
            if governing_stat == "AGI":
                result = self._apply_check_penalty(result, session.agi_check_penalty())
        return result

    def _npc_skill_bonus(self, entity: dict, skill: str) -> int:
        skill_lower = str(skill or "").lower().replace(" ", "_")
        if skill_lower in {"insight", "perception", "investigation"}:
            stat_key = Character.DND_SKILL_STATS.get(skill_lower, "INS")
            base = ability_modifier(int(entity.get("stats", {}).get(stat_key, 10)))
            legacy = int((entity.get("skills") or {}).get(skill_lower, 0))
            return base + legacy
        return int((entity.get("skills") or {}).get(skill_lower, 0))

    def _check_ap(self, session: GameSession, cost_key: str):
        """Check if player has enough AP. Returns ActionResult on failure, None on success."""
        from engine.api.game_engine import ActionResult

        if session.ap_tracker is None:
            return None
        if session.in_combat():
            return None
        cost = ACTION_COSTS.get(cost_key, 1)
        if not session.ap_tracker.can_afford(cost):
            return ActionResult(
                narrative=f"Not enough action points! ({session.ap_tracker.current_ap}/{session.ap_tracker.max_ap} AP, need {cost})",
                scene_type=session.dm_context.scene_type,
            )
        session.ap_tracker.spend(cost)
        if session.ap_tracker.current_ap <= 0 and not session.in_combat():
            session.narration_context["_auto_refresh_after_action"] = True
        return None

    def _format_skill_check(self, result: SkillCheckResult, ability_name: str, dc: int) -> str:
        if result.critical == "success":
            return f"[NATURAL 20! Critical Success on {ability_name} check (DC {dc})]"
        if result.critical == "failure":
            return f"[NATURAL 1! Critical Failure on {ability_name} check (DC {dc})]"
        if result.success:
            return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Success by {result.margin}]"
        return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Failed by {abs(result.margin)}]"

    def _get_player_ability(self, session: GameSession, ability: str) -> int:
        return session.player.stats.get(ability, 10)

    def _apply_check_penalty(self, result: SkillCheckResult, penalty: int) -> SkillCheckResult:
        if penalty <= 0:
            return result
        total = result.total - penalty
        success = result.success if result.critical in {"success", "failure"} else total >= result.dc
        return SkillCheckResult(
            roll=result.roll,
            modifier=result.modifier - penalty,
            total=total,
            dc=result.dc,
            success=success,
            margin=total - result.dc,
            critical=result.critical,
        )

    def _roll_ability_check(self, session: GameSession, ability: str, dc: int) -> SkillCheckResult:
        import engine.api.game_engine as _ge

        result = _ge.roll_check(self._get_player_ability(session, ability), dc)
        penalty = session.agi_check_penalty() if ability == "AGI" else 0
        return self._apply_check_penalty(result, penalty)

    def _contested_agi_check(self, session: GameSession, opponent_score: int) -> tuple[SkillCheckResult, SkillCheckResult, str]:
        result_a, result_b, _winner = contested_check(self._get_player_ability(session, "AGI"), opponent_score)
        result_a = self._apply_check_penalty(result_a, session.agi_check_penalty())
        if result_a.total > result_b.total:
            winner = "a"
        elif result_b.total > result_a.total:
            winner = "b"
        else:
            winner = "tie"
        result_a = SkillCheckResult(
            roll=result_a.roll,
            modifier=result_a.modifier,
            total=result_a.total,
            dc=result_b.total,
            success=(winner == "a"),
            margin=result_a.total - result_b.total,
            critical=result_a.critical,
        )
        result_b = SkillCheckResult(
            roll=result_b.roll,
            modifier=result_b.modifier,
            total=result_b.total,
            dc=result_a.total,
            success=(winner == "b"),
            margin=result_b.total - result_a.total,
            critical=result_b.critical,
        )
        return result_a, result_b, winner

    def _simulate_long_action_ap(self, session: GameSession, total_cost: int) -> tuple[int, Optional[int]]:
        tracker = session.ap_tracker
        if tracker is None:
            return 15, None

        cost = max(0, int(total_cost))
        if cost == 0:
            return 15, tracker.current_ap

        if cost <= tracker.current_ap:
            tracker.spend(cost)
            return 15, None

        remaining_cost = cost
        if tracker.current_ap > 0:
            remaining_cost -= tracker.current_ap
            tracker.current_ap = 0

        current_minute = session.game_time.minute if getattr(session, "game_time", None) else 0
        minutes_until_refresh = 60 - current_minute if current_minute else 60
        elapsed_minutes = minutes_until_refresh

        while remaining_cost > tracker.max_ap:
            remaining_cost -= tracker.max_ap
            elapsed_minutes += 60

        ap_after_action = tracker.max_ap - remaining_cost
        return elapsed_minutes, ap_after_action
