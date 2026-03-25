"""
Tests for engine.world.ethics -- Ethics & Cultural Values (AC-18, AC-19)
"""
import pytest

from engine.world.ethics import (
    ACTION_TYPES,
    FACTION_ETHICS,
    FACTION_VALUES,
    REACTION_LEVELS,
    ActionEvaluation,
    compare_factions,
    evaluate_action,
    evaluate_action_full,
    get_all_factions,
    get_faction_context,
)


# ---------------------------------------------------------------------------
# AC-18: Faction ethics data completeness
# ---------------------------------------------------------------------------

class TestFactionEthicsData:
    """Verify that all faction/action combinations are defined."""

    def test_all_six_factions_exist(self):
        expected = {
            "harbor_guard", "thieves_guild", "merchant_guild",
            "forest_elves", "mountain_dwarves", "temple_order",
        }
        assert expected == set(FACTION_ETHICS.keys())

    def test_all_factions_have_all_actions(self):
        for faction, ethics in FACTION_ETHICS.items():
            for action in ACTION_TYPES:
                assert action in ethics, f"{faction} missing action {action}"

    def test_all_reactions_are_valid_levels(self):
        for faction, ethics in FACTION_ETHICS.items():
            for action, reaction in ethics.items():
                assert reaction in REACTION_LEVELS, (
                    f"{faction}.{action} has invalid reaction '{reaction}'"
                )

    def test_faction_values_have_all_factions(self):
        assert set(FACTION_VALUES.keys()) == set(FACTION_ETHICS.keys())

    def test_faction_values_range(self):
        for faction, values in FACTION_VALUES.items():
            for key, val in values.items():
                assert 0 <= val <= 100, f"{faction}.{key} = {val} out of range"

    def test_faction_values_expected_keys(self):
        expected_keys = {"order", "commerce", "tradition", "nature", "wealth", "art", "honor", "faith"}
        for faction, values in FACTION_VALUES.items():
            assert set(values.keys()) == expected_keys, f"{faction} missing value keys"


# ---------------------------------------------------------------------------
# AC-19: evaluate_action and get_faction_context
# ---------------------------------------------------------------------------

class TestEvaluateAction:
    """Test the evaluate_action function."""

    def test_harbor_guard_kill_citizen_is_serious_crime(self):
        rep, consequence = evaluate_action("harbor_guard", "KILL_CITIZEN")
        assert rep == -50
        assert consequence is not None

    def test_thieves_guild_theft_is_valued(self):
        rep, consequence = evaluate_action("thieves_guild", "THEFT")
        assert rep == 5
        assert consequence is None

    def test_temple_order_desecrate_is_unthinkable(self):
        rep, consequence = evaluate_action("temple_order", "DESECRATE")
        assert rep == -100
        assert consequence is not None

    def test_merchant_guild_trade_is_honored(self):
        rep, consequence = evaluate_action("merchant_guild", "TRADE")
        assert rep == 15
        assert consequence is None

    def test_forest_elves_help_poor_is_honored(self):
        rep, consequence = evaluate_action("forest_elves", "HELP_POOR")
        assert rep == 15

    def test_unknown_faction_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown faction"):
            evaluate_action("nonexistent_faction", "THEFT")

    def test_unknown_action_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown action"):
            evaluate_action("harbor_guard", "FLY_TO_MOON")

    def test_evaluate_action_full_returns_dataclass(self):
        result = evaluate_action_full("mountain_dwarves", "KILL_ENEMY")
        assert isinstance(result, ActionEvaluation)
        assert result.faction == "mountain_dwarves"
        assert result.action_type == "KILL_ENEMY"
        assert result.reaction_level == "honored"
        assert result.rep_change == 15

    def test_acceptable_has_zero_rep_change(self):
        rep, consequence = evaluate_action("thieves_guild", "TRADE")
        assert rep == 0
        assert consequence is None


class TestGetFactionContext:
    """Test the get_faction_context function."""

    def test_returns_dict_with_expected_keys(self):
        ctx = get_faction_context("harbor_guard")
        assert "faction" in ctx
        assert "values" in ctx
        assert "top_values" in ctx
        assert "crimes" in ctx
        assert "honored_actions" in ctx
        assert "personality" in ctx
        assert "ethics_summary" in ctx

    def test_top_values_has_three_items(self):
        ctx = get_faction_context("forest_elves")
        assert len(ctx["top_values"]) == 3

    def test_crimes_list_contains_serious_offenses(self):
        ctx = get_faction_context("harbor_guard")
        assert "KILL_CITIZEN" in ctx["crimes"]

    def test_honored_actions_correct(self):
        ctx = get_faction_context("temple_order")
        assert "HELP_POOR" in ctx["honored_actions"]

    def test_unknown_faction_raises(self):
        with pytest.raises(KeyError):
            get_faction_context("ghost_pirates")

    def test_personality_non_empty(self):
        for faction in get_all_factions():
            ctx = get_faction_context(faction)
            assert len(ctx["personality"]) > 0


class TestCompareFactions:
    """Test faction comparison utility."""

    def test_compare_returns_all_actions(self):
        result = compare_factions("harbor_guard", "thieves_guild")
        assert set(result.keys()) == set(ACTION_TYPES)

    def test_agreement_field_is_bool(self):
        result = compare_factions("harbor_guard", "mountain_dwarves")
        for action, data in result.items():
            assert isinstance(data["agreement"], bool)

    def test_same_faction_all_agree(self):
        result = compare_factions("harbor_guard", "harbor_guard")
        for action, data in result.items():
            assert data["agreement"] is True
