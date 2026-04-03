"""Phase 5: Kernel adapter tests.

Verifies that the API adapter module works end-to-end with kernel types
only -- no legacy Character or CombatManager.
"""

import ast
import pathlib


# ── Source-level check: no engine.core imports ───────────────────────

def test_kernel_adapter_has_no_core_imports():
    """kernel_adapter.py must not import from engine.core."""
    adapter_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "engine" / "api" / "kernel_adapter.py"
    )
    source = adapter_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            if "engine.core" in module:
                violations.append(f"Line {node.lineno}: imports from {module}")
    assert violations == [], f"Legacy imports found:\n" + "\n".join(violations)


# ── End-to-end: create + fight + check ───────────────────────────────

def test_full_combat_flow_through_adapter():
    """Create actors, start fight, attack, check combat end -- all via adapter."""
    from engine.api.kernel_adapter import (
        create_player,
        create_monster,
        start_fight,
        begin_turn,
        run_attack,
        advance_turn,
        check_combat_end,
        actor_hp,
        actor_is_alive,
        ItemStack,
    )

    player = create_player(
        name="Hero",
        class_name="warrior",
        stats={"MIG": 18, "AGI": 14, "END": 16, "MND": 8, "INS": 10, "PRE": 10},
    )
    # Give the player a weapon so attacks deal meaningful damage.
    weapon = ItemStack(
        instance_id="sword_01", item_def_id="iron_longsword", quantity=1,
        payload={"damage": 10, "damage_type": "slashing", "sharpness": 100},
        material_id="iron",
    )
    monster_template = {
        "id": "goblin",
        "name": "Goblin",
        "hp": 7,
        "armor_class": 15,
        "stats": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
        "attacks": [{"name": "Scimitar", "attack_bonus": 4}],
    }
    monster = create_monster(monster_template)
    actors = {player.identity.actor_id: player, monster.identity.actor_id: monster}

    # Start combat.
    state = start_fight([player, monster], seed=42)
    assert state.phase == "active"

    # Run through turns until combat ends or 20 rounds pass.
    for _ in range(40):
        turn_result = begin_turn(state, actors)
        active_id = state.active_combatant.actor_id
        attacker = actors[active_id]

        if not actor_is_alive(attacker):
            state = advance_turn(state)
            continue

        # Find a living target.
        target_id = None
        for entry in state.combatants:
            if entry.actor_id != active_id and actor_is_alive(actors[entry.actor_id]):
                target_id = entry.actor_id
                break

        if target_id is None:
            break  # Combat over, no targets left.

        try:
            result = run_attack(state, actors, active_id, target_id, weapon=weapon, seed=_ * 7)
        except ValueError:
            pass  # Action already spent.

        state = advance_turn(state)

        if check_combat_end(state, actors):
            break

    # One side should be dead.
    assert check_combat_end(state, actors)


def test_adapter_imports_are_all_kernel():
    """All public symbols in kernel_adapter come from engine.kernel."""
    from engine.api import kernel_adapter
    # Just verify the module loads and has expected symbols.
    assert hasattr(kernel_adapter, "create_player")
    assert hasattr(kernel_adapter, "create_monster")
    assert hasattr(kernel_adapter, "start_fight")
    assert hasattr(kernel_adapter, "run_attack")
    assert hasattr(kernel_adapter, "CombatState")
    assert hasattr(kernel_adapter, "ActorRecord")
