"""
Ember RPG -- NPC Behavior Tree (Sprint 1, FR-04 / Section 5.3)

Rimworld-inspired ThinkTree for NPC AI decision-making.
Nodes return SUCCESS, FAILURE, or RUNNING.
Priority nodes try children top-to-bottom, first non-FAILURE wins.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine.world.entity import Entity, EntityType


class Status(Enum):
    """Behavior tree tick result."""
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BehaviorContext:
    """
    Shared context passed to every node during a tick.

    Contains everything an NPC needs to make decisions:
    the entity itself, references to the spatial index,
    game time, and a scratch pad for inter-node communication.
    """

    def __init__(
        self,
        entity: Entity,
        *,
        spatial_index: Any = None,
        game_time: Any = None,
        map_data: Any = None,
        hostiles: Optional[List[Entity]] = None,
        friendlies: Optional[List[Entity]] = None,
        blackboard: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.entity = entity
        self.spatial_index = spatial_index
        self.game_time = game_time
        self.map_data = map_data
        self.hostiles = hostiles or []
        self.friendlies = friendlies or []
        self.blackboard: Dict[str, Any] = blackboard or {}


# ======================================================================
# Base node classes
# ======================================================================

class BehaviorNode(ABC):
    """Abstract base for all behavior tree nodes."""

    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def tick(self, ctx: BehaviorContext) -> Status:
        """Evaluate this node and return a Status."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"


class PriorityNode(BehaviorNode):
    """
    Tries children in order. Returns the first non-FAILURE result.
    If all children fail, returns FAILURE.
    """

    def __init__(self, children: List[BehaviorNode], name: str = "Priority") -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: BehaviorContext) -> Status:
        for child in self.children:
            result = child.tick(ctx)
            if result != Status.FAILURE:
                return result
        return Status.FAILURE


class SequenceNode(BehaviorNode):
    """
    Runs children in order. Returns FAILURE on first failure.
    Returns SUCCESS only if all children succeed.
    """

    def __init__(self, children: List[BehaviorNode], name: str = "Sequence") -> None:
        super().__init__(name)
        self.children = children

    def tick(self, ctx: BehaviorContext) -> Status:
        for child in self.children:
            result = child.tick(ctx)
            if result != Status.SUCCESS:
                return result
        return Status.SUCCESS


class ConditionNode(BehaviorNode):
    """
    Checks a predicate. Returns SUCCESS if True, FAILURE if False.
    """

    def __init__(self, predicate: Callable[[BehaviorContext], bool], name: str = "Condition") -> None:
        super().__init__(name)
        self.predicate = predicate

    def tick(self, ctx: BehaviorContext) -> Status:
        return Status.SUCCESS if self.predicate(ctx) else Status.FAILURE


class ActionNode(BehaviorNode):
    """
    Performs an action. The action callable returns a Status.
    """

    def __init__(self, action: Callable[[BehaviorContext], Status], name: str = "Action") -> None:
        super().__init__(name)
        self.action = action

    def tick(self, ctx: BehaviorContext) -> Status:
        return self.action(ctx)


# ======================================================================
# Pre-built NPC behavior nodes (from PRD Section 5.3)
# ======================================================================

class FleeNode(BehaviorNode):
    """
    Flee if safety need < threshold AND hostile is nearby.
    Picks direction away from nearest hostile and attempts to move.
    """

    def __init__(self, safety_threshold: float = 20.0, name: str = "Flee") -> None:
        super().__init__(name)
        self.safety_threshold = safety_threshold

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity

        # Check safety need
        if entity.needs is not None:
            if entity.needs.safety >= self.safety_threshold:
                return Status.FAILURE
        elif entity.disposition != "afraid":
            return Status.FAILURE

        # Must have hostiles nearby
        if not ctx.hostiles:
            return Status.FAILURE

        # Find nearest hostile
        nearest = min(
            ctx.hostiles,
            key=lambda h: max(
                abs(h.position[0] - entity.position[0]),
                abs(h.position[1] - entity.position[1]),
            ),
        )

        # Compute flee direction (away from hostile)
        dx = entity.position[0] - nearest.position[0]
        dy = entity.position[1] - nearest.position[1]

        # Normalise to single step
        move_x = (1 if dx > 0 else -1) if dx != 0 else 0
        move_y = (1 if dy > 0 else -1) if dy != 0 else 0

        new_x = entity.position[0] + move_x
        new_y = entity.position[1] + move_y

        ctx.blackboard["action"] = "flee"
        ctx.blackboard["target_pos"] = (new_x, new_y)
        return Status.SUCCESS


class CombatNode(BehaviorNode):
    """
    Engage in combat if hostile player/creature is within range.
    """

    def __init__(self, attack_range: int = 1, name: str = "Combat") -> None:
        super().__init__(name)
        self.attack_range = attack_range

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        if not ctx.hostiles:
            return Status.FAILURE

        # Find closest hostile within attack range
        for hostile in ctx.hostiles:
            dist = max(
                abs(hostile.position[0] - entity.position[0]),
                abs(hostile.position[1] - entity.position[1]),
            )
            if dist <= self.attack_range:
                ctx.blackboard["action"] = "attack"
                ctx.blackboard["target"] = hostile
                return Status.SUCCESS

        # Hostiles exist but out of range — move toward nearest
        nearest = min(
            ctx.hostiles,
            key=lambda h: max(
                abs(h.position[0] - entity.position[0]),
                abs(h.position[1] - entity.position[1]),
            ),
        )
        dx = nearest.position[0] - entity.position[0]
        dy = nearest.position[1] - entity.position[1]
        move_x = (1 if dx > 0 else -1) if dx != 0 else 0
        move_y = (1 if dy > 0 else -1) if dy != 0 else 0
        ctx.blackboard["action"] = "move_toward_hostile"
        ctx.blackboard["target_pos"] = (
            entity.position[0] + move_x,
            entity.position[1] + move_y,
        )
        return Status.RUNNING


class SatisfyNeedNode(BehaviorNode):
    """
    If a specific need is below threshold, attempt to satisfy it.
    Sets blackboard action to "satisfy_need" with the need name.
    """

    def __init__(
        self,
        need_name: str,
        threshold: float = 15.0,
        satisfy_action: str = "seek",
        name: str = "",
    ) -> None:
        super().__init__(name or f"SatisfyNeed({need_name})")
        self.need_name = need_name
        self.threshold = threshold
        self.satisfy_action = satisfy_action

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        if entity.needs is None:
            return Status.FAILURE

        current = getattr(entity.needs, self.need_name, None)
        if current is None:
            return Status.FAILURE

        if current >= self.threshold:
            return Status.FAILURE

        ctx.blackboard["action"] = "satisfy_need"
        ctx.blackboard["need"] = self.need_name
        ctx.blackboard["satisfy_action"] = self.satisfy_action
        return Status.SUCCESS


class FollowScheduleNode(BehaviorNode):
    """
    Follow the NPC's daily schedule based on current game time.
    Checks the schedule for the current time period and sets a move target.
    """

    def __init__(self, name: str = "FollowSchedule") -> None:
        super().__init__(name)

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        if entity.schedule is None or ctx.game_time is None:
            return Status.FAILURE

        schedule = entity.schedule
        game_time = ctx.game_time

        # Try to get scheduled location
        try:
            from engine.world.schedules import hour_to_period
            period = hour_to_period(game_time.hour if hasattr(game_time, 'hour') else 8)
            location = schedule.get_location(period) if hasattr(schedule, 'get_location') else None
        except (ImportError, AttributeError):
            location = None

        if location is None:
            return Status.FAILURE

        ctx.blackboard["action"] = "follow_schedule"
        ctx.blackboard["schedule_location"] = location
        return Status.SUCCESS


class PatrolNode(BehaviorNode):
    """
    Follow a patrol route. Guards cycle through waypoints.
    """

    def __init__(self, name: str = "Patrol") -> None:
        super().__init__(name)

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        if entity.schedule is None:
            return Status.FAILURE

        schedule = entity.schedule
        if not hasattr(schedule, 'patrol_route') or not schedule.patrol_route:
            return Status.FAILURE

        next_pos = schedule.next_patrol_position()
        if next_pos is None:
            return Status.FAILURE

        ctx.blackboard["action"] = "patrol"
        ctx.blackboard["target_pos"] = tuple(next_pos)
        return Status.SUCCESS


class WanderNode(BehaviorNode):
    """
    Random movement within a small radius of current position.
    """

    def __init__(self, wander_radius: int = 3, name: str = "Wander") -> None:
        super().__init__(name)
        self.wander_radius = wander_radius

    def tick(self, ctx: BehaviorContext) -> Status:
        entity = ctx.entity
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)

        if dx == 0 and dy == 0:
            return Status.FAILURE  # didn't actually move

        new_x = entity.position[0] + dx
        new_y = entity.position[1] + dy

        ctx.blackboard["action"] = "wander"
        ctx.blackboard["target_pos"] = (new_x, new_y)
        return Status.SUCCESS


class IdleNode(BehaviorNode):
    """
    Do nothing. Always succeeds. The fallback behavior.
    """

    def __init__(self, name: str = "Idle") -> None:
        super().__init__(name)

    def tick(self, ctx: BehaviorContext) -> Status:
        ctx.blackboard["action"] = "idle"
        return Status.SUCCESS


# ======================================================================
# Factory: create a standard NPC behavior tree
# ======================================================================

def create_npc_behavior_tree(is_guard: bool = False) -> PriorityNode:
    """
    Build the standard NPC behavior tree from PRD Section 5.3:

    Priority:
      1. Flee (safety < 20 AND hostile nearby)
      2. Combat (hostile in range)
      3. Satisfy critical need (sustenance < 15, safety < 15)
      4. Follow schedule
      5. Satisfy moderate need (social < 40, commerce < 40)
      6. Patrol (guards only)
      7. Wander
      8. Idle
    """
    children: List[BehaviorNode] = [
        FleeNode(safety_threshold=20.0),
        CombatNode(attack_range=1),
        # Critical needs
        PriorityNode([
            SatisfyNeedNode("sustenance", threshold=15.0, satisfy_action="eat"),
            SatisfyNeedNode("safety", threshold=15.0, satisfy_action="seek_safety"),
        ], name="SatisfyCriticalNeed"),
        FollowScheduleNode(),
        # Moderate needs
        PriorityNode([
            SatisfyNeedNode("social", threshold=40.0, satisfy_action="socialize"),
            SatisfyNeedNode("commerce", threshold=40.0, satisfy_action="trade"),
        ], name="SatisfyModerateNeed"),
    ]

    if is_guard:
        children.append(PatrolNode())

    children.append(WanderNode())
    children.append(IdleNode())

    return PriorityNode(children, name="NPCBehavior")
