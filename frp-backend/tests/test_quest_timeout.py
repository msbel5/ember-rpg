"""Tests for engine.world.quest_timeout — AC-46..AC-48."""

import pytest
from engine.world.quest_timeout import QuestEntry, QuestStatus, QuestTracker


class TestQuestEntry:
    def test_default_status_is_active(self):
        q = QuestEntry(quest_id="q1", title="Save the village")
        assert q.status == QuestStatus.ACTIVE

    def test_no_deadline_by_default(self):
        q = QuestEntry(quest_id="q1", title="Explore")
        assert q.deadline_hour is None


class TestQuestTracker:
    def test_add_quest(self):
        tracker = QuestTracker()
        q = tracker.add_quest("q1", "Slay the dragon", current_hour=0, deadline_hour=100)
        assert q.quest_id == "q1"
        assert q.deadline_hour == 100
        assert q.status == QuestStatus.ACTIVE

    def test_complete_quest(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Fetch herbs", current_hour=0, deadline_hour=50)
        q = tracker.complete_quest("q1", current_hour=30)
        assert q.status == QuestStatus.COMPLETED
        assert q.completed_hour == 30

    def test_complete_already_completed_raises(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Task", current_hour=0, deadline_hour=50)
        tracker.complete_quest("q1", 10)
        with pytest.raises(ValueError):
            tracker.complete_quest("q1", 20)

    def test_tick_expires_overdue_quest(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Timed quest", current_hour=0, deadline_hour=10)
        result = tracker.tick(15)
        assert len(result["expired"]) == 1
        assert result["expired"][0]["quest_id"] == "q1"
        assert tracker.quests["q1"].status == QuestStatus.EXPIRED

    def test_tick_sends_reminders(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Urgent", current_hour=0, deadline_hour=30,
                          reminder_hours=[24.0, 8.0, 1.0])
        result = tracker.tick(23)  # 7 hours remaining → triggers 8.0 threshold
        reminders = result["reminders"]
        assert len(reminders) >= 1
        assert reminders[0]["quest_id"] == "q1"

    def test_reminder_not_sent_twice(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Urgent", current_hour=0, deadline_hour=30,
                          reminder_hours=[8.0])
        tracker.tick(23)
        result = tracker.tick(24)
        assert len(result["reminders"]) == 0

    def test_quest_without_deadline_never_expires(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Eternal quest", current_hour=0)
        result = tracker.tick(999999)
        assert len(result["expired"]) == 0

    def test_consequence_handler_called(self):
        tracker = QuestTracker()
        calls = []
        tracker.register_consequence("reputation_loss",
                                     lambda q: (calls.append(q.quest_id), {"rep": -10})[1])
        tracker.add_quest("q1", "Escort mission", current_hour=0, deadline_hour=10,
                          timeout_consequence="reputation_loss")
        result = tracker.tick(15)
        assert len(calls) == 1
        assert result["expired"][0]["consequence_result"] == {"rep": -10}

    def test_get_active_quests(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Active", current_hour=0, deadline_hour=100)
        tracker.add_quest("q2", "Also active", current_hour=0)
        tracker.add_quest("q3", "Will expire", current_hour=0, deadline_hour=5)
        tracker.tick(10)  # expires q3
        active = tracker.get_active_quests()
        ids = [q.quest_id for q in active]
        assert "q1" in ids
        assert "q2" in ids
        assert "q3" not in ids

    def test_get_expired_quests(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Doomed", current_hour=0, deadline_hour=5)
        tracker.tick(10)
        expired = tracker.get_expired_quests()
        assert len(expired) == 1
        assert expired[0].quest_id == "q1"

    def test_fail_quest(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Fail me", current_hour=0)
        q = tracker.fail_quest("q1")
        assert q.status == QuestStatus.EXPIRED

    def test_check_reminders_convenience(self):
        tracker = QuestTracker()
        tracker.add_quest("q1", "Remind me", current_hour=0, deadline_hour=30,
                          reminder_hours=[24.0])
        reminders = tracker.check_reminders(7)  # 23h remaining → triggers 24h
        assert len(reminders) >= 1
