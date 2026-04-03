from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.effects import EffectDef
from engine.kernel.spells import (
    CastingAttempt,
    SpellDef,
    SpellSlot,
    Spellbook,
    begin_casting,
    compute_max_spell_slots,
    learn_spell,
    resolve_cast,
    rest_refresh_spellbook,
    tick_casting,
)


def _actor(*, actor_id: str = "caster", stats: dict[str, int] | None = None, raw_payload: dict | None = None) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats=stats or {"MND": 10, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 0, "hp": 20, "max_hp": 20},
        skills={},
        raw_payload=raw_payload or {},
    )


def _effect_registry() -> dict[str, EffectDef]:
    return {
        "magic_missile_force": EffectDef(
            effect_def_id="magic_missile_force",
            label="Magic Missile Force",
            category="dot",
            damage_per_tick=4,
            damage_type="force",
            timing_mode="instant",
        ),
        "heal_10": EffectDef(
            effect_def_id="heal_10",
            label="Heal 10",
            category="healing",
            healing_per_tick=10,
            timing_mode="instant",
        ),
    }


def test_ac01_compute_max_spell_slots_adds_ability_bonus():
    actor = _actor(
        stats={"MND": 16, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 0, "hp": 20, "max_hp": 20},
        raw_payload={"level": 5},
    )
    class_table = {"wizard": {5: {1: 2, 2: 1}}}

    slots = compute_max_spell_slots(actor, "wizard", class_table)

    assert slots[1] == 3


def test_ac02_learn_spell_succeeds_when_roll_is_within_int_chance():
    actor = _actor(stats={"MND": 14, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 0, "hp": 20, "max_hp": 20})
    spellbook = Spellbook(actor_id=actor.identity.actor_id, spell_type="wizard")
    spell_def = SpellDef(
        spell_id="magic_missile",
        label="Magic Missile",
        spell_type="wizard",
        school="evocation",
        level=1,
        casting_time=1,
        range=60,
        target_type="creature",
    )

    success, _ = learn_spell(actor, spellbook, spell_def, d100_roll=55)

    assert success is True
    assert spellbook.known_spells[1] == ["magic_missile"]


def test_ac03_learn_spell_fails_and_consumes_scroll_on_bad_roll():
    actor = _actor(stats={"MND": 14, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 0, "hp": 20, "max_hp": 20})
    spellbook = Spellbook(actor_id=actor.identity.actor_id, spell_type="wizard")
    spell_def = SpellDef(
        spell_id="magic_missile",
        label="Magic Missile",
        spell_type="wizard",
        school="evocation",
        level=1,
        casting_time=1,
        range=60,
        target_type="creature",
    )

    success, message = learn_spell(actor, spellbook, spell_def, d100_roll=65)

    assert success is False
    assert "consumed" in message


def test_ac04_rest_refresh_clears_expended_flags():
    spellbook = Spellbook(
        actor_id="caster",
        spell_type="wizard",
        slots={1: [SpellSlot(1, "magic_missile", memorized=True, expended=True) for _ in range(3)]},
    )

    rest_refresh_spellbook(spellbook)

    assert all(slot.expended is False for slot in spellbook.slots[1])


def test_ac05_begin_casting_returns_attempt_for_memorized_spell():
    spell_def = SpellDef(
        spell_id="magic_missile",
        label="Magic Missile",
        spell_type="wizard",
        school="evocation",
        level=1,
        casting_time=3,
        range=60,
        target_type="creature",
    )
    spellbook = Spellbook(
        actor_id="caster",
        spell_type="wizard",
        slots={1: [SpellSlot(1, "magic_missile", memorized=True, expended=False)]},
    )

    ok, attempt, error = begin_casting(_actor(), spellbook, spell_def, target_id="target", target_point=None, current_tick=10)

    assert ok is True
    assert error == ""
    assert attempt is not None and attempt.ticks_remaining == 3


def test_ac06_tick_casting_interrupts_when_concentration_fails():
    caster = _actor(stats={"MND": 14, "INS": 10, "PRE": 10, "END": 14, "magic_resistance": 0, "hp": 20, "max_hp": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 2, 60, "creature"),
        tick_started=10,
        ticks_remaining=2,
    )

    status, updated = tick_casting(attempt, damage_taken=8, d20_roll=15, d100_roll=99, caster=caster)

    assert status == "interrupted"
    assert updated.failed is True


def test_ac07_tick_casting_continues_when_concentration_succeeds():
    caster = _actor(stats={"MND": 14, "INS": 10, "PRE": 10, "END": 14, "magic_resistance": 0, "hp": 20, "max_hp": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 2, 60, "creature"),
        tick_started=10,
        ticks_remaining=2,
    )

    status, updated = tick_casting(attempt, damage_taken=8, d20_roll=16, d100_roll=99, caster=caster)

    assert status == "casting"
    assert updated.failed is False


def test_ac08_tick_casting_fails_on_spell_failure_roll():
    caster = _actor(raw_payload={"spell_failure": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 1, 60, "creature"),
        tick_started=10,
        ticks_remaining=1,
    )

    status, updated = tick_casting(attempt, damage_taken=0, d20_roll=1, d100_roll=15, caster=caster)

    assert status == "failed"
    assert updated.failure_reason == "spell failure"


def test_ac09_tick_casting_succeeds_when_spell_failure_roll_misses():
    caster = _actor(raw_payload={"spell_failure": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 1, 60, "creature"),
        tick_started=10,
        ticks_remaining=1,
    )

    status, updated = tick_casting(attempt, damage_taken=0, d20_roll=1, d100_roll=25, caster=caster)

    assert status == "ready"
    assert updated.completed is True


def test_ac10_begin_casting_blocks_on_aura_cooldown():
    caster = _actor(raw_payload={"last_cast_tick": 100})
    spellbook = Spellbook(actor_id="caster", spell_type="wizard", slots={1: [SpellSlot(1, "magic_missile", memorized=True, expended=False)]})
    spell_def = SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 1, 60, "creature")

    ok, attempt, error = begin_casting(caster, spellbook, spell_def, target_id="target", target_point=None, current_tick=103)

    assert ok is False
    assert attempt is None
    assert error == "aura cooldown"


def test_ac11_begin_casting_allows_after_aura_cooldown_expires():
    caster = _actor(raw_payload={"last_cast_tick": 100})
    spellbook = Spellbook(actor_id="caster", spell_type="wizard", slots={1: [SpellSlot(1, "magic_missile", memorized=True, expended=False)]})
    spell_def = SpellDef("magic_missile", "Magic Missile", "wizard", "evocation", 1, 1, 60, "creature")

    ok, attempt, error = begin_casting(caster, spellbook, spell_def, target_id="target", target_point=None, current_tick=106)

    assert ok is True
    assert error == ""
    assert attempt is not None


def test_ac12_resolve_cast_negates_effects_on_magic_resistance():
    caster = _actor(raw_payload={"effect_registry": _effect_registry()})
    target = _actor(actor_id="target", stats={"MND": 10, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 40, "hp": 20, "max_hp": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef(
            "magic_missile",
            "Magic Missile",
            "wizard",
            "evocation",
            1,
            1,
            60,
            "creature",
            hostile=True,
            effect_def_ids=["magic_missile_force"],
        ),
        completed=True,
    )

    result = resolve_cast(attempt, caster, target, d100_roll=35, current_tick=200)

    assert result["resisted"] is True
    assert result["effects_applied"] == []


def test_ac13_resolve_cast_applies_effects_when_not_resisted():
    caster = _actor(raw_payload={"effect_registry": _effect_registry()})
    target = _actor(actor_id="target", stats={"MND": 10, "INS": 10, "PRE": 10, "END": 10, "magic_resistance": 40, "hp": 20, "max_hp": 20})
    attempt = CastingAttempt(
        caster_id="caster",
        spell_def=SpellDef(
            "magic_missile",
            "Magic Missile",
            "wizard",
            "evocation",
            1,
            1,
            60,
            "creature",
            hostile=True,
            effect_def_ids=["magic_missile_force"],
        ),
        completed=True,
    )

    result = resolve_cast(attempt, caster, target, d100_roll=45, current_tick=200)

    assert result["resisted"] is False
    assert result["effects_applied"] == ["magic_missile_force"]


def test_ac14_spellbook_round_trip_preserves_known_and_slot_state():
    spellbook = Spellbook(
        actor_id="caster",
        spell_type="wizard",
        known_spells={1: ["magic_missile", "shield"], 2: ["mirror_image"]},
        slots={1: [SpellSlot(1, "magic_missile", memorized=True, expended=False), SpellSlot(1, "shield", memorized=True, expended=True)]},
        max_slots={1: 2, 2: 1},
    )

    restored = Spellbook.from_dict(spellbook.to_dict())

    assert restored == spellbook
