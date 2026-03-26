"""World bootstrap and runtime helper methods for GameEngine mixins."""
from __future__ import annotations

import copy
import random
from typing import TYPE_CHECKING, Any

from engine.api.game_session import GameSession
from engine.data_loader import (
    get_role_anchor_map,
    get_role_skill_profiles,
    get_role_stats,
    get_scene_anchor_offsets,
    get_scene_role_sets,
)
from engine.world.body_parts import BodyPartTracker
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds
from engine.world.proximity import astar_path, distance, manhattan_distance
from engine.world.schedules import DEFAULT_SCHEDULES, NPCSchedule

from engine.api.runtime_constants import (
    DEFAULT_NPC_ALIGNMENT,
    DEFAULT_NPC_ATTITUDE,
    NPC_VISUALS,
    ROLE_PRODUCTION,
    WORKSTATION_ANCHORS,
    WORKSTATION_SPECS,
)

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult


class HelperWorldMixin:
    """Focused helpers for scene population, pathing support, and world ticking."""

    def _scene_roles_for_location(self, location: str) -> list[dict[str, Any]]:
        loc_lower = location.lower()
        scene_role_sets = get_scene_role_sets()
        if any(word in loc_lower for word in ["tavern", "inn"]):
            return list(scene_role_sets.get("tavern_inn", []))
        if any(word in loc_lower for word in ["market", "harbor", "town", "city"]):
            return list(scene_role_sets.get("settlement", []))
        if any(word in loc_lower for word in ["forest", "road", "path"]):
            return list(scene_role_sets.get("road_wilds", []))
        return list(scene_role_sets.get("default", []))

    def _step_toward(self, start: tuple, target: tuple) -> tuple:
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
        return (start[0] + step_x, start[1] + step_y)

    def _move_entity_if_possible(self, session: GameSession, entity: Entity, target_pos: tuple) -> bool:
        if tuple(entity.position) == tuple(target_pos):
            return False
        tx, ty = target_pos
        if session.map_data and not session.map_data.is_walkable(tx, ty):
            return False
        if session.spatial_index and session.spatial_index.blocking_at(tx, ty):
            blockers = [candidate for candidate in session.spatial_index.at(tx, ty) if candidate.id != entity.id and candidate.blocking]
            if blockers:
                return False
        if session.spatial_index:
            session.spatial_index.move(entity, tx, ty)
        else:
            entity.move_to(tx, ty)
        return True

    def _merge_world_events(self, session: GameSession, result: "ActionResult", world_events: list[dict[str, Any]]) -> None:
        if not world_events:
            return
        result.state_changes.setdefault("world_events", []).extend(copy.deepcopy(world_events))
        messages: list[str] = []
        for event in world_events:
            event_type = event.get("type")
            if event_type == "quest_complete":
                messages.append(
                    f"Quest complete: {event.get('title', event.get('quest_id', 'Unknown quest'))}. "
                    f"+{event.get('reward_gold', 0)} gold, +{event.get('reward_xp', 0)} XP."
                )
            elif event.get("hours_remaining") is not None:
                messages.append(
                    f"Reminder: {event.get('title', event.get('quest_id', 'A quest'))} has "
                    f"{event.get('hours_remaining')} hours remaining."
                )
            elif event.get("consequence"):
                messages.append(f"Quest failed: {event.get('title', event.get('quest_id', 'Unknown quest'))}.")
            elif event_type == "caravan_arrival":
                messages.append("A caravan arrives and local merchants restock their wares.")
        if messages:
            result.narrative = f"{result.narrative}\n" + "\n".join(messages)

    def _find_walkable_near(self, session: GameSession, cx: int, cy: int, radius: int = 5, min_dist: int = 2) -> list[int]:
        if session.map_data is not None:
            for r in range(max(1, min_dist), radius + 1):
                candidates = []
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if abs(dx) != r and abs(dy) != r:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if session.map_data.is_walkable(nx, ny):
                            if session.spatial_index is None or not session.spatial_index.blocking_at(nx, ny):
                                candidates.append([nx, ny])
                if candidates:
                    return random.choice(candidates)
            if min_dist > 1:
                for r in range(1, min_dist):
                    candidates = []
                    for dx in range(-r, r + 1):
                        for dy in range(-r, r + 1):
                            if abs(dx) != r and abs(dy) != r:
                                continue
                            nx, ny = cx + dx, cy + dy
                            if session.map_data.is_walkable(nx, ny):
                                if session.spatial_index is None or not session.spatial_index.blocking_at(nx, ny):
                                    candidates.append([nx, ny])
                    if candidates:
                        return random.choice(candidates)
        return [cx + random.randint(-3, 3), cy + random.randint(-3, 3)]

    def _scene_anchor_positions(self, session: GameSession) -> dict[str, list[int]]:
        anchor_offsets = get_scene_anchor_offsets()
        if not session.map_data:
            px, py = session.position[0], session.position[1]
            return {name: [px, py] for name in anchor_offsets}

        spawn_x, spawn_y = session.map_data.spawn_point
        anchors: dict[str, list[int]] = {}
        for name, (dx, dy) in anchor_offsets.items():
            anchors[name] = self._find_walkable_near(session, spawn_x + dx, spawn_y + dy, radius=4)
        return anchors

    def _spawn_workstations(self, session: GameSession, anchors: dict[str, list[int]]) -> None:
        if session.spatial_index is None:
            return
        existing = {entity.id for entity in session.spatial_index.all_entities()}
        for workstation_id, spec in WORKSTATION_SPECS.items():
            entity_id = f"workstation_{workstation_id}"
            if entity_id in existing:
                continue
            anchor_name = WORKSTATION_ANCHORS.get(workstation_id, "shop")
            pos = anchors.get(anchor_name, list(session.position))
            entity = Entity(
                id=entity_id,
                entity_type=EntityType.FURNITURE,
                name=spec["name"],
                position=tuple(pos),
                glyph=spec["glyph"],
                color=spec["color"],
                blocking=False,
                inventory=[{"workstation": workstation_id}],
            )
            session.spatial_index.add(entity)
            session.entities[entity_id] = {
                "name": spec["name"],
                "type": entity.entity_type.value,
                "position": list(pos),
                "role": workstation_id,
                "faction": "utility",
                "blocking": entity.blocking,
                "alive": True,
                "glyph": spec["glyph"],
                "color": spec["color"],
                "entity_ref": entity,
            }

    def _stabilize_opening_position(self, session: GameSession, location: str) -> None:
        if session.player_entity is None or session.spatial_index is None:
            return

        def openness(candidate: list[int]) -> int:
            score = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nx, ny = candidate[0] + dx, candidate[1] + dy
                if session.map_data is not None and not session.map_data.is_walkable(nx, ny):
                    continue
                blockers = [
                    blocker
                    for blocker in session.spatial_index.at(nx, ny)
                    if blocker.id != "player" and blocker.blocking
                ]
                if blockers:
                    continue
                score += 1
            return score

        workstation_positions = [
            entity.get("position", [])
            for entity in session.entities.values()
            if entity.get("type") == "furniture"
        ]

        def reachable_workstations(candidate: list[int]) -> int:
            if session.map_data is None:
                return 0
            reachable = 0
            for destination in workstation_positions:
                if not isinstance(destination, list) or len(destination) < 2:
                    continue
                path = astar_path(session.map_data, candidate, destination, max_steps=80)
                if path:
                    reachable += 1
            return reachable

        priority_roles = [str(entry.get("role", "")).strip().lower() for entry in self._scene_roles_for_location(location) if entry.get("role")]
        priority_targets = [(entity_id, entity) for preferred_role in priority_roles for entity_id, entity in session.entities.items() if entity.get("role") == preferred_role]
        if not priority_targets: return
        candidate_positions: dict[tuple[int, int], list[int]] = {}
        for entity_id, entity in priority_targets:
            target_pos = self._live_entity_position(session, entity_id, entity.get("position", [0, 0]))
            for candidate in self._approach_goal_candidates(session, target_pos, interaction_radius=2):
                candidate_positions[(candidate[0], candidate[1])] = candidate
        if not candidate_positions: return

        def priority_score(candidate: list[int]) -> tuple[int, int, int, int, int, int, int]:
            anchor_nearby = 0
            nearby_roles = 0
            anchor_distances = [99, 99]
            for idx, (entity_id, entity) in enumerate(priority_targets):
                target_pos = self._live_entity_position(session, entity_id, entity.get("position", [0, 0]))
                target_distance = int(distance(candidate, target_pos))
                if idx < len(anchor_distances):
                    anchor_distances[idx] = target_distance
                    if target_distance <= 2:
                        anchor_nearby += 1
                if target_distance <= 2:
                    nearby_roles += 1
            return (
                anchor_nearby,
                nearby_roles,
                -anchor_distances[0],
                -anchor_distances[1],
                reachable_workstations(candidate),
                openness(candidate),
                -manhattan_distance(session.position, candidate),
            )

        best_pos = max(candidate_positions.values(), key=priority_score)
        self._move_entity_if_possible(session, session.player_entity, tuple(best_pos))
        session.position = list(best_pos)
        if session.viewport is not None and session.map_data is not None:
            session.viewport.center_on(best_pos[0], best_pos[1])
            session.viewport.compute_fov(
                lambda x, y: not session.map_data.is_walkable(x, y),
                best_pos[0],
                best_pos[1],
                radius=session.viewport.fov_radius,
            )
        for entity_id, entity in priority_targets:
            target_pos = self._live_entity_position(session, entity_id, entity.get("position", [0, 0]))
            if distance(best_pos, target_pos) <= 2: session.hold_entity_position(entity_id, turns=1)

    def _ensure_scene_accessibility(self, session: GameSession) -> None:
        if session.map_data is None or session.spatial_index is None:
            return

        def blocked_positions(excluded_id: str) -> set[tuple[int, int]]:
            blocked = set()
            for blocker in session.spatial_index.all_entities():
                if blocker.id in {"player", excluded_id} or not blocker.blocking:
                    continue
                blocked.add(tuple(blocker.position))
            return blocked

        def is_reachable(entity_id: str, entity: dict[str, Any]) -> bool:
            position = entity.get("position", [0, 0])
            if entity.get("type") == "furniture":
                return bool(
                    astar_path(
                        session.map_data,
                        session.position,
                        position,
                        max_steps=80,
                        blocked_positions=blocked_positions(entity_id),
                    )
                )
            target_pos = self._live_entity_position(session, entity_id, position)
            candidates = self._approach_goal_candidates(session, target_pos)
            for candidate in candidates:
                if candidate == session.position:
                    return True
                path = astar_path(
                    session.map_data,
                    session.position,
                    candidate,
                    max_steps=80,
                    blocked_positions=blocked_positions(entity_id),
                )
                if path:
                    return True
            return False

        for entity_id, entity in list(session.entities.items()):
            role = entity.get("role")
            entity_type = entity.get("type")
            if entity_type != "furniture" and role not in {"merchant", "guard", "blacksmith", "priest", "beggar", "innkeeper"}:
                continue
            if is_reachable(entity_id, entity):
                continue
            new_pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=8, min_dist=2)
            entity["position"] = list(new_pos)
            live_entity = entity.get("entity_ref")
            if live_entity is not None:
                session.spatial_index.move(live_entity, new_pos[0], new_pos[1])
                session.sync_entity_record(entity_id, live_entity)

    def _populate_scene_entities(self, session: GameSession, location: str) -> None:
        session.entities = {}
        anchors = self._scene_anchor_positions(session)

        roles = [
            (str(entry["role"]), str(entry["faction"]))
            for entry in self._scene_roles_for_location(location)
            if entry.get("role") and entry.get("faction")
        ]

        for role, faction in roles:
            npc_id = f"{role}_{len(session.entities) + 1}"
            gender = random.choice(["male", "female"])
            name_faction = "human"
            if faction == "mountain_dwarves":
                name_faction = "dwarf"
            elif faction == "forest_elves":
                name_faction = "elf"
            name = session.name_gen.generate_name(faction=name_faction, gender=gender, npc_id=npc_id)

            if role in {"merchant", "innkeeper"}:
                pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=4, min_dist=2)
            else:
                role_anchor = get_role_anchor_map().get(role)
                if role_anchor and role_anchor in anchors:
                    anchor_x, anchor_y = anchors[role_anchor]
                    pos = self._find_walkable_near(session, anchor_x, anchor_y, radius=6, min_dist=2)
                else:
                    pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=10, min_dist=3)
            needs = NPCNeeds()

            glyph, color = NPC_VISUALS.get(role, ("?", "white"))
            body = BodyPartTracker()
            schedule_data = DEFAULT_SCHEDULES.get(role, DEFAULT_SCHEDULES["merchant"])
            schedule_positions = {
                period: list(anchors.get(place, pos))
                for period, place in schedule_data.items()
            }
            patrol_route = None
            if role == "guard":
                patrol_route = [
                    list(anchors.get("gate", pos)),
                    list(anchors.get("market_square", pos)),
                    list(anchors.get("tavern", pos)),
                    list(anchors.get("gate", pos)),
                ]
            schedule = NPCSchedule(
                npc_id=npc_id,
                npc_name=name,
                locations=dict(schedule_data),
                positions=schedule_positions,
                patrol_route=patrol_route,
            )

            npc_skills = dict(get_role_skill_profiles().get(role, {}))
            role_stats = get_role_stats()
            stat_profile = dict(role_stats.get("default", {}))
            stat_profile.update(role_stats.get(role, {}))
            disposition = stat_profile.get("disposition", "friendly")
            hp_value = int(stat_profile.get("hp", 8))
            max_hp_value = int(stat_profile.get("max_hp", hp_value))

            entity = Entity(
                id=npc_id,
                entity_type=EntityType.NPC,
                name=name,
                position=tuple(pos),
                glyph=glyph,
                color=color,
                blocking=True,
                needs=needs,
                skills=npc_skills if npc_skills else None,
                body=body,
                faction=faction,
                schedule=schedule,
                job=role,
                disposition=disposition,
                attitude=DEFAULT_NPC_ATTITUDE.get(role, "indifferent"),
                alignment=DEFAULT_NPC_ALIGNMENT.get(role, "TN"),
                hp=hp_value,
                max_hp=max_hp_value,
            )

            if session.spatial_index is not None:
                session.spatial_index.add(entity)

            session.entities[npc_id] = {
                "name": name,
                "type": "npc",
                "position": list(pos),
                "faction": faction,
                "role": role,
                "needs": needs,
                "body": body,
                "schedule": schedule,
                "gender": gender,
                "hp": entity.hp,
                "max_hp": entity.max_hp,
                "alive": entity.alive,
                "blocking": entity.blocking,
                "attitude": entity.attitude,
                "alignment": entity.alignment,
                "alignment_axes": dict(getattr(entity, "alignment_axes", {}) or {}),
                "entity_ref": entity,
            }
            session.sync_entity_record(npc_id, entity)

        self._spawn_workstations(session, anchors)
        self._ensure_scene_accessibility(session)
        self._stabilize_opening_position(session, location)

    def _run_hourly_world_updates(self, session: GameSession, hour_marker: int, events: list[dict[str, Any]]) -> None:
        for entity in session.entities.values():
            role = entity.get("role")
            for recipe_key in ROLE_PRODUCTION.get(role, ()):
                try:
                    session.location_stock.produce(recipe_key)
                except Exception:
                    continue

        caravan_events = session.caravan_manager.tick(hour_marker)
        for caravan_event in caravan_events:
            if caravan_event.get("type") == "arrival" and caravan_event.get("goods_delivered"):
                for item, qty in caravan_event["goods_delivered"].items():
                    session.location_stock.add_stock(item, qty)
                caravan_event = dict(caravan_event)
                caravan_event["type"] = "caravan_arrival"
            events.append(caravan_event)

        session.rumor_network.decay(hours=1.0)
        session.rumor_network.prune_expired()
