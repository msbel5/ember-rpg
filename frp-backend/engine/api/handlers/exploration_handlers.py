"""Exploration handler methods for GameEngine — mixin class."""
from __future__ import annotations

from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.api.game_session import GameSession
from engine.api.action_parser import ParsedAction, ActionIntent
from engine.core.dm_agent import DMEvent, EventType, SceneType
from engine.world.entity import EntityType
from engine.world.action_points import ACTION_COSTS
from engine.world.proximity import distance, manhattan_distance, astar_path, check_proximity
from engine.world.skill_checks import roll_check

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult


class ExplorationMixin:
    """Exploration handler methods: look, examine, move, search, open, sneak, climb, lockpick, pray, push, go_to, unknown."""

    def _live_entity_position(self, session: GameSession, entity_id: str, fallback: Optional[List[int]] = None) -> List[int]:
        record = session.entities.get(entity_id, {})
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            return [int(entity_ref.position[0]), int(entity_ref.position[1])]
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            return [int(position[0]), int(position[1])]
        return list(fallback or [0, 0])

    def _approach_goal_candidates(self, session: GameSession, target_pos: List[int]) -> List[List[int]]:
        candidates: List[List[int]] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            gx = int(target_pos[0]) + dx
            gy = int(target_pos[1]) + dy
            if [gx, gy] == session.position:
                candidates.append([gx, gy])
                continue
            if session.map_data is not None and not session.map_data.is_walkable(gx, gy):
                continue
            if session.spatial_index and session.spatial_index.blocking_at(gx, gy):
                blockers = [
                    entity
                    for entity in session.spatial_index.at(gx, gy)
                    if entity.id != "player" and entity.blocking
                ]
                if blockers:
                    continue
            candidates.append([gx, gy])
        candidates.sort(key=lambda pos: manhattan_distance(session.position, pos))
        return candidates

    def _handle_look(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Handle 'look around', 'look', 'observe' — deterministic scene + DM flavor."""
        from engine.api.game_engine import ActionResult
        # Combat look
        if session.dm_context.scene_type == SceneType.COMBAT and session.combat:
            enemies = [c for c in session.combat.combatants if not c.is_dead and c.name != session.player.name]
            enemy_desc = ", ".join([f"{e.name} (HP:{e.character.hp})" for e in enemies])
            narrative = (
                f"You're in combat! Enemies: {enemy_desc}. "
                f"Player HP: {session.player.hp}/{session.player.max_hp}"
            )
            return ActionResult(narrative=narrative, scene_type=SceneType.COMBAT)

        location = session.dm_context.location or "the area"
        px, py = session.position[0], session.position[1]

        # Build deterministic scene description with nearby entities
        scene_parts = [f"== {location} =="]

        # Time
        if session.game_time:
            scene_parts.append(f"Time: {session.game_time.to_string()}")

        # Nearby NPCs (within 5 tiles)
        nearby_npcs = []
        for eid, entity in session.entities.items():
            epos = entity.get("position", [0, 0])
            dist = abs(epos[0] - px) + abs(epos[1] - py)
            if dist <= 5 and entity.get("alive", True):
                role = entity.get("role", "")
                name = entity.get("name", eid)
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

        # Ground items at player position
        if session.spatial_index:
            items_here = [e for e in session.spatial_index.at(px, py) if e.entity_type == EntityType.ITEM]
            if items_here:
                scene_parts.append("On the ground:")
                for item in items_here:
                    scene_parts.append(f"  {item.name}")

        # AP status
        if session.ap_tracker:
            scene_parts.append(f"AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        deterministic_scene = "\n".join(scene_parts)

        # Add DM flavor narration
        world_context = self._build_world_context(session)
        desc = (
            f"{session.player.name} surveys their surroundings in {location}.\n"
            f"{world_context}"
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name,
            "location": location,
            "action": "look around",
            "world_context": world_context,
        })
        dm_flavor = self.dm.narrate(event, session.dm_context, self.llm)
        reveal_lines = self._apply_hidden_reveals(session, "passive")
        narrative = f"{deterministic_scene}\n\n{dm_flavor}"
        if reveal_lines:
            narrative = f"{narrative}\n" + "\n".join(reveal_lines)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_examine(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        target = action.target or session.dm_context.location

        # Proximity check for examining entities
        prox_fail = self._check_entity_proximity(session, target, "examine")
        if prox_fail:
            return prox_fail
        ap_fail = self._check_ap(session, "examine")
        if ap_fail:
            return ap_fail

        world_context = self._build_world_context(session)
        desc = f"{session.player.name} examines {target} closely, looking for details.\n{world_context}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "action": f"examine {target}",
            "target": target,
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        reveal_lines = self._apply_hidden_reveals(session, "search")
        if reveal_lines:
            narrative = f"{narrative}\n" + "\n".join(reveal_lines)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_move(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        enc_penalty = self._encumbrance_penalty(session)
        if enc_penalty >= 999:
            return ActionResult(
                narrative="You're too overencumbered to move! Drop some items first.",
                scene_type=session.dm_context.scene_type,
            )
        if session.dm_context.scene_type == SceneType.COMBAT and session.combat is not None:
            flee_words = ["flee", "run", "escape", "retreat"]
            if action.raw_input and any(w in action.raw_input.lower() for w in flee_words):
                return self._handle_flee(session, action)
            if session.combat.active_combatant.name != session.player.name:
                return ActionResult(
                    narrative=f"It is {session.combat.active_combatant.name}'s turn.",
                    scene_type=SceneType.COMBAT,
                    combat_state=self._combat_state(session.combat),
                    state_changes={"_skip_world_tick": True},
                )

        dest = action.direction or action.target or action.action_detail or "forward"
        # Clean direction strings like "to the tavern" -> "the tavern"
        if dest and dest.startswith("to "):
            dest = dest[3:]

        DIRECTION_DELTAS = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
        }
        has_map = session.map_data is not None
        MAP_SIZE = session.map_data.width if has_map else 32
        MAP_H = session.map_data.height if has_map else 32
        dest_lower = dest.lower()

        moved = False
        blocked_msg = None

        if session.dm_context.scene_type == SceneType.COMBAT and session.combat is not None and dest_lower in DIRECTION_DELTAS:
            dx, dy = DIRECTION_DELTAS[dest_lower]
            old_pos = tuple(session.position)
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blockers = [e for e in session.spatial_index.at(new_x, new_y) if e.blocking and e.id != "player"]
                if blockers:
                    blocked_msg = f"{blockers[0].name} is blocking the way."
                else:
                    blocked_msg = "Something blocks your path."
            else:
                move_result = session.combat.move_combatant(dx, dy)
                if move_result.get("error"):
                    blocked_msg = move_result["error"]
                else:
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
                    hostile_alert = ""
                    oa_messages = self._opportunity_attack_messages(session, old_pos, (new_x, new_y))
                    narrative = f"You reposition in combat. (Position: {new_x},{new_y})"
                    if oa_messages:
                        narrative = f"{narrative}\n" + "\n".join(oa_messages)
                    return ActionResult(
                        narrative=narrative,
                        scene_type=session.dm_context.scene_type,
                        combat_state=self._combat_state(session.combat),
                        state_changes={"position": list(session.position), "_skip_world_tick": True},
                    )

        if dest_lower in ("left", "right"):
            # Turn only, don't move
            turn_map = {
                "left":  {"north": "west", "west": "south", "south": "east", "east": "north"},
                "right": {"north": "east", "east": "south", "south": "west", "west": "north"},
            }
            session.facing = turn_map[dest_lower].get(session.facing, session.facing)
        elif dest_lower in DIRECTION_DELTAS:
            session.facing = dest_lower
            dx, dy = DIRECTION_DELTAS[dest_lower]
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            # Clamp to map bounds
            new_x = max(0, min(MAP_SIZE - 1, new_x))
            new_y = max(0, min(MAP_H - 1, new_y))

            # Check walkability via map_data
            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            # Check blocking entities via spatial_index
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blockers = session.spatial_index.at(new_x, new_y)
                blocker_names = [e.name for e in blockers if e.blocking and e.id != "player"]
                if blocker_names:
                    blocked_msg = f"{blocker_names[0]} is blocking the way."
                else:
                    blocked_msg = "Something blocks your path."
            else:
                # Check AP cost (including encumbrance)
                move_cost = ACTION_COSTS.get("move_flat", 1)
                if session.ap_tracker and not session.ap_tracker.can_move(move_cost, enc_penalty):
                    blocked_msg = f"Not enough action points to move. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})"
                else:
                    # Spend AP
                    if session.ap_tracker:
                        session.ap_tracker.spend_movement(move_cost, enc_penalty)
                    # Move player in spatial index
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
        elif dest_lower == "forward":
            DIRECTION_DELTAS_LOCAL = {
                "north": (0, -1), "south": (0, 1),
                "east": (1, 0), "west": (-1, 0),
            }
            dx, dy = DIRECTION_DELTAS_LOCAL.get(session.facing, (0, -1))
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            new_x = max(0, min(MAP_SIZE - 1, new_x))
            new_y = max(0, min(MAP_H - 1, new_y))

            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blocked_msg = "Something blocks your path."
            else:
                if session.ap_tracker:
                    if not session.ap_tracker.spend_movement(ACTION_COSTS.get("move_flat", 1), enc_penalty):
                        blocked_msg = "Not enough action points to move."
                    else:
                        if session.spatial_index and session.player_entity:
                            session.spatial_index.move(session.player_entity, new_x, new_y)
                        session.position = [new_x, new_y]
                        moved = True
                else:
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
        else:
            # Named destination or coordinate
            import re
            coord_match = re.match(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$", str(dest))
            if coord_match:
                try:
                    x = int(coord_match.group(1))
                    y = int(coord_match.group(2))
                    x = max(0, min(MAP_SIZE - 1, x))
                    y = max(0, min(MAP_H - 1, y))
                    if has_map and not session.map_data.is_walkable(x, y):
                        blocked_msg = "That position is not walkable."
                    elif session.spatial_index and session.spatial_index.blocking_at(x, y):
                        blocked_msg = "Something blocks your path."
                    else:
                        move_cost = ACTION_COSTS.get("move_flat", 1)
                        if session.ap_tracker and not session.ap_tracker.can_move(move_cost, enc_penalty):
                            blocked_msg = f"Not enough action points to move. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})"
                        else:
                            if session.ap_tracker:
                                session.ap_tracker.spend_movement(move_cost, enc_penalty)
                            if session.spatial_index and session.player_entity:
                                session.spatial_index.move(session.player_entity, x, y)
                            session.position = [x, y]
                            moved = True
                except Exception:
                    pass
            else:
                # Check if named destination matches an NPC — auto-pathfind
                target_entity = self._find_entity_by_name(session, dest)
                if target_entity is not None:
                    # Delegate to go_to handler
                    from engine.api.action_parser import ParsedAction as _PA, ActionIntent as _AI
                    goto_action = _PA(intent=_AI.GO_TO, raw_input=action.raw_input, target=dest)
                    return self._handle_go_to(session, goto_action)
                # Unknown destination — don't silently teleport
                return ActionResult(
                    narrative=f"You don't know how to get to '{dest}'. Try a direction (north/south/east/west) or 'approach <name>'.",
                    scene_type=session.dm_context.scene_type,
                    state_changes={"_skip_world_tick": True},
                )

        if blocked_msg:
            return ActionResult(
                narrative=blocked_msg,
                scene_type=session.dm_context.scene_type,
                state_changes={"_skip_world_tick": True},
            )

        # Recompute FOV and center viewport after movement
        if moved and session.viewport and has_map:
            session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0], session.position[1],
                radius=session.viewport.fov_radius,
            )

        # Check for hostile entities in visible range -> report them
        hostile_alert = ""
        if moved and session.spatial_index and session.viewport:
            nearby = session.spatial_index.in_radius(session.position[0], session.position[1], 5)
            hostiles = [e for e in nearby if e.is_hostile() and e.is_alive() and e.id != "player"]
            if hostiles:
                names = ", ".join(e.name for e in hostiles)
                hostile_alert = f" You spot hostile creatures nearby: {names}!"

        # Build concise movement narrative
        DIRECTION_DELTAS_ALL = {
            "north": (0, -1), "south": (0, 1),
            "east": (1, 0), "west": (-1, 0),
        }
        direction_name = dest_lower if dest_lower in DIRECTION_DELTAS_ALL else dest
        px, py = session.position[0], session.position[1]
        base_narrative = f"You move {direction_name}. (Position: {px},{py})"

        # Add nearby entity awareness
        if session.spatial_index:
            nearby = session.spatial_index.in_radius(px, py, 3)
            notable = [e for e in nearby if e.id != "player" and e.alive]
            if notable:
                names = ", ".join(f"{e.name}" for e in notable[:3])
                base_narrative += f" You see {names} nearby."

        if hostile_alert:
            base_narrative += hostile_alert

        narrative = base_narrative

        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
            state_changes={"position": list(session.position)} if moved else {},
        )

    def _handle_search(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Search current area for hidden items/traps/secrets."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "search")
        if ap_fail:
            return ap_fail

        dc = 13
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)
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

        desc = f"{session.player.name} searches {target}. {narrative}"
        event = DMEvent(type=EventType.DISCOVERY, description=desc, data={
            "player_name": session.player.name, "action": "search", "target": target,
            "success": check_result.success, "roll": check_result.total,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_open(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "open")
        if ap_fail:
            return ap_fail
        target = action.target or "the door"
        desc = f"{session.player.name} tries to open {target}."
        event = DMEvent(type=EventType.DISCOVERY, description=desc)
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _handle_sneak(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Enter stealth mode with AGI check."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "sneak")
        if ap_fail:
            return ap_fail

        dc = 13
        ability = "AGI"
        check_result = self._roll_ability_check(session, ability, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = "You melt into the shadows, moving silently. You are now sneaking."
        else:
            if check_result.critical == "failure":
                narrative = "You stumble loudly! Everyone nearby notices you."
            else:
                narrative = "You try to move quietly, but you're spotted."

        desc = f"{session.player.name} attempts to sneak. {'Success' if check_result.success else 'Failure'}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "sneak", "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_climb(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Climb a surface using higher of AGI or MIG."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "climb")
        if ap_fail:
            return ap_fail

        target = action.target or "the surface"
        dc = 13
        agi = self._get_player_ability(session, "AGI")
        mig = self._get_player_ability(session, "MIG")
        ability, ability_score = ("AGI", agi) if agi >= mig else ("MIG", mig)

        if ability == "AGI":
            check_result = self._roll_ability_check(session, ability, dc)
        else:
            check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"You skillfully climb {target}, finding handholds with ease."
        else:
            if check_result.critical == "failure":
                narrative = f"You slip and fall from {target}! A bruising tumble."
            else:
                narrative = f"You struggle to grip {target} and slide back down."

        desc = f"{session.player.name} attempts to climb {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "climb", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_lockpick(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Pick a lock with AGI check. Requires lockpick in inventory."""
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
        ability = "AGI"
        check_result = self._roll_ability_check(session, ability, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"*Click!* The lock on {target} opens with a satisfying snap."
        else:
            if check_result.critical == "failure":
                # Lockpick breaks on critical failure
                session.remove_item("lockpick")
                narrative = f"Your lockpick snaps inside {target}! The lockpick is lost."
            else:
                narrative = f"The lock on {target} resists your attempts."

        desc = f"{session.player.name} attempts to pick the lock on {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "lockpick", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_pray(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Pray at a shrine or temple. INS check for small heal on success."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "pray")
        if ap_fail:
            return ap_fail

        target = action.target or "the gods"
        dc = 10
        ability = "INS"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

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

        desc = f"{session.player.name} prays to {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "pray", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
            state_changes=state_changes,
        )

    def _handle_push(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Push a heavy object with MIG check."""
        from engine.api.game_engine import ActionResult
        ap_fail = self._check_ap(session, "push")
        if ap_fail:
            return ap_fail

        target = action.target or "the object"
        dc = 14
        ability = "MIG"
        ability_score = self._get_player_ability(session, ability)
        check_result = roll_check(ability_score, dc)
        check_text = self._format_skill_check(check_result, ability, dc)

        if check_result.success:
            narrative = f"With a mighty heave, you push {target}! It grinds forward."
        else:
            narrative = f"You strain against {target}, but it won't budge."

        desc = f"{session.player.name} attempts to push {target}."
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name, "action": "push", "target": target,
            "success": check_result.success,
        })
        dm_narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(
            narrative=f"{check_text}\n{dm_narrative}",
            scene_type=session.dm_context.scene_type,
        )

    def _handle_go_to(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        """Auto-pathfind to a named NPC or location using A*."""
        from engine.api.game_engine import ActionResult
        target = (action.target or "").strip()
        if not target:
            return ActionResult(
                narrative="Go to whom? Specify an NPC or location name.",
                scene_type=session.dm_context.scene_type,
            )
        # Find target entity
        entity = self._find_entity_by_name(session, target)
        if entity is None:
            # Fall back to regular move
            return self._handle_move(session, action)
        entity_id, entity_data = entity
        enc_penalty = self._encumbrance_penalty(session)
        if enc_penalty >= 999:
            return ActionResult(
                narrative="You're too overencumbered to move!",
                scene_type=session.dm_context.scene_type,
            )

        npc_name = entity_data.get("name", target)
        steps_taken = 0
        refresh_count = 0
        blocked_reason: Optional[str] = None
        world_events: List[Dict[str, Any]] = []

        while steps_taken < 40:
            current_target = session.entities.get(entity_id)
            if current_target is None:
                blocked_reason = f"{npc_name} is no longer here."
                break
            if not current_target.get("alive", True):
                blocked_reason = f"{npc_name} can no longer respond to your approach."
                break

            target_pos = self._live_entity_position(session, entity_id, current_target.get("position", [0, 0]))
            if manhattan_distance(session.position, target_pos) <= 1:
                blocked_reason = None
                break

            goal_candidates = self._approach_goal_candidates(session, target_pos)
            best_path: List[List[int]] = []
            for candidate in goal_candidates:
                if candidate == session.position:
                    best_path = []
                    break
                candidate_path = astar_path(session.map_data, session.position, candidate, max_steps=40)
                if candidate_path and (not best_path or len(candidate_path) < len(best_path)):
                    best_path = candidate_path

            if not goal_candidates or not best_path:
                blocked_reason = f"Can't find a path to {npc_name}."
                break

            move_cost = ACTION_COSTS.get("move_flat", 1)
            if session.ap_tracker:
                if not session.ap_tracker.can_move(move_cost, enc_penalty):
                    blocked_reason = (
                        f"Not enough action points to keep moving toward {npc_name}. "
                        f"(AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})"
                    )
                    break
                session.ap_tracker.spend_movement(move_cost, enc_penalty)
            # Check walkability and blocking
            nx, ny = best_path[0][0], best_path[0][1]
            if session.spatial_index and session.spatial_index.blocking_at(nx, ny):
                blockers = [
                    candidate
                    for candidate in session.spatial_index.at(nx, ny)
                    if candidate.id != "player" and candidate.blocking
                ]
                blocked_reason = f"{blockers[0].name} blocks the way to {npc_name}." if blockers else f"Something blocks the way to {npc_name}."
                break
            if session.spatial_index and session.player_entity:
                session.spatial_index.move(session.player_entity, nx, ny)
            session.position = [nx, ny]
            steps_taken += 1
            world_events.extend(self._world_tick(session, minutes=15, refresh_ap=False))
            if session.ap_tracker is not None and not session.in_combat() and session.ap_tracker.current_ap <= 0:
                session.ap_tracker.refresh()
                refresh_count += 1
        # Update viewport
        if session.viewport and session.map_data:
            session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0], session.position[1],
                radius=session.viewport.fov_radius,
            )
        session.sync_player_state()
        target_pos = self._live_entity_position(session, entity_id, entity_data.get("position", [0, 0]))
        dist_remaining = manhattan_distance(session.position, target_pos)
        refresh_note = " (New turn — AP refreshed)" if refresh_count else ""
        if dist_remaining <= 1:
            result = ActionResult(
                narrative=f"You walk to {npc_name} ({steps_taken} steps). You're now close enough to interact.{refresh_note}",
                scene_type=session.dm_context.scene_type,
                state_changes={"position": list(session.position), "_skip_world_tick": True},
            )
            self._merge_world_events(session, result, world_events)
            return result
        result = ActionResult(
            narrative=(
                f"You walk toward {npc_name} ({steps_taken} steps) but couldn't end close enough to interact. "
                f"{blocked_reason or f'({int(dist_remaining)} tiles away)'}{refresh_note}"
            ),
            scene_type=session.dm_context.scene_type,
            state_changes={"position": list(session.position), "_skip_world_tick": True},
        )
        self._merge_world_events(session, result, world_events)
        return result

    def _handle_unknown(self, session: GameSession, action: ParsedAction) -> "ActionResult":
        from engine.api.game_engine import ActionResult
        # Unknown intent -> pass raw input to LLM as free-form DM action
        desc = (
            f"The player says or does: '{action.raw_input}'. "
            f"They are in {session.dm_context.location}. "
            f"As the Dungeon Master, interpret this action and respond narratively. "
            f"If unclear, make a reasonable creative interpretation."
        )
        event = DMEvent(type=EventType.EXPLORATION, description=desc, data={
            "player_name": session.player.name,
            "location": session.dm_context.location,
            "raw_input": action.raw_input,
            "action": "free_form",
        })
        narrative = self.dm.narrate(event, session.dm_context, self.llm)
        return ActionResult(narrative=narrative, scene_type=session.dm_context.scene_type)

    def _apply_hidden_reveals(self, session: GameSession, mode: str) -> List[str]:
        reveals: List[str] = []
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

    def _find_entity_by_name(self, session: GameSession, target_name: str) -> Optional[tuple]:
        """Find entity by partial name match. Returns (entity_id, entity_dict) or None."""
        if not target_name:
            return None
        target_lower = target_name.lower()
        for eid, entity in session.entities.items():
            if target_lower in entity.get("name", "").lower() or target_lower in entity.get("role", "").lower():
                return (eid, entity)
        return None

    def _check_entity_proximity(self, session: GameSession, target_name: str, action_type: str) -> Optional["ActionResult"]:
        """Check if target entity is in range for action. Returns ActionResult on failure, None if OK."""
        from engine.api.game_engine import ActionResult
        found = self._find_entity_by_name(session, target_name)
        if found is None:
            return None  # No entity found, let the handler deal with it normally
        eid, entity = found
        target_pos = entity.get("position", [0, 0])
        ok, msg = check_proximity(session.position, target_pos, action_type)
        if not ok:
            return ActionResult(
                narrative=f"{msg} {entity['name']} is at position {target_pos}.",
                scene_type=session.dm_context.scene_type,
            )
        return None
