"""Combat narration helper methods."""
from __future__ import annotations

from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.core.dm_agent import DMEvent, EventType


class CombatNarrationMixin:
    """Focused helpers for combat narration and encounter start text."""

    def _build_combat_narrative(self, session, attacker_name, target, hit, damage, crit=False, fumble=False):
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
            event = DMEvent(
                type=EventType.COMBAT,
                description=desc,
                data={
                    "player_name": session.player.name,
                    "target_name": target.name,
                    "hit": hit,
                    "damage": damage,
                    "player_hp": session.player.hp,
                    "player_max_hp": session.player.max_hp,
                    "target_hp": target.hp,
                    "action": "attack",
                },
            )
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_enemy_combat_narrative(self, session, enemy, hit, damage):
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
            event = DMEvent(
                type=EventType.COMBAT,
                description=desc,
                data={
                    "attacker_name": enemy.name,
                    "player_name": session.player.name,
                    "hit": hit,
                    "damage": damage,
                    "player_hp": session.player.hp,
                    "player_max_hp": session.player.max_hp,
                    "action": "enemy_attack",
                },
            )
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_death_narrative(self, session, enemy_name):
        fallback = f"{enemy_name} has been defeated!"
        if self.llm is None:
            return fallback
        try:
            event = DMEvent(
                type=EventType.COMBAT,
                description=f"{enemy_name} has been defeated! Describe their death dramatically in 1-2 sentences.",
                data={"enemy_name": enemy_name, "action": "enemy_death"},
            )
            return self.dm.narrate(event, session.dm_context, self.llm)
        except Exception:
            return fallback

    def _build_combat_start_result(self, session: GameSession, enemies: list[Character]):
        from engine.api.game_engine import ActionResult

        enemy_names = ", ".join(enemy.name for enemy in enemies) or "an enemy"
        active_name = session.combat.active_combatant.name if session.combat and not session.combat.combat_ended else session.player.name
        fallback = f"Combat begins against {enemy_names}. Initiative is rolled; {active_name} acts first."
        try:
            event = DMEvent(
                type=EventType.COMBAT_START,
                description=(
                    f"{session.player.name} enters combat with {enemy_names} in {session.dm_context.location}. "
                    f"The fight starts now. Initiative is rolled and {active_name} has the first turn."
                ),
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
