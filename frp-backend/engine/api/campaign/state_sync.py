"""Single-authority synchronization helpers for campaign runtime."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from engine.world.schedules import GameTime as LivingGameTime, hour_to_period

if TYPE_CHECKING:
    from .context import CampaignContext

logger = logging.getLogger(__name__)


def sync_context_clock(context: "CampaignContext") -> None:
    """Mirror the world simulation clock into UI-facing projections."""
    snapshot = getattr(getattr(context, "world", None), "simulation_snapshot", None)
    if snapshot is None:
        return

    hour = int(getattr(snapshot, "current_hour", 0)) % 24
    day = int(getattr(snapshot, "current_day", 1))

    if getattr(context, "game_time", None) is None:
        context.game_time = LivingGameTime(hour=hour, day=day)
    else:
        context.game_time.hour = hour
        context.game_time.minute = 0
        context.game_time.day = day
        context.game_time._period = hour_to_period(hour)  # type: ignore[attr-defined]

    runtime = getattr(context, "kernel_runtime", {}) or {}
    game_state = runtime.get("game_state")
    if game_state is not None:
        game_state.world_time.hour = hour
        game_state.world_time.day = day
        game_state.raw_payload.setdefault("calendar", {})
        game_state.raw_payload["calendar"].update({"hour": hour, "day": day})

    settlement = getattr(context, "settlement_state", None)
    if isinstance(settlement, dict):
        settlement["current_hour"] = int(getattr(snapshot, "current_hour", hour))
        settlement["current_day"] = day
        settlement["season"] = str(getattr(snapshot, "season", settlement.get("season", "spring")))

    from .region_projection import sync_schedule_projection

    sync_schedule_projection(context, current_hour=hour)


def sync_player_position(
    context: "CampaignContext",
    x: int,
    y: int,
    *,
    center_viewport: bool = True,
) -> None:
    """Update every player-position surface from one canonical coordinate pair."""
    px, py = int(x), int(y)
    context.position = [px, py]

    player = getattr(context, "player", None)
    if player is not None:
        player.position.x = px
        player.position.y = py

    runtime = getattr(context, "kernel_runtime", {}) or {}
    actors = runtime.get("actors", {})
    player_actor = actors.get("player")
    if player_actor is not None:
        player_actor.position.x = px
        player_actor.position.y = py

    player_entity = getattr(context, "player_entity", None)
    spatial_index = getattr(context, "spatial_index", None)
    if player_entity is not None:
        if spatial_index is not None:
            current = spatial_index.get_position(player_entity.id)
            if current is None:
                player_entity.position = (px, py)
                spatial_index.add(player_entity)
            else:
                spatial_index.move(player_entity, px, py)
        else:
            player_entity.position = (px, py)
        if player is not None:
            player_entity.hp = player.hp
            player_entity.max_hp = player.max_hp

    viewport = getattr(context, "viewport", None)
    if viewport is not None and center_viewport:
        viewport.center_on(px, py)

    game_state = runtime.get("game_state")
    if game_state is not None:
        game_state.raw_payload["current_area_position"] = [px, py]

    context.campaign_state["position"] = [px, py]
    logger.debug("Synchronized player position to (%d,%d)", px, py)


__all__ = ["sync_context_clock", "sync_player_position"]
