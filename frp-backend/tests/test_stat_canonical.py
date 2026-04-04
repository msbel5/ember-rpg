"""Phase 0: Stat Unification -- canonical Ember stat vocabulary.

Asserts that all kernel functions use ONLY Ember stat keys
(MIG, AGI, END, MND, INS, PRE) and never fall back to D&D names
(STR, DEX, CON, INT, WIS, CHA).
"""

import ast
import pathlib

from engine.kernel.actor_records import ActorRecord
from engine.kernel.actor_foundation import ActorIdentity, ActorPosition
from engine.kernel.actor_body import BodyState
from engine.world.body_parts import BodyPartTracker

# ── Canonical stat keys ──────────────────────────────────────────────
EMBER_STATS = {"MIG", "AGI", "END", "MND", "INS", "PRE"}
DND_STATS = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}

KERNEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "engine" / "kernel"


def _make_actor(stats: dict[str, int] | None = None) -> ActorRecord:
    """Build a minimal ActorRecord with Ember-only stats for testing."""
    default_stats = {"MIG": 14, "AGI": 12, "END": 13, "MND": 10, "INS": 11, "PRE": 10}
    return ActorRecord(
        identity=ActorIdentity(actor_id="test_actor", display_name="Test", actor_type="pc"),
        position=ActorPosition(x=0, y=0),
        action_points=3,
        max_action_points=3,
        alive=True,
        stats=stats or default_stats,
        skills={},
        body_state=BodyState.from_tracker(BodyPartTracker()),
        raw_payload={"level": 5, "bab": 5},
    )


# ── Source-level scan: no D&D stat keys in kernel code ───────────────
class _StatKeyVisitor(ast.NodeVisitor):
    """AST visitor that flags string literals matching D&D stat keys."""

    def __init__(self, filepath: pathlib.Path):
        self.filepath = filepath
        self.violations: list[str] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in DND_STATS:
            self.violations.append(
                f"{self.filepath.name}:{node.lineno} -- "
                f"D&D stat key '{node.value}' found as string literal"
            )
        self.generic_visit(node)


def test_no_dnd_stat_keys_in_kernel_source():
    """Scan every .py file under engine/kernel/ for D&D stat string literals."""
    violations: list[str] = []
    for py_file in sorted(KERNEL_DIR.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        visitor = _StatKeyVisitor(py_file)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    assert violations == [], (
        "D&D stat keys still present in kernel source:\n"
        + "\n".join(violations)
    )


# ── SAVE_STAT_MAP uses Ember keys only ───────────────────────────────
def test_save_stat_map_uses_ember_keys_only():
    """SAVE_STAT_MAP in effects.py must contain only Ember stat keys."""
    from engine.kernel.effects import SAVE_STAT_MAP

    for save_type, candidates in SAVE_STAT_MAP.items():
        for key in candidates:
            assert key in EMBER_STATS, (
                f"SAVE_STAT_MAP['{save_type}'] contains non-Ember key '{key}'"
            )


# ── combat_math: attack_stat uses Ember keys ─────────────────────────
def test_attack_stat_uses_ember_key():
    """attack_stat() must read MIG (melee) or AGI (finesse/ranged)."""
    from engine.kernel.combat_math import attack_stat

    actor = _make_actor()
    # Melee: should use MIG (14) not STR
    melee_val = attack_stat(actor, weapon=None)
    assert melee_val == 14  # raw stat, no effect modifiers


def test_defense_agi_stat_uses_agi():
    """defense_agi_stat() must read AGI, not DEX."""
    from engine.kernel.combat_math import defense_agi_stat

    actor = _make_actor()
    agi_val = defense_agi_stat(actor)
    assert agi_val == 12  # AGI value


# ── spells: ability scores use Ember keys ─────────────────────────────
def test_spell_ability_score_uses_ember_keys():
    """_spell_ability_score must use MND/INS/PRE for mage/priest/channeler."""
    from engine.kernel.spells import _spell_ability_score

    actor = _make_actor({"MIG": 10, "AGI": 10, "END": 10, "MND": 16, "INS": 14, "PRE": 12})
    assert _spell_ability_score(actor, "mage") == 16   # MND
    assert _spell_ability_score(actor, "priest") == 14  # INS
    assert _spell_ability_score(actor, "channeler") == 12  # PRE


# ── dialog: NPC reaction uses PRE ─────────────────────────────────────
def test_npc_reaction_uses_pre():
    """compute_npc_reaction must read PRE, not CHA."""
    from engine.kernel.dialog import compute_npc_reaction

    player = _make_actor({"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 18})
    npc = _make_actor()
    # (PRE-10)*2 + reputation(0) + relationship(0) = 16
    assert compute_npc_reaction(player, npc, reputation=0) == 16


# ── store: actor CHA helper uses PRE ──────────────────────────────────
def test_store_actor_pre_uses_pre():
    """_actor_pre must read PRE, not CHA."""
    from engine.kernel.store import _actor_pre

    actor = _make_actor({"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 16})
    assert _actor_pre(actor) == 16


# ── area: door opening uses MIG ──────────────────────────────────────
def test_door_force_uses_mig():
    """open_door strength check must read MIG, not STR."""
    # We can't easily unit-test open_door without full area state,
    # but we verify the source has no STR reference via the AST scan above.
    # This test verifies the stat_value helper returns MIG.
    from engine.kernel.combat_math import stat_value

    actor = _make_actor({"MIG": 18, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    assert stat_value(actor, "MIG") == 18


# ── pathfinding: movement speed uses AGI ──────────────────────────────
def test_movement_speed_uses_agi():
    """compute_movement_speed must read AGI, not DEX."""
    from engine.kernel.pathfinding_algorithms import compute_movement_speed

    actor = _make_actor({"MIG": 10, "AGI": 16, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
    speed = compute_movement_speed(actor, encumbrance_ratio=0.0)
    # AGI 16 -> modifier +3 -> base = max(4, 10 - 3) = 7
    assert speed == 7


# ── syndromes: toughness uses END ─────────────────────────────────────
def test_syndrome_resistance_uses_end():
    """apply_syndrome toughness lookup must use END, not CON."""
    # The AST scan covers the source-level check.
    # Here we verify END is read correctly through stat_value.
    from engine.kernel.combat_math import stat_value

    actor = _make_actor({"MIG": 10, "AGI": 10, "END": 16, "MND": 10, "INS": 10, "PRE": 10})
    assert stat_value(actor, "END") == 16
