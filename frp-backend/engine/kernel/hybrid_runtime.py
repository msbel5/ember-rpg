from __future__ import annotations

import random

from engine.kernel.actor import ActorRecord
from engine.kernel.colony import ColonyPressureState, pressure_tags_from_metrics, quest_seeds_from_shortages
from engine.kernel.hybrid_types import (
    LocalActionResolution,
    LocalMapState,
    MacroStateView,
    MilitaryState,
    PathAuthorityState,
    SquadMemberRecord,
    SquadRecord,
    TravelState,
)
from engine.kernel.world_state import FactionRecord, RegionRecord, TravelEdge, WorldState
from engine.worldgen.models import RegionSnapshot, WorldBlueprint


_DEFENSE_ALERT_LEVELS = {
    "normal": 0,
    "concern": 1,
    "alert": 2,
    "fortified": 3,
}


def macro_state_from_world(world_state: WorldState, region_id: str | None = None) -> MacroStateView:
    resolved_region_id = str(region_id or world_state.active_region_id or "")
    region = world_state.regions.get(resolved_region_id)
    if region is None:
        raise ValueError(f"Unknown region '{resolved_region_id}'.")
    faction_ids = list(dict.fromkeys(region.faction_ids + ([region.controller_faction_id] if region.controller_faction_id else [])))
    factions = [
        world_state.factions[faction_id]
        for faction_id in faction_ids
        if faction_id in world_state.factions
    ]
    return MacroStateView(
        active_region_id=resolved_region_id,
        region=region,
        factions=factions,
        travel_options=travel_options_for_region(world_state, resolved_region_id),
    )


def travel_options_for_region(world_state: WorldState, region_id: str) -> list[TravelEdge]:
    return [
        edge
        for edge in world_state.travel_edges
        if edge.source_region_id == region_id or edge.destination_region_id == region_id
    ]


def initiate_travel(world_state: WorldState, origin_id: str, destination_id: str, seed: int) -> TravelState:
    del seed
    edge = _find_travel_edge(world_state, origin_id, destination_id)
    if edge is None:
        raise ValueError(f"No travel edge connects '{origin_id}' to '{destination_id}'.")
    return TravelState(
        status="preparing",
        origin_region_id=origin_id,
        destination_region_id=destination_id,
        travel_hours_remaining=max(0, int(edge.travel_hours)),
        travel_hours_total=max(0, int(edge.travel_hours)),
        edge_id=edge.edge_id,
        danger_level=_edge_danger_level(edge),
    )


def tick_travel(travel: TravelState, seed: int) -> TravelState:
    updated = TravelState.from_dict(travel.to_dict())
    if updated.status in {"idle", "arrived"}:
        return updated
    if updated.status == "preparing":
        updated.status = "traveling"
        return updated
    if updated.status == "arriving":
        updated.status = "arrived"
        return updated
    if updated.status != "traveling":
        return updated
    if updated.paused_for_encounter and not updated.encounter_resolved:
        return updated
    if not updated.encounter_checked:
        updated.encounter_roll = random.Random(int(seed)).random()
        updated.encounter_checked = True
        encounter_chance = min(0.95, max(0, int(updated.danger_level)) * 0.15)
        if updated.encounter_roll < encounter_chance:
            updated.encounter_triggered = True
            updated.paused_for_encounter = True
            return updated
    updated.travel_hours_remaining = max(0, updated.travel_hours_remaining - 1)
    if updated.travel_hours_remaining == 0:
        updated.status = "arriving"
    return updated


def complete_travel(travel: TravelState, world_state: WorldState) -> PathAuthorityState:
    if travel.status not in {"arriving", "arrived"}:
        raise ValueError("Travel must be arriving or arrived before completion.")
    destination_id = str(travel.destination_region_id)
    world_state.active_region_id = destination_id
    site_id = _site_id_for_region(world_state, destination_id)
    region = world_state.regions.get(destination_id)
    spawn_point = _region_spawn_point(region)
    return PathAuthorityState(
        active_region_id=destination_id,
        active_site_id=site_id,
        local_map_id=f"region::{destination_id}",
        hydrated_from_region=region is not None,
        travel_edge_count=len(travel_options_for_region(world_state, destination_id)),
        reindex_required=False,
        local_map_loaded=region is not None,
        spawn_point=spawn_point,
    )


def hydrate_local_map(world_state: WorldState, region_id: str) -> LocalMapState:
    region = world_state.regions.get(region_id)
    if region is None:
        return LocalMapState(region_id=region_id, site_id="", width=0, height=0, spawn_point=[10, 7], terrain_tags=[], biome_id="unknown")
    return LocalMapState(
        region_id=region.region_id,
        site_id=_site_id_for_region(world_state, region.region_id),
        width=max(0, int(region.width)),
        height=max(0, int(region.height)),
        spawn_point=_region_spawn_point(region),
        terrain_tags=[str(tag) for tag in region.metadata.get("terrain_tags", [])][:12],
        biome_id=region.biome_id,
    )


def advance_local_action(
    actor: ActorRecord,
    colony_pressure: ColonyPressureState,
    *,
    action_id: str,
    ap_cost: int = 1,
    hours: int = 1,
    military: MilitaryState | None = None,
) -> LocalActionResolution:
    if ap_cost < 0:
        raise ValueError("Action point cost cannot be negative.")
    if actor.action_points < ap_cost:
        raise ValueError("Actor does not have enough action points.")
    actor.action_points -= ap_cost
    actor.raw_payload["last_local_action"] = str(action_id)
    actor.raw_payload["world_hours_elapsed"] = int(actor.raw_payload.get("world_hours_elapsed", 0)) + max(0, int(hours))
    updated_pressure = _advance_colony_pressure(colony_pressure, hours=max(0, int(hours)))
    if military is not None:
        updated_pressure = apply_squad_orders(military, updated_pressure)
    return LocalActionResolution(
        actor_id=actor.identity.actor_id,
        action_id=str(action_id),
        hours_advanced=max(0, int(hours)),
        remaining_action_points=actor.action_points,
        colony_pressure=updated_pressure,
    )


def path_authority_from_world(world: WorldBlueprint, region_snapshot: RegionSnapshot) -> PathAuthorityState:
    active_region_id = str(world.simulation_snapshot.active_region_id if world.simulation_snapshot else region_snapshot.region_id)
    active_site_id = str(next((node["id"] for node in world.settlement_nodes if str(node.get("region_id")) == region_snapshot.region_id), region_snapshot.region_id))
    return PathAuthorityState(
        active_region_id=active_region_id,
        active_site_id=active_site_id,
        local_map_id=f"region::{region_snapshot.region_id}",
        hydrated_from_region=True,
        travel_edge_count=sum(1 for edge in world.travel_edges if edge.get("from_region_id") == region_snapshot.region_id or edge.get("to_region_id") == region_snapshot.region_id),
        reindex_required=False,
        local_map_loaded=True,
        spawn_point=[int(region_snapshot.layout.center_feature["x"]), int(region_snapshot.layout.center_feature["y"])],
    )


def local_map_state_from_region(region_snapshot: RegionSnapshot) -> LocalMapState:
    terrain_tags = sorted({str(tile.get("terrain", "unknown")) for row in region_snapshot.typed_tiles for tile in row})
    active_site_id = str(region_snapshot.metadata.get("settlement_id", region_snapshot.region_id) or region_snapshot.region_id)
    return LocalMapState(
        region_id=region_snapshot.region_id,
        site_id=active_site_id,
        width=region_snapshot.width,
        height=region_snapshot.height,
        spawn_point=[int(region_snapshot.layout.center_feature["x"]), int(region_snapshot.layout.center_feature["y"])],
        terrain_tags=terrain_tags[:12],
        biome_id=str(region_snapshot.metadata.get("biome_id", "unknown")),
    )


def military_state_from_settlement(settlement_state: dict[str, object]) -> MilitaryState:
    defense_posture = str(settlement_state.get("defense_posture", "normal"))
    alert_level = _DEFENSE_ALERT_LEVELS.get(defense_posture, 0)
    residents = list(settlement_state.get("residents", []))
    members: list[SquadMemberRecord] = []
    for resident in residents:
        role = str(resident.get("role", "soldier"))
        drafted = bool(resident.get("drafted"))
        if drafted or role in {"commander", "guard", "warden", "medic", "scout"}:
            members.append(
                SquadMemberRecord(
                    actor_id=str(resident.get("id", "")),
                    label=str(resident.get("name", resident.get("id", "Resident"))),
                    duty=str(resident.get("assignment", "garrison")),
                    drafted=drafted,
                    role=role,
                    equipment_policy=str(resident.get("equipment_policy", "default")),
                )
            )
    if not members:
        return MilitaryState(squads=[], defense_posture=defense_posture, alert_level=alert_level)
    squad = SquadRecord(
        squad_id="settlement_watch",
        label="Settlement Watch",
        posture=_squad_posture_for_defense(defense_posture),
        members=members,
        orders=_orders_for_posture(defense_posture),
        equipment_policy={
            "weapon": "best_available" if defense_posture in {"alert", "fortified"} else "standard_issue",
            "armor": "best_available" if defense_posture == "fortified" else "standard_issue",
        },
    )
    return MilitaryState(squads=[squad], defense_posture=defense_posture, alert_level=alert_level)


def apply_squad_orders(military: MilitaryState, colony_pressure: ColonyPressureState) -> ColonyPressureState:
    updated = ColonyPressureState.from_dict(colony_pressure.to_dict())
    guard_count = 0
    patrol_count = 0
    for squad in military.squads:
        active_members = [member for member in squad.members if member.role != "commander"]
        if "guard_gate" in squad.orders:
            guard_count += len(active_members)
        if any(order.startswith("patrol") for order in squad.orders):
            patrol_count += len(active_members)
    updated.safety = min(100, updated.safety + guard_count * 5)
    updated.unrest = max(0, updated.unrest - patrol_count * 2)
    updated.pressure_tags = pressure_tags_from_metrics(
        food=updated.food,
        safety=updated.safety,
        morale=updated.morale,
        supply=updated.supply,
        housing=updated.housing,
        unrest=updated.unrest,
    )
    return updated


def _advance_colony_pressure(colony_pressure: ColonyPressureState, *, hours: int) -> ColonyPressureState:
    updated = ColonyPressureState.from_dict(colony_pressure.to_dict())
    if hours <= 0:
        return updated
    updated.food = max(0, updated.food - hours)
    safety_penalty = hours if updated.unrest >= 25 else 0
    updated.safety = max(0, updated.safety - safety_penalty)
    morale_penalty = hours
    if updated.food < 50:
        morale_penalty += 1
    if updated.safety < 50:
        morale_penalty += 1
    updated.morale = max(0, updated.morale - morale_penalty)
    updated.supply = max(0, updated.supply - max(1, hours // 2))
    if updated.food < 55 and "food" not in updated.shortages:
        updated.shortages.append("food")
    if updated.safety < 55 and "security" not in updated.shortages:
        updated.shortages.append("security")
    if updated.supply < 55 and "materials" not in updated.shortages:
        updated.shortages.append("materials")
    updated.shortages = list(dict.fromkeys(updated.shortages))
    updated.quest_seeds = quest_seeds_from_shortages(updated.shortages)
    updated.pressure_tags = pressure_tags_from_metrics(
        food=updated.food,
        safety=updated.safety,
        morale=updated.morale,
        supply=updated.supply,
        housing=updated.housing,
        unrest=updated.unrest,
    )
    return updated


def _orders_for_posture(defense_posture: str) -> list[str]:
    if defense_posture == "fortified":
        return ["guard_gate", "patrol_market"]
    if defense_posture == "alert":
        return ["guard_gate", "escort_caravan"]
    return ["reserve", "escort"]


def _squad_posture_for_defense(defense_posture: str) -> str:
    if defense_posture == "fortified":
        return "defensive"
    if defense_posture == "alert":
        return "patrol"
    return "escort"


def _site_id_for_region(world_state: WorldState, region_id: str) -> str:
    region = world_state.regions.get(region_id)
    if region is not None and region.site_ids:
        return str(region.site_ids[0])
    for site in world_state.sites.values():
        if site.region_id == region_id:
            return site.site_id
    return region_id


def _find_travel_edge(world_state: WorldState, origin_id: str, destination_id: str) -> TravelEdge | None:
    for edge in world_state.travel_edges:
        matches_forward = edge.source_region_id == origin_id and edge.destination_region_id == destination_id
        matches_reverse = edge.source_region_id == destination_id and edge.destination_region_id == origin_id
        if matches_forward or matches_reverse:
            return edge
    return None


def _edge_danger_level(edge: TravelEdge) -> int:
    return max(0, int(getattr(edge, "danger_level", 0)))


def _region_spawn_point(region: RegionRecord | None) -> list[int]:
    if region is None:
        return [10, 7]
    raw = region.metadata.get("spawn_point")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return [int(raw[0]), int(raw[1])]
    width = max(1, int(region.width or 1))
    height = max(1, int(region.height or 1))
    return [width // 2, height // 2]


__all__ = [
    "advance_local_action",
    "apply_squad_orders",
    "complete_travel",
    "hydrate_local_map",
    "initiate_travel",
    "local_map_state_from_region",
    "macro_state_from_world",
    "military_state_from_settlement",
    "path_authority_from_world",
    "tick_travel",
    "travel_options_for_region",
]
