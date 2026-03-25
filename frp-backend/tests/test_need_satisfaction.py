"""Tests for NeedSatisfactionEngine (FR-60..FR-62, AC-43..AC-45)."""
import pytest

from engine.world.npc_needs import NPCNeeds
from engine.world.need_satisfaction import NeedSatisfactionEngine, SatisfactionAction


@pytest.fixture
def engine():
    return NeedSatisfactionEngine()


class TestSustenanceSatisfaction:
    """AC-43: sustenance auto-satisfaction at tavern."""

    def test_eat_at_tavern_when_hungry(self, engine):
        """sustenance < 30 at tavern with food -> eat, +40 sustenance, -1 food."""
        needs = NPCNeeds(sustenance=20)
        stock = {"food": 5}
        actions = engine.check_and_satisfy(needs, "village_tavern", stock, [])

        eat_actions = [a for a in actions if a.action_type == "eat"]
        assert len(eat_actions) == 1
        assert needs.sustenance == 60.0  # 20 + 40
        assert stock["food"] == 4

    def test_no_eat_when_not_hungry(self, engine):
        """sustenance >= 30 -> no eating."""
        needs = NPCNeeds(sustenance=50)
        stock = {"food": 5}
        actions = engine.check_and_satisfy(needs, "village_tavern", stock, [])
        assert not any(a.action_type == "eat" for a in actions)

    def test_no_eat_at_tavern_no_food(self, engine):
        """At tavern but food stock is 0 -> no eating."""
        needs = NPCNeeds(sustenance=10)
        stock = {"food": 0}
        actions = engine.check_and_satisfy(needs, "village_tavern", stock, [])
        # Should deviate since sustenance < 15 but already at tavern -- no deviate
        # Actually sustenance < 15 and location IS tavern, so no deviate.
        # But food=0 so no eat either.  Only other needs might trigger.
        eat_actions = [a for a in actions if a.action_type == "eat"]
        assert len(eat_actions) == 0

    def test_deviate_to_tavern_when_starving(self, engine):
        """AC-44: sustenance < 15 and NOT at tavern -> deviate_to_tavern."""
        needs = NPCNeeds(sustenance=10)
        stock = {"food": 5}
        actions = engine.check_and_satisfy(needs, "marketplace", stock, [])

        deviate = [a for a in actions if a.action_type == "deviate_to_tavern"]
        assert len(deviate) == 1
        assert deviate[0].side_effects["destination"] == "tavern"
        # Should NOT eat yet (not at tavern)
        assert not any(a.action_type == "eat" for a in actions)


class TestSocialSatisfaction:
    """AC-45: social auto-satisfaction via chat."""

    def test_chat_when_lonely(self, engine):
        """social < 25 with nearby NPC -> chat, +15 social."""
        needs = NPCNeeds(social=20)
        actions = engine.check_and_satisfy(
            needs, "square", {"food": 0}, ["guard_bob"]
        )
        chat_actions = [a for a in actions if a.action_type == "chat"]
        assert len(chat_actions) == 1
        assert needs.social == 35.0  # 20 + 15
        assert chat_actions[0].side_effects["chat_partner"] == "guard_bob"

    def test_no_chat_when_social_ok(self, engine):
        needs = NPCNeeds(social=50)
        actions = engine.check_and_satisfy(
            needs, "square", {"food": 0}, ["guard_bob"]
        )
        assert not any(a.action_type == "chat" for a in actions)

    def test_no_chat_when_alone(self, engine):
        needs = NPCNeeds(social=10)
        actions = engine.check_and_satisfy(needs, "square", {"food": 0}, [])
        assert not any(a.action_type == "chat" for a in actions)


class TestDutySatisfaction:

    def test_return_to_post_low_duty(self, engine):
        needs = NPCNeeds(duty=15)
        actions = engine.check_and_satisfy(needs, "tavern", {"food": 0}, [])
        duty_actions = [a for a in actions if a.action_type == "return_to_post"]
        assert len(duty_actions) == 1
        assert needs.duty == 45.0  # 15 + 30

    def test_no_return_when_duty_ok(self, engine):
        needs = NPCNeeds(duty=50)
        actions = engine.check_and_satisfy(needs, "tavern", {"food": 0}, [])
        assert not any(a.action_type == "return_to_post" for a in actions)


class TestSafetySatisfaction:

    def test_flee_when_unsafe_unguarded(self, engine):
        needs = NPCNeeds(safety=10)
        actions = engine.check_and_satisfy(
            needs, "dark_alley", {"food": 0, "guarded": False}, []
        )
        flee = [a for a in actions if a.action_type == "flee_to_guarded_zone"]
        assert len(flee) == 1

    def test_shelter_when_unsafe_guarded(self, engine):
        needs = NPCNeeds(safety=10)
        actions = engine.check_and_satisfy(
            needs, "barracks", {"food": 0, "guarded": True}, []
        )
        shelter = [a for a in actions if a.action_type == "take_shelter"]
        assert len(shelter) == 1
        assert needs.safety == 35.0  # 10 + 25

    def test_no_flee_when_safe(self, engine):
        needs = NPCNeeds(safety=80)
        actions = engine.check_and_satisfy(
            needs, "dark_alley", {"food": 0, "guarded": False}, []
        )
        assert not any(
            a.action_type in ("flee_to_guarded_zone", "take_shelter")
            for a in actions
        )


class TestSatisfactionActionSerialization:

    def test_to_dict(self):
        action = SatisfactionAction(
            action_type="eat",
            need_addressed="sustenance",
            description="Ate food",
            side_effects={"stock_food": -1},
        )
        d = action.to_dict()
        assert d["action_type"] == "eat"
        assert d["side_effects"]["stock_food"] == -1
