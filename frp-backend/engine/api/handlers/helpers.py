"""Helper utility methods for GameEngine — mixin class."""
from __future__ import annotations

import copy
import random
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from engine.api.game_session import GameSession
from engine.core.character import Character
from engine.world.proximity import distance, astar_path, check_proximity
from engine.world.entity import Entity, EntityType
from engine.world.action_points import ACTION_COSTS
from engine.world.skill_checks import (
    roll_check,
    contested_check,
    SkillCheckResult,
    ability_modifier,
)
from engine.world.schedules import DEFAULT_SCHEDULES, NPCSchedule
from engine.world.npc_needs import NPCNeeds
from engine.world.body_parts import BodyPartTracker

if TYPE_CHECKING:
    from engine.api.game_engine import ActionResult

# Re-export constants needed by this mixin
from engine.api.game_engine import (
    NPC_VISUALS,
    WORKSTATION_SPECS,
    WORKSTATION_ANCHORS,
    ROLE_PRODUCTION,
    DEFAULT_NPC_ATTITUDE,
    DEFAULT_NPC_ALIGNMENT,
)


class HelperMixin:
    """Utility / helper methods used across multiple handler mixins."""

    # --- Encumbrance & Time ---

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

    # --- Skill Checks ---

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
        # Use game_engine module-level roll_check so test patches work
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

    def _npc_skill_bonus(self, entity: Dict[str, Any], skill: str) -> int:
        skill_lower = str(skill or "").lower().replace(" ", "_")
        if skill_lower in {"insight", "perception", "investigation"}:
            stat_key = Character.DND_SKILL_STATS.get(skill_lower, "INS")
            base = ability_modifier(int(entity.get("stats", {}).get(stat_key, 10)))
            legacy = int((entity.get("skills") or {}).get(skill_lower, 0))
            return base + legacy
        return int((entity.get("skills") or {}).get(skill_lower, 0))

    # --- AP & Skill Check Helpers ---

    def _check_ap(self, session: GameSession, cost_key: str) -> Optional["ActionResult"]:
        """Check if player has enough AP. Returns ActionResult on failure, None on success."""
        from engine.api.game_engine import ActionResult
        if session.ap_tracker is None:
            return None  # backward compat
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
        """Format a skill check result for narrative."""
        if result.critical == "success":
            return f"[NATURAL 20! Critical Success on {ability_name} check (DC {dc})]"
        elif result.critical == "failure":
            return f"[NATURAL 1! Critical Failure on {ability_name} check (DC {dc})]"
        elif result.success:
            return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Success by {result.margin}]"
        else:
            return f"[{ability_name} check: rolled {result.roll}+{result.modifier}={result.total} vs DC {dc} -- Failed by {abs(result.margin)}]"

    def _get_player_ability(self, session: GameSession, ability: str) -> int:
        """Get a player's ability score by abbreviation (MIG, AGI, etc.)."""
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
        # Use game_engine module-level roll_check so test patches work
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

    # --- AP simulation for long actions ---

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

    # --- Movement helpers ---

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

    # --- World event merging ---

    def _merge_world_events(self, session: GameSession, result: "ActionResult", world_events: List[Dict[str, Any]]) -> None:
        if not world_events:
            return
        result.state_changes.setdefault("world_events", []).extend(copy.deepcopy(world_events))
        messages: List[str] = []
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

    # --- Map / Scene helpers ---

    def _find_walkable_near(self, session: GameSession, cx: int, cy: int, radius: int = 5, min_dist: int = 2) -> list:
        """Find a walkable tile near (cx, cy) using map_data.

        min_dist: minimum distance from (cx, cy) — keeps a buffer zone around spawn.
        Falls back to random offset if no walkable tile found.
        """
        if session.map_data is not None:
            # Try positions in expanding rings, starting from min_dist
            for r in range(max(1, min_dist), radius + 1):
                candidates = []
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        if abs(dx) != r and abs(dy) != r:
                            continue  # only ring edges
                        nx, ny = cx + dx, cy + dy
                        if session.map_data.is_walkable(nx, ny):
                            if session.spatial_index is None or not session.spatial_index.blocking_at(nx, ny):
                                candidates.append([nx, ny])
                if candidates:
                    return random.choice(candidates)
            # If min_dist prevented finding anything, try again from ring 1
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
        # Fallback: random offset at min_dist
        return [cx + random.randint(-3, 3), cy + random.randint(-3, 3)]

    def _scene_anchor_positions(self, session: GameSession) -> Dict[str, List[int]]:
        if not session.map_data:
            px, py = session.position[0], session.position[1]
            return {name: [px, py] for name in {
                "home", "shop", "market_square", "tavern", "gate",
                "forge", "temple", "alley", "docks", "campfire",
            }}

        spawn_x, spawn_y = session.map_data.spawn_point
        offsets = {
            "home": (-6, -3),
            "shop": (5, -1),
            "market_square": (0, 4),
            "tavern": (6, 5),
            "gate": (0, -7),
            "forge": (8, 1),
            "temple": (-8, 1),
            "alley": (-6, 5),
            "docks": (9, 6),
            "campfire": (-4, 7),
        }
        anchors: Dict[str, List[int]] = {}
        for name, (dx, dy) in offsets.items():
            anchors[name] = self._find_walkable_near(session, spawn_x + dx, spawn_y + dy, radius=4)
        return anchors

    def _spawn_workstations(self, session: GameSession, anchors: Dict[str, List[int]]) -> None:
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

    def _populate_scene_entities(self, session: GameSession, location: str) -> None:
        """Populate session with NPC Entity objects in the spatial index, plus backward-compat dict."""
        session.entities = {}
        loc_lower = location.lower()
        anchors = self._scene_anchor_positions(session)

        # Define NPC archetypes by location type
        if any(w in loc_lower for w in ["tavern", "inn"]):
            roles = [("innkeeper", "merchant_guild"), ("merchant", "merchant_guild"),
                     ("guard", "harbor_guard"), ("quest_giver", "merchant_guild"),
                     ("beggar", "thieves_guild")]
        elif any(w in loc_lower for w in ["market", "harbor", "town", "city"]):
            roles = [("merchant", "merchant_guild"), ("innkeeper", "merchant_guild"),
                     ("guard", "harbor_guard"),
                     ("blacksmith", "mountain_dwarves"), ("beggar", "thieves_guild"),
                     ("priest", "temple_order")]
        elif any(w in loc_lower for w in ["forest", "road", "path"]):
            roles = [("spy", "thieves_guild"), ("guard", "harbor_guard")]
        else:
            roles = [("merchant", "merchant_guild"), ("guard", "harbor_guard")]

        for role, faction in roles:
            npc_id = f"{role}_{len(session.entities) + 1}"
            # Pick gender randomly
            gender = random.choice(["male", "female"])
            # Choose faction-appropriate name generation faction
            name_faction = "human"
            if faction == "mountain_dwarves":
                name_faction = "dwarf"
            elif faction == "forest_elves":
                name_faction = "elf"
            name = session.name_gen.generate_name(faction=name_faction, gender=gender, npc_id=npc_id)

            # Keep key NPCs reachable but NOT adjacent to spawn (min_dist=2 prevents blocking)
            if role in {"merchant", "innkeeper"}:
                pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=4, min_dist=1)
            else:
                role_anchor = {
                    "merchant": "shop",
                    "blacksmith": "forge",
                    "priest": "temple",
                    "quest_giver": "market_square",
                    "guard": "gate",
                    "beggar": "alley",
                    "spy": "alley",
                }.get(role)
                if role_anchor and role_anchor in anchors:
                    anchor_x, anchor_y = anchors[role_anchor]
                    pos = self._find_walkable_near(session, anchor_x, anchor_y, radius=6, min_dist=2)
                else:
                    pos = self._find_walkable_near(session, session.position[0], session.position[1], radius=10, min_dist=3)
            needs = NPCNeeds()

            # Determine glyph/color from NPC_VISUALS
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

            # Build NPC skills based on role
            npc_skills = {}
            if role == "guard":
                npc_skills = {"melee": 3, "patrol": 2}
            elif role == "merchant":
                npc_skills = {"trade": 4, "appraisal": 3}
            elif role == "blacksmith":
                npc_skills = {"smithing": 5, "trade": 2}
            elif role == "innkeeper":
                npc_skills = {"trade": 3, "cooking": 4}
            elif role == "healer":
                npc_skills = {"healing": 5, "herbalism": 3}
            elif role == "priest":
                npc_skills = {"healing": 3, "divine_magic": 4}

            # Create proper Entity object
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
                disposition="friendly" if role != "spy" else "neutral",
                attitude=DEFAULT_NPC_ATTITUDE.get(role, "indifferent"),
                alignment=DEFAULT_NPC_ALIGNMENT.get(role, "TN"),
                hp=12 if role == "guard" else 8,
                max_hp=12 if role == "guard" else 8,
            )

            # Add to spatial index
            if session.spatial_index is not None:
                session.spatial_index.add(entity)

            # Backward-compatible dict representation in session.entities
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
                "entity_ref": entity,  # reference to the Entity object
            }
            session.sync_entity_record(npc_id, entity)

        self._spawn_workstations(session, anchors)

    # --- Living World Helpers ---

    def _run_hourly_world_updates(self, session: GameSession, hour_marker: int, events: List[Dict[str, Any]]) -> None:
        for entity in session.entities.values():
            role = entity.get("role")
            for recipe_key in ROLE_PRODUCTION.get(role, ()):
                try:
                    session.location_stock.produce(recipe_key)
                except Exception:
                    continue

        caravan_events = session.caravan_manager.tick(hour_marker)
        for ce in caravan_events:
            if ce.get("type") == "arrival" and ce.get("goods_delivered"):
                for item, qty in ce["goods_delivered"].items():
                    session.location_stock.add_stock(item, qty)
                ce = dict(ce)
                ce["type"] = "caravan_arrival"
            events.append(ce)

        session.rumor_network.decay(hours=1.0)
        session.rumor_network.prune_expired()
