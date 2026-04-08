"""Campaign payload builders and persistence helpers."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.api.campaign_kernel import (
    build_canonical_actor_records,
    build_canonical_game_state,
    build_canonical_world_state,
)
from engine.kernel.creation import ABILITY_ORDER
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
from engine.map import TileType

from engine.api.combat_bridge import build_combat_payload

from .region_projection import build_world_entities, sync_combat_projection
from .settlement import build_character_sheet, current_player_turn_resources
from .live_kernel import (
    build_actor_spell_payload,
    build_runtime_crime_payload,
    build_runtime_knowledge_payload,
    build_runtime_travel_payload,
    ensure_kernel_runtime,
    serialize_kernel_runtime,
)
from .party_bridge import party_member_ids
from .quest_bridge import current_quest_offers
from .world import (
    build_current_region_summary,
    build_fog_payload,
    build_travel_options,
    build_world_graph,
    map_payload_from_region,
    region_payload,
    runtime_region_state,
)

if TYPE_CHECKING:
    from .context import CampaignContext


_ADVISOR_TRANSIENT_KEYS = (
    "advisor",
    "advisor_view",
)
_CRIME_DUPLICATE_KEYS = (
    "crime_state",
)


def _strip_advisor_keys(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    for key in _ADVISOR_TRANSIENT_KEYS:
        payload.pop(key, None)


def _strip_crime_duplicate_keys(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    for key in _CRIME_DUPLICATE_KEYS:
        payload.pop(key, None)


def _sanitize_persisted_actor_payloads(actors: Any) -> None:
    if not isinstance(actors, list):
        return
    for actor in actors:
        if not isinstance(actor, dict):
            continue
        _strip_advisor_keys(actor.get("raw_payload"))
        _strip_crime_duplicate_keys(actor.get("raw_payload"))


def _sanitize_campaign_snapshot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _strip_advisor_keys(payload)
    game_state = payload.get("game_state")
    if isinstance(game_state, dict):
        _strip_advisor_keys(game_state.get("raw_payload"))
    _sanitize_persisted_actor_payloads(payload.get("actors"))
    return payload


def campaign_payload(context: "CampaignContext") -> dict[str, Any]:
    ensure_kernel_runtime(context)
    sync_combat_projection(context)
    if hasattr(context, "_knowledge_topic_cache"):
        delattr(context, "_knowledge_topic_cache")
    context_data = context.to_dict()
    _strip_advisor_keys(context_data)
    runtime_state = runtime_region_state(context.world, context.region_snapshot.region_id)
    combat_state = _enrich_combat_payload(context, build_combat_payload(context))
    kernel_payload = _sanitize_campaign_snapshot_payload(build_kernel_payload(context))
    crime_payload = build_runtime_crime_payload(context, context.kernel_runtime or {})
    knowledge_payload = build_campaign_knowledge_payload(context)
    travel_payload = build_runtime_travel_payload(context.kernel_runtime or {})
    fog_payload = build_fog_payload(context)
    normalized_party = party_member_ids(context)
    context.campaign_state["party"] = list(normalized_party)
    payload_scene = str(context_data.get("scene", "exploration"))
    if isinstance(travel_payload, dict) and str(travel_payload.get("status", "")).lower() not in {"", "idle", "arrived", "completed", "resolved", "cancelled"}:
        payload_scene = "travel"
    if isinstance(combat_state, dict) and combat_state and combat_state.get("phase") != "resolved":
        payload_scene = "combat"
    player_payload = copy.deepcopy(context_data["player"])
    # Ensure top-level name/hp fields for frontend contract.
    if context.player:
        player_payload.setdefault("name", context.player.name)
        player_payload.setdefault("hp", int(context.player.stats.get("hp", 0)))
        player_payload.setdefault("max_hp", int(context.player.stats.get("max_hp", 0)))
        player_payload.setdefault("alignment", context.player.alignment)
        stats = player_payload.get("stats")
        if isinstance(stats, dict):
            normalized_stats = {
                ability: stats[ability]
                for ability in ABILITY_ORDER
                if ability in stats
            }
            if normalized_stats:
                player_payload["stats"] = normalized_stats
    player_payload["turn_resources"] = current_player_turn_resources(context)
    player_payload["spellcasting"] = build_actor_spell_payload(context.player)
    return _sanitize_campaign_snapshot_payload({
        "world": {
            "seed": context.world.seed,
            "profile_id": context.world.profile_id,
            "adapter_id": context.adapter_id,
            "active_region_id": _payload_active_region_id(kernel_payload, context),
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
        "travel_options": build_travel_options(context.world, context=context),
        "travel_state": travel_payload,
        "current_region_summary": build_current_region_summary(context.world, context.region_snapshot),
        "player": player_payload,
        "scene": payload_scene,
        "location": context_data["location"],
        "combat": combat_state,
        "crime_state": crime_payload,
        "knowledge": knowledge_payload,
        "conversation_state": context_data.get("conversation_state", {}),
        "region": region_payload(context),
        "map_data": map_payload_from_region(context.region_snapshot),
        "fog": fog_payload,
        "world_entities": build_world_entities(context.world, context.region_snapshot, context.adapter_id, context=context),
        "ground_items": copy.deepcopy(context_data.get("ground_items", [])),
        "active_quests": copy.deepcopy(context_data.get("active_quests", [])),
        "completed_quest_ids": list(context.campaign_state.get("completed_quest_ids", [])),
        "failed_quest_ids": list(context.campaign_state.get("failed_quest_ids", [])),
        "quest_offers": copy.deepcopy(current_quest_offers(context)),
        "party": normalized_party,
        "settlement": copy.deepcopy(context.settlement_state),
        "character_sheet": build_character_sheet(context, context.settlement_state),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-12:]),
    })


def persist_campaign_state(context: "CampaignContext") -> None:
    ensure_kernel_runtime(context)
    sync_combat_projection(context)
    _strip_advisor_keys(context.campaign_state)
    _strip_crime_duplicate_keys(context.campaign_state)
    kernel_payload = _sanitize_campaign_snapshot_payload(build_kernel_payload(context))
    fog_payload = build_fog_payload(context)
    context.campaign_state["party"] = party_member_ids(context)
    context.campaign_state["fog"] = copy.deepcopy(fog_payload)
    context.campaign_state["campaign"] = {
        "campaign_id": context.campaign_id,
        "adapter_id": context.adapter_id,
        "profile_id": context.profile_id,
        "seed": context.seed,
        "active_region_id": _payload_active_region_id(kernel_payload, context),
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
        "fog": copy.deepcopy(fog_payload),
        "fog_by_region": copy.deepcopy(context.campaign_state.get("fog_by_region", {})),
        "recent_event_log": copy.deepcopy(context.recent_event_log[-20:]),
    }
    _sanitize_campaign_snapshot_payload(context.campaign_state["campaign"])
    _strip_crime_duplicate_keys(context.campaign_state["campaign"])
    context.campaign_state.pop("campaign_v2", None)


def build_campaign_knowledge_payload(context: "CampaignContext") -> dict[str, Any]:
    return build_runtime_knowledge_payload(context, context.kernel_runtime or {})


def build_kernel_payload(context: "CampaignContext") -> dict[str, Any]:
    sync_combat_projection(context)
    if context.kernel_runtime:
        return serialize_kernel_runtime(context)
    active_site_id = _active_site_id(context)
    canonical_world_state = build_canonical_world_state(context.world)
    canonical_actor_records = build_canonical_actor_records(
        context,
        active_region_id=context.region_snapshot.region_id,
        active_site_id=active_site_id,
    )
    canonical_game_state = build_canonical_game_state(
        context,
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
        "active_store_id": str(ensure_kernel_runtime(context).get("active_store_id", "") or ""),
        "stores": [store.to_dict() for store in ensure_kernel_runtime(context).get("stores", [])],
    }


def _enrich_combat_payload(context: "CampaignContext", combat_state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(combat_state, dict) or not combat_state.get("combatants"):
        return combat_state
    enriched = copy.deepcopy(combat_state)
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors") or {}
    combatants = [entry for entry in enriched.get("combatants", []) if isinstance(entry, dict)]
    by_actor_id = {str(entry.get("actor_id", "")): entry for entry in combatants if str(entry.get("actor_id", "")).strip()}
    for entry in combatants:
        actor_id = str(entry.get("actor_id", "")).strip()
        actor = actors.get(actor_id)
        if actor is None:
            continue
        record = context.entities.get(actor_id) if isinstance(getattr(context, "entities", None), dict) else None
        position = getattr(actor, "position", None)
        if position is not None:
            entry["position"] = [int(getattr(position, "x", 0)), int(getattr(position, "y", 0))]
            entry["projected_position"] = list(entry["position"])
        if isinstance(record, dict):
            blocking = record.get("blocking")
            if blocking is None:
                entity_ref = record.get("entity_ref")
                blocking = getattr(entity_ref, "blocking", None)
            if blocking is not None:
                entry["blocking"] = bool(blocking)
        turn_resources = entry.get("turn_resources")
        if not isinstance(turn_resources, dict):
            entry["turn_resources"] = {}
        target = by_actor_id.get(actor_id)
        if target is not None and actor_id == enriched.get("turn_actor_id"):
            target["position"] = entry.get("position", target.get("position"))
    for target in [item for item in enriched.get("targets", []) if isinstance(item, dict)]:
        actor_id = str(target.get("actor_id", "")).strip()
        actor = actors.get(actor_id)
        if actor is None:
            continue
        position = getattr(actor, "position", None)
        if position is not None:
            target["position"] = [int(getattr(position, "x", 0)), int(getattr(position, "y", 0))]
        zones = _called_shot_zones(actor)
        if zones:
            target["called_shot_zones"] = zones
    active_actor = actors.get(str(enriched.get("turn_actor_id", "")).strip())
    if active_actor is not None:
        enriched["move_options"] = _combat_move_options(context, active_actor)
    return enriched


def _combat_move_options(context: "CampaignContext", actor: Any) -> list[dict[str, Any]]:
    spatial_index = getattr(context, "spatial_index", None)
    map_data = getattr(context, "map_data", None)
    if actor is None or spatial_index is None:
        return []
    position = getattr(actor, "position", None)
    if position is None:
        return []
    current_x = int(getattr(position, "x", 0))
    current_y = int(getattr(position, "y", 0))
    directions = {
        "north": (0, -1),
        "south": (0, 1),
        "west": (-1, 0),
        "east": (1, 0),
    }
    options: list[dict[str, Any]] = []
    for direction, (dx, dy) in directions.items():
        x = current_x + dx
        y = current_y + dy
        available = True
        blocked_reason: str | None = None
        if map_data is not None:
            width = int(getattr(map_data, "width", 0))
            height = int(getattr(map_data, "height", 0))
            if x < 0 or y < 0 or x >= width or y >= height:
                available = False
                blocked_reason = "out_of_bounds"
            else:
                tile = map_data.tiles[y][x]
                if tile in {TileType.WALL, TileType.WATER, TileType.TREE}:
                    available = False
                    blocked_reason = "blocked_terrain"
        if available and spatial_index.blocking_at(x, y):
            available = False
            blocked_reason = "occupied"
        options.append(
            {
                "direction": direction,
                "x": x,
                "y": y,
                "position": [x, y],
                "available": available,
                "blocked_reason": blocked_reason,
            }
        )
    return options


def _called_shot_zones(actor: Any) -> list[str]:
    body_state = getattr(actor, "body_state", None)
    if body_state is None:
        return []
    parts = getattr(body_state, "parts", {}) or {}
    if not isinstance(parts, dict):
        return []
    return [str(part_id) for part_id in sorted(parts) if str(part_id).strip()]


def _active_site_id(context: "CampaignContext") -> str:
    return str(
        context.settlement_state.get("settlement_id")
        or context.region_snapshot.metadata.get("settlement_id")
        or context.region_snapshot.region_id
    )


def _payload_active_region_id(kernel_payload: dict[str, Any], context: "CampaignContext") -> str:
    path_authority = dict(kernel_payload.get("path_authority", {}))
    return str(path_authority.get("active_region_id") or context.region_snapshot.region_id)


__all__ = ["build_kernel_payload", "campaign_payload", "persist_campaign_state"]
