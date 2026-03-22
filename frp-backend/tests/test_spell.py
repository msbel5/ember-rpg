"""
Ember RPG - Core Engine
Magic system tests
"""
import pytest
import json
import tempfile
from pathlib import Path
from engine.core.spell import Spell, SpellDatabase, SpellSchool, TargetType
from engine.core.character import Character
from engine.core.effect import HealEffect, DamageEffect, BuffEffect


class TestSpellCreation:
    """Test spell definition and properties."""
    
    def test_damage_spell_creation(self):
        """Create a damage spell."""
        fireball = Spell(
            name="Fireball",
            cost=5,
            range=60,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="3d6", damage_type="fire")],
            school=SpellSchool.EVOCATION,
            level=3,
            description="A roaring ball of flame"
        )
        
        assert fireball.name == "Fireball"
        assert fireball.cost == 5
        assert fireball.range == 60
        assert fireball.target_type == TargetType.SINGLE
        assert fireball.school == SpellSchool.EVOCATION
        assert fireball.level == 3
        assert len(fireball.effects) == 1
    
    def test_heal_spell_creation(self):
        """Create a healing spell."""
        cure = Spell(
            name="Cure Wounds",
            cost=2,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[HealEffect(amount="2d8+2")],
            school=SpellSchool.ABJURATION,
            level=1
        )
        
        assert cure.name == "Cure Wounds"
        assert cure.school == SpellSchool.ABJURATION
        assert isinstance(cure.effects[0], HealEffect)
    
    def test_self_buff_spell(self):
        """Create a self-buff spell."""
        shield = Spell(
            name="Shield",
            cost=2,
            range=0,
            target_type=TargetType.SELF,
            effects=[BuffEffect(stat="END", bonus=4, duration=10)],
            school=SpellSchool.ABJURATION
        )
        
        assert shield.target_type == TargetType.SELF
        assert shield.range == 0


class TestSpellCasting:
    """Test spell casting mechanics."""
    
    def test_cast_damage_spell(self):
        """Cast a damage spell on a target."""
        magic_missile = Spell(
            name="Magic Missile",
            cost=3,
            range=120,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="2d4+2", damage_type="force")]
        )
        
        caster = Character(name="Wizard", spell_points=10, max_spell_points=10)
        target = Character(name="Orc", hp=20, max_hp=20)
        
        result = magic_missile.cast(caster, target)
        
        assert caster.spell_points == 7  # 10 - 3
        assert target.hp < 20  # Damaged
        assert result['caster'] == "Wizard"
        assert result['target'] == "Orc"
        assert result['spell'] == "Magic Missile"
        assert result['cost'] == 3
        assert len(result['effects']) == 1
    
    def test_cast_self_buff(self):
        """Cast a self-buff spell."""
        shield = Spell(
            name="Shield",
            cost=2,
            range=0,
            target_type=TargetType.SELF,
            effects=[BuffEffect(stat="END", bonus=4, duration=10)]
        )
        
        caster = Character(
            name="Mage",
            spell_points=10,
            max_spell_points=10,
            stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}
        )
        
        result = shield.cast(caster)
        
        assert caster.spell_points == 8  # 10 - 2
        assert caster.stats['END'] == 14  # 10 + 4
        assert result['target'] == "Mage"  # Self-targeted
    
    def test_cast_heal_spell(self):
        """Cast a healing spell on ally."""
        cure = Spell(
            name="Cure Wounds",
            cost=2,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[HealEffect(amount="2d8+2")]
        )
        
        caster = Character(name="Cleric", spell_points=10, max_spell_points=10)
        ally = Character(name="Fighter", hp=30, max_hp=50)
        
        result = cure.cast(caster, ally)
        
        assert caster.spell_points == 8
        assert ally.hp > 30  # Healed
        assert ally.hp <= 50  # Capped at max
    
    def test_insufficient_spell_points(self):
        """Casting fails if insufficient spell points."""
        expensive_spell = Spell(
            name="Meteor Swarm",
            cost=20,
            range=240,
            target_type=TargetType.AREA,
            effects=[DamageEffect(amount="10d6", damage_type="fire")]
        )
        
        caster = Character(name="Weak Mage", spell_points=5, max_spell_points=10)
        
        with pytest.raises(ValueError, match="Insufficient spell points"):
            expensive_spell.cast(caster)
        
        # Spell points unchanged
        assert caster.spell_points == 5
    
    def test_single_target_spell_requires_target(self):
        """Single-target spell fails without target."""
        shock = Spell(
            name="Shocking Grasp",
            cost=2,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="2d8", damage_type="lightning")]
        )
        
        caster = Character(name="Mage", spell_points=10, max_spell_points=10)
        
        with pytest.raises(ValueError, match="requires a target"):
            shock.cast(caster)  # No target provided


class TestSpellSerialization:
    """Test spell save/load."""
    
    def test_spell_to_dict(self):
        """Spell serializes to dict."""
        fireball = Spell(
            name="Fireball",
            cost=5,
            range=60,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="3d6", damage_type="fire")],
            school=SpellSchool.EVOCATION,
            level=3,
            description="Fiery explosion"
        )
        
        data = fireball.to_dict()
        
        assert data['name'] == "Fireball"
        assert data['cost'] == 5
        assert data['target_type'] == "single"
        assert data['school'] == "evocation"
        assert len(data['effects']) == 1
    
    def test_spell_from_dict(self):
        """Spell deserializes from dict."""
        data = {
            "name": "Lightning Bolt",
            "cost": 4,
            "range": 100,
            "target_type": "single",
            "school": "evocation",
            "level": 3,
            "description": "A bolt of lightning",
            "effects": [
                {"type": "damage", "amount": "4d6", "damage_type": "lightning"}
            ]
        }
        
        spell = Spell.from_dict(data)
        
        assert spell.name == "Lightning Bolt"
        assert spell.cost == 4
        assert spell.target_type == TargetType.SINGLE
        assert spell.school == SpellSchool.EVOCATION
        assert len(spell.effects) == 1
        assert isinstance(spell.effects[0], DamageEffect)
    
    def test_round_trip_serialization(self):
        """Spell survives round-trip."""
        original = Spell(
            name="Cure Serious Wounds",
            cost=4,
            range=5,
            target_type=TargetType.SINGLE,
            effects=[HealEffect(amount="4d8+4")],
            school=SpellSchool.ABJURATION,
            level=3
        )
        
        data = original.to_dict()
        restored = Spell.from_dict(data)
        
        assert restored.name == original.name
        assert restored.cost == original.cost
        assert restored.target_type == original.target_type
        assert len(restored.effects) == 1


class TestSpellDatabase:
    """Test spell database loading and querying."""
    
    def test_empty_database(self):
        """Create empty database."""
        db = SpellDatabase()
        assert len(db.spells) == 0
    
    def test_add_spell(self):
        """Add spell to database."""
        db = SpellDatabase()
        
        fireball = Spell(
            name="Fireball",
            cost=5,
            range=60,
            target_type=TargetType.SINGLE,
            effects=[DamageEffect(amount="3d6", damage_type="fire")],
            school=SpellSchool.EVOCATION
        )
        
        db.add(fireball)
        assert len(db.spells) == 1
    
    def test_get_spell_by_name(self):
        """Retrieve spell by name."""
        db = SpellDatabase()
        db.add(Spell(name="Fireball", cost=5, range=60, target_type=TargetType.SINGLE))
        db.add(Spell(name="Lightning Bolt", cost=4, range=100, target_type=TargetType.SINGLE))
        
        spell = db.get("Fireball")
        assert spell is not None
        assert spell.name == "Fireball"
    
    def test_get_spell_case_insensitive(self):
        """Spell name lookup is case-insensitive."""
        db = SpellDatabase()
        db.add(Spell(name="Magic Missile", cost=3, range=120, target_type=TargetType.SINGLE))
        
        assert db.get("magic missile") is not None
        assert db.get("MAGIC MISSILE") is not None
        assert db.get("Magic Missile") is not None
    
    def test_get_nonexistent_spell(self):
        """Get returns None for missing spell."""
        db = SpellDatabase()
        assert db.get("Nonexistent Spell") is None
    
    def test_filter_by_school(self):
        """Filter spells by school."""
        db = SpellDatabase()
        db.add(Spell(name="Fireball", cost=5, range=60, target_type=TargetType.SINGLE, school=SpellSchool.EVOCATION))
        db.add(Spell(name="Shield", cost=2, range=0, target_type=TargetType.SELF, school=SpellSchool.ABJURATION))
        db.add(Spell(name="Lightning", cost=4, range=100, target_type=TargetType.SINGLE, school=SpellSchool.EVOCATION))
        
        evocation = db.filter(school=SpellSchool.EVOCATION)
        assert len(evocation) == 2
        assert all(s.school == SpellSchool.EVOCATION for s in evocation)
    
    def test_filter_by_cost(self):
        """Filter spells by max cost."""
        db = SpellDatabase()
        db.add(Spell(name="Cantrip", cost=1, range=30, target_type=TargetType.SINGLE))
        db.add(Spell(name="Moderate", cost=5, range=60, target_type=TargetType.SINGLE))
        db.add(Spell(name="Expensive", cost=10, range=120, target_type=TargetType.SINGLE))
        
        cheap = db.filter(max_cost=5)
        assert len(cheap) == 2
        assert all(s.cost <= 5 for s in cheap)
    
    def test_filter_by_level(self):
        """Filter spells by max level."""
        db = SpellDatabase()
        db.add(Spell(name="L1", cost=2, range=30, target_type=TargetType.SINGLE, level=1))
        db.add(Spell(name="L3", cost=5, range=60, target_type=TargetType.SINGLE, level=3))
        db.add(Spell(name="L5", cost=8, range=100, target_type=TargetType.SINGLE, level=5))
        
        low_level = db.filter(max_level=3)
        assert len(low_level) == 2
        assert all(s.level <= 3 for s in low_level)
    
    def test_load_from_json(self):
        """Load spells from JSON file."""
        # Create temp JSON file
        spell_data = {
            "spells": [
                {
                    "name": "Fireball",
                    "cost": 5,
                    "range": 60,
                    "target_type": "single",
                    "school": "evocation",
                    "level": 3,
                    "description": "Fiery explosion",
                    "effects": [
                        {"type": "damage", "amount": "3d6", "damage_type": "fire"}
                    ]
                },
                {
                    "name": "Cure Wounds",
                    "cost": 2,
                    "range": 5,
                    "target_type": "single",
                    "school": "abjuration",
                    "level": 1,
                    "description": "Healing touch",
                    "effects": [
                        {"type": "heal", "amount": "2d8+2"}
                    ]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(spell_data, f)
            temp_path = f.name
        
        try:
            db = SpellDatabase(temp_path)
            
            assert len(db.spells) == 2
            
            fireball = db.get("Fireball")
            assert fireball is not None
            assert fireball.cost == 5
            assert fireball.school == SpellSchool.EVOCATION
            
            cure = db.get("Cure Wounds")
            assert cure is not None
            assert cure.school == SpellSchool.ABJURATION
        finally:
            Path(temp_path).unlink()


class TestSpellCanCast:
    """Test can_cast validation."""
    
    def test_can_cast_with_enough_points(self):
        """Can cast when spell points sufficient."""
        spell = Spell(name="Test", cost=5, range=30, target_type=TargetType.SINGLE)
        caster = Character(name="Mage", spell_points=10, max_spell_points=10)
        
        assert spell.can_cast(caster) is True
    
    def test_cannot_cast_with_insufficient_points(self):
        """Cannot cast when spell points insufficient."""
        spell = Spell(name="Expensive", cost=10, range=30, target_type=TargetType.SINGLE)
        caster = Character(name="Mage", spell_points=5, max_spell_points=10)
        
        assert spell.can_cast(caster) is False
    
    def test_can_cast_exact_cost(self):
        """Can cast when spell points exactly match cost."""
        spell = Spell(name="Test", cost=5, range=30, target_type=TargetType.SINGLE)
        caster = Character(name="Mage", spell_points=5, max_spell_points=10)
        
        assert spell.can_cast(caster) is True
