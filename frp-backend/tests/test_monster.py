"""
Ember RPG - Monster Bestiary Integration Tests
TDD: tests written first, then implementation verified.
"""
import json
import os
import pytest
from engine.core.monster import (
    Monster,
    MonsterDatabase,
    MonsterType,
    Attack,
    Abilities,
    Stats,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "monsters.json")


def get_db() -> MonsterDatabase:
    """Return a fully loaded MonsterDatabase from the real data file."""
    return MonsterDatabase(DATA_PATH)


# ---------------------------------------------------------------------------
# Data file sanity
# ---------------------------------------------------------------------------


class TestMonstersJsonFile:
    """Validate the raw JSON data file."""

    def test_file_exists(self):
        assert os.path.exists(DATA_PATH), f"monsters.json not found at {DATA_PATH}"

    def test_file_valid_json(self):
        with open(DATA_PATH) as f:
            data = json.load(f)
        assert "monsters" in data

    def test_at_least_30_monsters(self):
        with open(DATA_PATH) as f:
            data = json.load(f)
        assert len(data["monsters"]) >= 30

    def test_required_fields_present(self):
        required = {"id", "name", "type", "cr", "hp", "armor_class", "speed",
                    "stats", "attacks", "abilities", "xp_reward", "loot_table"}
        with open(DATA_PATH) as f:
            data = json.load(f)
        for m in data["monsters"]:
            missing = required - set(m.keys())
            assert not missing, f"Monster '{m.get('name')}' missing fields: {missing}"

    def test_cr_range(self):
        with open(DATA_PATH) as f:
            data = json.load(f)
        for m in data["monsters"]:
            assert 0 <= m["cr"] <= 30, f"CR out of range for {m['name']}: {m['cr']}"

    def test_all_types_valid(self):
        valid_types = {t.value for t in MonsterType}
        with open(DATA_PATH) as f:
            data = json.load(f)
        for m in data["monsters"]:
            assert m["type"] in valid_types, f"Invalid type '{m['type']}' for {m['name']}"

    def test_stats_have_six_scores(self):
        required_stats = {"str", "dex", "con", "int", "wis", "cha"}
        with open(DATA_PATH) as f:
            data = json.load(f)
        for m in data["monsters"]:
            missing = required_stats - set(m["stats"].keys())
            assert not missing, f"Missing stats for {m['name']}: {missing}"

    def test_each_monster_has_at_least_one_attack(self):
        with open(DATA_PATH) as f:
            data = json.load(f)
        for m in data["monsters"]:
            assert len(m["attacks"]) >= 1, f"{m['name']} has no attacks"


# ---------------------------------------------------------------------------
# MonsterDatabase loading
# ---------------------------------------------------------------------------


class TestMonsterDatabaseLoad:
    """Test MonsterDatabase initialisation and loading."""

    def test_empty_init(self):
        db = MonsterDatabase()
        assert db.monsters == []

    def test_load_from_file(self):
        db = get_db()
        assert len(db.monsters) >= 30

    def test_all_items_are_monster_instances(self):
        db = get_db()
        for m in db.monsters:
            assert isinstance(m, Monster)

    def test_monster_types_parsed(self):
        db = get_db()
        for m in db.monsters:
            assert isinstance(m.type, MonsterType)

    def test_attacks_parsed(self):
        db = get_db()
        for m in db.monsters:
            for atk in m.attacks:
                assert isinstance(atk, Attack)

    def test_abilities_parsed(self):
        db = get_db()
        for m in db.monsters:
            assert isinstance(m.abilities, Abilities)

    def test_stats_parsed(self):
        db = get_db()
        for m in db.monsters:
            assert isinstance(m.stats, Stats)


# ---------------------------------------------------------------------------
# MonsterDatabase.get
# ---------------------------------------------------------------------------


class TestMonsterDatabaseGet:
    """Test get() by name and id."""

    def test_get_by_name(self):
        db = get_db()
        wolf = db.get("Wolf")
        assert wolf is not None
        assert wolf.name == "Wolf"

    def test_get_case_insensitive(self):
        db = get_db()
        assert db.get("wolf") is not None
        assert db.get("WOLF") is not None

    def test_get_by_id(self):
        db = get_db()
        assert db.get("wolf") is not None

    def test_get_nonexistent_returns_none(self):
        db = get_db()
        assert db.get("Unicorn Dragon Supreme") is None

    def test_get_boss_by_name(self):
        db = get_db()
        lich = db.get("Lich")
        assert lich is not None
        assert lich.type == MonsterType.BOSS


# ---------------------------------------------------------------------------
# MonsterDatabase.filter
# ---------------------------------------------------------------------------


class TestMonsterDatabaseFilter:
    """Test filter() by type, min_cr, max_cr."""

    def test_filter_by_type_beast(self):
        db = get_db()
        beasts = db.filter(monster_type=MonsterType.BEAST)
        assert len(beasts) >= 3
        for m in beasts:
            assert m.type == MonsterType.BEAST

    def test_filter_by_type_undead(self):
        db = get_db()
        undead = db.filter(monster_type=MonsterType.UNDEAD)
        assert len(undead) >= 3
        for m in undead:
            assert m.type == MonsterType.UNDEAD

    def test_filter_by_type_humanoid(self):
        db = get_db()
        humanoids = db.filter(monster_type=MonsterType.HUMANOID)
        assert len(humanoids) >= 3

    def test_filter_by_type_elemental(self):
        db = get_db()
        elementals = db.filter(monster_type=MonsterType.ELEMENTAL)
        assert len(elementals) >= 3

    def test_filter_by_type_boss(self):
        db = get_db()
        bosses = db.filter(monster_type=MonsterType.BOSS)
        assert len(bosses) >= 3

    def test_filter_by_max_cr(self):
        db = get_db()
        low_cr = db.filter(max_cr=1.0)
        for m in low_cr:
            assert m.cr <= 1.0

    def test_filter_by_min_cr(self):
        db = get_db()
        high_cr = db.filter(min_cr=10.0)
        for m in high_cr:
            assert m.cr >= 10.0

    def test_filter_combined(self):
        db = get_db()
        results = db.filter(monster_type=MonsterType.BOSS, min_cr=10.0)
        assert len(results) >= 1
        for m in results:
            assert m.type == MonsterType.BOSS
            assert m.cr >= 10.0

    def test_filter_empty_result(self):
        db = get_db()
        results = db.filter(min_cr=100.0)
        assert results == []

    def test_filter_no_args_returns_all(self):
        db = get_db()
        assert len(db.filter()) == len(db.monsters)


# ---------------------------------------------------------------------------
# MonsterDatabase.add
# ---------------------------------------------------------------------------


class TestMonsterDatabaseAdd:
    """Test add() method."""

    def test_add_monster(self):
        db = MonsterDatabase()
        m = Monster(
            id="test_beast",
            name="Test Beast",
            type=MonsterType.BEAST,
            cr=0.5,
            hp=10,
            armor_class=12,
            speed=30,
            stats=Stats(str=10, dex=10, con=10, **{"int": 2}, wis=10, cha=5),
            attacks=[Attack("Claw", "1d4", "slashing", 2)],
            abilities=Abilities(),
            xp_reward=50,
        )
        db.add(m)
        assert len(db.monsters) == 1
        assert db.get("Test Beast") is m


# ---------------------------------------------------------------------------
# Monster dataclass helpers
# ---------------------------------------------------------------------------


class TestMonsterHelpers:
    """Test Monster instance helper methods."""

    def test_is_resistant_to(self):
        db = get_db()
        skeleton = db.get("Skeleton")
        assert skeleton is not None
        assert skeleton.is_resistant_to("piercing") is True
        assert skeleton.is_resistant_to("fire") is False

    def test_is_immune_to(self):
        db = get_db()
        skeleton = db.get("Skeleton")
        assert skeleton.is_immune_to("poison") is True
        assert skeleton.is_immune_to("slashing") is False

    def test_has_ability(self):
        db = get_db()
        wolf = db.get("Wolf")
        assert wolf.has_ability("Pack Tactics") is True
        assert wolf.has_ability("Fire Breath") is False

    def test_repr(self):
        db = get_db()
        wolf = db.get("Wolf")
        r = repr(wolf)
        assert "Wolf" in r
        assert "beast" in r

    def test_stats_modifier(self):
        stats = Stats(str=10, dex=14, con=12, **{"int": 8}, wis=10, cha=6)
        assert stats.modifier("str") == 0
        assert stats.modifier("dex") == 2
        assert stats.modifier("con") == 1
        assert stats.modifier("int") == -1
        assert stats.modifier("cha") == -2

    def test_to_dict_round_trip(self):
        db = get_db()
        original = db.get("Goblin")
        assert original is not None
        data = original.to_dict()
        restored = Monster.from_dict(data)
        assert restored.name == original.name
        assert restored.cr == original.cr
        assert restored.hp == original.hp
        assert restored.type == original.type
        assert len(restored.attacks) == len(original.attacks)

    def test_loot_table_populated(self):
        db = get_db()
        wolf = db.get("Wolf")
        assert isinstance(wolf.loot_table, list)
        assert len(wolf.loot_table) >= 1


# ---------------------------------------------------------------------------
# Category coverage checks
# ---------------------------------------------------------------------------


class TestCategoryCoverage:
    """Ensure all required monster categories are represented."""

    def test_has_wolf(self):
        assert get_db().get("Wolf") is not None

    def test_has_bear(self):
        db = get_db()
        bears = [m for m in db.monsters if "bear" in m.name.lower()]
        assert len(bears) >= 1

    def test_has_spider(self):
        db = get_db()
        spiders = [m for m in db.monsters if "spider" in m.name.lower()]
        assert len(spiders) >= 1

    def test_has_skeleton(self):
        assert get_db().get("Skeleton") is not None

    def test_has_zombie(self):
        assert get_db().get("Zombie") is not None

    def test_has_vampire(self):
        db = get_db()
        vampires = [m for m in db.monsters if "vampire" in m.name.lower()]
        assert len(vampires) >= 1

    def test_has_goblin(self):
        assert get_db().get("Goblin") is not None

    def test_has_orc(self):
        assert get_db().get("Orc") is not None

    def test_has_bandit(self):
        assert get_db().get("Bandit") is not None

    def test_has_fire_elemental(self):
        assert get_db().get("Fire Elemental") is not None

    def test_has_water_elemental(self):
        assert get_db().get("Water Elemental") is not None

    def test_has_earth_elemental(self):
        assert get_db().get("Earth Elemental") is not None

    def test_has_dragon(self):
        db = get_db()
        dragons = [m for m in db.monsters if "dragon" in m.name.lower()]
        assert len(dragons) >= 1

    def test_has_lich(self):
        assert get_db().get("Lich") is not None

    def test_has_demon_lord(self):
        db = get_db()
        demons = [m for m in db.monsters if "demon" in m.name.lower()]
        assert len(demons) >= 1
