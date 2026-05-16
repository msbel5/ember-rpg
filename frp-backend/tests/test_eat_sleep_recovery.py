"""Tests for eat/sleep recovery atom (Sprint 4).

AC: actor consumes meal / sleeps, hunger/fatigue decrement, event log records cause+effect
"""
import pytest

from engine.world.npc_needs import NPCNeeds
from engine.world.need_satisfaction import NeedSatisfactionEngine


class TestEatSleepRecovery:

    def test_sleep_at_barracks_when_tired(self):
        """fatigue < 30 at a sleep place -> sleep and regain fatigue."""
        needs = NPCNeeds(fatigue=20)
        stock = {"food": 0}
        engine = NeedSatisfactionEngine()
        actions = engine.check_and_satisfy(needs, "barracks", stock, [])

        sleep_actions = [a for a in actions if a.action_type == "sleep"]
        assert len(sleep_actions) == 1
        assert needs.fatigue == 80.0  # 20 + 60

    def test_deviate_to_sleep_when_exhausted_elsewhere(self):
        """fatigue < 15 outside sleep place -> deviate_to_sleep_place."""
        needs = NPCNeeds(fatigue=10)
        stock = {"food": 3}
        engine = NeedSatisfactionEngine()
        actions = engine.check_and_satisfy(needs, "marketplace", stock, [])

        deviate = [a for a in actions if a.action_type == "deviate_to_sleep_place"]
        assert len(deviate) == 1
        assert deviate[0].side_effects.get("destination") == "sleeping_place"
