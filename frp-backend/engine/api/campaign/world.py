"""World- and region-level projections for campaign runtime."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.worldgen import (
    WorldSeed,
    adapt_species,
    generate_world,
    initialize_simulation,
    load_adapter_pack,
    seed_civilizations,
    seed_species,
    simulate_history,
)
from engine.worldgen.models import RegionSnapshot, WorldBlueprint
from engine.worldgen.world_seed import stable_seed_from_parts

if TYPE_CHECKING:
    from .context import CampaignContext


def build_world(*, adapter_id: str, profile_id: str, seed: int) -> WorldBlueprint:
    adapter = load_adapter_pack(adapter_id)
    world = generate_world(int(WorldSeed(seed)), profile_id)
    world = seed_species(world)
    allowed_species = set(adapter.get("allowed_species") or [])
    if allowed_species:
        world.species_lineages = [
            lineage for lineage in world.species_lineages if lineage.species_id in allowed_species
        ]
        world.domestication_pools = {
            role: [species_id for species_id in species_ids if species_id in allowed_species]
            for role, species_ids in world.domestication_pools.items()
        }
    world = adapt_species(world, adapter_id)
    world = seed_civilizations(world)
    world = simulate_history(world)
    world = initialize_simulation(world)
    world.metadata["adapter_id"] = adapter_id
    return world


def derive_creation_world_seed(
    *,
    adapter_id: str,
    profile_id: str,
    seed: int,
    creation_profile: dict[str, Any] | None = None,
    creation_answers: list[dict[str, Any]] | None = None,
) -> int:
    profile = dict(creation_profile or {})
    answers = list(creation_answers or [])
    if not profile and not answers:
        return int(seed)
    answer_signature = "|".join(
        sorted(
            f"{str(item.get('question_id', '')).strip()}:{str(item.get('answer_id', '')).strip()}"
            for item in answers
            if str(item.get("question_id", "")).strip() and str(item.get("answer_id", "")).strip()
        )
    )
    settlement_bias = tuple(sorted((str(key), int(value)) for key, value in dict(profile.get("settlement_bias", {})).items()))
    faction_bias = tuple(sorted((str(key), int(value)) for key, value in dict(profile.get("faction_bias", {})).items()))
    adapter_bias = tuple(sorted((str(key), int(value)) for key, value in dict(profile.get("adapter_bias", {})).items()))
    return int(
        stable_seed_from_parts(
            int(seed),
            adapter_id,
            profile_id,
            answer_signature,
            settlement_bias,
            faction_bias,
            adapter_bias,
        )
    )


def choose_starting_settlement(
    world: WorldBlueprint,
    *,
    creation_profile: dict[str, Any] | None = None,
    creation_answers: list[dict[str, Any]] | None = None,
) -> Any:
    if not world.settlements:
        return None
    profile = dict(creation_profile or {})
    settlement_bias = {str(key): int(value) for key, value in dict(profile.get("settlement_bias", {})).items()}
    hints = dict(profile.get("world_seed_hints", {}))
    genesis = dict(profile.get("campaign_genesis", {}))
    preferred_settlement = str(hints.get("preferred_settlement", "")).strip()
    world_tags = {str(tag).strip().lower() for tag in list(genesis.get("world_tags", []))}
    answers = list(creation_answers or [])
    signature = "|".join(
        sorted(
            f"{str(item.get('question_id', '')).strip()}:{str(item.get('answer_id', '')).strip()}"
            for item in answers
            if str(item.get("question_id", "")).strip() and str(item.get("answer_id", "")).strip()
        )
    ) or str(world.seed)
    region_by_id = {str(region["id"]): region for region in world.regions}
    biome_bias = {
        "harbor": "coast",
        "coast": "coast",
        "sea": "coast",
        "ocean": "coast",
        "mountain": "mountain",
        "highland": "mountain",
        "forest": "temperate_forest",
        "wildwood": "temperate_forest",
        "marsh": "swamp",
        "swamp": "swamp",
        "frontier": "plains",
        "border": "plains",
        "desert": "desert",
    }

    def settlement_score(settlement: Any) -> float:
        region = region_by_id.get(str(settlement.region_id), {})
        score = float(settlement.population) / 1000.0
        score += float(settlement_bias.get(str(settlement.settlement_type), 0)) * 2.75
        if preferred_settlement and str(settlement.settlement_type) == preferred_settlement:
            score += 1.75
        biome_id = str(region.get("biome_id", "")).lower()
        for tag in world_tags:
            if biome_bias.get(tag, "") == biome_id:
                score += 1.15
        jitter = float(stable_seed_from_parts(signature, settlement.id) % 1000) / 10000.0
        return score + jitter

    return max(world.settlements, key=settlement_score)


def region_payload(context: "CampaignContext") -> dict[str, Any]:
    snapshot = context.region_snapshot.to_dict()
    snapshot["metadata"]["explainability"] = copy.deepcopy(
        next(
            (
                region.get("explainability", {})
                for region in context.world.regions
                if region["id"] == context.region_snapshot.region_id
            ),
            {},
        )
    )
    return snapshot


def build_world_graph(world: WorldBlueprint) -> dict[str, Any]:
    active_region_id = world.simulation_snapshot.active_region_id if world.simulation_snapshot else ""
    regions = []
    for region in world.regions:
        region_id = str(region["id"])
        runtime_state = runtime_region_state(world, region_id)
        regions.append(
            {
                "id": region_id,
                "grid_position": _region_grid_position(region),
                "biome_id": str(region["biome_id"]),
                "controller_faction_id": region.get("controller_faction_id"),
                "settlement_node_id": region.get("settlement_id"),
                "settlement_name": region.get("primary_settlement_name", ""),
                "faction_presence": copy.deepcopy(world.faction_presence.get(region_id, [])),
                "prosperity": runtime_state.get("prosperity", world.region_economy.get(region_id, {}).get("prosperity", 42)),
                "alerts": copy.deepcopy(runtime_state.get("alerts", world.region_alerts.get(region_id, []))),
            }
        )
    return {
        "active_region_id": active_region_id,
        "dimensions": copy.deepcopy(world.metadata.get("world_graph_dimensions", {})),
        "regions": regions,
        "nodes": copy.deepcopy(world.settlement_nodes),
        "edges": copy.deepcopy(world.travel_edges),
    }


def build_travel_options(world: WorldBlueprint) -> list[dict[str, Any]]:
    active_region_id = world.simulation_snapshot.active_region_id if world.simulation_snapshot else None
    active_node = next((item for item in world.settlement_nodes if item["region_id"] == active_region_id), None)
    if active_node is None:
        return []
    options: list[dict[str, Any]] = []
    for edge in world.travel_edges:
        if edge["from_settlement_id"] == active_node["id"]:
            destination_id = edge["to_settlement_id"]
            destination_region_id = edge["to_region_id"]
        elif edge["to_settlement_id"] == active_node["id"]:
            destination_id = edge["from_settlement_id"]
            destination_region_id = edge["from_region_id"]
        else:
            continue
        destination_node = next(
            (item for item in world.settlement_nodes if item["id"] == destination_id),
            None,
        )
        if destination_node is None:
            continue
        options.append(
            {
                "destination_settlement_id": destination_id,
                "destination_region_id": destination_region_id,
                "destination_name": destination_node["name"],
                "travel_hours": int(edge.get("travel_hours", 4)),
                "biome_id": destination_node.get("biome_id", ""),
            }
        )
    options.sort(key=lambda item: (item["travel_hours"], item["destination_name"]))
    return options


def build_current_region_summary(world: WorldBlueprint, region_snapshot: RegionSnapshot) -> dict[str, Any]:
    region = next(region for region in world.regions if region["id"] == region_snapshot.region_id)
    runtime_state = runtime_region_state(world, region_snapshot.region_id)
    settlement_node = next(
        (item for item in world.settlement_nodes if item["region_id"] == region_snapshot.region_id),
        None,
    )
    return {
        "region_id": region_snapshot.region_id,
        "biome_id": region_snapshot.biome_id,
        "grid_position": _region_grid_position(region),
        "settlement_node_id": settlement_node["id"] if settlement_node is not None else None,
        "settlement_name": settlement_node["name"] if settlement_node is not None else "",
        "controller_faction_id": region.get("controller_faction_id"),
        "weather": copy.deepcopy(runtime_state.get("weather", {})),
        "alerts": copy.deepcopy(runtime_state.get("alerts", [])),
        "faction_presence": copy.deepcopy(world.faction_presence.get(region_snapshot.region_id, [])),
    }


def map_payload_from_region(region_snapshot: RegionSnapshot) -> dict[str, Any]:
    tiles: list[list[str]] = []
    for row in region_snapshot.typed_tiles:
        tiles.append([str(tile.get("terrain", "grass")) for tile in row])
    return {
        "width": region_snapshot.width,
        "height": region_snapshot.height,
        "spawn_point": list(choose_spawn_point(region_snapshot)),
        "tiles": tiles,
        "metadata": {
            "map_type": "campaign_region",
            "region_id": region_snapshot.region_id,
            "biome_id": region_snapshot.biome_id,
        },
    }


def alerts_from_events(events: list[dict[str, Any]]) -> list[str]:
    alerts = []
    for event in events:
        if str(event.get("severity", "warning")).lower() == "info":
            continue
        event_type = str(event.get("event_type", "event"))
        region_id = str(event.get("region_id", "unknown"))
        alerts.append(f"{event_type.replace('_', ' ').title()} in {region_id}")
    return alerts[:4]


def runtime_region_state(world: WorldBlueprint, region_id: str) -> dict[str, Any]:
    if world.simulation_snapshot is None:
        return {}
    return dict(world.simulation_snapshot.region_states.get(region_id, {}))


def choose_spawn_point(region_snapshot: RegionSnapshot) -> tuple[int, int]:
    cx = int(region_snapshot.layout.center_feature["x"])
    cy = int(region_snapshot.layout.center_feature["y"]) + 2
    if 0 <= cy < region_snapshot.height and region_snapshot.typed_tiles[cy][cx]["passable"]:
        return (cx, cy)
    for x, y in region_snapshot.layout.road_tiles:
        tile = region_snapshot.typed_tiles[y][x]
        if tile["passable"]:
            return (int(x), int(y))
    return (1, 1)


def _region_grid_position(region: dict[str, Any]) -> list[int]:
    return [
        int(region["x"]) // max(1, int(region["width"])),
        int(region["y"]) // max(1, int(region["height"])),
    ]


__all__ = [
    "alerts_from_events",
    "build_current_region_summary",
    "build_travel_options",
    "build_world",
    "build_world_graph",
    "choose_spawn_point",
    "map_payload_from_region",
    "region_payload",
    "runtime_region_state",
]
