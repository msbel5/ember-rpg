"""Campaign payload builders and persistence helpers."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.api.campaign_kernel import (
    build_canonical_actor_records,
    build_canonical_game_state,
    build_canonical_world_state,
)
from engine.kernel import (
    colony_pressure_from_settlement,
    fluid_state_from_region,
    job_records_from_settlement,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
    power_network_from_settlement,
    production_ledger_from_settlement,
    reaction_defs_from_settlement,
    strange_mood_incident_from_settlement,
    syndrome_registry_from_actors,
    temperature_state_from_region,
    trap_state_from_settlement,
    worksite_records_from_settlement,
)
from engine.worldgen import snapshot_world

from .session import build_world_entities
from .settlement import build_character_sheet, current_player_turn_resources
from .live_kernel import ensure_kernel_runtime, serialize_kernel_runtime
from .world import (
    build_current_region_summary,
    build_travel_options,
    build_world_graph,
    map_payload_from_region,
    region_payload,
    runtime_region_state,
)

if TYPE_CHECKING:
    from .context import CampaignContext


def campaign_payload(context: "CampaignContext") -> dict[str, Any]:
    session_data = context.session.to_dict()
    runtime_state = runtime_region_state(context.world, context.region_snapshot.region_id)
    kernel_payload = build_kernel_payload(context)
    combat_state = session_data.get("combat")
    payload_scene = str(session_data.get("scene", "exploration"))
    if isinstance(combat_state, dict) and combat_state and not bool(combat_state.get("ended", False)):
        payload_scene = "combat"
    player_payload = copy.deepcopy(session_data["player"])
    player_payload["turn_resources"] = current_player_turn_resources(context.session)
    return {
        "world": {
            "seed": context.world.seed,
            "profile_id": context.world.profile_id,
            "adapter_id": context.adapter_id,
            "active_region_id": context.world.simulation_snapshot.active_region_id,
            "faction_count": len(context.world.factions),
            "settlement_count": len(context.world.settlements),
            "history_end_year": context.world.history_end_year,
            "current_hour": context.world.simulation_snapshot.current_hour if context.world.simulation_snapshot else 0,
            "current_day": context.world.simulation_snapshot.current_day if context.world.simulation_snapshot else 1,
            "season": context.world.simulation_snapshot.season if context.world.simulation_snapshot else "spring",
            "weather": copy.deepcopy(runtime_state.get("weather", {})),
        },
        **kernel_payload,
        "world_graph": build_world_graph(context.world),
        "travel_options": build_travel_options(context.world),
        "current_region_summary": build_current_region_summary(context.world, context.region_snapshot),
        "player": player_payload,
        "scene": payload_scene,
        "location": session_data["location"],
        "combat": combat_state,
        "conversation_state": session_data.get("conversation_state", {}),
        "region": region_payload(context),
        "map_data": map_payload_from_region(context.region_snapshot),
        "world_entities": build_world_entities(context.world, context.region_snapshot, context.adapter_id),
        "ground_items": copy.deepcopy(session_data.get("ground_items", [])),
        "active_quests": copy.deepcopy(runtime_state.get("active_quests", session_data.get("active_quests", []))),
        "quest_offers": copy.deepcopy(runtime_state.get("quest_offers", session_data.get("quest_offers", []))),
        "settlement": copy.deepcopy(context.settlement_state),
        "character_sheet": build_character_sheet(context.session, context.settlement_state),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-12:]),
    }


def persist_campaign_state(context: "CampaignContext") -> None:
    kernel_payload = build_kernel_payload(context)
    context.session.campaign_state["campaign"] = {
        "campaign_id": context.campaign_id,
        "adapter_id": context.adapter_id,
        "profile_id": context.profile_id,
        "seed": context.seed,
        "active_region_id": context.region_snapshot.region_id,
        "world_snapshot": snapshot_world(context.world),
        "world_state": kernel_payload["world_state"],
        "game_state": kernel_payload["game_state"],
        "actors": kernel_payload["actors"],
        "jobs": kernel_payload["jobs"],
        "reactions": kernel_payload["reactions"],
        "worksites": kernel_payload["worksites"],
        "colony_pressure": kernel_payload["colony_pressure"],
        "production_ledger": kernel_payload["production_ledger"],
        "path_authority": kernel_payload["path_authority"],
        "local_map_state": kernel_payload["local_map_state"],
        "military": kernel_payload["military"],
        "systems": kernel_payload["systems"],
        "stores": kernel_payload["stores"],
        "settlement_state": copy.deepcopy(context.settlement_state),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-20:]),
    }
    context.session.campaign_state.pop("campaign_v2", None)


def build_kernel_payload(context: "CampaignContext") -> dict[str, Any]:
    if context.kernel_runtime:
        return serialize_kernel_runtime(context)
    active_site_id = _active_site_id(context)
    canonical_world_state = build_canonical_world_state(context.world)
    canonical_actor_records = build_canonical_actor_records(
        context.session,
        active_region_id=context.region_snapshot.region_id,
        active_site_id=active_site_id,
    )
    canonical_game_state = build_canonical_game_state(
        context.session,
        campaign_id=context.campaign_id,
        seed=context.seed,
        active_region_id=context.region_snapshot.region_id,
        active_site_id=active_site_id,
    )
    colony_pressure_model = colony_pressure_from_settlement(context.settlement_state)
    strange_mood = strange_mood_incident_from_settlement(
        context.settlement_state,
        colony_pressure_model,
    )
    return {
        "world_state": canonical_world_state,
        "game_state": canonical_game_state.to_dict(),
        "actors": [actor.to_dict() for actor in canonical_actor_records],
        "jobs": [job.to_dict() for job in job_records_from_settlement(context.settlement_state)],
        "reactions": [reaction.to_dict() for reaction in reaction_defs_from_settlement(context.settlement_state)],
        "worksites": [worksite.to_dict() for worksite in worksite_records_from_settlement(context.settlement_state)],
        "colony_pressure": colony_pressure_model.to_dict(),
        "production_ledger": production_ledger_from_settlement(context.settlement_state).to_dict(),
        "path_authority": path_authority_from_world(context.world, context.region_snapshot).to_dict(),
        "local_map_state": local_map_state_from_region(context.region_snapshot).to_dict(),
        "military": military_state_from_settlement(context.settlement_state).to_dict(),
        "systems": {
            "syndrome_registry": [
                syndrome.to_dict() for syndrome in syndrome_registry_from_actors(canonical_actor_records)
            ],
            "power_network": power_network_from_settlement(context.settlement_state).to_dict(),
            "traps": [trap.to_dict() for trap in trap_state_from_settlement(context.settlement_state)],
            "fluid_state": fluid_state_from_region(context.region_snapshot).to_dict(),
            "temperature_state": temperature_state_from_region(context.region_snapshot).to_dict(),
            "strange_mood_incident": strange_mood.to_dict() if strange_mood is not None else None,
        },
        "stores": [store.to_dict() for store in ensure_kernel_runtime(context).get("stores", [])],
    }


def _active_site_id(context: "CampaignContext") -> str:
    return str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or context.region_snapshot.region_id
    )


__all__ = ["build_kernel_payload", "campaign_payload", "persist_campaign_state"]
