"""
Ember RPG - Core Engine
Effect system tests
"""
import pytest
from engine.core.character import Character
from engine.core.effect import Effect, HealEffect, DamageEffect, BuffEffect


class TestHealEffect:
    """Test healing effects."""
    
    def test_heal_restores_hp(self):
        """Heal effect restores HP."""
        char = Character(name="Test", hp=50, max_hp=100)
        effect = HealEffect(amount="2d6+2")
        
        message = effect.apply(char)
        
        assert char.hp > 50  # HP increased
        assert char.hp <= 100  # Capped at max
        assert "heals" in message
        assert "Test" in message
    
    def test_heal_capped_at_max_hp(self):
        """Heal cannot exceed max_hp."""
        char = Character(name="Test", hp=95, max_hp=100)
        effect = HealEffect(amount="10d10+50")  # Huge heal
        
        effect.apply(char)
        
        assert char.hp == 100  # Capped at max
    
    def test_heal_at_full_hp(self):
        """Heal at full HP has no effect."""
        char = Character(name="Test", hp=100, max_hp=100)
        effect = HealEffect(amount="2d6+2")
        
        message = effect.apply(char)
        
        assert char.hp == 100
        assert "heals 0 HP" in message
    
    def test_heal_serialization(self):
        """HealEffect serializes correctly."""
        effect = HealEffect(amount="2d6+2")
        data = effect.to_dict()
        
        assert data == {'type': 'heal', 'amount': '2d6+2'}
        
        restored = Effect.from_dict(data)
        assert isinstance(restored, HealEffect)
        assert restored.amount == "2d6+2"


class TestDamageEffect:
    """Test damage effects."""
    
    def test_damage_reduces_hp(self):
        """Damage effect reduces HP."""
        char = Character(name="Test", hp=100, max_hp=100)
        effect = DamageEffect(amount="2d6", damage_type="fire")
        
        message = effect.apply(char)
        
        assert char.hp < 100  # HP decreased
        assert "takes" in message
        assert "fire damage" in message
    
    def test_damage_can_reduce_below_zero(self):
        """Damage can bring HP below 0 (death)."""
        char = Character(name="Test", hp=10, max_hp=100)
        effect = DamageEffect(amount="10d10", damage_type="necrotic")
        
        effect.apply(char)
        
        assert char.hp < 0  # Dead
    
    def test_damage_serialization(self):
        """DamageEffect serializes correctly."""
        effect = DamageEffect(amount="1d6", damage_type="fire")
        data = effect.to_dict()
        
        assert data == {'type': 'damage', 'amount': '1d6', 'damage_type': 'fire'}
        
        restored = Effect.from_dict(data)
        assert isinstance(restored, DamageEffect)
        assert restored.amount == "1d6"
        assert restored.damage_type == "fire"


class TestBuffEffect:
    """Test buff effects."""
    
    def test_buff_increases_stat(self):
        """Buff effect increases stat temporarily."""
        char = Character(name="Test", stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        effect = BuffEffect(stat="MIG", bonus=2, duration=10)
        
        message = effect.apply(char)
        
        assert char.stats['MIG'] == 12  # +2
        assert "gains +2 MIG" in message
    
    def test_buff_multiple_stats(self):
        """Multiple buffs can stack."""
        char = Character(name="Test", stats={'MIG': 10, 'AGI': 14, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        
        BuffEffect(stat="MIG", bonus=2, duration=5).apply(char)
        BuffEffect(stat="AGI", bonus=4, duration=3).apply(char)
        
        assert char.stats['MIG'] == 12
        assert char.stats['AGI'] == 18
    
    def test_buff_invalid_stat(self):
        """Buff with invalid stat raises error."""
        char = Character(name="Test")
        effect = BuffEffect(stat="INVALID", bonus=2, duration=5)
        
        with pytest.raises(ValueError, match="Invalid stat"):
            effect.apply(char)
    
    def test_buff_serialization(self):
        """BuffEffect serializes correctly."""
        effect = BuffEffect(stat="MIG", bonus=4, duration=10)
        data = effect.to_dict()
        
        assert data == {'type': 'buff', 'stat': 'MIG', 'bonus': 4, 'duration': 10}
        
        restored = Effect.from_dict(data)
        assert isinstance(restored, BuffEffect)
        assert restored.stat == "MIG"
        assert restored.bonus == 4
        assert restored.duration == 10


class TestEffectDeserialization:
    """Test Effect.from_dict for all types."""
    
    def test_deserialize_heal(self):
        """Deserialize HealEffect."""
        data = {'type': 'heal', 'amount': '3d8+3'}
        effect = Effect.from_dict(data)
        assert isinstance(effect, HealEffect)
        assert effect.amount == '3d8+3'
    
    def test_deserialize_damage(self):
        """Deserialize DamageEffect."""
        data = {'type': 'damage', 'amount': '2d6', 'damage_type': 'cold'}
        effect = Effect.from_dict(data)
        assert isinstance(effect, DamageEffect)
        assert effect.amount == '2d6'
        assert effect.damage_type == 'cold'
    
    def test_deserialize_buff(self):
        """Deserialize BuffEffect."""
        data = {'type': 'buff', 'stat': 'AGI', 'bonus': 3, 'duration': 5}
        effect = Effect.from_dict(data)
        assert isinstance(effect, BuffEffect)
        assert effect.stat == 'AGI'
    
    def test_deserialize_unknown_type(self):
        """Unknown effect type raises error."""
        data = {'type': 'unknown', 'value': 123}
        with pytest.raises(ValueError, match="Unknown effect type"):
            Effect.from_dict(data)
    
    def test_deserialize_missing_type(self):
        """Missing 'type' field raises error."""
        data = {'amount': '1d6'}
        with pytest.raises(ValueError, match="missing 'type' field"):
            Effect.from_dict(data)
