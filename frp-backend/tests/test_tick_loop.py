"""Tests for the campaign tick loop and runtime_commands extraction."""
from __future__ import annotations

import asyncio
import pytest

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.tick_loop import CampaignTickLoop, start_tick_loop, stop_tick_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_campaign() -> tuple[CampaignRuntime, str]:
    rt = CampaignRuntime()
    ctx = rt.create_campaign(player_name="TickTest", seed=42)
    return rt, ctx.campaign_id


# ---------------------------------------------------------------------------
# run_command extraction
# ---------------------------------------------------------------------------

class TestRunCommandExtraction:
    def test_run_command_returns_result(self):
        rt, cid = _create_campaign()
        result = rt.run_command(cid, "look around")
        assert "narrative" in result
        assert "command_type" in result
        assert "campaign" in result

    def test_run_command_advances_time(self):
        rt, cid = _create_campaign()
        ctx_before = rt.get_campaign(cid)
        hour_before = ctx_before.world.simulation_snapshot.current_hour
        rt.run_command(cid, "rest")
        ctx_after = rt.get_campaign(cid)
        assert ctx_after.world.simulation_snapshot.current_hour != hour_before


# ---------------------------------------------------------------------------
# advance_world_tick
# ---------------------------------------------------------------------------

class TestAdvanceWorldTick:
    def test_advance_returns_events(self):
        from engine.api.campaign.runtime_commands import advance_world_tick
        rt, cid = _create_campaign()
        ctx = rt.get_campaign(cid)
        events = advance_world_tick(ctx, hours=1)
        assert isinstance(events, list)

    def test_advance_increments_time(self):
        from engine.api.campaign.runtime_commands import advance_world_tick
        rt, cid = _create_campaign()
        ctx = rt.get_campaign(cid)
        day_before = ctx.world.simulation_snapshot.current_day
        advance_world_tick(ctx, hours=24)
        assert ctx.world.simulation_snapshot.current_day > day_before


# ---------------------------------------------------------------------------
# CampaignTickLoop
# ---------------------------------------------------------------------------

class TestCampaignTickLoop:
    @pytest.mark.asyncio
    async def test_loop_starts_and_stops(self):
        rt, cid = _create_campaign()
        loop = CampaignTickLoop(rt, cid, tick_interval=0.05)
        await loop.start()
        assert loop.running
        await loop.stop()
        assert not loop.running

    @pytest.mark.asyncio
    async def test_loop_fires_tick(self):
        rt, cid = _create_campaign()
        tick_count = {"n": 0}

        async def on_tick(campaign_id, events, snapshot):
            tick_count["n"] += 1

        loop = CampaignTickLoop(rt, cid, tick_interval=0.05, on_tick=on_tick)
        await loop.start()
        await asyncio.sleep(0.2)
        await loop.stop()
        assert tick_count["n"] >= 1

    @pytest.mark.asyncio
    async def test_loop_pauses(self):
        rt, cid = _create_campaign()
        tick_count = {"n": 0}

        async def on_tick(campaign_id, events, snapshot):
            tick_count["n"] += 1

        loop = CampaignTickLoop(rt, cid, tick_interval=0.05, on_tick=on_tick)
        loop.pause()
        await loop.start()
        await asyncio.sleep(0.15)
        await loop.stop()
        assert tick_count["n"] == 0

    @pytest.mark.asyncio
    async def test_loop_stops_on_missing_campaign(self):
        rt, cid = _create_campaign()
        loop = CampaignTickLoop(rt, cid, tick_interval=0.05)
        await loop.start()
        rt.delete_campaign(cid)
        await asyncio.sleep(0.15)
        assert not loop.running


# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

class TestTickLoopRegistry:
    @pytest.mark.asyncio
    async def test_start_and_stop_registry(self):
        rt, cid = _create_campaign()
        loop = await start_tick_loop(rt, cid, interval=0.05)
        assert loop.running
        await stop_tick_loop(cid)
        assert not loop.running

    @pytest.mark.asyncio
    async def test_duplicate_start_returns_same_loop(self):
        rt, cid = _create_campaign()
        loop1 = await start_tick_loop(rt, cid, interval=0.05)
        loop2 = await start_tick_loop(rt, cid, interval=0.05)
        assert loop1 is loop2
        await stop_tick_loop(cid)
