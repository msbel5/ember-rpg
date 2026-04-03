"""Async background tick loop for campaign idle simulation.

When a campaign is active but the player isn't issuing commands, this loop
advances the world simulation at regular intervals — keeping the colony,
NPCs, economy, and environment alive.

Usage:
    loop = CampaignTickLoop(runtime, campaign_id, on_tick=push_fn)
    await loop.start()
    ...
    await loop.stop()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional

from .runtime_commands import advance_world_tick

logger = logging.getLogger(__name__)

# Default: one game-hour every 30 real seconds.
DEFAULT_TICK_INTERVAL = 30.0
DEFAULT_TICK_HOURS = 1


class CampaignTickLoop:
    """Manages an asyncio task that periodically ticks a campaign's world."""

    def __init__(
        self,
        runtime: Any,
        campaign_id: str,
        *,
        tick_interval: float = DEFAULT_TICK_INTERVAL,
        tick_hours: int = DEFAULT_TICK_HOURS,
        on_tick: Optional[Callable[[str, list[dict[str, Any]], dict[str, Any]], Coroutine]] = None,
    ):
        self._runtime = runtime
        self._campaign_id = campaign_id
        self._interval = tick_interval
        self._tick_hours = tick_hours
        self._on_tick = on_tick
        self._task: Optional[asyncio.Task] = None
        self._paused = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def paused(self) -> bool:
        return self._paused

    async def start(self) -> None:
        """Start the background tick task."""
        if self.running:
            return
        self._task = asyncio.create_task(self._loop(), name=f"tick_{self._campaign_id[:8]}")
        logger.info("Tick loop started for campaign %s (interval=%.1fs)", self._campaign_id[:8], self._interval)

    async def stop(self) -> None:
        """Cancel the background tick task."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Tick loop stopped for campaign %s", self._campaign_id[:8])

    def pause(self) -> None:
        """Pause ticking (e.g. during combat)."""
        self._paused = True

    def resume(self) -> None:
        """Resume ticking after pause."""
        self._paused = False

    async def _loop(self) -> None:
        """Main tick loop — runs until cancelled."""
        while True:
            await asyncio.sleep(self._interval)
            if self._paused:
                continue
            try:
                context = self._runtime.get_campaign(self._campaign_id)
            except (KeyError, ValueError):
                logger.info("Campaign %s no longer exists, stopping tick loop", self._campaign_id[:8])
                break
            if context.session.in_combat():
                continue
            try:
                events = advance_world_tick(context, hours=self._tick_hours)
                if self._on_tick is not None:
                    from .persistence import campaign_payload
                    snapshot = campaign_payload(context)
                    await self._on_tick(self._campaign_id, events, snapshot)
                logger.debug("Tick: campaign=%s events=%d", self._campaign_id[:8], len(events))
            except Exception:
                logger.exception("Tick error for campaign %s", self._campaign_id[:8])


# Registry of active tick loops.
_tick_loops: dict[str, CampaignTickLoop] = {}


async def start_tick_loop(
    runtime: Any,
    campaign_id: str,
    on_tick: Optional[Callable] = None,
    interval: float = DEFAULT_TICK_INTERVAL,
) -> CampaignTickLoop:
    """Create and start a tick loop for a campaign."""
    if campaign_id in _tick_loops and _tick_loops[campaign_id].running:
        return _tick_loops[campaign_id]
    loop = CampaignTickLoop(runtime, campaign_id, tick_interval=interval, on_tick=on_tick)
    _tick_loops[campaign_id] = loop
    await loop.start()
    return loop


async def stop_tick_loop(campaign_id: str) -> None:
    """Stop and remove tick loop for a campaign."""
    loop = _tick_loops.pop(campaign_id, None)
    if loop is not None:
        await loop.stop()


def get_tick_loop(campaign_id: str) -> Optional[CampaignTickLoop]:
    """Get the tick loop for a campaign, or None."""
    return _tick_loops.get(campaign_id)


__all__ = ["CampaignTickLoop", "get_tick_loop", "start_tick_loop", "stop_tick_loop"]
