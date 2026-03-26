"""Movement and targeting methods for exploration actions."""
from __future__ import annotations

import re
from typing import Optional

from engine.api.action_parser import ActionIntent, ParsedAction
from engine.api.game_session import GameSession
from engine.core.dm_agent import SceneType
from engine.world.action_points import ACTION_COSTS
from engine.world.proximity import astar_path, check_proximity, distance, manhattan_distance


class ExplorationNavigationMixin:
    """Focused exploration helpers for movement, approach, and proximity."""

    def _live_entity_position(self, session: GameSession, entity_id: str, fallback: Optional[list[int]] = None) -> list[int]:
        record = session.entities.get(entity_id, {})
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            return [int(entity_ref.position[0]), int(entity_ref.position[1])]
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            return [int(position[0]), int(position[1])]
        return list(fallback or [0, 0])

    def _approach_goal_candidates(
        self,
        session: GameSession,
        target_pos: list[int],
        *,
        interaction_radius: int = 1,
        allow_target_tile: bool = False,
    ) -> list[list[int]]:
        candidates: list[list[int]] = []
        tx = int(target_pos[0])
        ty = int(target_pos[1])
        for dx in range(-interaction_radius, interaction_radius + 1):
            for dy in range(-interaction_radius, interaction_radius + 1):
                chebyshev_dist = max(abs(dx), abs(dy))
                if chebyshev_dist == 0 and not allow_target_tile:
                    continue
                if chebyshev_dist == 0 and allow_target_tile:
                    pass
                elif chebyshev_dist == 0 or chebyshev_dist > interaction_radius:
                    continue
                gx = tx + dx
                gy = ty + dy
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
        candidates.sort(key=lambda pos: (distance(session.position, pos), manhattan_distance(session.position, pos)))
        return candidates

    def _handle_move(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        enc_penalty = self._encumbrance_penalty(session)
        if enc_penalty >= 999:
            return ActionResult(
                narrative="You're too overencumbered to move! Drop some items first.",
                scene_type=session.dm_context.scene_type,
            )
        if session.dm_context.scene_type == SceneType.COMBAT and session.combat is not None:
            flee_words = ["flee", "run", "escape", "retreat"]
            if action.raw_input and any(word in action.raw_input.lower() for word in flee_words):
                return self._handle_flee(session, action)
            if session.combat.active_combatant.name != session.player.name:
                return ActionResult(
                    narrative=f"It is {session.combat.active_combatant.name}'s turn.",
                    scene_type=SceneType.COMBAT,
                    combat_state=self._combat_state(session.combat),
                    state_changes={"_skip_world_tick": True},
                )

        dest = action.direction or action.target or action.action_detail or "forward"
        if dest and dest.startswith("to "):
            dest = dest[3:]

        direction_deltas = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }
        has_map = session.map_data is not None
        map_width = session.map_data.width if has_map else 32
        map_height = session.map_data.height if has_map else 32
        dest_lower = dest.lower()

        moved = False
        blocked_msg = None

        if session.dm_context.scene_type == SceneType.COMBAT and session.combat is not None and dest_lower in direction_deltas:
            dx, dy = direction_deltas[dest_lower]
            old_pos = tuple(session.position)
            new_x = session.position[0] + dx
            new_y = session.position[1] + dy
            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blockers = [entity for entity in session.spatial_index.at(new_x, new_y) if entity.blocking and entity.id != "player"]
                blocked_msg = f"{blockers[0].name} is blocking the way." if blockers else "Something blocks your path."
            else:
                move_result = session.combat.move_combatant(dx, dy)
                if move_result.get("error"):
                    blocked_msg = move_result["error"]
                else:
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
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
            turn_map = {
                "left": {"north": "west", "west": "south", "south": "east", "east": "north"},
                "right": {"north": "east", "east": "south", "south": "west", "west": "north"},
            }
            session.facing = turn_map[dest_lower].get(session.facing, session.facing)
        elif dest_lower in direction_deltas:
            session.facing = dest_lower
            dx, dy = direction_deltas[dest_lower]
            new_x = max(0, min(map_width - 1, session.position[0] + dx))
            new_y = max(0, min(map_height - 1, session.position[1] + dy))
            if has_map and not session.map_data.is_walkable(new_x, new_y):
                blocked_msg = "A solid wall blocks your path."
            elif session.spatial_index and session.spatial_index.blocking_at(new_x, new_y):
                blocker_names = [entity.name for entity in session.spatial_index.at(new_x, new_y) if entity.blocking and entity.id != "player"]
                blocked_msg = f"{blocker_names[0]} is blocking the way." if blocker_names else "Something blocks your path."
            else:
                move_cost = ACTION_COSTS.get("move_flat", 1)
                if session.ap_tracker and not session.ap_tracker.can_move(move_cost, enc_penalty):
                    blocked_msg = f"Not enough action points to move. (AP: {session.ap_tracker.current_ap}/{session.ap_tracker.max_ap})"
                else:
                    if session.ap_tracker:
                        session.ap_tracker.spend_movement(move_cost, enc_penalty)
                    if session.spatial_index and session.player_entity:
                        session.spatial_index.move(session.player_entity, new_x, new_y)
                    session.position = [new_x, new_y]
                    moved = True
        elif dest_lower == "forward":
            dx, dy = direction_deltas.get(session.facing, (0, -1))
            new_x = max(0, min(map_width - 1, session.position[0] + dx))
            new_y = max(0, min(map_height - 1, session.position[1] + dy))
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
            coord_match = re.match(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$", str(dest))
            if coord_match:
                try:
                    x = max(0, min(map_width - 1, int(coord_match.group(1))))
                    y = max(0, min(map_height - 1, int(coord_match.group(2))))
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
                target_entity = self._find_entity_by_name(session, dest)
                if target_entity is not None:
                    return self._handle_go_to(session, ParsedAction(intent=ActionIntent.GO_TO, raw_input=action.raw_input, target=dest))
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

        if moved and session.viewport and has_map:
            session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0],
                session.position[1],
                radius=session.viewport.fov_radius,
            )

        hostile_alert = ""
        if moved and session.spatial_index and session.viewport:
            nearby = session.spatial_index.in_radius(session.position[0], session.position[1], 5)
            hostiles = [entity for entity in nearby if entity.is_hostile() and entity.is_alive() and entity.id != "player"]
            if hostiles:
                names = ", ".join(entity.name for entity in hostiles)
                hostile_alert = f" You spot hostile creatures nearby: {names}!"

        direction_name = dest_lower if dest_lower in direction_deltas else dest
        px, py = session.position[0], session.position[1]
        narrative = f"You move {direction_name}. (Position: {px},{py})"
        if session.spatial_index:
            nearby = session.spatial_index.in_radius(px, py, 3)
            notable = [entity for entity in nearby if entity.id != "player" and entity.alive]
            if notable:
                names = ", ".join(entity.name for entity in notable[:3])
                narrative += f" You see {names} nearby."
        if hostile_alert:
            narrative += hostile_alert

        return ActionResult(
            narrative=narrative,
            scene_type=session.dm_context.scene_type,
            state_changes={"position": list(session.position)} if moved else {},
        )

    def _handle_go_to(self, session: GameSession, action: ParsedAction):
        from engine.api.game_engine import ActionResult

        target = (action.target or "").strip()
        if not target:
            return ActionResult(
                narrative="Go to whom? Specify an NPC or location name.",
                scene_type=session.dm_context.scene_type,
            )
        entity = self._find_entity_by_name(session, target)
        if entity is None:
            return self._handle_move(session, action)
        entity_id, entity_data = entity
        enc_penalty = self._encumbrance_penalty(session)
        if enc_penalty >= 999:
            return ActionResult(
                narrative="You're too overencumbered to move!",
                scene_type=session.dm_context.scene_type,
            )

        npc_name = entity_data.get("name", target)
        target_blocking = bool(entity_data.get("blocking", True))
        target_type = str(entity_data.get("type", "")).lower()
        interaction_radius = 2 if target_type in {"furniture", "building", "workstation"} or not target_blocking else 1
        steps_taken = 0
        refresh_count = 0
        blocked_reason: Optional[str] = None
        world_events: list[dict[str, object]] = []

        while steps_taken < 40:
            current_target = session.entities.get(entity_id)
            if current_target is None:
                blocked_reason = f"{npc_name} is no longer here."
                break
            if not current_target.get("alive", True):
                blocked_reason = f"{npc_name} can no longer respond to your approach."
                break

            target_pos = self._live_entity_position(session, entity_id, current_target.get("position", [0, 0]))
            if distance(session.position, target_pos) <= interaction_radius:
                blocked_reason = None
                break

            goal_candidates = self._approach_goal_candidates(
                session,
                target_pos,
                interaction_radius=interaction_radius,
                allow_target_tile=not target_blocking,
            )
            best_path: list[list[int]] = []
            blocked_positions = set()
            if session.spatial_index is not None:
                for blocker in session.spatial_index.all_entities():
                    if blocker.id in {"player", entity_id} or not blocker.blocking:
                        continue
                    blocked_positions.add(tuple(blocker.position))
            for candidate in goal_candidates:
                if candidate == session.position:
                    best_path = []
                    break
                candidate_path = astar_path(
                    session.map_data,
                    session.position,
                    candidate,
                    max_steps=40,
                    blocked_positions=blocked_positions,
                )
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

        if session.viewport and session.map_data:
            session.viewport.center_on(session.position[0], session.position[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                session.position[0],
                session.position[1],
                radius=session.viewport.fov_radius,
            )
        session.sync_player_state()
        target_pos = self._live_entity_position(session, entity_id, entity_data.get("position", [0, 0]))
        dist_remaining = distance(session.position, target_pos)
        refresh_note = " (New turn — AP refreshed)" if refresh_count else ""
        if dist_remaining <= interaction_radius:
            session.hold_entity_position(entity_id, turns=1)
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

    def _find_entity_by_name(self, session: GameSession, target_name: str) -> Optional[tuple]:
        if not target_name:
            return None
        target_lower = target_name.lower()
        for entity_id, entity in session.entities.items():
            if target_lower in entity.get("name", "").lower() or target_lower in entity.get("role", "").lower():
                return (entity_id, entity)
        return None

    def _check_entity_proximity(self, session: GameSession, target_name: str, action_type: str):
        from engine.api.game_engine import ActionResult

        found = self._find_entity_by_name(session, target_name)
        if found is None:
            return None
        entity_id, entity = found
        target_pos = self._live_entity_position(session, entity_id, entity.get("position", [0, 0]))
        ok, msg = check_proximity(session.position, target_pos, action_type)
        if not ok:
            return ActionResult(
                narrative=f"{msg} {entity['name']} is at position {target_pos}.",
                scene_type=session.dm_context.scene_type,
            )
        return None
