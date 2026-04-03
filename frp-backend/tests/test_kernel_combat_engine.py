"""Phase 1: Kernel-native combat engine tests.

Tests the turn-management layer that wraps existing kernel combat math.
All combat uses ActorRecord directly -- no legacy Character or CombatManager.
"""

from engine.kernel.actor_records import ActorRecord
from engine.kernel.actor_foundation import ActorIdentity, ActorPosition
from engine.kernel.actor_body import BodyState
from engine.kernel.actor_items import ItemStack, MaterialDef, EquipmentLoadout
from engine.kernel.combat_engine import (
    CombatantEntry,
    CombatState,
    TurnResources,
    end_turn,
    execute_attack,
    is_combat_over,
    roll_initiative,
    start_combat,
    start_turn,
)
from engine.world.body_parts import BodyPartTracker


# ── Test helpers ─────────────────────────────────────────────────────

def _actor(
    actor_id: str = "player",
    *,
    stats: dict | None = None,
    is_player: bool = False,
    bab: int = 3,
    hp: int = 20,
) -> ActorRecord:
    """Build a minimal ActorRecord for combat tests."""
    default_stats = {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10}
    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=actor_id.title(),
            actor_type="pc" if is_player else "npc",
        ),
        position=ActorPosition(x=0, y=0),
        action_points=3,
        max_action_points=3,
        alive=True,
        stats=stats or default_stats,
        skills={"melee": 4},
        body_state=BodyState.from_tracker(BodyPartTracker()),
        raw_payload={"bab": bab, "level": 5, "hp": hp, "max_hp": hp},
    )


def _weapon() -> ItemStack:
    """Build a basic iron longsword ItemStack."""
    return ItemStack(
        instance_id="sword_01",
        item_def_id="iron_longsword",
        quantity=1,
        payload={
            "damage": 8,
            "damage_type": "slashing",
            "sharpness": 100,
        },
        material_id="iron",
    )


# ── Initiative ───────────────────────────────────────────────────────

def test_initiative_uses_agi_modifier():
    """Initiative = d20 + ability_modifier(AGI) + initiative_bonus."""
    actor = _actor(stats={"MIG": 10, "AGI": 16, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    # AGI 16 -> modifier +3. With seed=42 the d20 is deterministic.
    init_a = roll_initiative(actor, seed=42)
    init_b = roll_initiative(actor, seed=42)
    assert init_a == init_b, "Same seed must produce same initiative"
    # Modifier should be factored in (d20 range 1-20, +3 = 4-23)
    assert 4 <= init_a <= 23


def test_initiative_deterministic_across_actors():
    """Different actors with same seed+AGI get same initiative."""
    actor_a = _actor("a", stats={"MIG": 10, "AGI": 14, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    actor_b = _actor("b", stats={"MIG": 10, "AGI": 14, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    assert roll_initiative(actor_a, seed=7) == roll_initiative(actor_b, seed=7)


# ── Start combat ─────────────────────────────────────────────────────

def test_start_combat_sorts_by_initiative():
    """Combatants sorted by initiative descending."""
    player = _actor("player", is_player=True, stats={"MIG": 10, "AGI": 18, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    enemy = _actor("goblin", stats={"MIG": 10, "AGI": 8, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    state = start_combat([player, enemy], seed=42)
    assert state.phase == "active"
    assert state.round_number == 1
    assert len(state.combatants) == 2
    # Higher AGI should tend to go first (with same seed)
    initiatives = [c.initiative for c in state.combatants]
    assert initiatives == sorted(initiatives, reverse=True)


def test_start_combat_creates_turn_resources():
    """Each combatant gets fresh D&D turn resources."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=1)
    first = state.combatants[0]
    assert first.turn_resources.action is True
    assert first.turn_resources.bonus_action is True
    assert first.turn_resources.reaction is True
    assert first.turn_resources.movement >= 6


# ── Turn management ──────────────────────────────────────────────────

def test_start_turn_resets_resources():
    """start_turn resets action/bonus_action/reaction/movement."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=1)
    # Spend the action
    active = state.combatants[state.current_turn_index]
    active.turn_resources.action = False
    active.turn_resources.movement = 0
    # Start turn should reset
    result = start_turn(state, {"player": player, "goblin": enemy})
    assert result.active_combatant.turn_resources.action is True
    assert result.active_combatant.turn_resources.movement >= 6


def test_end_turn_advances_to_next():
    """end_turn advances current_turn_index."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=1)
    old_idx = state.current_turn_index
    state = end_turn(state)
    assert state.current_turn_index != old_idx


def test_end_turn_wraps_and_increments_round():
    """When all combatants have acted, round increments."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=1)
    state = end_turn(state)  # first -> second
    state = end_turn(state)  # second -> first, round++
    assert state.round_number == 2
    assert state.current_turn_index == 0


# ── Attack execution ─────────────────────────────────────────────────

def test_attack_uses_kernel_resolve_attack():
    """execute_attack delegates to kernel resolve_attack, not legacy."""
    player = _actor("player", is_player=True, stats={"MIG": 18, "AGI": 14, "END": 12, "MND": 10, "INS": 10, "PRE": 10}, bab=6)
    enemy = _actor("goblin", stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10}, bab=1)
    state = start_combat([player, enemy], seed=10)
    actors = {"player": player, "goblin": enemy}
    weapon = _weapon()

    # Find who goes first
    active = state.combatants[state.current_turn_index]
    attacker_id = active.actor_id
    defender_id = "goblin" if attacker_id == "player" else "player"

    result = execute_attack(state, actors, attacker_id, defender_id, weapon=weapon, seed=99)
    # Result should have kernel CombatResult fields
    assert result.combat_result is not None
    assert result.combat_result.attack_roll is not None
    assert result.combat_result.defense is not None


def test_attack_consumes_action():
    """After attacking, action resource is spent."""
    player = _actor("player", is_player=True, bab=6)
    enemy = _actor("goblin", bab=1)
    state = start_combat([player, enemy], seed=10)
    actors = {"player": player, "goblin": enemy}
    active = state.combatants[state.current_turn_index]

    execute_attack(state, actors, active.actor_id, "goblin" if active.actor_id == "player" else "player", seed=50)
    assert active.turn_resources.action is False


def test_attack_without_action_raises():
    """Cannot attack when action is already spent."""
    player = _actor("player", is_player=True, bab=6)
    enemy = _actor("goblin", bab=1)
    state = start_combat([player, enemy], seed=10)
    actors = {"player": player, "goblin": enemy}
    active = state.combatants[state.current_turn_index]
    active.turn_resources.action = False  # Spend it

    try:
        execute_attack(state, actors, active.actor_id, "goblin" if active.actor_id == "player" else "player", seed=50)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "action" in str(e).lower()


# ── Damage through tissue layers ─────────────────────────────────────

def test_damage_creates_wound_on_hit():
    """A successful hit should create a WoundRecord on the defender."""
    player = _actor("player", is_player=True, stats={"MIG": 20, "AGI": 14, "END": 12, "MND": 10, "INS": 10, "PRE": 10}, bab=10)
    enemy = _actor("goblin", stats={"MIG": 8, "AGI": 8, "END": 8, "MND": 8, "INS": 8, "PRE": 8}, bab=0)
    state = start_combat([player, enemy], seed=10)
    actors = {"player": player, "goblin": enemy}

    # Force player to go first by using high seed
    active = state.combatants[state.current_turn_index]
    attacker_id = active.actor_id
    defender_id = "goblin" if attacker_id == "player" else "player"
    defender = actors[defender_id]

    # Execute multiple attacks until we get a hit
    for seed in range(100, 200):
        result = execute_attack(state, actors, attacker_id, defender_id, weapon=_weapon(), seed=seed)
        active.turn_resources.action = True  # Reset for next try
        if result.combat_result.hit:
            # On hit, wound should exist
            assert result.combat_result.strike_resolution is not None
            assert result.combat_result.strike_resolution.wound is not None
            return
    # If we got here, something is very wrong with hit math
    assert False, "Failed to hit after 100 attempts"


# ── Combat end condition ──────────────────────────────────────────────

def test_combat_over_when_all_enemies_dead():
    """Combat ends when all non-player combatants are dead."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    enemy.alive = False
    state = start_combat([player, enemy], seed=1)
    actors = {"player": player, "goblin": enemy}
    assert is_combat_over(state, actors) is True


def test_combat_not_over_while_enemies_alive():
    """Combat continues while enemies live."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=1)
    actors = {"player": player, "goblin": enemy}
    assert is_combat_over(state, actors) is False


# ── Serialization ─────────────────────────────────────────────────────

def test_combat_state_round_trip():
    """CombatState serializes and deserializes cleanly."""
    player = _actor("player", is_player=True)
    enemy = _actor("goblin")
    state = start_combat([player, enemy], seed=42)
    data = state.to_dict()
    restored = CombatState.from_dict(data)
    assert restored.round_number == state.round_number
    assert restored.phase == state.phase
    assert len(restored.combatants) == len(state.combatants)
    assert restored.combatants[0].actor_id == state.combatants[0].actor_id
    assert restored.combatants[0].initiative == state.combatants[0].initiative
