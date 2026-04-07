"""
Spell payload and request contract tests.

Freezes the spell data shapes that later UI will consume.
Covers: SpellDef, SpellSlot, Spellbook, CastingAttempt shapes,
        spell-point casting, slot-based memorization, channeler bypass,
        and truthfulness of combat available_actions regarding cast.
"""

from __future__ import annotations

import pytest

from _seed_robust_helpers import ensure_attack_target

from engine.kernel.actor import ActorIdentity, ActorPosition
from engine.kernel.actor_records import ActorRecord
from engine.kernel.spells import (
    CastingAttempt,
    SpellDef,
    SpellSlot,
    Spellbook,
    begin_casting,
    rest_refresh_spellbook,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _actor(
    *,
    actor_id: str = "caster",
    spell_points: int = 10,
    max_spell_points: int = 10,
    raw_payload: dict | None = None,
) -> ActorRecord:
    rp = raw_payload or {}
    rp.setdefault("spell_points", spell_points)
    rp.setdefault("max_spell_points", max_spell_points)
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=4,
        max_action_points=4,
        alive=True,
        stats={"MND": 14, "INS": 12, "PRE": 12, "END": 12, "MIG": 10, "AGI": 10,
               "magic_resistance": 0, "hp": 20, "max_hp": 20},
        skills={},
        raw_payload=rp,
    )


def _spell_def(
    spell_id: str = "magic_missile",
    label: str = "Magic Missile",
    spell_type: str = "mage",
    level: int = 1,
) -> SpellDef:
    return SpellDef(
        spell_id=spell_id,
        label=label,
        spell_type=spell_type,
        school="evocation",
        level=level,
        casting_time=1,
        range=60,
        target_type="creature",
    )


def _mage_spellbook(
    actor_id: str = "caster",
    spell_id: str = "magic_missile",
    memorized: bool = True,
    expended: bool = False,
    max_slots: dict | None = None,
) -> Spellbook:
    return Spellbook(
        actor_id=actor_id,
        spell_type="mage",
        known_spells={1: [spell_id]},
        slots={1: [SpellSlot(1, spell_id, memorized=memorized, expended=expended)]},
        max_slots=max_slots or {1: 2},
    )


# ── SpellDef shape ───────────────────────────────────────────────────


class TestSpellDefShape:
    """Freeze SpellDef fields the UI will read."""

    def test_spell_def_has_required_fields(self):
        sd = _spell_def()
        d = sd.to_dict()
        required = {"spell_id", "label", "spell_type", "school", "level",
                     "casting_time", "range", "target_type"}
        missing = required - set(d.keys())
        assert not missing, f"SpellDef missing fields: {sorted(missing)}"

    def test_spell_def_round_trips(self):
        sd = _spell_def()
        restored = SpellDef.from_dict(sd.to_dict())
        assert restored.spell_id == sd.spell_id
        assert restored.level == sd.level
        assert restored.school == sd.school

    def test_spell_def_level_is_positive_integer(self):
        sd = _spell_def()
        assert isinstance(sd.level, int) and sd.level >= 1

    def test_spell_def_casting_time_is_non_negative(self):
        sd = _spell_def()
        assert isinstance(sd.casting_time, int) and sd.casting_time >= 0


# ── SpellSlot shape ──────────────────────────────────────────────────


class TestSpellSlotShape:
    """Freeze SpellSlot fields."""

    def test_spell_slot_has_required_fields(self):
        slot = SpellSlot(1, "magic_missile", memorized=True, expended=False)
        d = slot.to_dict()
        required = {"spell_level", "spell_id", "memorized", "expended"}
        missing = required - set(d.keys())
        assert not missing, f"SpellSlot missing fields: {sorted(missing)}"

    def test_spell_slot_round_trips(self):
        slot = SpellSlot(1, "magic_missile", memorized=True, expended=False)
        restored = SpellSlot.from_dict(slot.to_dict())
        assert restored.spell_level == 1
        assert restored.spell_id == "magic_missile"
        assert restored.memorized is True
        assert restored.expended is False

    def test_memorized_and_expended_are_booleans(self):
        slot = SpellSlot(1, "shield", memorized=True, expended=True)
        d = slot.to_dict()
        assert isinstance(d["memorized"], bool)
        assert isinstance(d["expended"], bool)


# ── Spellbook shape ──────────────────────────────────────────────────


class TestSpellbookShape:
    """Freeze Spellbook fields: known_spells, slots, max_slots."""

    def test_spellbook_has_required_fields(self):
        sb = _mage_spellbook()
        d = sb.to_dict()
        required = {"actor_id", "spell_type", "known_spells", "slots", "max_slots"}
        missing = required - set(d.keys())
        assert not missing, f"Spellbook missing fields: {sorted(missing)}"

    def test_spellbook_round_trips(self):
        sb = _mage_spellbook()
        restored = Spellbook.from_dict(sb.to_dict())
        assert restored.actor_id == sb.actor_id
        assert restored.spell_type == sb.spell_type
        assert restored.known_spells == sb.known_spells
        assert restored.max_slots == sb.max_slots

    def test_known_spells_is_dict_of_level_to_spell_id_lists(self):
        sb = _mage_spellbook()
        d = sb.to_dict()
        for level_key, spell_ids in d["known_spells"].items():
            assert isinstance(spell_ids, list)
            for sid in spell_ids:
                assert isinstance(sid, str)

    def test_slots_is_dict_of_level_to_slot_lists(self):
        sb = _mage_spellbook()
        d = sb.to_dict()
        for level_key, slot_list in d["slots"].items():
            assert isinstance(slot_list, list)
            for slot in slot_list:
                assert "spell_level" in slot
                assert "memorized" in slot
                assert "expended" in slot

    def test_max_slots_is_dict_of_level_to_int(self):
        sb = _mage_spellbook()
        d = sb.to_dict()
        for level_key, count in d["max_slots"].items():
            assert isinstance(count, int)
            assert count >= 0


# ── Slot-based memorization contract ─────────────────────────────────


class TestSlotBasedMemorizationContract:
    """Prepared casters do not pretend to have infinite slots."""

    def test_available_slots_bounded_by_max_slots(self):
        sb = _mage_spellbook(max_slots={1: 2})
        assert sb.available_slots(1) <= sb.max_slots[1]

    def test_expended_slot_reduces_available_count(self):
        sb = Spellbook(
            actor_id="caster",
            spell_type="mage",
            known_spells={1: ["magic_missile"]},
            slots={1: [
                SpellSlot(1, "magic_missile", memorized=True, expended=False),
                SpellSlot(1, "magic_missile", memorized=True, expended=True),
            ]},
            max_slots={1: 2},
        )
        assert sb.available_slots(1) == 1

    def test_all_expended_means_zero_available(self):
        sb = Spellbook(
            actor_id="caster",
            spell_type="mage",
            slots={1: [
                SpellSlot(1, "magic_missile", memorized=True, expended=True),
                SpellSlot(1, "shield", memorized=True, expended=True),
            ]},
            max_slots={1: 2},
        )
        assert sb.available_slots(1) == 0

    def test_rest_refresh_clears_expended_not_max_slots(self):
        sb = Spellbook(
            actor_id="caster",
            spell_type="mage",
            slots={1: [
                SpellSlot(1, "magic_missile", memorized=True, expended=True),
                SpellSlot(1, "shield", memorized=True, expended=True),
            ]},
            max_slots={1: 2},
        )
        rest_refresh_spellbook(sb)
        assert sb.available_slots(1) == 2
        assert sb.max_slots[1] == 2


# ── Channeler / point caster contract ────────────────────────────────


class TestChannelerContract:
    """Point casters do not pretend to use memorized slots."""

    def test_channeler_memorize_returns_false(self):
        sb = Spellbook(actor_id="caster", spell_type="channeler")
        assert sb.memorize("ember_burst", 1) is False

    def test_channeler_begin_casting_does_not_require_memorized_slot(self):
        actor = _actor()
        sb = Spellbook(actor_id="caster", spell_type="channeler")
        sd = _spell_def(spell_type="channeler")
        ok, attempt, error = begin_casting(
            actor, sb, sd, target_id="target", target_point=None, current_tick=10,
        )
        assert ok is True
        assert error == ""

    def test_channeler_has_no_slots_by_default(self):
        sb = Spellbook(actor_id="caster", spell_type="channeler")
        assert sb.slots == {}
        assert sb.max_slots == {}


# ── CastingAttempt shape ─────────────────────────────────────────────


class TestCastingAttemptShape:
    """Freeze CastingAttempt / concentration payload fields."""

    def test_casting_attempt_has_required_fields(self):
        attempt = CastingAttempt(
            caster_id="caster",
            spell_def=_spell_def(),
            target_id="target",
            tick_started=10,
            ticks_remaining=2,
        )
        d = attempt.to_dict()
        required = {"caster_id", "spell_def", "target_id", "tick_started",
                     "ticks_remaining", "interrupted", "failed", "failure_reason", "completed"}
        missing = required - set(d.keys())
        assert not missing, f"CastingAttempt missing fields: {sorted(missing)}"

    def test_casting_attempt_round_trips(self):
        attempt = CastingAttempt(
            caster_id="caster",
            spell_def=_spell_def(),
            target_id="target",
            tick_started=10,
            ticks_remaining=2,
        )
        restored = CastingAttempt.from_dict(attempt.to_dict())
        assert restored.caster_id == attempt.caster_id
        assert restored.spell_def.spell_id == attempt.spell_def.spell_id
        assert restored.ticks_remaining == attempt.ticks_remaining
        assert restored.completed == attempt.completed

    def test_casting_attempt_status_flags_are_booleans(self):
        attempt = CastingAttempt(
            caster_id="caster",
            spell_def=_spell_def(),
        )
        d = attempt.to_dict()
        assert isinstance(d["interrupted"], bool)
        assert isinstance(d["failed"], bool)
        assert isinstance(d["completed"], bool)


# ── Player spell point contract ──────────────────────────────────────


class TestPlayerSpellPointContract:
    """Actor spell_points and max_spell_points shape."""

    def test_spell_points_readable(self):
        actor = _actor(spell_points=8, max_spell_points=12)
        assert actor.spell_points == 8
        assert actor.max_spell_points == 12

    def test_spell_points_writable(self):
        actor = _actor(spell_points=10, max_spell_points=10)
        actor.spell_points = 5
        assert actor.spell_points == 5

    def test_spell_points_never_exceed_max_by_setter(self):
        """Setting spell_points does not automatically clamp to max,
        but the value stored should be the exact value set."""
        actor = _actor(spell_points=0, max_spell_points=10)
        actor.spell_points = 10
        assert actor.spell_points == 10

    def test_zero_sp_caster_is_valid(self):
        """A warrior with 0/0 spell points is a valid state."""
        actor = _actor(spell_points=0, max_spell_points=0)
        assert actor.spell_points == 0
        assert actor.max_spell_points == 0


# ── Spell request shape (cast command) ───────────────────────────────


class TestSpellRequestShape:
    """Freeze the 'cast X [at Y]' command contract."""

    def test_cast_command_returns_spell_cmd_type(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime()
        ctx = rt.create_campaign("SpellProbe", "mage", "fantasy_ember", "standard", 42)
        player = ctx.kernel_runtime["actors"]["player"]
        player.spell_points = 10
        player.raw_payload["max_spell_points"] = 10
        result = rt.run_command(ctx.campaign_id, "cast magic missile")
        assert result["command_type"] == "spell"

    def test_cast_unknown_spell_returns_spell_cmd_type(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime()
        ctx = rt.create_campaign("SpellProbe2", "mage", "fantasy_ember", "standard", 43)
        result = rt.run_command(ctx.campaign_id, "cast nonexistent_zap")
        assert result["command_type"] == "spell"
        assert "unknown" in result["narrative"].lower()

    def test_cast_without_prepared_slot_returns_spell_cmd_type(self):
        from engine.api.campaign.runtime import CampaignRuntime
        rt = CampaignRuntime()
        ctx = rt.create_campaign("SpellProbe3", "mage", "fantasy_ember", "standard", 44)
        player = ctx.kernel_runtime["actors"]["player"]
        player.spell_points = 0
        result = rt.run_command(ctx.campaign_id, "cast fireball")
        assert result["command_type"] == "spell"
        assert "no available slot" in result["narrative"].lower()


# ── Combat available_actions cast truthfulness ───────────────────────


class TestCombatCastTruthfulness:
    """Combat available_actions should only include 'cast' when the runtime
    can actually dispatch casting for the acting combatant."""

    def test_combat_available_actions_include_cast_for_supported_mage(self):
        from fastapi.testclient import TestClient
        from main import app
        tc = TestClient(app)

        payload = tc.post("/game/campaigns", json={
            "player_name": "CastProbe",
            "player_class": "mage",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 55,
        }).json()
        campaign_id = payload["campaign_id"]
        target = ensure_attack_target(campaign_id, actor_id="spell_contract_target", name="Spell Contract Fang")
        body = tc.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"attack {target['name']}"},
        ).json()
        assert body.get("command_type") == "combat"

        actions = body["campaign"]["combat"]["available_actions"]
        assert "cast" in actions, (
            "Combat payload should advertise 'cast' when the active mage can cast in combat"
        )
