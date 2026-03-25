"""Tests for Module 3: NPC Schedules & Movement (FR-10..FR-14)"""
import pytest
from engine.world.schedules import (
    TimePeriod, GameTime, WorldTickScheduler, NPCSchedule,
    hour_to_period, DEFAULT_SCHEDULES,
)


class TestTimePeriod:
    def test_dawn(self):
        assert hour_to_period(6) == TimePeriod.DAWN

    def test_morning(self):
        assert hour_to_period(9) == TimePeriod.MORNING

    def test_afternoon(self):
        assert hour_to_period(14) == TimePeriod.AFTERNOON

    def test_evening(self):
        assert hour_to_period(19) == TimePeriod.EVENING

    def test_night(self):
        assert hour_to_period(23) == TimePeriod.NIGHT
        assert hour_to_period(3) == TimePeriod.NIGHT


class TestGameTime:
    def test_initial_state(self):
        t = GameTime()
        assert t.hour == 8
        assert t.period == TimePeriod.MORNING

    def test_advance_within_period(self):
        t = GameTime(hour=9, minute=0)
        changed = t.advance(15)
        assert changed is False
        assert t.minute == 15

    def test_advance_crosses_period(self):
        t = GameTime(hour=11, minute=50)
        changed = t.advance(15)  # 11:50 → 12:05
        assert changed is True
        assert t.hour == 12
        assert t.period == TimePeriod.AFTERNOON

    def test_advance_crosses_midnight(self):
        t = GameTime(hour=23, minute=50)
        t.advance(30)  # 23:50 → 00:20
        assert t.hour == 0
        assert t.day == 2
        assert t.period == TimePeriod.NIGHT

    def test_to_string(self):
        t = GameTime(hour=14, minute=30, day=3)
        s = t.to_string()
        assert "Day 3" in s
        assert "14:30" in s

    def test_to_dict(self):
        t = GameTime(hour=20)
        d = t.to_dict()
        assert d["period"] == "evening"
        assert d["hour"] == 20


class TestWorldTickScheduler:
    def test_register_npc(self):
        scheduler = WorldTickScheduler()
        scheduler.register_npc("m1", "Old Merchant", "merchant")
        loc = scheduler.get_npc_location("m1", TimePeriod.MORNING)
        assert loc == "shop"

    def test_npc_moves_on_period_change(self):
        """AC-09: Merchant at shop during morning, market during afternoon."""
        scheduler = WorldTickScheduler()
        scheduler.register_npc("m1", "Old Merchant", "merchant")

        time_morning = GameTime(hour=9)
        scheduler.tick(time_morning)  # Initialize last_period

        time_afternoon = GameTime(hour=14)
        movements = scheduler.tick(time_afternoon)

        assert len(movements) == 1
        assert movements[0]["npc_id"] == "m1"
        assert movements[0]["from"] == "shop"
        assert movements[0]["to"] == "market_square"

    def test_tavern_occupancy(self):
        """AC-08: Tavern has 0 NPCs at 07:00, 3+ NPCs at 20:00."""
        scheduler = WorldTickScheduler()
        scheduler.register_npc("m1", "Merchant", "merchant")
        scheduler.register_npc("b1", "Blacksmith", "blacksmith")
        scheduler.register_npc("g1", "Guard", "guard")
        scheduler.register_npc("i1", "Innkeeper", "innkeeper")
        scheduler.register_npc("bg1", "Beggar", "beggar")

        # Dawn (07:00) — only innkeeper at tavern
        dawn_npcs = scheduler.get_npcs_at_location("tavern", TimePeriod.DAWN)
        assert "i1" in dawn_npcs
        assert "m1" not in dawn_npcs

        # Evening (20:00) — merchant, blacksmith, guard, innkeeper, beggar at tavern
        evening_npcs = scheduler.get_npcs_at_location("tavern", TimePeriod.EVENING)
        assert len(evening_npcs) >= 3

    def test_guard_patrol(self):
        """AC-10: Guard cycles through patrol positions."""
        patrol = [[5, 5], [5, 10], [10, 10], [10, 5]]
        scheduler = WorldTickScheduler()
        scheduler.register_npc("g1", "Guard", "guard", patrol_route=patrol)

        moves = scheduler.advance_guard_patrols()
        assert moves[0]["patrol_position"] == [5, 5]

        moves = scheduler.advance_guard_patrols()
        assert moves[0]["patrol_position"] == [5, 10]

        moves = scheduler.advance_guard_patrols()
        assert moves[0]["patrol_position"] == [10, 10]

        moves = scheduler.advance_guard_patrols()
        assert moves[0]["patrol_position"] == [10, 5]

        # Wraps around
        moves = scheduler.advance_guard_patrols()
        assert moves[0]["patrol_position"] == [5, 5]

    def test_no_movement_same_period(self):
        scheduler = WorldTickScheduler()
        scheduler.register_npc("m1", "Merchant", "merchant")

        t1 = GameTime(hour=9)
        scheduler.tick(t1)

        t2 = GameTime(hour=10)  # Still morning
        movements = scheduler.tick(t2)
        assert len(movements) == 0

    def test_custom_schedule(self):
        custom = {
            "dawn": "secret_lair",
            "morning": "market_square",
            "afternoon": "secret_lair",
            "evening": "tavern",
            "night": "secret_lair",
        }
        scheduler = WorldTickScheduler()
        scheduler.register_npc("spy1", "Shadow", "spy", custom_schedule=custom)

        loc = scheduler.get_npc_location("spy1", TimePeriod.DAWN)
        assert loc == "secret_lair"
