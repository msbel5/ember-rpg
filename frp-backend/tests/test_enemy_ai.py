"""
Tests for Enemy AI (Deliverable 3)
"""
import pytest
from unittest.mock import MagicMock, patch
from engine.core.enemy_ai import EnemyAI, CombatAction
from engine.core.combat import Combatant, CombatManager
from engine.core.character import Character


def make_char(name, hp=100, max_hp=100, classes=None, enemy_type=None, special_moves=None):
    """Helper to create a Character-like object."""
    char = MagicMock(spec=Character)
    char.name = name
    char.hp = hp
    char.max_hp = max_hp
    char.classes = classes or {}
    char.enemy_type = enemy_type
    char.special_moves = special_moves or []
    char.ac = 10
    char.stat_modifier = MagicMock(return_value=0)
    char.skill_bonus = MagicMock(return_value=0)
    char.initiative_bonus = 0
    char.dominant_class = None
    char.level = 1
    char.spell_points = 0
    char.max_spell_points = 0
    char.xp = 0
    return char


def make_combatant(char, initiative=10):
    c = Combatant(character=char, initiative=initiative)
    return c


def make_combat_manager(combatants):
    """Build a mock CombatManager with the given combatants already set."""
    mgr = MagicMock()
    mgr.combatants = combatants
    return mgr


def test_enemy_flees_when_low_hp():
    """Beast-type enemy with low HP should choose flee."""
    ai = EnemyAI()
    enemy_char = make_char("Wolf", hp=5, max_hp=100, enemy_type="beast")
    enemy = make_combatant(enemy_char)
    # Player target
    player_char = make_char("Hero", hp=80, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([enemy, player])

    action = ai.choose_action(enemy, mgr)
    assert action.action_type == "flee"


def test_enemy_targets_healer_first():
    """Enemy should attack priest/healer before other targets."""
    ai = EnemyAI()
    enemy_char = make_char("Orc", hp=100, max_hp=100, enemy_type="humanoid")
    enemy = make_combatant(enemy_char)

    warrior_char = make_char("Warrior", hp=100, max_hp=100, classes={"warrior": 1})
    warrior = make_combatant(warrior_char, initiative=8)
    priest_char = make_char("Priest", hp=100, max_hp=100, classes={"priest": 1})
    priest = make_combatant(priest_char, initiative=6)

    mgr = make_combat_manager([enemy, warrior, priest])

    # Disable special moves to isolate healer targeting
    with patch('random.random', return_value=0.9):  # 90% > 30% => no special
        action = ai.choose_action(enemy, mgr)

    assert action.action_type == "attack"
    assert action.target_index == 2  # priest is index 2


def test_boss_never_flees():
    """Boss-type enemies should never flee, even at low HP."""
    ai = EnemyAI()
    boss_char = make_char("Dragon", hp=1, max_hp=1000, enemy_type="boss")
    boss = make_combatant(boss_char)
    player_char = make_char("Hero", hp=80, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([boss, player])

    action = ai.choose_action(boss, mgr)
    assert action.action_type != "flee"


def test_undead_never_flees():
    """Undead-type enemies should never flee."""
    ai = EnemyAI()
    undead_char = make_char("Skeleton", hp=1, max_hp=50, enemy_type="undead")
    undead = make_combatant(undead_char)
    player_char = make_char("Hero", hp=80, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([undead, player])

    action = ai.choose_action(undead, mgr)
    assert action.action_type != "flee"


def test_enemy_uses_special_move():
    """Enemy with special_moves should sometimes use them (30% chance)."""
    ai = EnemyAI()
    enemy_char = make_char("Troll", hp=100, max_hp=100, enemy_type="beast",
                           special_moves=["Rend", "Slam"])
    enemy = make_combatant(enemy_char)
    player_char = make_char("Hero", hp=100, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([enemy, player])

    # Force random to trigger special move
    with patch('random.random', return_value=0.1):  # 10% < 30% => use special
        action = ai.choose_action(enemy, mgr)

    assert action.action_type == "special"
    assert action.special_move in ["Rend", "Slam"]


def test_enemy_focuses_wounded_target():
    """Enemy should continue attacking a wounded (< 50% HP) target."""
    ai = EnemyAI()
    enemy_char = make_char("Goblin", hp=60, max_hp=80, enemy_type="humanoid")
    enemy = make_combatant(enemy_char)

    healthy_char = make_char("Tank", hp=100, max_hp=100)
    healthy = make_combatant(healthy_char, initiative=8)
    wounded_char = make_char("Mage", hp=20, max_hp=100)  # 20% HP
    wounded = make_combatant(wounded_char, initiative=6)

    mgr = make_combat_manager([enemy, healthy, wounded])

    with patch('random.random', return_value=0.9):  # no special
        action = ai.choose_action(enemy, mgr)

    assert action.action_type == "attack"
    assert action.target_index == 2  # wounded mage


def test_construct_never_flees():
    """Construct-type enemies should never flee."""
    ai = EnemyAI()
    construct_char = make_char("Golem", hp=2, max_hp=200, enemy_type="construct")
    construct = make_combatant(construct_char)
    player_char = make_char("Hero", hp=80, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([construct, player])

    action = ai.choose_action(construct, mgr)
    assert action.action_type != "flee"


def test_enemy_ai_default_attack():
    """Enemy with no special conditions should attack a random target."""
    ai = EnemyAI()
    enemy_char = make_char("Goblin", hp=60, max_hp=80, enemy_type="humanoid")
    enemy = make_combatant(enemy_char)
    player_char = make_char("Hero", hp=100, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([enemy, player])

    with patch('random.random', return_value=0.9):  # no special
        action = ai.choose_action(enemy, mgr)

    assert action.action_type == "attack"
    assert action.target_index == 1


def test_enemy_ai_dead_combatant_excluded():
    """Dead combatants should not be targets."""
    ai = EnemyAI()
    enemy_char = make_char("Orc", hp=100, max_hp=100, enemy_type="humanoid")
    enemy = make_combatant(enemy_char)

    dead_char = make_char("Dead", hp=0, max_hp=100)
    dead = make_combatant(dead_char, initiative=8)
    dead.is_dead = True
    alive_char = make_char("Hero", hp=100, max_hp=100)
    alive = make_combatant(alive_char, initiative=6)

    mgr = make_combat_manager([enemy, dead, alive])

    with patch('random.random', return_value=0.9):
        action = ai.choose_action(enemy, mgr)

    # Should target alive (index 2), not dead (index 1)
    assert action.target_index == 2


def test_enemy_ai_max_hp_zero_no_flee():
    """Enemy with max_hp=0 should not flee (division guard)."""
    ai = EnemyAI()
    enemy_char = make_char("Weird", hp=0, max_hp=0, enemy_type="beast")
    enemy = make_combatant(enemy_char)
    player_char = make_char("Hero", hp=100, max_hp=100)
    player = make_combatant(player_char, initiative=8)
    mgr = make_combat_manager([enemy, player])

    # Should not raise ZeroDivisionError
    result = ai._should_flee(enemy)
    assert result is False


def test_enemy_ai_no_players_returns_wait():
    """If all targets are dead/gone, enemy should wait."""
    ai = EnemyAI()
    enemy_char = make_char("Orc", hp=100, max_hp=100, enemy_type="humanoid")
    enemy = make_combatant(enemy_char)
    # No other combatants
    mgr = make_combat_manager([enemy])
    action = ai.choose_action(enemy, mgr)
    assert action.action_type == "wait"


def test_enemy_uses_special_on_healer():
    """Enemy with special moves should use them against a healer (30% chance)."""
    ai = EnemyAI()
    enemy_char = make_char("Troll", hp=100, max_hp=100, enemy_type="beast",
                           special_moves=["Rend"])
    enemy = make_combatant(enemy_char)
    priest_char = make_char("Priest", hp=100, max_hp=100, classes={"priest": 1})
    priest = make_combatant(priest_char, initiative=8)
    mgr = make_combat_manager([enemy, priest])

    with patch('random.random', return_value=0.1):  # triggers special
        action = ai.choose_action(enemy, mgr)

    assert action.action_type == "special"
    assert action.target_index == 1
    assert action.special_move == "Rend"


def test_pick_special_move_none_when_empty():
    """_pick_special_move returns None when no special moves."""
    ai = EnemyAI()
    enemy_char = make_char("Goblin", special_moves=[])
    enemy = make_combatant(enemy_char)
    result = ai._pick_special_move(enemy)
    assert result is None
