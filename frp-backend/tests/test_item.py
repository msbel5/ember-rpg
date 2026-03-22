"""
Ember RPG - Core Engine
Item system tests
"""
import pytest
from engine.core.item import Item, ItemType, Rarity
from engine.core.effect import HealEffect, DamageEffect, BuffEffect
from engine.core.character import Character


class TestItemCreation:
    """Test item creation and basic properties."""
    
    def test_weapon_creation(self):
        """Create a weapon with damage dice."""
        longsword = Item(
            name="Longsword",
            value=15,
            weight=3.0,
            item_type=ItemType.WEAPON,
            damage_dice="1d10",
            damage_type="slashing"
        )
        assert longsword.name == "Longsword"
        assert longsword.value == 15
        assert longsword.weight == 3.0
        assert longsword.item_type == ItemType.WEAPON
        assert longsword.damage_dice == "1d10"
        assert longsword.damage_type == "slashing"
        assert longsword.rarity == Rarity.COMMON
        assert longsword.total_value == 15
        assert longsword.total_weight == 3.0
    
    def test_armor_creation(self):
        """Create armor with AC bonus."""
        plate_armor = Item(
            name="Plate Armor",
            value=1500,
            weight=45.0,
            item_type=ItemType.ARMOR,
            armor_bonus=6,
            armor_type="heavy",
            rarity=Rarity.UNCOMMON
        )
        assert plate_armor.armor_bonus == 6
        assert plate_armor.armor_type == "heavy"
        assert plate_armor.rarity == Rarity.UNCOMMON
    
    def test_consumable_with_effects(self):
        """Create consumable with heal effect."""
        potion = Item(
            name="Potion of Healing",
            value=50,
            weight=0.5,
            item_type=ItemType.CONSUMABLE,
            effects=[HealEffect(amount="2d6+2")],
            stackable=True
        )
        assert len(potion.effects) == 1
        assert isinstance(potion.effects[0], HealEffect)
        assert potion.stackable is True
    
    def test_quest_item_restrictions(self):
        """Quest items cannot be dropped or sold."""
        ancient_key = Item(
            name="Ancient Key",
            value=0,
            weight=0.1,
            item_type=ItemType.QUEST,
            can_drop=False,
            can_sell=False,
            description="A key covered in glowing runes"
        )
        assert ancient_key.can_drop is False
        assert ancient_key.can_sell is False
        assert ancient_key.description != ""
    
    def test_currency_item(self):
        """Currency items are stackable."""
        gold = Item(
            name="Gold Coins",
            value=1,
            weight=0.02,
            item_type=ItemType.CURRENCY,
            stackable=True,
            quantity=100
        )
        assert gold.stackable is True
        assert gold.quantity == 100


class TestItemStacking:
    """Test stackable item mechanics."""
    
    def test_stackable_total_value(self):
        """Stackable items calculate total value correctly."""
        gold = Item(
            name="Gold Coins",
            value=1,
            weight=0.02,
            item_type=ItemType.CURRENCY,
            stackable=True,
            quantity=100
        )
        assert gold.total_value == 100  # 1 × 100
    
    def test_stackable_total_weight(self):
        """Stackable items calculate total weight correctly."""
        arrows = Item(
            name="Arrows",
            value=1,
            weight=0.05,
            item_type=ItemType.WEAPON,
            stackable=True,
            quantity=20
        )
        assert arrows.total_weight == 1.0  # 0.05 × 20
    
    def test_non_stackable_defaults(self):
        """Non-stackable items default to quantity 1."""
        sword = Item(
            name="Sword",
            value=15,
            weight=3.0,
            item_type=ItemType.WEAPON,
            stackable=False
        )
        assert sword.quantity == 1
        assert sword.total_value == 15
        assert sword.total_weight == 3.0


class TestItemEffects:
    """Test item effect application."""
    
    def test_apply_heal_effect(self):
        """Potion heals character."""
        char = Character(name="Warrior", hp=50, max_hp=100)
        potion = Item(
            name="Potion",
            value=50,
            weight=0.5,
            item_type=ItemType.CONSUMABLE,
            effects=[HealEffect(amount="2d6+2")]
        )
        
        messages = potion.apply_effects(char)
        
        assert char.hp > 50  # HP increased
        assert len(messages) == 1
        assert "heals" in messages[0]
    
    def test_apply_multiple_effects(self):
        """Item with multiple effects applies all."""
        char = Character(name="Test", hp=100, max_hp=100, stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        elixir = Item(
            name="Elixir of Might",
            value=500,
            weight=0.5,
            item_type=ItemType.CONSUMABLE,
            effects=[
                BuffEffect(stat="MIG", bonus=4, duration=10),
                HealEffect(amount="1d6")
            ]
        )
        
        messages = elixir.apply_effects(char)
        
        assert len(messages) == 2
        assert char.stats['MIG'] == 14  # +4 buff
        assert char.hp >= 100  # Heal applied (may be capped)
    
    def test_apply_damage_effect(self):
        """Poison item deals damage."""
        char = Character(name="Test", hp=100, max_hp=100)
        poison = Item(
            name="Vial of Poison",
            value=25,
            weight=0.1,
            item_type=ItemType.CONSUMABLE,
            effects=[DamageEffect(amount="1d6", damage_type="poison")]
        )
        
        messages = poison.apply_effects(char)
        
        assert char.hp < 100  # Damaged
        assert "poison damage" in messages[0]


class TestItemRarity:
    """Test item rarity system."""
    
    def test_common_rarity(self):
        """Common items have default rarity."""
        item = Item(
            name="Iron Sword",
            value=10,
            weight=3.0,
            item_type=ItemType.WEAPON
        )
        assert item.rarity == Rarity.COMMON
    
    def test_rare_item(self):
        """Rare items have correct rarity."""
        item = Item(
            name="Rare Gem",
            value=500,
            weight=0.1,
            item_type=ItemType.QUEST,
            rarity=Rarity.RARE
        )
        assert item.rarity == Rarity.RARE
    
    def test_legendary_item(self):
        """Legendary items have correct rarity."""
        item = Item(
            name="Excalibur",
            value=10000,
            weight=4.0,
            item_type=ItemType.WEAPON,
            rarity=Rarity.LEGENDARY,
            damage_dice="2d10",
            damage_type="radiant"
        )
        assert item.rarity == Rarity.LEGENDARY


class TestItemSerialization:
    """Test item save/load."""
    
    def test_simple_weapon_serialization(self):
        """Simple weapon round-trips correctly."""
        original = Item(
            name="Longsword",
            value=15,
            weight=3.0,
            item_type=ItemType.WEAPON,
            damage_dice="1d10",
            damage_type="slashing"
        )
        
        data = original.to_dict()
        restored = Item.from_dict(data)
        
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.weight == original.weight
        assert restored.item_type == original.item_type
        assert restored.damage_dice == original.damage_dice
        assert restored.damage_type == original.damage_type
    
    def test_consumable_with_effects_serialization(self):
        """Consumable with effects round-trips correctly."""
        original = Item(
            name="Healing Potion",
            value=50,
            weight=0.5,
            item_type=ItemType.CONSUMABLE,
            effects=[HealEffect(amount="2d6+2")],
            stackable=True,
            quantity=3
        )
        
        data = original.to_dict()
        restored = Item.from_dict(data)
        
        assert restored.name == original.name
        assert len(restored.effects) == 1
        assert isinstance(restored.effects[0], HealEffect)
        assert restored.stackable is True
        assert restored.quantity == 3
    
    def test_complex_item_serialization(self):
        """Complex item with multiple effects and properties."""
        original = Item(
            name="Flaming Sword of Power",
            value=5000,
            weight=3.5,
            item_type=ItemType.WEAPON,
            damage_dice="1d10",
            damage_type="slashing",
            rarity=Rarity.EPIC,
            effects=[
                DamageEffect(amount="1d6", damage_type="fire"),
                BuffEffect(stat="MIG", bonus=2, duration=0)  # Permanent
            ],
            description="A legendary blade wreathed in eternal flames"
        )
        
        data = original.to_dict()
        restored = Item.from_dict(data)
        
        assert restored.name == original.name
        assert restored.rarity == Rarity.EPIC
        assert len(restored.effects) == 2
        assert isinstance(restored.effects[0], DamageEffect)
        assert isinstance(restored.effects[1], BuffEffect)
        assert restored.description == original.description


class TestItemEdgeCases:
    """Test edge cases and validation."""
    
    def test_zero_value_item(self):
        """Items can have zero value (quest items)."""
        item = Item(
            name="Worthless Trinket",
            value=0,
            weight=0.1,
            item_type=ItemType.QUEST
        )
        assert item.value == 0
        assert item.total_value == 0
    
    def test_zero_weight_item(self):
        """Items can have zero weight (ethereal items)."""
        item = Item(
            name="Ghostly Coin",
            value=1,
            weight=0.0,
            item_type=ItemType.CURRENCY
        )
        assert item.weight == 0.0
        assert item.total_weight == 0.0
    
    def test_large_stack(self):
        """Items can have large stacks."""
        gold = Item(
            name="Gold",
            value=1,
            weight=0.02,
            item_type=ItemType.CURRENCY,
            stackable=True,
            quantity=10000
        )
        assert gold.total_value == 10000
        assert gold.total_weight == 200.0
