"""
Tests for the context-sensitive interaction system.
Covers: available interactions, handling with skill checks, AP costs,
lock picking, trap detection, persuasion, trading, various target types.
"""

import random

import pytest

from engine.world.interactions import (
    INTERACTION_RULES,
    InteractionHandler,
    InteractionResult,
    InteractionType,
    get_available_interactions,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _rigged_rng(*values: int) -> random.Random:
    rng = random.Random()
    call_iter = iter(values)
    def _fixed_randint(a: int, b: int) -> int:
        return next(call_iter)
    rng.randint = _fixed_randint  # type: ignore[assignment]
    return rng


def _make_player(abilities: dict | None = None) -> dict:
    base = {"MIG": 14, "AGI": 14, "END": 12, "MND": 12, "INS": 12, "PRE": 14}
    if abilities:
        base.update(abilities)
    return {"abilities": base}


def _make_tile(terrain: str = "grass", flags: set | None = None, items: list | None = None) -> dict:
    return {
        "terrain": terrain,
        "flags": flags or set(),
        "items": items or [],
    }


# ── get_available_interactions ───────────────────────────────────────

class TestAvailableInteractions:
    def test_friendly_npc_offers_talk_trade_examine(self):
        tile = _make_tile()
        entities = [{"entity_type": "npc", "disposition": "friendly", "alive": True}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.TALK in result
        assert InteractionType.TRADE in result
        assert InteractionType.EXAMINE in result

    def test_hostile_npc_offers_attack_flee_sneak(self):
        tile = _make_tile()
        entities = [{"entity_type": "npc", "disposition": "hostile", "alive": True}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.ATTACK in result
        assert InteractionType.FLEE in result
        assert InteractionType.SNEAK in result

    def test_locked_door_offers_pick_and_force(self):
        tile = _make_tile()
        entities = [{"entity_type": "door", "locked": True}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.LOCK_PICK in result
        assert InteractionType.FORCE_OPEN in result
        assert InteractionType.EXAMINE in result

    def test_unlocked_door_offers_open_close(self):
        tile = _make_tile()
        entities = [{"entity_type": "door", "locked": False}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.OPEN in result
        assert InteractionType.CLOSE in result

    def test_chest_offers_open_examine_search(self):
        tile = _make_tile()
        entities = [{"entity_type": "chest", "locked": False, "trapped": False}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.OPEN in result
        assert InteractionType.EXAMINE in result
        assert InteractionType.SEARCH in result

    def test_workstation_offers_craft_examine_use(self):
        tile = _make_tile()
        entities = [{"entity_type": "workstation"}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.CRAFT in result
        assert InteractionType.EXAMINE in result
        assert InteractionType.USE in result

    def test_water_tile_offers_drink_swim_fish_fill(self):
        tile = _make_tile(terrain="shallow_water")
        result = get_available_interactions(tile, [], _make_player())
        assert InteractionType.DRINK in result
        assert InteractionType.SWIM in result
        assert InteractionType.FISH in result
        assert InteractionType.FILL in result

    def test_tree_offers_chop_examine_climb(self):
        tile = _make_tile(flags={"TREE"})
        result = get_available_interactions(tile, [], _make_player())
        assert InteractionType.CHOP in result
        assert InteractionType.EXAMINE in result
        assert InteractionType.CLIMB in result

    def test_item_on_ground_from_tile(self):
        tile = _make_tile(items=["sword_01"])
        result = get_available_interactions(tile, [], _make_player())
        assert InteractionType.PICK_UP in result
        assert InteractionType.EXAMINE in result

    def test_dead_npc_classified_as_corpse(self):
        tile = _make_tile()
        entities = [{"entity_type": "npc", "disposition": "neutral", "alive": False}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.LOOT in result
        assert InteractionType.BURY in result

    def test_trapped_chest_offers_disarm(self):
        tile = _make_tile()
        entities = [{"entity_type": "chest", "locked": False, "trapped": True}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.DISARM_TRAP in result

    def test_altar_offers_pray(self):
        tile = _make_tile()
        entities = [{"entity_type": "altar"}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.PRAY in result

    def test_lever_offers_push_pull(self):
        tile = _make_tile()
        entities = [{"entity_type": "lever"}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.PUSH in result
        assert InteractionType.PULL in result

    def test_empty_tile_no_interactions(self):
        tile = _make_tile()
        result = get_available_interactions(tile, [], _make_player())
        assert result == []

    def test_bed_offers_rest_and_search(self):
        tile = _make_tile()
        entities = [{"entity_type": "bed"}]
        result = get_available_interactions(tile, entities, _make_player())
        assert InteractionType.REST in result
        assert InteractionType.SEARCH in result


# ── InteractionHandler ───────────────────────────────────────────────

class TestInteractionHandler:
    def setup_method(self):
        self.handler = InteractionHandler()

    def test_talk_always_succeeds(self):
        result = self.handler.handle(
            InteractionType.TALK,
            _make_player(),
            {"target_type": "npc_friendly", "name": "Merchant"},
            {},
        )
        assert result.success is True
        assert result.ap_cost == 1

    def test_lock_pick_with_high_roll_succeeds(self):
        result = self.handler.handle(
            InteractionType.LOCK_PICK,
            _make_player({"AGI": 16}),
            {"target_type": "door_locked", "name": "Iron Door"},
            {"dc": 14, "rng": _rigged_rng(18)},
        )
        assert result.success is True
        assert result.skill_check is not None
        assert result.skill_check.roll == 18
        assert result.state_changes.get("locked") is False
        assert result.ap_cost == 2

    def test_lock_pick_with_low_roll_fails(self):
        result = self.handler.handle(
            InteractionType.LOCK_PICK,
            _make_player({"AGI": 10}),
            {"target_type": "door_locked", "name": "Iron Door"},
            {"dc": 15, "rng": _rigged_rng(3)},
        )
        assert result.success is False
        assert "locked" not in result.state_changes

    def test_force_open_sets_broken(self):
        result = self.handler.handle(
            InteractionType.FORCE_OPEN,
            _make_player({"MIG": 18}),
            {"target_type": "door_locked", "name": "Wooden Door"},
            {"dc": 14, "rng": _rigged_rng(15)},
        )
        assert result.success is True
        assert result.state_changes.get("broken") is True
        assert result.state_changes.get("locked") is False

    def test_disarm_trap_on_chest(self):
        result = self.handler.handle(
            InteractionType.DISARM_TRAP,
            _make_player({"AGI": 16}),
            {"target_type": "chest_trapped", "name": "Trapped Chest"},
            {"dc": 14, "rng": _rigged_rng(15)},
        )
        assert result.success is True
        assert result.state_changes.get("trapped") is False

    def test_persuade_friendly_npc(self):
        result = self.handler.handle(
            InteractionType.PERSUADE,
            _make_player({"PRE": 16}),
            {"target_type": "npc_friendly", "name": "Guard"},
            {"dc": 14, "rng": _rigged_rng(12)},
        )
        # Roll 12 + mod 3 = 15 >= 14
        assert result.success is True
        assert result.ap_cost == 1

    def test_trade_no_skill_check(self):
        result = self.handler.handle(
            InteractionType.TRADE,
            _make_player(),
            {"target_type": "npc_friendly", "name": "Shopkeeper"},
            {},
        )
        assert result.success is True
        assert result.skill_check is None

    def test_climb_tree_with_skill_check(self):
        result = self.handler.handle(
            InteractionType.CLIMB,
            _make_player({"AGI": 14}),
            {"target_type": "tree", "name": "Oak Tree"},
            {"dc": 12, "rng": _rigged_rng(10)},
        )
        # Roll 10 + mod 2 = 12 >= 12
        assert result.success is True
        assert result.ap_cost == 2

    def test_pick_up_item_sets_picked_up(self):
        result = self.handler.handle(
            InteractionType.PICK_UP,
            _make_player(),
            {"target_type": "item", "name": "Gold Coin"},
            {},
        )
        assert result.success is True
        assert result.state_changes.get("picked_up") is True
        assert result.ap_cost == 1

    def test_unknown_rule_returns_failure(self):
        result = self.handler.handle(
            InteractionType.MINE,
            _make_player(),
            {"target_type": "npc_friendly", "name": "Guard"},
            {},
        )
        assert result.success is False
        assert result.ap_cost == 0

    def test_critical_failure_adds_narrative(self):
        result = self.handler.handle(
            InteractionType.LOCK_PICK,
            _make_player({"AGI": 10}),
            {"target_type": "door_locked", "name": "Vault Door"},
            {"dc": 15, "rng": _rigged_rng(1)},
        )
        assert result.success is False
        assert result.skill_check is not None
        assert result.skill_check.critical == "failure"
        assert "critical failure" in result.narrative_prompt.lower()

    def test_rest_on_bed_costs_zero_ap(self):
        result = self.handler.handle(
            InteractionType.REST,
            _make_player(),
            {"target_type": "bed", "name": "Straw Bed"},
            {},
        )
        assert result.success is True
        assert result.ap_cost == 0
        assert result.state_changes.get("rested") is True


# ── INTERACTION_RULES coverage ───────────────────────────────────────

class TestInteractionRules:
    def test_at_least_50_rules(self):
        assert len(INTERACTION_RULES) >= 50

    def test_all_rules_have_required_keys(self):
        for (target_type, itype), rule in INTERACTION_RULES.items():
            assert "skill" in rule, f"Missing 'skill' in ({target_type}, {itype})"
            assert "dc_range" in rule, f"Missing 'dc_range' in ({target_type}, {itype})"
            assert "ap_cost" in rule, f"Missing 'ap_cost' in ({target_type}, {itype})"
            assert "requirements" in rule, f"Missing 'requirements' in ({target_type}, {itype})"

    def test_dc_ranges_are_valid(self):
        for (target_type, itype), rule in INTERACTION_RULES.items():
            lo, hi = rule["dc_range"]
            assert lo <= hi, f"Invalid dc_range in ({target_type}, {itype}): {lo} > {hi}"

    def test_ap_costs_non_negative(self):
        for (target_type, itype), rule in INTERACTION_RULES.items():
            assert rule["ap_cost"] >= 0, f"Negative AP in ({target_type}, {itype})"

    def test_skills_are_valid_or_none(self):
        valid = {None, "MIG", "AGI", "END", "MND", "INS", "PRE"}
        for (target_type, itype), rule in INTERACTION_RULES.items():
            assert rule["skill"] in valid, f"Bad skill in ({target_type}, {itype}): {rule['skill']}"
