"""
Ember RPG - Core Engine
Combat spell casting integration tests
"""
import pytest
from engine.core.combat import CombatManager
from engine.core.character import Character
from engine.core.spell import Spell, SpellSchool, TargetType
from engine.core.effect import HealEffect, DamageEffect, BuffEffect


class TestCombatSpellCasting:
    """Test spell casting in combat."""
    
    def test_cast_damage_spell_in_combat(self):
        """Cast damage spell during combat."""
        mage = Character(
            name="Mage",
            spell_points=10,
            max_spell_points=10,
            stats={'MIG': 10, 'AGI': 20, 'END': 10, 'MND': 16, 'INS': 10, 'PRE': 10},
            initiative_bonus=100
        )
        warrior = Character(
            name="Warrior",
            hp=50,
            max_hp=50,
            stats={'MIG': 16, 'AGI': 10, 'END': 14, 'MND': 8, 'INS': 10, 'PRE': 10}
        )
        
        shock = Spell(
            name="Shocking Grasp",
            cost=2,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="2d8", damage_type="lightning")],
            school=SpellSchool.EVOCATION
        )
        
        combat = CombatManager([mage, warrior], seed=1)
        combat.start_turn()
        
        # Ensure mage is active
        assert combat.active_combatant.name == "Mage"
        
        # Find warrior index
        warrior_idx = next(i for i, c in enumerate(combat.combatants) if c.name == "Warrior")
        
        initial_ap = combat.active_combatant.ap
        result = combat.cast_spell(shock, target_index=warrior_idx)
        
        assert 'effects' in result
        assert result['caster'] == "Mage"
        assert result['target'] == "Warrior"
        assert result['spell'] == "Shocking Grasp"
        assert combat.active_combatant.ap == initial_ap - 2  # Costs 2 AP
        assert mage.spell_points == 8  # 10 - 2
        assert warrior.hp < 50  # Damaged
    
    def test_cast_heal_spell_in_combat(self):
        """Cast healing spell on ally."""
        cleric = Character(
            name="Cleric",
            spell_points=10,
            max_spell_points=10,
            hp=30,
            max_hp=50,
            initiative_bonus=100
        )
        fighter = Character(name="Fighter", hp=20, max_hp=50)
        
        cure = Spell(
            name="Cure Wounds",
            cost=2,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[HealEffect(amount="2d8+2")],
            school=SpellSchool.ABJURATION
        )
        
        combat = CombatManager([cleric, fighter], seed=1)
        combat.start_turn()
        
        fighter_idx = next(i for i, c in enumerate(combat.combatants) if c.name == "Fighter")
        result = combat.cast_spell(cure, target_index=fighter_idx)
        
        assert 'effects' in result
        assert combat.combatants[fighter_idx].character.hp > 20  # Healed
    
    def test_cast_self_buff_in_combat(self):
        """Cast self-buff spell."""
        mage = Character(
            name="Mage",
            spell_points=10,
            max_spell_points=10,
            stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 16, 'INS': 10, 'PRE': 10},
            initiative_bonus=100
        )
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        shield = Spell(
            name="Shield",
            cost=2,
            range=0,
            target_type=TargetType.SELF,
            effects=[BuffEffect(stat="END", bonus=4, duration=10)],
            school=SpellSchool.ABJURATION
        )
        
        combat = CombatManager([mage, enemy], seed=1)
        combat.start_turn()
        
        result = combat.cast_spell(shield)  # No target needed for SELF
        
        assert result['target'] == "Mage"
        assert mage.stats['END'] == 14  # 10 + 4
    
    def test_insufficient_ap_for_spell(self):
        """Spell fails if insufficient AP."""
        mage = Character(
            name="Mage",
            spell_points=10,
            max_spell_points=10,
            initiative_bonus=100
        )
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        spell = Spell(
            name="Test",
            cost=1,
            range=30,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="1d4", damage_type="force")]
        )
        
        combat = CombatManager([mage, enemy], seed=1)
        combat.start_turn()
        
        # Use 2 AP (leaving 1)
        combat.active_combatant.ap = 1
        
        result = combat.cast_spell(spell, target_index=1)
        
        assert 'error' in result
        assert "Insufficient AP" in result['error']
    
    def test_insufficient_spell_points_in_combat(self):
        """Spell fails if insufficient spell points."""
        mage = Character(
            name="Mage",
            spell_points=1,
            max_spell_points=10,
            initiative_bonus=100
        )
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        expensive_spell = Spell(
            name="Expensive",
            cost=10,
            range=60,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="5d6", damage_type="fire")]
        )
        
        combat = CombatManager([mage, enemy], seed=1)
        combat.start_turn()
        
        result = combat.cast_spell(expensive_spell, target_index=1)
        
        assert 'error' in result
        assert "Insufficient spell points" in result['error']
    
    def test_single_target_spell_requires_target_in_combat(self):
        """Single-target spell fails without target."""
        mage = Character(
            name="Mage",
            spell_points=10,
            max_spell_points=10,
            initiative_bonus=100
        )
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        spell = Spell(
            name="Test",
            cost=2,
            range=30,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="1d6", damage_type="fire")]
        )
        
        combat = CombatManager([mage, enemy], seed=1)
        combat.start_turn()
        
        result = combat.cast_spell(spell)  # No target
        
        assert 'error' in result
        assert "requires target" in result['error']
