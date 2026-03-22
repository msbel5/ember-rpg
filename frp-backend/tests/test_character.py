"""
Ember RPG - Core Engine
Character system tests (TDD)
"""
import pytest
from engine.core.character import Character, ProficiencyLevel


class TestCharacterCreation:
    """Test character creation and initialization."""
    
    def test_default_character(self):
        """TC1: Create character with minimal args."""
        char = Character(name="Aldric")
        assert char.name == "Aldric"
        assert char.race == "Human"
        assert char.total_level == 0
        assert char.stats['MIG'] == 10
        assert char.stats['AGI'] == 10
        assert char.stats['END'] == 10
        assert char.stats['MND'] == 10
        assert char.stats['INS'] == 10
        assert char.stats['PRE'] == 10
        assert char.hp == 10
        assert char.max_hp == 10
        assert char.ac == 10
        assert char.gold == 0
        assert char.inventory == []
        assert char.equipment == {}
    
    def test_custom_character(self):
        """TC2: Create character with custom attributes."""
        char = Character(
            name="Theron",
            race="Elf",
            classes={'Warrior': 5},
            stats={'MIG': 16, 'AGI': 14, 'END': 12, 'MND': 8, 'INS': 10, 'PRE': 13},
            hp=54,
            max_hp=54,
            ac=17,
            gold=100
        )
        assert char.name == "Theron"
        assert char.race == "Elf"
        assert char.total_level == 5
        assert char.dominant_class == "Warrior"
        assert char.stat_modifier('MIG') == 3
        assert char.hp == 54
        assert char.ac == 17
        assert char.gold == 100


class TestStatModifiers:
    """Test stat modifier calculations."""
    
    @pytest.mark.parametrize("stat_value,expected_mod", [
        (3, -4),
        (4, -3),
        (5, -3),
        (8, -1),
        (9, -1),
        (10, 0),
        (11, 0),
        (12, 1),
        (14, 2),
        (16, 3),
        (18, 4),
        (20, 5),
    ])
    def test_stat_modifier_calculation(self, stat_value, expected_mod):
        """TC3: Verify stat modifier formula."""
        char = Character(name="Test", stats={'MIG': stat_value})
        assert char.stat_modifier('MIG') == expected_mod
    
    def test_all_stats_modifiers(self):
        """Verify modifiers for all six stats."""
        char = Character(
            name="Test",
            stats={'MIG': 16, 'AGI': 14, 'END': 12, 'MND': 18, 'INS': 10, 'PRE': 8}
        )
        assert char.stat_modifier('MIG') == 3
        assert char.stat_modifier('AGI') == 2
        assert char.stat_modifier('END') == 1
        assert char.stat_modifier('MND') == 4
        assert char.stat_modifier('INS') == 0
        assert char.stat_modifier('PRE') == -1
    
    def test_invalid_stat_name(self):
        """TC8: Invalid stat name raises error."""
        char = Character(name="Test")
        with pytest.raises(ValueError, match="Unknown stat"):
            char.stat_modifier('INVALID')


class TestSkillBonuses:
    """Test skill bonus calculations."""
    
    def test_untrained_skill(self):
        """TC4: Untrained skill (prof=0, stat=10) = 0."""
        char = Character(name="Test", stats={'AGI': 10})
        assert char.skill_bonus('stealth') == 0
    
    def test_trained_skill(self):
        """TC4: Trained skill (prof=2, stat=14) = 4."""
        char = Character(
            name="Test",
            stats={'AGI': 14},
            skills={'stealth': ProficiencyLevel.TRAINED.value}
        )
        assert char.skill_bonus('stealth') == 2 + 2  # stat mod + prof
    
    def test_expert_skill(self):
        """TC4: Expert skill (prof=4, stat=18) = 8."""
        char = Character(
            name="Test",
            stats={'AGI': 18},
            skills={'stealth': ProficiencyLevel.EXPERT.value}
        )
        assert char.skill_bonus('stealth') == 4 + 4  # stat mod + prof
    
    def test_master_skill(self):
        """TC4: Master skill (prof=6, stat=20) = 11."""
        char = Character(
            name="Test",
            stats={'INS': 20},
            skills={'perception': ProficiencyLevel.MASTER.value}
        )
        assert char.skill_bonus('perception') == 5 + 6  # stat mod + prof
    
    def test_all_skills_mapped_to_stats(self):
        """Verify all 12 skills have governing stats."""
        char = Character(
            name="Test",
            stats={'MIG': 14, 'AGI': 12, 'END': 10, 'MND': 16, 'INS': 13, 'PRE': 11},
            skills={
                'athletics': 2, 'stealth': 2, 'survival': 2,
                'melee': 2, 'ranged': 2, 'defense': 2,
                'arcana': 2, 'lore': 2, 'perception': 2,
                'persuasion': 2, 'deception': 2, 'intimidation': 2
            }
        )
        # Spot check a few
        assert char.skill_bonus('athletics') == 2 + 2  # MIG
        assert char.skill_bonus('stealth') == 1 + 2    # AGI
        assert char.skill_bonus('arcana') == 3 + 2     # MND
        assert char.skill_bonus('perception') == 1 + 2 # INS
    
    def test_invalid_skill_name(self):
        """TC8: Invalid skill name raises error."""
        char = Character(name="Test")
        with pytest.raises(ValueError, match="Unknown skill"):
            char.skill_bonus('invalid_skill')


class TestMulticlass:
    """Test multiclass support."""
    
    def test_single_class_level(self):
        """TC5: Single class total_level."""
        char = Character(name="Warrior", classes={'Warrior': 5})
        assert char.total_level == 5
        assert char.dominant_class == 'Warrior'
    
    def test_multiclass_total_level(self):
        """TC5: Multiclass total_level = sum."""
        char = Character(
            name="Spellblade",
            classes={'Warrior': 5, 'Mage': 3}
        )
        assert char.total_level == 8
        assert char.dominant_class == 'Warrior'
    
    def test_add_class_new(self):
        """TC5: add_class creates new class entry."""
        char = Character(name="Test")
        char.add_class('Warrior', 3)
        assert char.classes == {'Warrior': 3}
        assert char.total_level == 3
    
    def test_add_class_existing(self):
        """TC5: add_class increases existing class."""
        char = Character(name="Test", classes={'Mage': 5})
        char.add_class('Mage', 2)
        assert char.classes['Mage'] == 7
        assert char.total_level == 7
    
    def test_multiclass_level_up(self):
        """TC5: Level up different classes independently."""
        char = Character(name="Test")
        char.add_class('Warrior', 5)
        char.add_class('Mage', 3)
        
        assert char.total_level == 8
        assert char.dominant_class == 'Warrior'
        
        # Level up Mage
        char.add_class('Mage', 1)
        assert char.classes['Mage'] == 4
        assert char.total_level == 9
    
    def test_no_classes(self):
        """Edge case: Character with no classes."""
        char = Character(name="Commoner")
        assert char.total_level == 0
        assert char.dominant_class is None


class TestEquipment:
    """Test equipment management."""
    
    def test_equip_item(self):
        """TC6: Equip item to slot."""
        char = Character(name="Knight")
        char.equip_item('weapon', 'longsword_001')
        assert char.equipment['weapon'] == 'longsword_001'
    
    def test_equip_multiple_slots(self):
        """TC6: Equip items to multiple slots."""
        char = Character(name="Knight")
        char.equip_item('weapon', 'longsword_001')
        char.equip_item('armor', 'plate_armor_001')
        char.equip_item('offhand', 'shield_001')
        char.equip_item('accessory', 'ring_001')
        
        assert char.equipment == {
            'weapon': 'longsword_001',
            'armor': 'plate_armor_001',
            'offhand': 'shield_001',
            'accessory': 'ring_001'
        }
    
    def test_unequip_item(self):
        """TC6: Unequip item returns item ID."""
        char = Character(name="Knight")
        char.equip_item('weapon', 'longsword_001')
        
        removed = char.unequip_item('weapon')
        assert removed == 'longsword_001'
        assert 'weapon' not in char.equipment
    
    def test_unequip_empty_slot(self):
        """Edge case: Unequip empty slot returns None."""
        char = Character(name="Test")
        removed = char.unequip_item('weapon')
        assert removed is None
    
    def test_invalid_equipment_slot(self):
        """TC8: Invalid slot raises error."""
        char = Character(name="Test")
        with pytest.raises(ValueError, match="Invalid slot"):
            char.equip_item('invalid_slot', 'item')


class TestSerialization:
    """Test character save/load."""
    
    def test_to_dict(self):
        """TC7: Serialize character to dict."""
        char = Character(
            name="Wizard",
            race="Human",
            classes={'Mage': 10},
            stats={'MIG': 8, 'AGI': 12, 'END': 10, 'MND': 18, 'INS': 14, 'PRE': 13},
            hp=80,
            max_hp=80,
            spell_points=66,
            max_spell_points=66,
            skills={'arcana': 6, 'lore': 4},
            gold=500,
            inventory=['wand_001', 'spellbook_001'],
            equipment={'weapon': 'staff_001', 'accessory': 'ring_001'}
        )
        
        data = char.to_dict()
        
        assert data['name'] == 'Wizard'
        assert data['race'] == 'Human'
        assert data['classes'] == {'Mage': 10}
        assert data['stats']['MND'] == 18
        assert data['hp'] == 80
        assert data['spell_points'] == 66
        assert data['skills'] == {'arcana': 6, 'lore': 4}
        assert data['gold'] == 500
        assert data['inventory'] == ['wand_001', 'spellbook_001']
        assert data['equipment'] == {'weapon': 'staff_001', 'accessory': 'ring_001'}
    
    def test_from_dict(self):
        """TC7: Deserialize character from dict."""
        data = {
            'name': 'Rogue',
            'race': 'Halfling',
            'classes': {'Rogue': 7},
            'stats': {'MIG': 10, 'AGI': 18, 'END': 12, 'MND': 8, 'INS': 14, 'PRE': 13},
            'hp': 70,
            'max_hp': 70,
            'ac': 16,
            'initiative_bonus': 2,
            'spell_points': 0,
            'max_spell_points': 0,
            'skills': {'stealth': 6, 'perception': 4},
            'gold': 300,
            'inventory': ['dagger_001', 'thieves_tools'],
            'equipment': {'weapon': 'shortsword_001'},
            'conditions': []
        }
        
        char = Character.from_dict(data)
        
        assert char.name == 'Rogue'
        assert char.race == 'Halfling'
        assert char.total_level == 7
        assert char.stats['AGI'] == 18
        assert char.skill_bonus('stealth') == 4 + 6  # AGI mod + prof
        assert char.gold == 300
    
    def test_round_trip_serialization(self):
        """TC7: Serialize -> deserialize produces identical character."""
        original = Character(
            name="Paladin",
            race="Human",
            classes={'Warrior': 8, 'Priest': 2},
            stats={'MIG': 16, 'AGI': 10, 'END': 14, 'MND': 12, 'INS': 11, 'PRE': 15},
            hp=100,
            max_hp=100,
            ac=19,
            spell_points=24,
            max_spell_points=24,
            skills={'melee': 4, 'persuasion': 2},
            gold=750,
            inventory=['longsword_001', 'shield_001', 'healing_potion'],
            equipment={'weapon': 'longsword_001', 'offhand': 'shield_001', 'armor': 'plate_armor_001'},
            conditions=['blessed']
        )
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = Character.from_dict(data)
        
        # Verify all fields match
        assert restored.name == original.name
        assert restored.race == original.race
        assert restored.classes == original.classes
        assert restored.stats == original.stats
        assert restored.hp == original.hp
        assert restored.max_hp == original.max_hp
        assert restored.ac == original.ac
        assert restored.spell_points == original.spell_points
        assert restored.skills == original.skills
        assert restored.gold == original.gold
        assert restored.inventory == original.inventory
        assert restored.equipment == original.equipment
        assert restored.conditions == original.conditions
        assert restored.total_level == original.total_level
        assert restored.dominant_class == original.dominant_class


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_extreme_stat_values(self):
        """Test stat modifiers at extremes."""
        char = Character(name="Test", stats={'MIG': 3, 'AGI': 20})
        assert char.stat_modifier('MIG') == -4
        assert char.stat_modifier('AGI') == 5
    
    def test_empty_inventory_and_equipment(self):
        """Character starts with empty inventory."""
        char = Character(name="Test")
        assert char.inventory == []
        assert char.equipment == {}
        assert char.gold == 0
    
    def test_conditions_list(self):
        """Conditions can be added/removed."""
        char = Character(name="Test")
        char.conditions.append('poisoned')
        char.conditions.append('stunned')
        assert 'poisoned' in char.conditions
        assert 'stunned' in char.conditions
        
        char.conditions.remove('poisoned')
        assert 'poisoned' not in char.conditions
