"""Travel command ownership for the campaign runtime."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.api.campaign.knowledge import discover_travel_topics
from engine.api.campaign.runtime_common import stable_seed
from engine.api.campaign.world import build_travel_options
from engine.kernel import TravelState, complete_travel, hydrate_local_map, initiate_travel, tick_travel
from engine.kernel.hybrid_runtime import resolve_travel_encounter

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


def _travel_runtime_state(context: "CampaignContext") -> TravelState:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    travel_state = runtime.get("travel_state")
    if isinstance(travel_state, TravelState):
        return travel_state
    if isinstance(travel_state, dict):
        try:
            normalized = TravelState.from_dict(travel_state)
        except TypeError:
            normalized = TravelState(status=str(travel_state.get("status", "idle") or "idle"))
        runtime["travel_state"] = normalized
        return normalized
    normalized = TravelState(status="idle")
    runtime["travel_state"] = normalized
    return normalized


def _travel_is_active(context: "CampaignContext") -> bool:
    status = str(_travel_runtime_state(context).status).strip().lower()
    return status not in {"", "idle", "arrived"}


def _set_travel_scene(context: "CampaignContext", scene_name: str) -> None:
    if context.dm_context is not None:
        context.dm_context.scene_type_name = scene_name


def _travel_seed(context: "CampaignContext", travel_state: TravelState, action_id: str) -> int:
    simulation = context.world.simulation_snapshot
    current_day = int(getattr(simulation, "current_day", 0) or 0) if simulation is not None else 0
    current_hour = int(getattr(simulation, "current_hour", 0) or 0) if simulation is not None else 0
    return stable_seed(
        context.seed,
        context.campaign_id,
        action_id,
        travel_state.origin_region_id,
        travel_state.destination_region_id,
        travel_state.edge_id,
        current_day,
        current_hour,
        travel_state.travel_hours_remaining,
    )


def _current_travel_route(context: "CampaignContext") -> dict[str, Any] | None:
    travel_state = _travel_runtime_state(context)
    if not _travel_is_active(context):
        return None
    options = build_travel_options(context.world, context=context)
    route_id = str(travel_state.edge_id).strip()
    destination_region_id = str(travel_state.destination_region_id).strip()
    destination_settlement_id = str(
        getattr(travel_state, "destination_settlement_id", "") or ""
    ).strip()
    return next(
        (
            option
            for option in options
            if (
                route_id and str(option.get("route_id", "")).strip() == route_id
            ) or (
                str(option.get("destination_region_id", "")).strip() == destination_region_id
                and (
                    not destination_settlement_id
                    or str(option.get("destination_settlement_id", "")).strip() == destination_settlement_id
                )
            )
        ),
        None,
    )


def _select_travel_route(
    context: "CampaignContext",
    command_text: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    target = command_text[len("travel"):].strip().lower() if command_text.lower().startswith("travel") else ""
    route_id = str(payload.get("route_id", "")).strip()
    destination_region_id = str(payload.get("destination_region_id", "")).strip()
    destination_settlement_id = str(payload.get("destination_settlement_id", "")).strip()
    options = build_travel_options(context.world, context=context)
    if route_id:
        return next((item for item in options if str(item.get("route_id", "")).strip() == route_id), None)
    if destination_region_id:
        return next(
            (
                item
                for item in options
                if str(item.get("destination_region_id", "")).strip() == destination_region_id
                and (
                    not destination_settlement_id
                    or str(item.get("destination_settlement_id", "")).strip() == destination_settlement_id
                )
            ),
            None,
        )
    if target:
        return next(
            (
                item
                for item in options
                if target in str(item.get("destination_name", "")).lower()
                or target in str(item.get("destination_region_id", "")).lower()
                or target == str(item.get("destination_settlement_id", "")).lower()
                or target == str(item.get("route_id", "")).lower()
            ),
            None,
        )
    return options[0] if options else None


def _apply_completed_travel(context: "CampaignContext", travel_state: TravelState) -> str:
    runtime = context.kernel_runtime or {}
    kernel_world = runtime.get("world_state")
    if kernel_world is None:
        raise ValueError("Kernel world state is missing for travel completion.")
    authority = complete_travel(travel_state, kernel_world)
    runtime["path_authority"] = authority
    runtime["local_map_state"] = hydrate_local_map(kernel_world, authority.active_region_id)
    runtime["travel_state"] = TravelState(status="idle")
    if context.world.simulation_snapshot is not None:
        context.world.simulation_snapshot.active_region_id = authority.active_region_id
    discover_travel_topics(
        context,
        destination_region_id=str(travel_state.destination_region_id or authority.active_region_id),
    )
    _set_travel_scene(context, "exploration")
    route = _current_travel_route(context)
    destination_name = ""
    if route is not None:
        destination_name = str(route.get("destination_name", "")).strip()
    if not destination_name:
        destination_name = str(authority.active_region_id)
    return f"Travel complete. You arrive at {destination_name}."


def handle_travel(
    context: "CampaignContext",
    command_text: str,
    args: Optional[dict[str, Any]] = None,
) -> str:
    payload = dict(args or {})
    runtime = getattr(context, "kernel_runtime", {}) or {}
    if not runtime:
        from engine.api.campaign.live_kernel import ensure_kernel_runtime

        runtime = ensure_kernel_runtime(context)
    raw = command_text.strip().lower()
    action_id = str(payload.get("action_id", "")).strip().lower()
    if raw in {"continue travel", "resume travel"}:
        action_id = "advance"
    elif raw == "resolve travel encounter":
        action_id = "resolve_encounter"
    elif raw.startswith("travel") or not action_id:
        action_id = action_id or "start"

    active_state = _travel_runtime_state(context)
    if action_id == "start":
        if _travel_is_active(context):
            route = _current_travel_route(context)
            destination_name = str(route.get("destination_name", "your destination")) if route is not None else "your destination"
            context.campaign_state["last_travel_hours"] = 0
            _set_travel_scene(context, "travel")
            return f"You are already traveling to {destination_name}. Use continue travel to keep moving."
        selected = _select_travel_route(context, command_text, payload)
        if selected is None:
            context.campaign_state["last_travel_hours"] = 0
            return "No reachable travel route matches that destination."
        kernel_world = runtime.get("world_state")
        if kernel_world is None:
            raise ValueError("Kernel world state is missing for travel start.")
        kernel_world.active_region_id = str(context.world.simulation_snapshot.active_region_id)
        travel_state = initiate_travel(
            kernel_world,
            str(context.world.simulation_snapshot.active_region_id),
            str(selected["destination_region_id"]),
            seed=_travel_seed(context, TravelState(
                status="preparing",
                origin_region_id=str(context.world.simulation_snapshot.active_region_id),
                destination_region_id=str(selected["destination_region_id"]),
                travel_hours_remaining=int(selected.get("travel_hours", 0) or 0),
                travel_hours_total=int(selected.get("travel_hours", 0) or 0),
                edge_id=str(selected.get("route_id", "")),
                danger_level=int(selected.get("danger_level", 0) or 0),
            ), "start"),
        )
        travel_state.edge_id = str(selected.get("route_id", "")).strip() or travel_state.edge_id
        runtime["travel_state"] = travel_state
        discover_travel_topics(
            context,
            destination_region_id=str(selected.get("destination_region_id", "")).strip(),
            destination_settlement_id=str(selected.get("destination_settlement_id", "")).strip(),
        )
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return (
            f"You set out for {selected['destination_name']}. "
            f"The route will take about {int(selected.get('travel_hours', 0) or 0)}h."
        )

    if not _travel_is_active(context):
        context.campaign_state["last_travel_hours"] = 0
        return "No active travel route. Start traveling first."

    if action_id == "resolve_encounter":
        if not active_state.paused_for_encounter or active_state.encounter_resolved:
            context.campaign_state["last_travel_hours"] = 0
            _set_travel_scene(context, "travel")
            return "There is no unresolved travel encounter to resolve."
        runtime["travel_state"] = resolve_travel_encounter(active_state)
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return "You regroup and resolve the travel encounter. The route can continue."

    if action_id != "advance":
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return f"Unsupported travel action '{action_id}'."

    if active_state.paused_for_encounter and not active_state.encounter_resolved:
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return "Travel is paused by an encounter. Resolve the travel encounter before moving on."

    ticking_state = TravelState.from_dict(active_state.to_dict())
    if str(ticking_state.status).strip().lower() == "preparing":
        ticking_state.status = "traveling"
    updated = tick_travel(ticking_state, seed=_travel_seed(context, ticking_state, "advance"))
    runtime["travel_state"] = updated
    context.campaign_state["last_travel_hours"] = 1
    _set_travel_scene(context, "travel")
    route = _current_travel_route(context)
    destination_name = str(route.get("destination_name", "your destination")) if route is not None else "your destination"
    if updated.paused_for_encounter and not updated.encounter_resolved:
        return f"Travel toward {destination_name} is interrupted by an encounter."
    if updated.status in {"arriving", "arrived"} or updated.travel_hours_remaining <= 0:
        return _apply_completed_travel(context, updated)
    return (
        f"You continue toward {destination_name}. "
        f"{int(updated.travel_hours_remaining)}h remain on the route."
    )


__all__ = ["handle_travel"]
