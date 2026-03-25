"""
Ember RPG - Phase 6: Campaign Generator Tests
"""
import pytest
from engine.campaign import (
    Quest, QuestObjective, QuestStatus, QuestType,
    WorldEvent, EventType, StoryArc,
    CampaignGenerator, CampaignManager
)


class TestQuestObjective:
    def test_initial_state(self):
        obj = QuestObjective("Kill 3 goblins", "goblin", 3)
        assert obj.current_count == 0
        assert obj.completed is False

    def test_progress_increments(self):
        obj = QuestObjective("Kill 3 goblins", "goblin", 3)
        obj.progress(1)
        assert obj.current_count == 1

    def test_progress_returns_true_on_complete(self):
        obj = QuestObjective("Kill 1 goblin", "goblin", 1)
        result = obj.progress(1)
        assert result is True
        assert obj.completed is True

    def test_progress_returns_false_if_not_complete(self):
        obj = QuestObjective("Kill 3 goblins", "goblin", 3)
        result = obj.progress(1)
        assert result is False

    def test_progress_clamped_at_required(self):
        obj = QuestObjective("Kill 2 goblins", "goblin", 2)
        obj.progress(5)
        assert obj.current_count == 2

    def test_progress_ignores_if_already_complete(self):
        obj = QuestObjective("Kill 1 goblin", "goblin", 1)
        obj.progress(1)
        result = obj.progress(1)
        assert result is False

    def test_progress_text(self):
        obj = QuestObjective("Kill goblins", "goblin", 3)
        obj.progress(2)
        assert obj.progress_text() == "2/3"


class TestQuest:
    def _make_quest(self):
        return Quest(
            id="q001",
            title="Test Quest",
            description="A test.",
            quest_type=QuestType.KILL,
            giver="Elder",
            objectives=[QuestObjective("Kill goblin", "goblin", 1)],
            rewards={"gold": 50, "xp": 100},
        )

    def test_initial_available(self):
        q = self._make_quest()
        assert q.status == QuestStatus.AVAILABLE

    def test_activate(self):
        q = self._make_quest()
        q.activate()
        assert q.status == QuestStatus.ACTIVE

    def test_activate_only_from_available(self):
        q = self._make_quest()
        q.status = QuestStatus.COMPLETED
        q.activate()
        assert q.status == QuestStatus.COMPLETED  # Not changed

    def test_is_complete_false(self):
        q = self._make_quest()
        assert q.is_complete() is False

    def test_is_complete_true(self):
        q = self._make_quest()
        q.objectives[0].progress(1)
        assert q.is_complete() is True

    def test_complete_returns_rewards(self):
        q = self._make_quest()
        rewards = q.complete()
        assert rewards["gold"] == 50
        assert rewards["xp"] == 100
        assert q.status == QuestStatus.COMPLETED

    def test_fail(self):
        q = self._make_quest()
        q.fail()
        assert q.status == QuestStatus.FAILED

    def test_summary(self):
        q = self._make_quest()
        q.activate()
        summary = q.summary()
        assert "ACTIVE" in summary
        assert "Test Quest" in summary


class TestWorldEvent:
    def _make_event(self):
        return WorldEvent(
            event_type=EventType.AMBUSH,
            title="Ambush",
            description="You're surrounded!",
            options=["Fight", "Flee"],
            outcomes={0: "Victory!", 1: "Escaped!"},
        )

    def test_trigger(self):
        e = self._make_event()
        desc = e.trigger()
        assert e.triggered is True
        assert desc == "You're surrounded!"

    def test_resolve_fight(self):
        e = self._make_event()
        result = e.resolve(0)
        assert result == "Victory!"

    def test_resolve_flee(self):
        e = self._make_event()
        result = e.resolve(1)
        assert result == "Escaped!"

    def test_resolve_unknown_option(self):
        e = self._make_event()
        result = e.resolve(99)
        assert isinstance(result, str)


class TestStoryArc:
    def _make_arc(self):
        q1 = Quest(id="q1", title="Q1", description="", quest_type=QuestType.KILL,
                   giver="NPC", objectives=[QuestObjective("Kill", "goblin", 1)],
                   status=QuestStatus.ACTIVE)
        q2 = Quest(id="q2", title="Q2", description="", quest_type=QuestType.FETCH,
                   giver="NPC", objectives=[QuestObjective("Fetch", "item", 1)])
        return StoryArc(id="arc1", title="Test Arc", premise="A story.", quests=[q1, q2])

    def test_current_quest(self):
        arc = self._make_arc()
        assert arc.current_quest().id == "q1"

    def test_advance_moves_to_next(self):
        arc = self._make_arc()
        arc.advance()
        assert arc.current_quest_idx == 1

    def test_advance_returns_next_quest(self):
        arc = self._make_arc()
        next_q = arc.advance()
        assert next_q.id == "q2"

    def test_advance_past_end_completes_arc(self):
        arc = self._make_arc()
        arc.advance()
        result = arc.advance()
        assert result is None
        assert arc.completed is True

    def test_random_event(self):
        import random
        arc = self._make_arc()
        event = WorldEvent(
            event_type=EventType.DISCOVERY,
            title="Find",
            description="Found something.",
        )
        arc.world_events = [event]
        rng = random.Random(1)
        e = arc.random_event(rng)
        assert e is not None
        assert e.triggered is True

    def test_random_event_none_when_all_triggered(self):
        import random
        arc = self._make_arc()
        arc.world_events = []
        rng = random.Random(1)
        e = arc.random_event(rng)
        assert e is None


class TestCampaignGenerator:
    def test_generate_arc(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(num_quests=3)
        assert isinstance(arc, StoryArc)
        assert arc.id.startswith("arc_")
        assert len(arc.quests) == 3

    def test_generate_arc_has_premise(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc()
        assert len(arc.premise) > 0

    def test_generate_arc_first_quest_active(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(num_quests=3)
        assert arc.quests[0].status == QuestStatus.ACTIVE

    def test_generate_arc_custom_title(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(title="My Arc")
        assert arc.title == "My Arc"

    def test_generate_arc_has_world_events(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc()
        assert len(arc.world_events) > 0

    def test_generate_arc_deterministic(self):
        arc1 = CampaignGenerator(seed=7).generate_arc(num_quests=3)
        arc2 = CampaignGenerator(seed=7).generate_arc(num_quests=3)
        assert arc1.premise == arc2.premise
        assert len(arc1.quests) == len(arc2.quests)
        assert arc1.quests[0].title == arc2.quests[0].title

    def test_generate_side_quest(self):
        gen = CampaignGenerator(seed=42)
        q = gen.generate_side_quest("Forest", difficulty=2)
        assert isinstance(q, Quest)
        assert q.location == "Forest"

    def test_quest_has_objectives(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(num_quests=2)
        for q in arc.quests:
            assert len(q.objectives) >= 1


class TestCampaignManager:
    def _setup(self):
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(num_quests=3)
        manager = CampaignManager()
        manager.start_arc(arc)
        return manager, arc

    def test_start_arc(self):
        manager, arc = self._setup()
        assert manager.get_arc(arc.id) is arc

    def test_get_arc_nonexistent(self):
        manager = CampaignManager()
        assert manager.get_arc("nope") is None

    def test_active_quests(self):
        manager, arc = self._setup()
        active = manager.active_quests()
        assert len(active) == 1

    def test_available_quests(self):
        manager, arc = self._setup()
        available = manager.available_quests()
        assert len(available) >= 1

    def test_complete_objective_and_get_rewards(self):
        manager, arc = self._setup()
        q = arc.quests[0]
        # Get the target from the first objective
        target = q.objectives[0].target
        # Fill up all objectives
        for obj in q.objectives:
            rewards = manager.complete_objective(arc.id, q.id, obj.target, obj.required_count)
        assert rewards is not None
        assert "gold" in rewards

    def test_complete_objective_advances_arc(self):
        manager, arc = self._setup()
        q = arc.quests[0]
        for obj in q.objectives:
            manager.complete_objective(arc.id, q.id, obj.target, obj.required_count)
        # Arc should have moved to next quest
        assert arc.current_quest_idx == 1

    def test_complete_objective_wrong_arc(self):
        manager, arc = self._setup()
        q = arc.quests[0]
        result = manager.complete_objective("wrong_arc", q.id, "goblin", 1)
        assert result is None

    def test_complete_objective_inactive_quest(self):
        manager, arc = self._setup()
        # Quest[1] is still AVAILABLE, not ACTIVE
        q = arc.quests[1]
        result = manager.complete_objective(arc.id, q.id, q.objectives[0].target, 1)
        assert result is None
