"""Tests for kernel bridges: commerce, spells, medical commands."""
from __future__ import annotations

import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign_commands import (
    maybe_handle_commerce_command,
    maybe_handle_medical_command,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign():
    rt = CampaignRuntime(llm=None)
    ctx = rt.create_campaign(player_name="BridgeTest", seed=42)
    return rt, ctx


# ---------------------------------------------------------------------------
# Commerce commands
# ---------------------------------------------------------------------------

class TestCommerceCommands:
    def test_buy_command_recognized(self):
        _, ctx = _make_campaign()
        result = maybe_handle_commerce_command(ctx, "buy bread")
        # May fail to find merchant, but command is recognized.
        assert result is not None
        assert isinstance(result[0], str)
        assert result[1] == "commerce"

    def test_sell_command_recognized(self):
        _, ctx = _make_campaign()
        result = maybe_handle_commerce_command(ctx, "sell iron_bar")
        assert result is not None
        assert result[1] == "commerce"

    def test_rent_room_recognized(self):
        _, ctx = _make_campaign()
        result = maybe_handle_commerce_command(ctx, "rent room")
        assert result is not None
        assert result[1] == "commerce"

    def test_identify_recognized(self):
        _, ctx = _make_campaign()
        result = maybe_handle_commerce_command(ctx, "identify strange ring")
        assert result is not None
        assert result[1] == "commerce"

    def test_non_commerce_returns_none(self):
        _, ctx = _make_campaign()
        result = maybe_handle_commerce_command(ctx, "attack goblin")
        assert result is None

    def test_buy_via_runtime(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "buy bread")
        assert "narrative" in result
        assert "command_type" in result
        assert result["command_type"] == "commerce"


# ---------------------------------------------------------------------------
# Medical commands
# ---------------------------------------------------------------------------

class TestMedicalCommands:
    def test_diagnose_self(self):
        _, ctx = _make_campaign()
        result = maybe_handle_medical_command(ctx, "diagnose self")
        assert result is not None
        assert isinstance(result[0], str)
        assert result[1] == "medical"

    def test_treat_self(self):
        _, ctx = _make_campaign()
        result = maybe_handle_medical_command(ctx, "treat self")
        assert result is not None
        assert result[1] == "medical"

    def test_non_medical_returns_none(self):
        _, ctx = _make_campaign()
        result = maybe_handle_medical_command(ctx, "look around")
        assert result is None

    def test_diagnose_via_runtime(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "diagnose self")
        assert "narrative" in result
        assert result["command_type"] == "medical"


# ---------------------------------------------------------------------------
# Spell pipeline (integration)
# ---------------------------------------------------------------------------

class TestSpellPipeline:
    def test_cast_command_via_runtime(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "cast magic missile")
        assert "narrative" in result
        # Should not crash — spell pipeline is wired.

    def test_rest_command_works(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "rest")
        assert "narrative" in result
        assert result.get("hours_advanced", 0) >= 1  # short rest = 1h, long rest = 8h


# ---------------------------------------------------------------------------
# Command dispatch priority
# ---------------------------------------------------------------------------

class TestCommandDispatchOrder:
    def test_commerce_uses_specialized_command_type(self):
        """Buy/sell should be intercepted by the commerce handler."""
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "buy healing_potion")
        # Commerce handler intercepts — could be item not found, no merchant, etc.
        narrative = result.get("narrative", "").lower()
        assert result.get("command_type") == "commerce"
        assert any(k in narrative for k in ("buy", "merchant", "bought", "not found", "stock", "item", "gold"))

    def test_medical_uses_specialized_command_type(self):
        rt, ctx = _make_campaign()
        result = rt.run_command(ctx.campaign_id, "diagnose self")
        narrative = result.get("narrative", "").lower()
        assert result.get("command_type") == "medical"
        assert "diagnos" in narrative or "wound" in narrative or "injur" in narrative or "stable" in narrative
