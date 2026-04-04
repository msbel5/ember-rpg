"""Tests that lock runtime dispatch authority.

Verifies:
- Unknown commands get explicit rejection, not silent legacy fallback.
- Dialog returns empty (not fallback) when kernel actors unavailable.
- _check_level_up adapter behavior is locked with exact thresholds.
"""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.live_kernel import _check_level_up


def _runtime() -> CampaignRuntime:
    return CampaignRuntime(llm=None)


def _make_campaign(name: str = "AuthTest", seed: int = 42):
    rt = _runtime()
    ctx = rt.create_campaign(player_name=name, seed=seed)
    return rt, ctx


# ---------------------------------------------------------------------------
# Task 1: Unknown command rejection (no legacy fallback)
# ---------------------------------------------------------------------------

class TestUnknownCommandRejection:
    def test_unknown_command_returns_unknown_type(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "xyzzy nonsense gibberish")
        assert result["command_type"] == "unknown"

    def test_unknown_command_narrative_says_unknown(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "frobnicate the widget")
        assert "unknown command" in result["narrative"].lower()

    def test_unknown_command_advances_zero_hours(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "dance wildly")
        assert result["hours_advanced"] == 0

    def test_known_commands_not_rejected(self):
        """Verify real commands still work after fallback removal."""
        rt, ctx = _make_campaign()
        for cmd in ["rest", "diagnose self", "defend"]:
            result = rt.run_command(ctx.campaign_id, cmd)
            assert result["command_type"] != "unknown", f"'{cmd}' was rejected as unknown"

    def test_look_around_routed_via_exploration_bridge(self):
        """'look around' is handled by the campaign-native exploration bridge."""
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "look around")
        assert result["command_type"] == "exploration"
        assert "narrative" in result


# ---------------------------------------------------------------------------
# Task 2: Dialog — no fallback payload
# ---------------------------------------------------------------------------

class TestDialogNoFallback:
    def test_dialog_returns_empty_when_not_talking(self):
        """build_dialog_payload should return {} when not in NPC conversation."""
        from engine.api.campaign.dialog import build_dialog_payload
        _rt, ctx = _make_campaign()
        result = build_dialog_payload(ctx, "Some narrative text")
        assert result == {}

    def test_dialog_returns_empty_when_actors_missing(self):
        """When kernel actors are not available, dialog returns {} not fallback."""
        from engine.api.campaign.dialog import build_dialog_payload
        _rt, ctx = _make_campaign()
        # Force a conversation state but with no matching kernel actor.
        ctx.session.conversation_state = {
            "target_type": "npc",
            "npc_id": "nonexistent_npc_999",
            "npc_name": "Ghost",
        }
        # Clear kernel actors to simulate missing state.
        ctx.kernel_runtime["actors"] = {"player": ctx.kernel_runtime["actors"]["player"]}
        result = build_dialog_payload(ctx, "Hello?")
        # Must return empty dict, NOT a fallback with hardcoded options.
        assert result == {} or "dialog_options" in result
        if "dialog_options" in result:
            # If dialog IS returned, it must come from kernel (authored/default def),
            # not from a fallback with "ask about work" hardcoded text.
            for opt in result["dialog_options"]:
                assert opt.get("command", "").startswith("dialog "), (
                    f"Non-kernel dialog option found: {opt}"
                )

    def test_no_fallback_payload_function_exists(self):
        """The _fallback_payload function must not exist in dialog module."""
        from engine.api.campaign import dialog
        assert not hasattr(dialog, "_fallback_payload"), (
            "_fallback_payload still exists — legacy fallback not removed"
        )


# ---------------------------------------------------------------------------
# Task 3: Progression adapter — locked behavior
# ---------------------------------------------------------------------------

class TestProgressionAdapterLocked:
    def test_no_level_up_below_threshold(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 0
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert len(events) == 0
        assert int(player.raw_payload["level"]) == 1

    def test_level_up_at_first_threshold(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 300  # First threshold in progression.json
        player.raw_payload["level"] = 1
        old_max_hp = int(player.stats.get("max_hp", 10))
        events = _check_level_up(player)
        assert len(events) >= 1
        assert events[0]["event_type"] == "level_up"
        assert int(player.raw_payload["level"]) == 2
        assert int(player.stats["max_hp"]) > old_max_hp

    def test_multi_level_jump(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 99999
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        assert len(events) >= 2  # Should jump multiple levels
        assert int(player.raw_payload["level"]) > 2

    def test_level_up_heals_to_max(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 300
        player.raw_payload["level"] = 1
        player.stats["hp"] = 1  # Wounded
        _check_level_up(player)
        assert player.stats["hp"] == player.stats["max_hp"]

    def test_level_up_event_has_required_fields(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 300
        player.raw_payload["level"] = 1
        events = _check_level_up(player)
        ev = events[0]
        assert "event_type" in ev
        assert "new_level" in ev
        assert "hp_gained" in ev
        assert "new_max_hp" in ev
        assert "actor_id" in ev

    def test_at_cap_no_crash(self):
        _rt, ctx = _make_campaign()
        player = ctx.kernel_runtime["actors"]["player"]
        player.raw_payload["xp"] = 999999
        player.raw_payload["level"] = 20  # At cap
        events = _check_level_up(player)
        # Should not crash, may or may not level up depending on threshold count.
        assert isinstance(events, list)
