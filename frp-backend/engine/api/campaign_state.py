"""Compatibility facade for campaign state helpers."""
from engine.api.campaign.persistence import campaign_payload, persist_campaign_state
from engine.api.campaign.region_projection import apply_region_to_context, build_map_data, build_world_entities, seed_region_entities
from engine.api.campaign.settlement import build_character_sheet, build_settlement_state
from engine.api.campaign.world import (
    alerts_from_events,
    build_current_region_summary,
    build_travel_options,
    build_world,
    build_world_graph,
    choose_spawn_point,
    map_payload_from_region,
    region_payload,
)

__all__ = [
    "alerts_from_events",
    "apply_region_to_context",
    "build_character_sheet",
    "build_current_region_summary",
    "build_map_data",
    "build_settlement_state",
    "build_travel_options",
    "build_world",
    "build_world_entities",
    "build_world_graph",
    "campaign_payload",
    "choose_spawn_point",
    "map_payload_from_region",
    "persist_campaign_state",
    "region_payload",
    "seed_region_entities",
]
