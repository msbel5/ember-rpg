"""Phase 4: Save schema v4 round-trip fidelity tests.

Ensures all kernel state survives save/load cycles with zero data loss.
"""

from engine.kernel.actor_records import ActorRecord, create_player_actor, create_monster_actor
from engine.kernel.actor_body import WoundRecord, ConditionRecord
from engine.kernel.effects import EffectDef, EffectInstance, EffectQueue
from engine.kernel.combat_engine import CombatState, start_combat
from engine.kernel.game_state import GameState
from engine.save.save_models import CURRENT_SCHEMA_VERSION, SaveFile, validate_schema_version


# ── Schema version ───────────────────────────────────────────────────

def test_schema_version_is_v4():
    """Current schema version must be 4.0."""
    assert CURRENT_SCHEMA_VERSION == "4.0"


def test_reject_v3_save():
    """Loading a v3 save should raise with migration hint."""
    v3_save = {
        "save_id": "old",
        "player_id": "p1",
        "session_data": {},
        "timestamp": "2026-01-01T00:00:00",
        "schema_version": "3.0",
    }
    try:
        validate_schema_version(v3_save)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "4.0" in str(e)
        assert "3.0" in str(e) or "unsupported" in str(e).lower()


# ── ActorRecord round-trip ───────────────────────────────────────────

def test_actor_record_stats_round_trip():
    """Actor stats survive save/load."""
    actor = create_player_actor(
        name="Arin",
        class_name="warrior",
        stats={"MIG": 18, "AGI": 14, "END": 16, "MND": 8, "INS": 10, "PRE": 12},
    )
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert restored.stats["MIG"] == 18
    assert restored.stats["AGI"] == 14
    assert restored.stats["END"] == 16
    assert restored.identity.display_name == "Arin"


def test_wounds_survive_round_trip():
    """Wounds on BodyState must persist through serialization."""
    actor = create_player_actor(name="Wounded", class_name="warrior", stats={"MIG": 14, "AGI": 12, "END": 14, "MND": 10, "INS": 10, "PRE": 10})
    actor.body_state.wounds.append(WoundRecord(
        wound_id="w1", body_part_id="chest", damage_type="slashing",
        damage_amount=8, bleeding=3, pain=5, open_wound=True, fracture=True,
    ))
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert len(restored.body_state.wounds) == 1
    w = restored.body_state.wounds[0]
    assert w.body_part_id == "chest"
    assert w.bleeding == 3
    assert w.fracture is True
    assert w.open_wound is True


def test_conditions_survive_round_trip():
    """ConditionRecords persist through serialization."""
    actor = create_player_actor(name="Sick", class_name="mage", stats={"MIG": 8, "AGI": 10, "END": 10, "MND": 16, "INS": 14, "PRE": 12})
    actor.body_state.conditions.append(ConditionRecord(
        condition_id="poisoned_01", name="poisoned", severity=2,
    ))
    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert len(restored.body_state.conditions) == 1
    assert restored.body_state.conditions[0].name == "poisoned"


# ── EffectQueue round-trip ───────────────────────────────────────────

def test_effects_survive_round_trip():
    """EffectQueue with active instances must persist."""
    actor = create_player_actor(name="Buffed", class_name="warrior", stats={"MIG": 16, "AGI": 12, "END": 14, "MND": 10, "INS": 10, "PRE": 10})
    effect_def = EffectDef(
        effect_def_id="str_buff",
        label="Bull's Strength",
        category="stat_mod",
        target_stat="MIG",
        modifier_type="flat",
        modifier_value=4,
        base_duration_ticks=10,
    )
    instance = EffectInstance(
        instance_id="inst_01",
        effect_def_id="str_buff",
        effect_def=effect_def,
        source_id="spell",
        target_id="player",
        ticks_remaining=10,
    )
    eq = EffectQueue(actor_id="player")
    eq.add(instance)
    actor.effect_queue = eq

    data = actor.to_dict()
    restored = ActorRecord.from_dict(data)
    assert restored.effect_queue is not None
    assert len(restored.effect_queue.instances) == 1
    inst = restored.effect_queue.instances[0]
    assert inst.effect_def.target_stat == "MIG"
    assert inst.effect_def.modifier_value == 4


# ── CombatState round-trip ───────────────────────────────────────────

def test_combat_state_survives_round_trip():
    """CombatState from combat_engine.py must serialize cleanly."""
    player = create_player_actor(name="Hero", class_name="warrior", stats={"MIG": 16, "AGI": 14, "END": 14, "MND": 10, "INS": 10, "PRE": 10})
    enemy = create_monster_actor({"id": "goblin", "name": "Goblin", "hp": 7, "stats": {"MIG": 8, "AGI": 14}})
    state = start_combat([player, enemy], seed=42)
    data = state.to_dict()
    restored = CombatState.from_dict(data)
    assert restored.round_number == state.round_number
    assert restored.phase == state.phase
    assert len(restored.combatants) == 2
    assert restored.combatants[0].initiative == state.combatants[0].initiative
    assert restored.combatants[0].turn_resources.action == state.combatants[0].turn_resources.action


# ── SaveFile round-trip ──────────────────────────────────────────────

def test_save_file_round_trip():
    """Full SaveFile with kernel data survives to_dict/from_dict."""
    actor = create_player_actor(name="Save", class_name="rogue", stats={"MIG": 10, "AGI": 16, "END": 12, "MND": 14, "INS": 10, "PRE": 12})
    save = SaveFile(
        save_id="save_001",
        player_id="player_01",
        session_data={"actors": {"player": actor.to_dict()}},
        timestamp="2026-04-03T12:00:00",
        schema_version="4.0",
    )
    data = save.to_dict()
    restored = SaveFile.from_dict(data)
    assert restored.save_id == "save_001"
    assert restored.schema_version == "4.0"
    restored_actor = ActorRecord.from_dict(restored.session_data["actors"]["player"])
    assert restored_actor.stats["AGI"] == 16
