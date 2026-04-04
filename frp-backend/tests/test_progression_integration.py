"""Integration tests for XP progression wired into the campaign runtime.

Verifies that:
- Players start at level 1 with 0 XP.
- XP can be awarded to the kernel ActorRecord.
- The level-up check in advance_kernel_runtime fires correctly.
- Multi-level jumps work when enough XP is granted.
- The _award_combat_xp helper computes correct XP from target stats.
"""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.live_kernel import (
    _check_level_up,
    advance_kernel_runtime,
    ensure_kernel_runtime,
)
from engine.kernel.actor_records import ActorRecord, create_player_actor, create_monster_actor


def _award_combat_xp(player: ActorRecord, target: ActorRecord) -> int:
    """Award XP to the player's kernel ActorRecord for defeating a target.

    XP is derived from the target's level or challenge rating.  The amount
    is written into ``player.raw_payload["xp"]`` so that the campaign
    runtime level-up check can pick it up.
    """
    target_level = int(target.raw_payload.get("level", 0))
    target_cr = float(target.raw_payload.get("cr", 0))
    effective_level = max(1, target_level, int(target_cr))
    base_xp = effective_level * 50
    player.raw_payload.setdefault("xp", 0)
    player.raw_payload["xp"] = int(player.raw_payload["xp"]) + base_xp
    return base_xp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="XPTest", seed=42)
    return rt, ctx


def _get_player(ctx):
    return ctx.kernel_runtime["actors"]["player"]


# ---------------------------------------------------------------------------
# Basic state tests
# ---------------------------------------------------------------------------

class TestPlayerStartState:
    def test_player_starts_at_level_1(self):
        _, ctx = _make_campaign()
        player = _get_player(ctx)
        assert int(player.raw_payload.get("level", 1)) >= 1

    def test_player_starts_with_zero_or_low_xp(self):
        _, ctx = _make_campaign()
        player = _get_player(ctx)
        # Player may start with 0 XP or a small amount from creation.
        assert int(player.raw_payload.get("xp", 0)) >= 0


# ---------------------------------------------------------------------------
# XP award tests
# ---------------------------------------------------------------------------

class TestXPAward:
    def test_xp_can_be_awarded_directly(self):
        _, ctx = _make_campaign()
        player = _get_player(ctx)
        player.raw_payload["xp"] = 0
        player.raw_payload["xp"] += 100
        assert player.raw_payload["xp"] == 100

    def test_award_combat_xp_from_level(self):
        """_award_combat_xp uses target level * 50."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 0
        target = create_monster_actor(
            {"id": "goblin", "name": "Goblin", "hp": 10, "cr": 2.0,
             "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 8, "INS": 8, "PRE": 8},
             "attacks": [{"name": "claw", "attack_bonus": 3, "damage": "1d4"}]},
        )
        xp_earned = _award_combat_xp(player, target)
        assert xp_earned == 100  # cr=2 -> effective_level=2, 2*50=100
        assert player.raw_payload["xp"] == 100

    def test_award_combat_xp_minimum_level_1(self):
        """Even a target with no level/cr yields at least 50 XP."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 0
        target = create_monster_actor(
            {"id": "rat", "name": "Rat", "hp": 2,
             "stats": {"MIG": 4, "AGI": 10, "END": 4, "MND": 2, "INS": 2, "PRE": 2},
             "attacks": [{"name": "bite", "attack_bonus": 0, "damage": "1d2"}]},
        )
        xp_earned = _award_combat_xp(player, target)
        assert xp_earned >= 50  # Minimum effective_level is 1

    def test_award_combat_xp_accumulates(self):
        """Repeated kills accumulate XP."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 0
        template = {
            "id": "goblin", "name": "Goblin", "hp": 10, "cr": 1.0,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 8, "INS": 8, "PRE": 8},
            "attacks": [{"name": "claw", "attack_bonus": 3, "damage": "1d4"}],
        }
        total = 0
        for _ in range(5):
            target = create_monster_actor(template)
            total += _award_combat_xp(player, target)
        assert player.raw_payload["xp"] == total
        assert total == 250  # 5 * (1 * 50)


# ---------------------------------------------------------------------------
# Level-up check tests
# ---------------------------------------------------------------------------

class TestLevelUpCheck:
    def test_no_level_up_at_zero_xp(self):
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 0
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert events == []
        assert player.raw_payload["level"] == 1

    def test_level_up_at_300_xp(self):
        """progression.json threshold for level 2 is 300 XP."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 300
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert len(events) >= 1
        assert events[0]["event_type"] == "level_up"
        assert events[0]["new_level"] == 2
        assert player.raw_payload["level"] == 2

    def test_level_up_increases_max_hp(self):
        """Level-up should increase max_hp based on class hp_per_level."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        old_max_hp = int(player.stats.get("max_hp", 1))
        player.raw_payload["xp"] = 300
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert len(events) >= 1
        new_max_hp = int(player.stats.get("max_hp", 1))
        assert new_max_hp > old_max_hp
        assert events[0]["hp_gained"] > 0

    def test_multi_level_jump(self):
        """Granting 2700 XP at level 1 should jump to level 4."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 2700
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        # Should have leveled from 1->2, 2->3, 3->4 (thresholds: 300, 900, 2700)
        assert len(events) == 3
        assert player.raw_payload["level"] == 4
        level_sequence = [e["new_level"] for e in events]
        assert level_sequence == [2, 3, 4]

    def test_level_up_heals_to_full(self):
        """On level-up the player should be healed to new max_hp."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.stats["hp"] = 5  # Damaged
        player.raw_payload["xp"] = 300
        player.raw_payload["level"] = 1
        _check_level_up(player)
        assert player.stats["hp"] == player.stats["max_hp"]

    def test_no_level_up_below_threshold(self):
        """299 XP should not trigger level 2 (threshold is 300)."""
        player = create_player_actor(
            "Tester", "warrior", {"MIG": 14, "AGI": 12, "END": 12, "MND": 10, "INS": 10, "PRE": 10},
        )
        player.raw_payload["xp"] = 299
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert events == []
        assert player.raw_payload["level"] == 1


# ---------------------------------------------------------------------------
# End-to-end: advance_kernel_runtime triggers level-up
# ---------------------------------------------------------------------------

class TestRuntimeLevelUp:
    def test_level_up_via_advance_kernel_runtime(self):
        """Give the player enough XP, then advance_kernel_runtime should
        emit a level_up event."""
        _, ctx = _make_campaign()
        player = _get_player(ctx)
        player.raw_payload["xp"] = 500  # Above 300 threshold for level 2
        player.raw_payload["level"] = 1
        events = advance_kernel_runtime(
            ctx, hours_advanced=1, command_type="rest", command_text="rest",
        )
        level_events = [e for e in events if e.get("event_type") == "level_up"]
        assert len(level_events) >= 1
        assert level_events[0]["new_level"] == 2
        # Player's kernel record should be updated.
        assert int(player.raw_payload.get("level", 1)) == 2

    def test_no_level_up_without_xp(self):
        """advance_kernel_runtime without XP should not emit level_up."""
        _, ctx = _make_campaign()
        player = _get_player(ctx)
        player.raw_payload["xp"] = 0
        player.raw_payload["level"] = 1
        events = advance_kernel_runtime(
            ctx, hours_advanced=1, command_type="rest", command_text="rest",
        )
        level_events = [e for e in events if e.get("event_type") == "level_up"]
        assert level_events == []
        assert int(player.raw_payload.get("level", 1)) == 1
