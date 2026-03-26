"""Non-movement exploration action handlers."""
from __future__ import annotations

from engine.api.action_parser import ParsedAction
from engine.api.game_session import GameSession
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.world.entity import EntityType
from engine.world.skill_checks import roll_check


class ExplorationInteractionMixin:
    """Focused exploration handlers for observation, utility, and free-form actions."""

    def _handle_look(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        if session.dm_context.scene_type == SceneType.COMBAT and session.combat:
            enemies = [combatant for combatant in session.combat.combatants if not combatant.is_dead and combatant.name != session.player.name]
            enemy_desc = ", ".join([f"{enemy.name} (HP:{enemy.character.hp})" for enemy in enemies])
            narrative = (
                f"You're in combat! Enemies: {enemy_desc}. "
                f"Player HP: {session.player.hp}/{session.player.max_hp}"
            )
            return ActionResult(narrative=narrative, scene_type=SceneType.COMBAT)

        location = session.dm_context.location or "the area"
        px, py = session.position[0], session.position[1]
        scene_parts = [f"== {location} =="]

        if session.game_time:
            scene_parts.append(f"Time: {session.game_time.to_string()}")

        nearby_npcs = []
        for entity_id, entity in session.entities.items():
            epos = entity.get("position", [0, 0])
            dist = abs(epos[0] - px) + abs(epos[1] - py)
            if dist <= 5 and entity.get("alive", True):
                role = entity.get("role", "")
                name = entity.get("name", entity_id)
                direction = ""
                dx, dy = epos[0] - px, epos[1] - py
                if abs(dx) > abs(dy):
                    direction = "east" if dx > 0 else "west"
                elif dy != 0:
                    direction = "south" if dy > 0 else "north"
                nearby_npcs.append(f"  {name} ({role}) — {dist} tile{'s' if dist != 1 else ''} {direction}")

        if nearby_npcs:
            scene_parts.append("Nearby:")
            scene_parts.extend(nearby_npcs)

        if session.spatial_index:
            items_here = [entity for entity in session.spatial_index.at(px, py) if entity.entity_type == EntityType.ITEM]
            if items_here:
                scene_parts.append("On the ground:")
                for item in items_here:
                    scene_parts.append(f"  {item.name}")

        if session.ap_tracker:
            scene_parts.append(f"AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        deterministic_scene = "\n".join(scene_parts)
        world_context = self._build_world_context(session)
        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} surveys their surroundings in {location}.\n{world_context}",
            data={
                "player_name": session.player.name,
                "location": location,
                "action": "look around",
                "world_context": world_context,
            },
        )
        dm_flavor = self.dm.narrate(event, session.dm_context, self.llm)
        reveal_lines = self._apply_hidden_reveals(session, "passive")
        narrative = f"{deterministic_scene}\n\n{dm_flavor}"
        if reveal_lines:
            narrative = f"{narrative}\n" + "\n".join(reveal_lines)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_examine(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = action.target or session.dm_context.location
        prox_fail = self._check_entity_proximity(session, target, "examine")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "examine")
        if ap_fail:
            return ap_fail

        world_context = self._build_world_context(session)
        event = DMEvent(
            type=EventType.DISCOVERY,
            description=f"{session.player.name} examines {target} closely, looking for details.\n{world_context}",
            data={
                "player_name": session.player.name,
                "location": session.dm_context.location,
                "action": f"examine {target}",
                "target": target,
            },
        )
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        reveal_lines = self._apply_hidden_reveals(session, "search")
        if reveal_lines:
            narrative = f"{narrative}\n" + "\n".join(reveal_lines)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_search(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "search")
        if ap_fail:
            return ap_fail

        dc = 13
        check_result = roll_check(self._get_player_ability(session, "INS"), dc)
        check_text = self._format_skill_check(check_result, "INS", dc)
        target = action.target or "the area"
        if check_result.success:
            if check_result.critical == "success":
                narrative = f"Your keen eyes discover something remarkable hidden within {target}! A rare find."
            else:
                narrative = f"You carefully search {target} and notice something previously hidden."
        else:
            if check_result.critical == "failure":
                narrative = f"You search {target} carelessly and accidentally trigger something!"
            else:
                narrative = f"You search {target} thoroughly but find nothing of interest."

        event = DMEvent(
            type=EventType.DISCOVERY,
            description=f"{session.player.name} searches {target}. {narrative}",
            data={
                "player_name": session.player.name,
                "action": "search",
                "target": target,
                "success": check_result.success,
                "roll": check_result.total,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_open(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "open")
        if ap_fail:
            return ap_fail
        target = action.target or "the door"
        event = DMEvent(type=EventType.DISCOVERY, description=f"{session.player.name} tries to open {target}.")
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_sneak(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "sneak")
        if ap_fail:
            return ap_fail

        dc = 13
        check_result = self._roll_ability_check(session, "AGI", dc)
        check_text = self._format_skill_check(check_result, "AGI", dc)
        if check_result.success:
            narrative = "You melt into the shadows, moving silently. You are now sneaking."
        elif check_result.critical == "failure":
            narrative = "You stumble loudly! Everyone nearby notices you."
        else:
            narrative = "You try to move quietly, but you're spotted."

        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} attempts to sneak. {'Success' if check_result.success else 'Failure'}.",
            data={
                "player_name": session.player.name,
                "action": "sneak",
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_climb(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "climb")
        if ap_fail:
            return ap_fail

        target = action.target or "the surface"
        dc = 13
        agi = self._get_player_ability(session, "AGI")
        mig = self._get_player_ability(session, "MIG")
        ability, ability_score = ("AGI", agi) if agi >= mig else ("MIG", mig)
        check_result = self._roll_ability_check(session, ability, dc) if ability == "AGI" else roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)
        if check_result.success:
            narrative = f"You skillfully climb {target}, finding handholds with ease."
        elif check_result.critical == "failure":
            narrative = f"You slip and fall from {target}! A bruising tumble."
        else:
            narrative = f"You struggle to grip {target} and slide back down."

        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} attempts to climb {target}.",
            data={
                "player_name": session.player.name,
                "action": "climb",
                "target": target,
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_lockpick(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "lock_pick")
        if ap_fail:
            return ap_fail

        target = action.target or "the lock"
        has_lockpick = any(
            "lockpick" in item.get("id", "").lower() or "lockpick" in item.get("name", "").lower()
            for item in session.inventory
        )
        if not has_lockpick:
            return ActionResult(
                narrative="You need a lockpick to attempt this!",
                scene_type=session.dm_context.scene_type,
            )

        dc = 14
        check_result = self._roll_ability_check(session, "AGI", dc)
        check_text = self._format_skill_check(check_result, "AGI", dc)
        if check_result.success:
            narrative = f"*Click!* The lock on {target} opens with a satisfying snap."
        elif check_result.critical == "failure":
            session.remove_item("lockpick")
            narrative = f"Your lockpick snaps inside {target}! The lockpick is lost."
        else:
            narrative = f"The lock on {target} resists your attempts."

        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} attempts to pick the lock on {target}.",
            data={
                "player_name": session.player.name,
                "action": "lockpick",
                "target": target,
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_pray(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "pray")
        if ap_fail:
            return ap_fail

        target = action.target or "the gods"
        dc = 10
        check_result = roll_check(self._get_player_ability(session, "INS"), dc)
        check_text = self._format_skill_check(check_result, "INS", dc)
        state_changes = {}
        if check_result.success:
            heal = max(1, session.player.max_hp // 8)
            session.player.hp = min(session.player.hp + heal, session.player.max_hp)
            state_changes["hp_restored"] = heal
            if check_result.critical == "success":
                narrative = f"A divine light washes over you! You feel blessed. (+{heal} HP)"
            else:
                narrative = f"You feel a warm sense of peace from your prayer. (+{heal} HP)"
        else:
            narrative = "You pray fervently, but the gods do not answer today."

        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} prays to {target}.",
            data={
                "player_name": session.player.name,
                "action": "pray",
                "target": target,
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
            state_changes=state_changes,
        )

    def _handle_push(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        ap_fail = self._check_ap(session, "push")
        if ap_fail:
            return ap_fail

        target = action.target or "the object"
        dc = 14
        check_result = roll_check(self._get_player_ability(session, "MIG"), dc)
        check_text = self._format_skill_check(check_result, "MIG", dc)
        narrative = (
            f"With a mighty heave, you push {target}! It grinds forward."
            if check_result.success
            else f"You strain against {target}, but it won't budge."
        )
        event = DMEvent(
            type=EventType.EXPLORATION,
            description=f"{session.player.name} attempts to push {target}.",
            data={
                "player_name": session.player.name,
                "action": "push",
                "target": target,
                "success": check_result.success,
            },
        )
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=f"{check_text}\n{dm_narrative}", scene_type=session.dm_context.scene_type)

    def _handle_unknown(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        event = DMEvent(
            type=EventType.EXPLORATION,
            description=(
                f"The player says or does: '{action.raw_input}'. "
                f"They are in {session.dm_context.location}. "
                f"As the Dungeon Master, interpret this action and respond narratively. "
                f"If unclear, make a reasonable creative interpretation."
            ),
            data={
                "player_name": session.player.name,
                "location": session.dm_context.location,
                "raw_input": action.raw_input,
                "action": "free_form",
            },
        )
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _apply_hidden_reveals(self, session: GameSession, mode: str) -> list[str]:
        reveals: list[str] = []
        if not session.spatial_index:
            return reveals
        px, py = session.position
        search_radius = 3 if mode == "search" else 2
        nearby = session.spatial_index.in_radius(px, py, search_radius)
        for entity in nearby:
            if getattr(entity, "hidden", False):
                entity.hidden = False
                reveals.append(f"You notice something hidden: {entity.name}!")
                if entity.id in session.entities:
                    session.entities[entity.id]["hidden"] = False
        return reveals
