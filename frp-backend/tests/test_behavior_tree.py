"""Tests for engine.world.behavior_tree — NPC AI behavior tree nodes."""
import pytest
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds
from engine.world.schedules import NPCSchedule, TimePeriod, GameTime, hour_to_period
from engine.world.behavior_tree import (
    Status,
    BehaviorContext,
    BehaviorNode,
    PriorityNode,
    SequenceNode,
    ConditionNode,
    ActionNode,
    FleeNode,
    CombatNode,
    SatisfyNeedNode,
    FollowScheduleNode,
    PatrolNode,
    WanderNode,
    IdleNode,
    create_npc_behavior_tree,
)


# ── helpers ──────────────────────────────────────────────────────────

def _npc(x: int = 5, y: int = 5, needs: NPCNeeds = None, disposition: str = "neutral", **kw) -> Entity:
    return Entity(
        id="npc_test",
        entity_type=EntityType.NPC,
        name="TestNPC",
        position=(x, y),
        glyph="N",
        color="white",
        blocking=True,
        needs=needs,
        disposition=disposition,
        **kw,
    )


def _hostile(x: int = 6, y: int = 5) -> Entity:
    return Entity(
        id="hostile_01",
        entity_type=EntityType.CREATURE,
        name="Goblin",
        position=(x, y),
        glyph="g",
        color="red",
        blocking=True,
        disposition="hostile",
    )


def _ctx(entity: Entity = None, hostiles=None, game_time=None, **kw) -> BehaviorContext:
    if entity is None:
        entity = _npc()
    return BehaviorContext(entity=entity, hostiles=hostiles, game_time=game_time, **kw)


# ── Status enum ──────────────────────────────────────────────────────

class TestStatus:
    def test_values(self):
        assert Status.SUCCESS.value == "success"
        assert Status.FAILURE.value == "failure"
        assert Status.RUNNING.value == "running"


# ── Base nodes ───────────────────────────────────────────────────────

class TestConditionNode:
    def test_true_predicate(self):
        node = ConditionNode(lambda ctx: True)
        assert node.tick(_ctx()) == Status.SUCCESS

    def test_false_predicate(self):
        node = ConditionNode(lambda ctx: False)
        assert node.tick(_ctx()) == Status.FAILURE

    def test_checks_entity(self):
        node = ConditionNode(lambda ctx: ctx.entity.hp > 5)
        e = _npc()
        e.hp = 10
        assert node.tick(_ctx(entity=e)) == Status.SUCCESS
        e.hp = 3
        assert node.tick(_ctx(entity=e)) == Status.FAILURE


class TestActionNode:
    def test_action_returns_success(self):
        node = ActionNode(lambda ctx: Status.SUCCESS)
        assert node.tick(_ctx()) == Status.SUCCESS

    def test_action_returns_running(self):
        node = ActionNode(lambda ctx: Status.RUNNING)
        assert node.tick(_ctx()) == Status.RUNNING

    def test_action_sets_blackboard(self):
        def do_something(ctx):
            ctx.blackboard["did_it"] = True
            return Status.SUCCESS

        ctx = _ctx()
        ActionNode(do_something).tick(ctx)
        assert ctx.blackboard["did_it"] is True


class TestPriorityNode:
    def test_first_success_wins(self):
        p = PriorityNode([
            ConditionNode(lambda ctx: False),
            ActionNode(lambda ctx: Status.SUCCESS, name="Winner"),
            ActionNode(lambda ctx: Status.SUCCESS, name="Never"),
        ])
        assert p.tick(_ctx()) == Status.SUCCESS

    def test_all_fail(self):
        p = PriorityNode([
            ConditionNode(lambda ctx: False),
            ConditionNode(lambda ctx: False),
        ])
        assert p.tick(_ctx()) == Status.FAILURE

    def test_running_returned(self):
        p = PriorityNode([
            ConditionNode(lambda ctx: False),
            ActionNode(lambda ctx: Status.RUNNING),
        ])
        assert p.tick(_ctx()) == Status.RUNNING


class TestSequenceNode:
    def test_all_succeed(self):
        s = SequenceNode([
            ActionNode(lambda ctx: Status.SUCCESS),
            ActionNode(lambda ctx: Status.SUCCESS),
        ])
        assert s.tick(_ctx()) == Status.SUCCESS

    def test_first_failure_stops(self):
        called = []

        def track(name):
            def fn(ctx):
                called.append(name)
                return Status.SUCCESS if name != "fail" else Status.FAILURE
            return fn

        s = SequenceNode([
            ActionNode(track("a")),
            ActionNode(track("fail")),
            ActionNode(track("c")),
        ])
        assert s.tick(_ctx()) == Status.FAILURE
        assert "c" not in called


# ── FleeNode ─────────────────────────────────────────────────────────

class TestFleeNode:
    def test_flees_when_safety_low_and_hostile_nearby(self):
        needs = NPCNeeds(safety=10)
        e = _npc(x=5, y=5, needs=needs)
        h = _hostile(x=6, y=5)
        ctx = _ctx(entity=e, hostiles=[h])
        result = FleeNode(safety_threshold=20).tick(ctx)
        assert result == Status.SUCCESS
        assert ctx.blackboard["action"] == "flee"
        # Should flee away from hostile (hostile at x=6, npc at x=5 => flee to x=4)
        assert ctx.blackboard["target_pos"][0] < 5

    def test_no_flee_when_safety_ok(self):
        needs = NPCNeeds(safety=80)
        e = _npc(needs=needs)
        ctx = _ctx(entity=e, hostiles=[_hostile()])
        assert FleeNode(safety_threshold=20).tick(ctx) == Status.FAILURE

    def test_no_flee_when_no_hostiles(self):
        needs = NPCNeeds(safety=5)
        e = _npc(needs=needs)
        ctx = _ctx(entity=e, hostiles=[])
        assert FleeNode().tick(ctx) == Status.FAILURE

    def test_flee_without_needs_uses_disposition(self):
        e = _npc(disposition="afraid")
        ctx = _ctx(entity=e, hostiles=[_hostile()])
        assert FleeNode().tick(ctx) == Status.SUCCESS


# ── CombatNode ───────────────────────────────────────────────────────

class TestCombatNode:
    def test_attacks_adjacent_hostile(self):
        e = _npc(x=5, y=5)
        h = _hostile(x=6, y=5)  # distance 1
        ctx = _ctx(entity=e, hostiles=[h])
        result = CombatNode(attack_range=1).tick(ctx)
        assert result == Status.SUCCESS
        assert ctx.blackboard["action"] == "attack"
        assert ctx.blackboard["target"] is h

    def test_moves_toward_far_hostile(self):
        e = _npc(x=5, y=5)
        h = _hostile(x=10, y=5)  # distance 5
        ctx = _ctx(entity=e, hostiles=[h])
        result = CombatNode(attack_range=1).tick(ctx)
        assert result == Status.RUNNING
        assert ctx.blackboard["action"] == "move_toward_hostile"

    def test_no_combat_without_hostiles(self):
        ctx = _ctx(hostiles=[])
        assert CombatNode().tick(ctx) == Status.FAILURE


# ── SatisfyNeedNode ──────────────────────────────────────────────────

class TestSatisfyNeedNode:
    def test_triggers_when_need_low(self):
        needs = NPCNeeds(sustenance=10)
        e = _npc(needs=needs)
        ctx = _ctx(entity=e)
        result = SatisfyNeedNode("sustenance", threshold=15, satisfy_action="eat").tick(ctx)
        assert result == Status.SUCCESS
        assert ctx.blackboard["need"] == "sustenance"
        assert ctx.blackboard["satisfy_action"] == "eat"

    def test_no_trigger_when_need_ok(self):
        needs = NPCNeeds(sustenance=80)
        e = _npc(needs=needs)
        ctx = _ctx(entity=e)
        assert SatisfyNeedNode("sustenance", threshold=15).tick(ctx) == Status.FAILURE

    def test_fails_without_needs(self):
        e = _npc(needs=None)
        ctx = _ctx(entity=e)
        assert SatisfyNeedNode("sustenance").tick(ctx) == Status.FAILURE

    def test_fails_for_unknown_need(self):
        needs = NPCNeeds()
        e = _npc(needs=needs)
        ctx = _ctx(entity=e)
        assert SatisfyNeedNode("nonexistent_need").tick(ctx) == Status.FAILURE


# ── FollowScheduleNode ──────────────────────────────────────────────

class TestFollowScheduleNode:
    def test_follows_schedule(self):
        schedule = NPCSchedule(
            npc_id="npc_test",
            npc_name="TestNPC",
            locations={"morning": "shop", "evening": "tavern"},
        )
        game_time = GameTime(hour=9)  # morning
        e = _npc(schedule=schedule)
        ctx = _ctx(entity=e, game_time=game_time)
        result = FollowScheduleNode().tick(ctx)
        assert result == Status.SUCCESS
        assert ctx.blackboard["schedule_location"] == "shop"

    def test_fails_without_schedule(self):
        e = _npc(schedule=None)
        ctx = _ctx(entity=e, game_time=GameTime())
        assert FollowScheduleNode().tick(ctx) == Status.FAILURE

    def test_fails_without_game_time(self):
        schedule = NPCSchedule(npc_id="x", npc_name="X")
        e = _npc(schedule=schedule)
        ctx = _ctx(entity=e, game_time=None)
        assert FollowScheduleNode().tick(ctx) == Status.FAILURE


# ── PatrolNode ───────────────────────────────────────────────────────

class TestPatrolNode:
    def test_patrol_cycles_waypoints(self):
        schedule = NPCSchedule(
            npc_id="guard_1",
            npc_name="Guard",
            patrol_route=[[1, 1], [5, 1], [5, 5], [1, 5]],
        )
        e = _npc(schedule=schedule)
        ctx = _ctx(entity=e)

        result = PatrolNode().tick(ctx)
        assert result == Status.SUCCESS
        assert ctx.blackboard["action"] == "patrol"
        first_pos = ctx.blackboard["target_pos"]

        # Second tick advances to next waypoint
        ctx2 = _ctx(entity=e)
        PatrolNode().tick(ctx2)
        assert ctx2.blackboard["target_pos"] != first_pos

    def test_fails_without_patrol_route(self):
        schedule = NPCSchedule(npc_id="npc", npc_name="NPC")
        e = _npc(schedule=schedule)
        ctx = _ctx(entity=e)
        assert PatrolNode().tick(ctx) == Status.FAILURE

    def test_fails_without_schedule(self):
        e = _npc(schedule=None)
        ctx = _ctx(entity=e)
        assert PatrolNode().tick(ctx) == Status.FAILURE


# ── WanderNode ───────────────────────────────────────────────────────

class TestWanderNode:
    def test_wander_sets_action(self):
        e = _npc(x=10, y=10)
        # Run several times — at least one should succeed (random)
        successes = 0
        for _ in range(20):
            ctx = _ctx(entity=e)
            result = WanderNode().tick(ctx)
            if result == Status.SUCCESS:
                successes += 1
                assert ctx.blackboard["action"] == "wander"
                tx, ty = ctx.blackboard["target_pos"]
                # Should be within 1 tile of current position
                assert abs(tx - 10) <= 1
                assert abs(ty - 10) <= 1
        assert successes > 0  # at least some should succeed


# ── IdleNode ─────────────────────────────────────────────────────────

class TestIdleNode:
    def test_always_succeeds(self):
        ctx = _ctx()
        assert IdleNode().tick(ctx) == Status.SUCCESS
        assert ctx.blackboard["action"] == "idle"


# ── Factory function ─────────────────────────────────────────────────

class TestFactory:
    def test_create_basic_tree(self):
        tree = create_npc_behavior_tree(is_guard=False)
        assert isinstance(tree, PriorityNode)
        assert tree.name == "NPCBehavior"
        # Should have: Flee, Combat, CriticalNeeds, Schedule, ModerateNeeds, Wander, Idle
        assert len(tree.children) == 7

    def test_create_guard_tree(self):
        tree = create_npc_behavior_tree(is_guard=True)
        assert isinstance(tree, PriorityNode)
        # Should have extra PatrolNode
        assert len(tree.children) == 8
        patrol_found = any(isinstance(c, PatrolNode) for c in tree.children)
        assert patrol_found

    def test_idle_npc_idles(self):
        """NPC with all needs satisfied and no threats should idle."""
        needs = NPCNeeds(safety=80, sustenance=80, social=80, commerce=80, duty=80)
        e = _npc(needs=needs)
        tree = create_npc_behavior_tree()
        ctx = _ctx(entity=e, hostiles=[])
        result = tree.tick(ctx)
        assert result == Status.SUCCESS
        # Should fall through to wander or idle
        assert ctx.blackboard["action"] in ("wander", "idle")

    def test_threatened_npc_flees(self):
        """NPC with low safety and hostiles nearby should flee."""
        needs = NPCNeeds(safety=5)
        e = _npc(needs=needs)
        tree = create_npc_behavior_tree()
        ctx = _ctx(entity=e, hostiles=[_hostile()])
        tree.tick(ctx)
        assert ctx.blackboard["action"] == "flee"

    def test_hungry_npc_eats(self):
        """NPC with critically low sustenance should seek food."""
        needs = NPCNeeds(safety=80, sustenance=5, social=80, commerce=80, duty=80)
        e = _npc(needs=needs)
        tree = create_npc_behavior_tree()
        ctx = _ctx(entity=e, hostiles=[])
        tree.tick(ctx)
        assert ctx.blackboard["action"] == "satisfy_need"
        assert ctx.blackboard["need"] == "sustenance"
