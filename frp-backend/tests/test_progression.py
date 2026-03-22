"""
Ember RPG - Core Engine
Leveling & Progression System tests
"""
import pytest
from engine.core.progression import ProgressionSystem, ClassAbility, LevelUpResult
from engine.core.character import Character


class TestXPThresholds:
    """Test XP-to-level conversion."""

    def test_level_1_at_start(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(0) == 1

    def test_level_1_just_below_2(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(299) == 1

    def test_level_2_at_threshold(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(300) == 2

    def test_level_3_at_threshold(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(900) == 3

    def test_level_5_at_threshold(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(6500) == 5

    def test_level_10_at_threshold(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(64000) == 10

    def test_level_20_max(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(355000) == 20

    def test_level_20_cap_above_max(self):
        ps = ProgressionSystem()
        assert ps.get_level_for_xp(999999) == 20


class TestAddXP:
    """Test XP addition and level-up detection."""

    def test_add_xp_no_level_up(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        result = ps.add_xp(char, 100)

        assert char.xp == 100
        assert char.level == 1
        assert result is None  # No level up

    def test_add_xp_triggers_level_up(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)

        assert char.xp == 300
        assert char.level == 2
        assert result is not None
        assert result.new_level == 2
        assert result.old_level == 1

    def test_multi_level_jump(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        ps.add_xp(char, 2700)

        assert char.level == 4

    def test_xp_accumulates_across_calls(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        ps.add_xp(char, 150)
        ps.add_xp(char, 150)

        assert char.xp == 300
        assert char.level == 2

    def test_level_20_cap(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        ps.add_xp(char, 999999)

        assert char.level == 20  # Capped

    def test_level_up_returns_correct_result(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)

        assert isinstance(result, LevelUpResult)
        assert result.old_level == 1
        assert result.new_level == 2


class TestHPIncrease:
    """Test HP increases on level-up."""

    def test_hp_increases_on_level_up(self):
        char = Character(name="Hero", hp=10, max_hp=10)
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)

        assert result.hp_increase > 0
        assert char.max_hp > 10
        assert char.hp == char.max_hp  # HP refilled on level-up

    def test_hp_increase_warrior_vs_mage(self):
        warrior = Character(name="Warrior", hp=10, max_hp=10,
                            classes={"warrior": 1})
        mage = Character(name="Mage", hp=10, max_hp=10,
                         classes={"mage": 1})
        ps = ProgressionSystem()

        warrior_result = ps.add_xp(warrior, 300)
        mage_result = ps.add_xp(mage, 300)

        # Warriors gain more HP than mages
        assert warrior_result.hp_increase >= mage_result.hp_increase


class TestSpellPoints:
    """Test spell point increases for casters."""

    def test_mage_gains_spell_points(self):
        mage = Character(name="Mage", spell_points=10, max_spell_points=10,
                         classes={"mage": 1})
        ps = ProgressionSystem()
        result = ps.add_xp(mage, 300)

        assert result.sp_increase > 0
        assert mage.max_spell_points > 10

    def test_warrior_no_spell_points(self):
        warrior = Character(name="Warrior", spell_points=0, max_spell_points=0,
                            classes={"warrior": 1})
        ps = ProgressionSystem()
        result = ps.add_xp(warrior, 300)

        assert result.sp_increase == 0
        assert warrior.max_spell_points == 0


class TestStatBonus:
    """Test stat bonuses on even levels."""

    def test_stat_bonus_at_level_2(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)  # -> level 2

        assert result.stat_bonus is not None

    def test_no_stat_bonus_at_odd_level(self):
        char = Character(name="Hero")
        ps = ProgressionSystem()
        ps.add_xp(char, 300)    # L2 — gets bonus
        result = ps.add_xp(char, 600)   # L3 — no bonus

        assert result.stat_bonus is None

    def test_stat_increases_on_bonus(self):
        char = Character(name="Hero",
                         stats={'MIG': 10, 'AGI': 10, 'END': 10,
                                'MND': 10, 'INS': 10, 'PRE': 10})
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)  # L2

        stat = result.stat_bonus
        assert char.stats[stat] == 11  # +1 to chosen stat


class TestClassAbilities:
    """Test class ability unlocking."""

    def test_warrior_l1_abilities(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("warrior", 1)

        assert len(abilities) >= 1
        names = [a.name for a in abilities]
        assert "Combat Stance" in names

    def test_warrior_l3_abilities(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("warrior", 3)

        assert len(abilities) == 3
        names = [a.name for a in abilities]
        assert "Combat Stance" in names
        assert "Second Wind" in names
        assert "Extra Attack" in names

    def test_mage_l1_abilities(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("mage", 1)

        names = [a.name for a in abilities]
        assert "Arcane Recovery" in names

    def test_abilities_have_correct_fields(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("warrior", 1)

        ability = abilities[0]
        assert isinstance(ability, ClassAbility)
        assert ability.name
        assert ability.description
        assert isinstance(ability.passive, bool)
        assert ability.required_level >= 1

    def test_unknown_class_returns_empty(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("dragon", 5)

        assert abilities == []

    def test_level_0_returns_empty(self):
        ps = ProgressionSystem()
        abilities = ps.get_abilities("warrior", 0)

        assert abilities == []

    def test_abilities_on_level_up(self):
        char = Character(name="Warrior", classes={"warrior": 1})
        ps = ProgressionSystem()
        result = ps.add_xp(char, 300)  # L2

        # Level 2 warrior should unlock Second Wind
        new_names = [a.name for a in result.new_abilities]
        assert "Second Wind" in new_names
