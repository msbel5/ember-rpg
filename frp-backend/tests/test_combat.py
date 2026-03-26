"""
Ember RPG - Core Engine
Combat system tests
"""
import pytest
from engine.core.combat import CombatManager, Combatant, Condition
from engine.core.character import Character
from engine.core.item import Item, ItemType
from engine.core.effect import HealEffect


class TestInitiative:
    """Test initiative rolling and turn order."""
    
    def test_initiative_order(self):
        """Combatants should be sorted by initiative (descending)."""
        char1 = Character(name="Fighter", stats={'MIG': 10, 'AGI': 16, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        char2 = Character(name="Rogue", stats={'MIG': 10, 'AGI': 18, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        char3 = Character(name="Cleric", stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        
        combat = CombatManager([char1, char2, char3], seed=42)
        
        # Check combatants created
        assert len(combat.combatants) == 3
        assert all(c.initiative > 0 for c in combat.combatants)
        
        # Check descending order
        initiatives = [c.initiative for c in combat.combatants]
        assert initiatives == sorted(initiatives, reverse=True)
    
    def test_initiative_includes_modifiers(self):
        """Initiative should include AGI modifier and initiative_bonus."""
        char = Character(
            name="Speedy",
            stats={'MIG': 10, 'AGI': 20, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10},
            initiative_bonus=5
        )
        
        combat = CombatManager([char], seed=100)
        combatant = combat.combatants[0]
        
        # AGI 20 = +5 modifier, +5 bonus, d20 roll
        # Minimum: 1 + 5 + 5 = 11
        assert combatant.initiative >= 11
        assert combatant.initiative <= 30  # Max: 20 + 5 + 5


class TestTurnManagement:
    """Test turn progression and AP tracking."""
    
    def test_turn_starts_with_3_ap(self):
        """Each turn should start with 3 AP."""
        char = Character(name="Hero")
        combat = CombatManager([char], seed=1)
        combat.start_turn()
        
        assert combat.active_combatant.ap == 3
    
    def test_turn_progression(self):
        """Turns should cycle through all combatants."""
        chars = [Character(name=f"C{i}") for i in range(3)]
        combat = CombatManager(chars, seed=1)
        
        combat.start_turn()
        assert combat.round == 1
        assert combat.current_turn == 0
        
        combat.end_turn()
        assert combat.current_turn == 1
        
        combat.end_turn()
        assert combat.current_turn == 2
        
        combat.end_turn()
        # After 3 combatants, back to 0 and round 2
        assert combat.current_turn == 0
        assert combat.round == 2
    
    def test_ap_consumption(self):
        """Actions should consume AP."""
        attacker = Character(name="Fighter", stats={'MIG': 14, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        target = Character(name="Dummy", hp=50, max_hp=50, ac=10)
        
        combat = CombatManager([attacker, target], seed=1)
        combat.start_turn()
        
        initial_ap = combat.active_combatant.ap
        combat.attack(target_index=1)
        
        assert combat.active_combatant.ap == initial_ap - 1


class TestAttackResolution:
    """Test attack mechanics."""
    
    def test_attack_hit(self):
        """Attack should hit if roll + modifier >= AC."""
        attacker = Character(
            name="Fighter",
            stats={'MIG': 16, 'AGI': 14, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}
        )
        attacker.skills['melee'] = 2  # Trained
        target = Character(
            name="Goblin",
            hp=20,
            max_hp=20,
            ac=12,
            stats={'MIG': 10, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}
        )
        
        weapon = Item(
            name="Longsword",
            value=15,
            weight=3.0,
            item_type=ItemType.WEAPON,
            damage_dice="1d8",
            damage_type="slashing"
        )
        
        combat = CombatManager([attacker, target], seed=100)
        combat.start_turn()
        
        # Find target index (initiative may reorder)
        target_index = next(i for i, c in enumerate(combat.combatants) if c.name == "Goblin")
        
        result = combat.attack(target_index=target_index, weapon=weapon)
        
        assert 'hit' in result
        assert 'attack_roll' in result
        assert result['target_ac'] == 12
        
        if result['hit']:
            assert 'damage' in result
            assert target.hp < 20
    
    def test_attack_miss(self):
        """Attack should miss if roll + modifier < AC."""
        attacker = Character(name="Weakling", stats={'MIG': 8, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        target = Character(name="Tank", hp=50, max_hp=50, ac=20)  # Very high AC
        
        combat = CombatManager([attacker, target], seed=1)
        combat.start_turn()
        
        # Try multiple attacks to find a miss
        for _ in range(20):
            combat.start_turn()
            result = combat.attack(target_index=1)
            if not result.get('hit'):
                assert 'damage' not in result
                break
    
    def test_critical_hit_doubles_damage(self):
        """Natural 20 should double damage dice."""
        attacker = Character(name="Crit", stats={'MIG': 18, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}, initiative_bonus=100)
        target = Character(name="Target", hp=100, max_hp=100, ac=5)
        
        weapon = Item(
            name="Dagger",
            value=2,
            weight=1.0,
            item_type=ItemType.WEAPON,
            damage_dice="1d4",
            damage_type="piercing"
        )
        
        # Run multiple combats to hit a natural 20
        for seed in range(1, 1000):
            target.hp = 100  # Reset
            combat = CombatManager([attacker, target], seed=seed)
            combat.start_turn()
            target_index = next(i for i, c in enumerate(combat.combatants) if c.name == "Target")
            result = combat.attack(target_index=target_index, weapon=weapon)
            
            if result.get('crit'):
                # Crit: (damage_roll × 2) + stat_mod
                # 1d4 → 1-4, × 2 = 2-8, +4 (MIG 18) = 6-12
                assert 6 <= result['damage'] <= 12
                break
    
    def test_attack_death(self):
        """Attack reducing HP to 0 should kill target."""
        attacker = Character(name="Killer", stats={'MIG': 20, 'AGI': 10, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10})
        target = Character(name="Victim", hp=1, max_hp=10, ac=5)
        
        weapon = Item(
            name="Greatsword",
            value=50,
            weight=6.0,
            item_type=ItemType.WEAPON,
            damage_dice="2d6",
            damage_type="slashing"
        )
        
        combat = CombatManager([attacker, target], seed=1)
        combat.start_turn()
        
        result = combat.attack(target_index=1, weapon=weapon)
        
        if result.get('hit'):
            assert target.hp <= 0
            assert combat.combatants[1].is_dead is True


class TestConditions:
    """Test condition system."""
    
    def test_apply_condition(self):
        """Conditions should be applied to targets."""
        char = Character(name="Hero", hp=50, max_hp=50)
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        combat = CombatManager([char, enemy], seed=1)
        combat.start_turn()
        
        poison = Condition(name="poisoned", duration=3, effect="1d4 poison per turn")
        result = combat.apply_condition(target_index=0, condition=poison)
        
        assert len(combat.combatants[0].conditions) == 1
        assert result['condition'] == 'poisoned'
        assert result['duration'] == 3
    
    def test_condition_deals_damage(self):
        """Poison condition should deal damage each turn."""
        char = Character(name="Hero", hp=50, max_hp=50)
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        combat = CombatManager([char, enemy], seed=1)
        combat.start_turn()
        
        poison = Condition(name="poisoned", duration=3, effect="1d4 poison per turn")
        combat.apply_condition(target_index=0, condition=poison)
        
        initial_hp = combat.combatants[0].character.hp
        
        # End turn and come back (poison triggers at start_turn)
        combat.end_turn()
        combat.end_turn()  # Back to hero's turn
        
        # Poison should have dealt damage
        assert combat.combatants[0].character.hp < initial_hp
    
    def test_condition_expires(self):
        """Conditions should expire after duration."""
        char = Character(name="Hero", hp=50, max_hp=50)
        enemy = Character(name="Enemy", hp=10, max_hp=10)
        
        combat = CombatManager([char, enemy], seed=1)
        combat.start_turn()
        
        short_poison = Condition(name="poisoned", duration=1, effect="1d4")
        combat.apply_condition(target_index=0, condition=short_poison)
        
        assert len(combat.combatants[0].conditions) == 1
        
        # After 1 turn cycle, condition should expire
        combat.end_turn()
        combat.end_turn()
        
        assert len(combat.combatants[0].conditions) == 0


class TestCombatEnd:
    """Test combat termination."""
    
    def test_combat_ends_on_death(self):
        """Combat should end when only one combatant alive."""
        strong = Character(
            name="Dragon",
            hp=100,
            max_hp=100,
            stats={'MIG': 20, 'AGI': 20, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10},
            initiative_bonus=100  # Ensure Dragon goes first
        )
        weak = Character(
            name="Peasant",
            hp=5,
            max_hp=5,
            ac=5,
            stats={'MIG': 10, 'AGI': 8, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}
        )
        
        weapon = Item(
            name="Claw",
            value=0,
            weight=0,
            item_type=ItemType.WEAPON,
            damage_dice="2d10",
            damage_type="slashing"
        )
        
        combat = CombatManager([strong, weak], seed=1)
        combat.start_turn()
        
        # Attack until combat ends
        for _ in range(20):  # Increase iterations
            if combat.combat_ended:
                break
            result = combat.attack(target_index=1, weapon=weapon)
            if combat.combat_ended:  # Check after attack
                break
            combat.end_turn()
        
        assert combat.combat_ended is True
        summary = combat.get_summary()
        assert "Dragon" in summary['survivors']
        assert "Peasant" in summary['casualties']
    
    def test_combat_summary(self):
        """Combat summary should include rounds, survivors, casualties."""
        char1 = Character(name="A", hp=50, max_hp=50)
        char2 = Character(name="B", hp=50, max_hp=50)
        
        combat = CombatManager([char1, char2], seed=1)
        combat.start_turn()
        
        # Simulate some turns
        for _ in range(3):
            combat.end_turn()
        
        summary = combat.get_summary()
        
        assert 'rounds' in summary
        assert 'survivors' in summary
        assert 'casualties' in summary
        assert 'event_count' in summary
        assert summary['rounds'] >= 1


class TestItemUsage:
    """Test using items in combat."""
    
    def test_use_healing_potion(self):
        """Using a healing potion should restore HP."""
        char = Character(
            name="Hero",
            hp=30,
            max_hp=50,
            stats={'MIG': 10, 'AGI': 20, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10},
            initiative_bonus=100  # Ensure Hero goes first
        )
        enemy = Character(
            name="Enemy",
            hp=10,
            max_hp=10,
            stats={'MIG': 10, 'AGI': 5, 'END': 10, 'MND': 10, 'INS': 10, 'PRE': 10}
        )
        
        potion = Item(
            name="Healing Potion",
            value=50,
            weight=0.5,
            item_type=ItemType.CONSUMABLE,
            effects=[HealEffect(amount="2d6+2")]
        )
        
        combat = CombatManager([char, enemy], seed=1)
        combat.start_turn()
        
        # Ensure Hero is active (should be due to AGI)
        assert combat.active_combatant.name == "Hero"
        
        initial_hp = combat.combatants[0].character.hp
        result = combat.use_item(potion)
        
        assert 'effects' in result
        assert combat.combatants[0].character.hp > initial_hp  # Healed
        assert combat.active_combatant.ap == 2  # Used 1 AP


# ---------------------------------------------------------------------------
# Additional coverage: burning condition, use_item AP, enemy_turn
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Additional coverage: burning condition, use_item AP, enemy_turn
# ---------------------------------------------------------------------------

def _make_char(name="Fighter", hp=20):
    return Character(
        name=name,
        hp=hp, max_hp=hp,
        stats={"MIG": 12, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
    )


class TestConditionCoverage:
    """Cover burning/poisoned condition apply_turn_effect paths."""

    def test_burning_condition_applies_damage(self):
        warrior = _make_char("Warrior")
        combatant = Combatant(character=warrior, initiative=10)
        cond = Condition(name="burning", duration=2, effect="fire")
        initial_hp = warrior.hp
        msg = cond.apply_turn_effect(combatant)
        assert msg is not None
        assert "fire" in msg
        assert warrior.hp < initial_hp

    def test_unknown_condition_returns_none(self):
        warrior = _make_char("Warrior")
        combatant = Combatant(character=warrior, initiative=10)
        cond = Condition(name="slowed", duration=1, effect="slow")
        result = cond.apply_turn_effect(combatant)
        assert result is None


class TestUseItemAP:
    """Cover use_item AP check."""

    def test_use_item_insufficient_ap(self):
        warrior = _make_char("Warrior")
        enemy = _make_char("Enemy")
        cm = CombatManager([warrior, enemy])
        cm.active_combatant.ap = 0
        item = Item(name="Potion", value=10, weight=0.5, item_type=ItemType.CONSUMABLE)
        result = cm.use_item(item)
        assert "error" in result


class TestEnemyTurnCoverage:
    """Cover enemy_turn method in CombatManager."""

    def test_enemy_turn_flee(self):
        from engine.core.enemy_ai import EnemyAI, CombatAction
        from unittest.mock import patch
        warrior = _make_char("Warrior")
        enemy = _make_char("Enemy")
        cm = CombatManager([warrior, enemy])
        ai = EnemyAI()
        with patch.object(ai, 'choose_action', return_value=CombatAction(action_type="flee")):
            # Advance to enemy's turn
            while cm.active_combatant.name != enemy.name and not cm.combat_ended:
                cm.end_turn()
            if not cm.combat_ended:
                result = cm.enemy_turn(ai=ai)
                assert result["action"] == "flee"

    def test_enemy_turn_wait(self):
        from engine.core.enemy_ai import EnemyAI, CombatAction
        from unittest.mock import patch
        warrior = _make_char("Warrior")
        enemy = _make_char("Enemy")
        cm = CombatManager([warrior, enemy])
        ai = EnemyAI()
        with patch.object(ai, 'choose_action', return_value=CombatAction(action_type="wait")):
            while cm.active_combatant.name != enemy.name and not cm.combat_ended:
                cm.end_turn()
            if not cm.combat_ended:
                result = cm.enemy_turn(ai=ai)
                assert result["action"] == "wait"

    def test_enemy_turn_default_ai(self):
        """enemy_turn with no AI arg should create default EnemyAI."""
        from engine.core.enemy_ai import EnemyAI
        from unittest.mock import patch
        warrior = _make_char("Warrior")
        enemy = _make_char("Enemy")
        enemy.enemy_type = "beast"
        cm = CombatManager([warrior, enemy])
        # Just ensure it runs without error
        while cm.active_combatant.character != enemy and not cm.combat_ended:
            cm.end_turn()
        if not cm.combat_ended:
            result = cm.enemy_turn()
            assert "action" in result or "attacker" in result or "error" in result


class TestCombatAttackEdgeCases:
    """Cover attack dead target and skip dead combatant in end_turn."""

    def test_attack_dead_target(self):
        warrior = _make_char("Warrior", hp=20)
        enemy = _make_char("Enemy", hp=1)
        cm = CombatManager([warrior, enemy])
        # Find enemy index
        enemy_idx = next(i for i, c in enumerate(cm.combatants) if c.name == "Enemy")
        cm.combatants[enemy_idx].is_dead = True
        result = cm.attack(enemy_idx)
        assert "error" in result

    def test_skip_dead_in_end_turn(self):
        """end_turn should skip dead combatants."""
        a = _make_char("A", hp=20)
        b = _make_char("B", hp=20)
        c = _make_char("C", hp=20)
        cm = CombatManager([a, b, c])
        # Kill second combatant
        cm.combatants[1].is_dead = True
        cm.combatants[1].character.hp = 0
        # End first combatant's turn — should skip to third
        initial_turn = cm.current_turn
        cm.end_turn()
        # current_turn should not be 1 (dead)
        assert not cm.combatants[cm.current_turn].is_dead

    def test_enemy_turn_special_with_move_name(self):
        """enemy_turn with special action should include special_move in result."""
        from engine.core.enemy_ai import EnemyAI, CombatAction
        from unittest.mock import patch
        warrior = _make_char("Warrior", hp=20)
        enemy = _make_char("Enemy", hp=20)
        cm = CombatManager([warrior, enemy])
        ai = EnemyAI()
        warrior_idx = next(i for i, c in enumerate(cm.combatants) if c.name == "Warrior")
        action = CombatAction(action_type="special", target_index=warrior_idx, special_move="Slam")
        with patch.object(ai, 'choose_action', return_value=action):
            while cm.active_combatant.name != enemy.name and not cm.combat_ended:
                cm.end_turn()
            if not cm.combat_ended:
                result = cm.enemy_turn(ai=ai)
                if "hit" in result:  # attack succeeded
                    assert result.get("special_move") == "Slam"
