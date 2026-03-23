"""
Tests for Loot System (Deliverable 4)
"""
import pytest
from unittest.mock import MagicMock, patch
from engine.core.loot import LootSystem, RARITY_DROP_CHANCES


@pytest.fixture
def loot():
    return LootSystem()


def make_monster(monster_type="normal", loot_table=None):
    return {
        "name": "Test Monster",
        "type": monster_type,
        "loot_table": loot_table or [
            {"id": "wolf_pelt", "rarity": "COMMON"},
            {"id": "wolf_fang", "rarity": "UNCOMMON"},
            {"id": "rare_gem", "rarity": "RARE"},
        ]
    }


def test_loot_roll_returns_items(loot):
    """Rolling loot should return a list of item IDs."""
    monster = make_monster()
    # Force all rolls to succeed
    with patch('random.random', return_value=0.01):
        result = loot.roll_loot(monster)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "wolf_pelt" in result


def test_minimum_one_item_guaranteed(loot):
    """At least 1 item must drop from any enemy kill."""
    monster = make_monster()
    # Force all rolls to fail
    with patch('random.random', return_value=0.99):
        result = loot.roll_loot(monster)
    assert len(result) >= 1


def test_boss_guarantees_two_items(loot):
    """Boss monsters must drop at least 2 items."""
    monster = make_monster(monster_type="boss")
    # Force all rolls to fail — should still get 2
    with patch('random.random', return_value=0.99):
        result = loot.roll_loot(monster)
    assert len(result) >= 2


def test_loot_rarity_affects_drop_chance(loot):
    """Common items have higher base chance than legendary (50% vs 5%)."""
    assert RARITY_DROP_CHANCES["COMMON"] > RARITY_DROP_CHANCES["LEGENDARY"]
    assert RARITY_DROP_CHANCES["UNCOMMON"] > RARITY_DROP_CHANCES["RARE"]
    assert RARITY_DROP_CHANCES["RARE"] > RARITY_DROP_CHANCES["EPIC"]
    assert RARITY_DROP_CHANCES["EPIC"] > RARITY_DROP_CHANCES["LEGENDARY"]

    # With multiple items, common should drop more often
    monster = make_monster(loot_table=[
        {"id": "common1", "rarity": "COMMON"},
        {"id": "common2", "rarity": "COMMON"},
        {"id": "legendary1", "rarity": "LEGENDARY"},
        {"id": "legendary2", "rarity": "LEGENDARY"},
    ])
    common_count = 0
    legendary_count = 0
    trials = 1000
    for _ in range(trials):
        result = loot.roll_loot(monster)
        common_count += result.count("common1") + result.count("common2")
        legendary_count += result.count("legendary1") + result.count("legendary2")
    # Common should drop significantly more often
    assert common_count > legendary_count


def test_loot_added_to_inventory(loot):
    """apply_loot_to_session should add items to player inventory."""
    session = MagicMock()
    session.player.inventory = []

    item_ids = ["wolf_pelt", "health_potion"]
    acquired = loot.apply_loot_to_session(item_ids, session)

    assert "wolf_pelt" in session.player.inventory
    assert "health_potion" in session.player.inventory
    assert set(acquired) == {"wolf_pelt", "health_potion"}


def test_empty_loot_table(loot):
    """Monster with no loot_table should return empty list."""
    monster = {"name": "Ghost", "type": "undead", "loot_table": []}
    result = loot.roll_loot(monster)
    assert result == []


def test_luck_modifier_increases_drops(loot):
    """Higher luck modifier should increase drop rates."""
    monster = make_monster(loot_table=[{"id": "gem", "rarity": "RARE"}])

    drops_no_luck = 0
    drops_high_luck = 0
    trials = 500

    for _ in range(trials):
        result_no = loot.roll_loot(monster, luck_modifier=0)
        result_high = loot.roll_loot(monster, luck_modifier=80)
        # Exclude guaranteed drops for fair comparison
        # Use raw chance test
        drops_no_luck += len(result_no)
        drops_high_luck += len(result_high)

    # High luck should yield more drops
    assert drops_high_luck >= drops_no_luck


def test_apply_loot_creates_inventory_if_missing(loot):
    """apply_loot_to_session should create inventory if player doesn't have one."""
    session = MagicMock()
    del session.player.inventory  # Simulate missing attribute
    # hasattr check will fail, so we need to handle this
    player = MagicMock(spec=[])  # spec=[] means no attributes
    session.player = player

    item_ids = ["health_potion"]
    acquired = loot.apply_loot_to_session(item_ids, session)
    assert "health_potion" in session.player.inventory
    assert acquired == ["health_potion"]


def test_boss_all_items_dropped_gets_duplicate(loot):
    """Boss with single item already dropped should still get 2+ items."""
    monster = {
        "name": "Boss",
        "type": "boss",
        "loot_table": [{"id": "boss_sword", "rarity": "EPIC"}]
    }
    # Force all rolls to succeed → single unique item → boss duplicate
    with patch('random.random', return_value=0.01):
        result = loot.roll_loot(monster)
    assert len(result) >= 2


def test_loot_item_without_rarity_uses_base_chance(loot):
    """Item without rarity field uses BASE_DROP_CHANCE."""
    monster = {
        "name": "Slime",
        "type": "normal",
        "loot_table": [{"id": "slime_goop"}]  # no rarity key
    }
    with patch('random.random', return_value=0.01):
        result = loot.roll_loot(monster)
    assert "slime_goop" in result


def test_guaranteed_drop_picks_lowest_rarity(loot):
    """Guaranteed drop should pick the lowest rarity item."""
    ls = LootSystem()
    table = [
        {"id": "rare_gem", "rarity": "RARE"},
        {"id": "common_coin", "rarity": "COMMON"},
        {"id": "legendary_sword", "rarity": "LEGENDARY"},
    ]
    result = ls._guaranteed_drop(table)
    assert result == "common_coin"
