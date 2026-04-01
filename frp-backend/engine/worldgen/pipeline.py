"""Deterministic world simulation pipeline for Ember RPG."""

from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any, Iterable, Optional

from .models import (
    FactionSeed,
    GlobalTickResult,
    HistoricalEvent,
    RegionSnapshot,
    SettlementLayout,
    SettlementSeed,
    SimulationSnapshot,
    SpeciesLineage,
    TectonicPlate,
    WorldBlueprint,
    WorldProfile,
)
from .settlement_generator import generate_settlement_layout as generate_settlement_layout_v2
from .terrain_generator import generate_world_blueprint
from .world_seed import WorldSeed, stable_seed_from_parts
from .world_tick import initialize_simulation as initialize_simulation_v2
from .world_tick import tick_global as tick_global_v2
from .registries import (
    load_adapter_pack,
    load_building_templates,
    load_culture_templates,
    load_furniture_templates,
    load_species_templates,
    load_world_biomes,
    load_world_profiles,
    validate_world_registries,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_grid(grid: list[list[float]], digits: int = 3) -> list[list[float]]:
    return [[round(value, digits) for value in row] for row in grid]


def _noise(seed: int, x: int, y: int) -> float:
    value = math.sin((seed + 1) * 12.9898 + x * 78.233 + y * 37.719) * 43758.5453
    return value - math.floor(value)


def _region_lookup(world: WorldBlueprint, region_id: str) -> dict[str, Any]:
    for region in world.regions:
        if region["id"] == region_id:
            return region
    raise ValueError(f"Unknown region_id: {region_id}")


def _plate_seed_points(seed: int, profile: WorldProfile) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [
        (rng.randrange(profile.world_width), rng.randrange(profile.world_height))
        for _ in range(profile.plate_count)
    ]


def _nearest_seed_index(seeds: list[tuple[int, int]], x: int, y: int) -> int:
    best_index = 0
    best_distance = None
    for index, (sx, sy) in enumerate(seeds):
        distance = (sx - x) ** 2 + (sy - y) ** 2
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def _build_tectonic_plates(seed: int, profile: WorldProfile) -> tuple[list[TectonicPlate], list[list[int]]]:
    rng = random.Random(seed)
    seeds = _plate_seed_points(seed, profile)
    plate_cells: list[list[tuple[int, int]]] = [[] for _ in range(profile.plate_count)]
    plate_map: list[list[int]] = []
    for y in range(profile.world_height):
        row = []
        for x in range(profile.world_width):
            plate_index = _nearest_seed_index(seeds, x, y)
            row.append(plate_index)
            plate_cells[plate_index].append((x, y))
        plate_map.append(row)

    continental_cutoff = max(1, profile.plate_count // 2)
    plates = [
        TectonicPlate(
            id=f"plate_{index}",
            cells=plate_cells[index],
            drift_x=round(rng.uniform(-1.0, 1.0), 3),
            drift_y=round(rng.uniform(-1.0, 1.0), 3),
            crust_type="continental" if index < continental_cutoff else "oceanic",
        )
        for index in range(profile.plate_count)
    ]
    return plates, plate_map


def _count_boundary_neighbors(plate_map: list[list[int]], x: int, y: int) -> int:
    height = len(plate_map)
    width = len(plate_map[0])
    current = plate_map[y][x]
    count = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height and plate_map[ny][nx] != current:
            count += 1
    return count


def _compute_elevation(
    seed: int,
    profile: WorldProfile,
    plates: list[TectonicPlate],
    plate_map: list[list[int]],
) -> list[list[float]]:
    crust_by_index = {index: plate.crust_type for index, plate in enumerate(plates)}
    elevation: list[list[float]] = []
    for y in range(profile.world_height):
        row = []
        for x in range(profile.world_width):
            plate_index = plate_map[y][x]
            crust_type = crust_by_index[plate_index]
            boundary_neighbors = _count_boundary_neighbors(plate_map, x, y)
            base = 0.55 if crust_type == "continental" else 0.16
            boundary_boost = boundary_neighbors * (0.09 if crust_type == "continental" else 0.03)
            ruggedness = (_noise(seed, x, y) - 0.5) * 0.18
            latitude_shaping = abs((y / max(1, profile.world_height - 1)) - 0.5) * 0.05
            row.append(_clamp(base + boundary_boost + ruggedness - latitude_shaping))
        elevation.append(row)
    return _round_grid(elevation)


def _compute_temperature(profile: WorldProfile, elevation: list[list[float]]) -> list[list[float]]:
    height = len(elevation)
    temperature: list[list[float]] = []
    for y in range(height):
        latitude_heat = 1.0 - abs((y / max(1, height - 1)) * 2 - 1)
        row = []
        for x in range(len(elevation[0])):
            row.append(_clamp(latitude_heat * 0.95 - elevation[y][x] * 0.28 + 0.05))
        temperature.append(row)
    return _round_grid(temperature)


def _compute_moisture(elevation: list[list[float]], temperature: list[list[float]]) -> list[list[float]]:
    height = len(elevation)
    width = len(elevation[0])
    water_cells = [(x, y) for y in range(height) for x in range(width) if elevation[y][x] < 0.28]
    if not water_cells:
        water_cells = [(0, y) for y in range(height)]

    moisture: list[list[float]] = []
    max_distance = width + height
    for y in range(height):
        row = []
        for x in range(width):
            nearest_water = min(abs(wx - x) + abs(wy - y) for wx, wy in water_cells)
            water_bonus = 1.0 - (nearest_water / max_distance)
            rain_shadow = 0.0
            for west in range(max(0, x - 4), x):
                if elevation[y][west] > 0.72:
                    rain_shadow += 0.06
            row.append(_clamp(0.18 + water_bonus * 0.8 - rain_shadow - temperature[y][x] * 0.05))
        moisture.append(row)
    return _round_grid(moisture)


def _lowest_neighbor(
    elevation: list[list[float]], x: int, y: int, visited: set[tuple[int, int]]
) -> Optional[tuple[int, int]]:
    height = len(elevation)
    width = len(elevation[0])
    candidates: list[tuple[float, tuple[int, int]]] = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
            candidates.append((elevation[ny][nx], (nx, ny)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _compute_drainage_and_rivers(
    seed: int, elevation: list[list[float]], moisture: list[list[float]]
) -> tuple[list[list[float]], list[dict[str, Any]]]:
    height = len(elevation)
    width = len(elevation[0])
    drainage = [
        [_clamp(0.25 + moisture[y][x] * 0.85 - elevation[y][x] * 0.15) for x in range(width)]
        for y in range(height)
    ]

    candidates = []
    for y in range(height):
        for x in range(width):
            if elevation[y][x] > 0.58 and moisture[y][x] > 0.52:
                candidates.append((elevation[y][x] + moisture[y][x] + _noise(seed + 77, x, y) * 0.1, x, y))
    candidates.sort(reverse=True)

    river_paths: list[dict[str, Any]] = []
    used_sources: set[tuple[int, int]] = set()
    for _, x, y in candidates:
        if len(river_paths) >= 3 or (x, y) in used_sources:
            break
        visited: set[tuple[int, int]] = set()
        path: list[tuple[int, int]] = []
        current = (x, y)
        for _ in range(32):
            cx, cy = current
            if current in visited:
                break
            visited.add(current)
            path.append(current)
            drainage[cy][cx] = 1.0
            if elevation[cy][cx] < 0.3:
                break
            neighbor = _lowest_neighbor(elevation, cx, cy, visited)
            if neighbor is None:
                break
            current = neighbor
        if len(path) >= 4:
            used_sources.add((x, y))
            river_paths.append({"source": [x, y], "path": [list(node) for node in path]})
    return _round_grid(drainage), river_paths


def _classify_biome(elevation: float, temperature: float, moisture: float, drainage: float) -> str:
    if elevation < 0.3:
        return "coast"
    if elevation >= 0.68:
        return "mountain"
    if temperature >= 0.65 and moisture <= 0.22:
        return "desert"
    if moisture >= 0.78 and drainage >= 0.75 and elevation <= 0.5:
        return "swamp"
    if moisture >= 0.58:
        return "temperate_forest"
    return "plains"


def _majority(values: Iterable[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _terrain_driver(avg_elevation: float, boundary_hits: int, river_present: bool) -> str:
    if avg_elevation >= 0.68:
        return "plate_boundary_mountains"
    if river_present and avg_elevation <= 0.45:
        return "river_basin"
    if boundary_hits > 0:
        return "tectonic_uplift"
    return "coastal_lowlands" if avg_elevation < 0.35 else "upland_continent"


def _climate_driver(avg_temperature: float, avg_moisture: float, water_access: str) -> str:
    if water_access == "coast":
        return "marine_influence"
    if avg_moisture >= 0.7:
        return "humid_belt"
    if avg_temperature >= 0.65 and avg_moisture <= 0.25:
        return "dry_interior"
    return "temperate_band"


def generate_world(seed: int, profile_id: str) -> WorldBlueprint:
    """Generate the deterministic macro world for a profile."""
    validate_world_registries()
    profiles = load_world_profiles()
    if profile_id not in profiles:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    profile = WorldProfile.from_dict(profiles[profile_id])
    canonical_seed = int(WorldSeed(seed))
    return generate_world_blueprint(canonical_seed, profile, load_world_biomes())


def seed_species(world: WorldBlueprint) -> WorldBlueprint:
    """Seed species lineages and domestication pools into the world."""
    species_registry = load_species_templates()
    lineages: list[SpeciesLineage] = []
    domestication_pools: dict[str, list[str]] = {}
    for species_id in sorted(species_registry.keys()):
        template = species_registry[species_id]
        scored_regions: list[tuple[float, str]] = []
        for region in world.regions:
            score = 0.0
            if region["biome_id"] in template["habitats"]:
                score += 0.6
            temp_min, temp_max = template["temperature_range"]
            moist_min, moist_max = template["moisture_range"]
            if temp_min <= region["avg_temperature"] <= temp_max:
                score += 0.2
            if moist_min <= region["avg_moisture"] <= moist_max:
                score += 0.2
            if score > 0.0:
                scored_regions.append((round(score, 3), region["id"]))
        scored_regions.sort(key=lambda item: (-item[0], item[1]))
        if not scored_regions and template["sapient"]:
            fallback = sorted(
                world.regions,
                key=lambda region: (
                    abs(region["avg_temperature"] - sum(template["temperature_range"]) / 2),
                    abs(region["avg_moisture"] - sum(template["moisture_range"]) / 2),
                ),
            )[0]
            scored_regions.append((0.1, fallback["id"]))
        if not scored_regions:
            continue
        lineages.append(
            SpeciesLineage(
                species_id=species_id,
                species_name=template["name"],
                sapient=bool(template["sapient"]),
                home_regions=[scored_regions[0][1]],
                expansion_regions=[region_id for _, region_id in scored_regions[1:3]],
                adapter_payload={},
            )
        )
        for role in template.get("domestication_roles", []):
            domestication_pools.setdefault(role, []).append(species_id)
    world.species_lineages = lineages
    world.domestication_pools = domestication_pools
    return world


def adapt_species(world: WorldBlueprint, adapter_id: str) -> WorldBlueprint:
    """Map kernel-native species lineages to adapter-facing display labels."""
    labels = load_adapter_pack(adapter_id).get("species_labels", {})
    for lineage in world.species_lineages:
        lineage.adapter_payload = {
            "adapter_id": adapter_id,
            "display_name": labels.get(lineage.species_id, lineage.species_name),
        }
    return world


def _region_grid_position(region: dict[str, Any]) -> tuple[int, int]:
    return (
        int(region["x"]) // max(1, int(region["width"])),
        int(region["y"]) // max(1, int(region["height"])),
    )


def _region_distance(left: dict[str, Any], right: dict[str, Any]) -> int:
    lx, ly = _region_grid_position(left)
    rx, ry = _region_grid_position(right)
    return abs(lx - rx) + abs(ly - ry)


def _lineage_candidate_regions(
    world: WorldBlueprint,
    lineage: SpeciesLineage,
    template: dict[str, Any],
) -> list[tuple[float, str]]:
    scored: list[tuple[float, str]] = []
    temp_mid = sum(template["temperature_range"]) / 2
    moist_mid = sum(template["moisture_range"]) / 2
    habitats = set(template.get("habitats", []))
    for region in world.regions:
        score = float(region.get("settlement_suitability", region.get("settlement_score", 0.0)))
        score += 0.32 if region["biome_id"] in habitats else -0.18
        score += max(0.0, 0.18 - abs(float(region["avg_temperature"]) - temp_mid) * 0.28)
        score += max(0.0, 0.16 - abs(float(region["avg_moisture"]) - moist_mid) * 0.22)
        if region["id"] in lineage.home_regions:
            score += 0.24
        elif region["id"] in lineage.expansion_regions:
            score += 0.12
        if region.get("river_present"):
            score += 0.06
        if region.get("water_access") == "coast":
            score += 0.05
        scored.append((round(score, 4), str(region["id"])))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored


def _settlement_type_for_species(species_id: str) -> str:
    return {
        "dwarf": "stronghold",
        "elf": "grove",
        "dragon": "eyrie",
        "synthetic": "hub",
        "auran": "wayport",
        "mycoid": "synod",
    }.get(species_id, "city")


def _focus_for_culture(culture: dict[str, Any]) -> list[str]:
    return sorted(
        culture["institution_bias"].keys(),
        key=lambda key: (-culture["institution_bias"][key], key),
    )[:3]


def _choose_region_with_spacing(
    world: WorldBlueprint,
    candidate_regions: list[tuple[float, str]],
    chosen_region_ids: list[str],
    min_distance: int,
    seed_label: str,
) -> dict[str, Any]:
    rng = random.Random(stable_seed_from_parts(world.seed, seed_label, len(chosen_region_ids)))
    chosen_regions = [_region_lookup(world, region_id) for region_id in chosen_region_ids]
    best_region = None
    best_score = None
    fallback_region = None
    fallback_score = None
    for base_score, region_id in candidate_regions:
        region = _region_lookup(world, region_id)
        distance_penalty = 0.0
        nearest = None
        for other in chosen_regions:
            distance = _region_distance(region, other)
            nearest = distance if nearest is None else min(nearest, distance)
            if distance < min_distance:
                distance_penalty += (min_distance - distance) * 0.18
        score = round(base_score - distance_penalty + rng.random() * 0.04, 4)
        if fallback_score is None or score > fallback_score:
            fallback_region = region
            fallback_score = score
        if nearest is None or nearest >= min_distance:
            if best_score is None or score > best_score:
                best_region = region
                best_score = score
    if best_region is not None:
        return best_region
    if fallback_region is not None:
        return fallback_region
    return _region_lookup(world, candidate_regions[0][1])


def _region_resources_to_economy(region: dict[str, Any], has_settlement: bool) -> dict[str, Any]:
    resources = set(region.get("resources", []))
    base_food = 24 if region["biome_id"] in {"plains", "temperate_forest", "coast"} else 12
    if "fish" in resources or "salt" in resources:
        base_food += 8
    ore = 24 if "ore" in resources else 8
    wood = 24 if {"timber", "herbs", "amber"} & resources else 10
    gold = int(16 + float(region.get("settlement_score", 0.0)) * 18 + (8 if has_settlement else 0))
    return {
        "resources": {
            "food": int(base_food + float(region.get("vegetation_density", 0.0)) * 12),
            "ore": ore,
            "wood": wood,
            "gold": gold,
        },
        "prosperity": round(42 + float(region.get("settlement_suitability", 0.0)) * 28 + (6 if has_settlement else 0), 3),
    }


def _build_travel_edges(world: WorldBlueprint) -> list[dict[str, Any]]:
    nodes = list(world.settlement_nodes)
    if len(nodes) < 2:
        return []
    positions = {
        str(node["id"]): tuple(int(value) for value in node.get("grid_position", [0, 0]))
        for node in nodes
    }
    node_by_id = {str(node["id"]): node for node in nodes}
    seen_pairs: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []

    def distance(left_id: str, right_id: str) -> int:
        lx, ly = positions[left_id]
        rx, ry = positions[right_id]
        return abs(lx - rx) + abs(ly - ry)

    visited = {str(nodes[0]["id"])}
    unvisited = {str(node["id"]) for node in nodes[1:]}
    while unvisited:
        best: tuple[int, str, str] | None = None
        for left_id in visited:
            for right_id in unvisited:
                candidate = (distance(left_id, right_id), left_id, right_id)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        _, left_id, right_id = best
        pair = tuple(sorted((left_id, right_id)))
        seen_pairs.add(pair)
        left_node = node_by_id[left_id]
        right_node = node_by_id[right_id]
        edges.append(
            {
                "id": f"edge_{left_id}_{right_id}",
                "from_settlement_id": left_id,
                "to_settlement_id": right_id,
                "from_region_id": left_node["region_id"],
                "to_region_id": right_node["region_id"],
                "travel_hours": max(2, distance(left_id, right_id) * 2),
            }
        )
        visited.add(right_id)
        unvisited.remove(right_id)

    for node in nodes:
        node_id = str(node["id"])
        neighbors = sorted(
            (
                (distance(node_id, str(other["id"])), str(other["id"]))
                for other in nodes
                if str(other["id"]) != node_id
            ),
            key=lambda item: (item[0], item[1]),
        )[:2]
        for dist, other_id in neighbors:
            pair = tuple(sorted((node_id, other_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            other_node = node_by_id[other_id]
            edges.append(
                {
                    "id": f"edge_{node_id}_{other_id}",
                    "from_settlement_id": node_id,
                    "to_settlement_id": other_id,
                    "from_region_id": node["region_id"],
                    "to_region_id": other_node["region_id"],
                    "travel_hours": max(2, dist * 2),
                }
            )
    edges.sort(key=lambda item: (item["from_region_id"], item["to_region_id"], item["id"]))
    return edges


def seed_civilizations(world: WorldBlueprint) -> WorldBlueprint:
    """Seed macro factions, settlement nodes, and travel graph from sapient lineages."""
    species_registry = load_species_templates()
    cultures = load_culture_templates()
    sapient_lineages = sorted(
        [lineage for lineage in world.species_lineages if lineage.sapient],
        key=lambda item: item.species_id,
    )
    world.factions = []
    world.settlements = []
    world.settlement_nodes = []
    world.faction_presence = {str(region["id"]): [] for region in world.regions}
    world.travel_edges = []
    world.region_economy = {}
    world.region_alerts = {str(region["id"]): [] for region in world.regions}

    if not sapient_lineages:
        return world

    lineage_candidates = {
        lineage.species_id: _lineage_candidate_regions(world, lineage, species_registry[lineage.species_id])
        for lineage in sapient_lineages
    }
    desired_faction_count = min(10, max(6, len(sapient_lineages) + 3))
    chosen_origins: list[str] = []
    for index in range(desired_faction_count):
        lineage = sapient_lineages[index % len(sapient_lineages)]
        template = species_registry[lineage.species_id]
        culture_id = template["culture_hint"]
        culture = cultures[culture_id]
        origin_region = _choose_region_with_spacing(
            world,
            lineage_candidates[lineage.species_id],
            chosen_origins,
            2,
            f"faction-origin:{lineage.species_id}:{index}",
        )
        chosen_origins.append(str(origin_region["id"]))
        faction_id = f"{lineage.species_id}_faction_{index:02d}_{world.seed % 997}"
        influence = round(0.42 + float(origin_region["settlement_suitability"]) * 0.34 + (index % 3) * 0.02, 3)
        cohesion = round(0.52 + len(culture["institution_bias"]) * 0.04, 3)
        world.factions.append(
            FactionSeed(
                id=faction_id,
                culture_id=culture_id,
                species_id=lineage.species_id,
                origin_region_id=str(origin_region["id"]),
                traits={"influence": influence, "cohesion": cohesion},
            )
        )

    faction_rotation = sorted(world.factions, key=lambda faction: (faction.species_id, faction.id))
    desired_settlement_count = min(20, max(12, len(faction_rotation) * 2))
    used_settlement_regions: list[str] = []
    biome_prefix = {
        "coast": "Harbor",
        "desert": "Sun",
        "mountain": "Stone",
        "plains": "Field",
        "swamp": "Mire",
        "temperate_forest": "Grove",
    }
    for settlement_index in range(desired_settlement_count):
        faction = faction_rotation[settlement_index % len(faction_rotation)]
        lineage = next(lineage for lineage in sapient_lineages if lineage.species_id == faction.species_id)
        culture = cultures[faction.culture_id]
        template = species_registry[faction.species_id]
        region = _choose_region_with_spacing(
            world,
            lineage_candidates[lineage.species_id],
            used_settlement_regions,
            2,
            f"settlement:{faction.id}:{settlement_index}",
        )
        if str(region["id"]) in used_settlement_regions:
            continue
        used_settlement_regions.append(str(region["id"]))
        settlement_type = _settlement_type_for_species(faction.species_id)
        focus = _focus_for_culture(culture)
        prefix = biome_prefix.get(str(region["biome_id"]), "Frontier")
        center_name = f"{prefix} {template['name']} {settlement_type.title()}"
        population = int(150 + float(region["settlement_suitability"]) * 180 + (settlement_index % 4) * 18)
        node_id = f"node_{region['id']}_{settlement_index:02d}"
        node = {
            "id": node_id,
            "region_id": str(region["id"]),
            "faction_id": faction.id,
            "name": center_name,
            "settlement_type": settlement_type,
            "population": population,
            "building_focus": focus,
            "primary": True,
            "node_type": "primary_settlement",
            "biome_id": str(region["biome_id"]),
            "grid_position": list(_region_grid_position(region)),
        }
        region["controller_faction_id"] = faction.id
        region["settlement_id"] = node_id
        region["settlement_node_ids"] = [node_id]
        region["primary_settlement_name"] = center_name
        world.settlement_nodes.append(node)
        world.settlements.append(
            SettlementSeed(
                id=node_id,
                faction_id=faction.id,
                region_id=str(region["id"]),
                settlement_type=settlement_type,
                population=population,
                center_name=center_name,
                building_focus=focus,
            )
        )
        world.faction_presence[str(region["id"])].append(
            {
                "faction_id": faction.id,
                "species_id": faction.species_id,
                "presence_type": "primary_settlement",
                "pressure": round(faction.traits.get("influence", 0.5), 3),
            }
        )

    for region in world.regions:
        region_id = str(region["id"])
        current_presence = world.faction_presence.setdefault(region_id, [])
        ranked = sorted(
            (
                (
                    next(score for score, candidate_region_id in lineage_candidates[faction.species_id] if candidate_region_id == region_id),
                    faction,
                )
                for faction in world.factions
            ),
            key=lambda item: (-item[0], item[1].id),
        )[:3]
        for score, faction in ranked:
            if any(item["faction_id"] == faction.id for item in current_presence):
                continue
            if score < 0.55:
                continue
            current_presence.append(
                {
                    "faction_id": faction.id,
                    "species_id": faction.species_id,
                    "presence_type": "minor_enclave" if score > 0.82 else "influence",
                    "pressure": round(min(0.95, score), 3),
                }
            )
        if current_presence and "controller_faction_id" not in region:
            region["controller_faction_id"] = current_presence[0]["faction_id"]
        world.region_economy[region_id] = _region_resources_to_economy(
            region,
            has_settlement=bool(region.get("settlement_id")),
        )

    world.travel_edges = _build_travel_edges(world)
    world.metadata["world_graph_dimensions"] = {
        "columns": len({int(region["x"]) for region in world.regions}),
        "rows": len({int(region["y"]) for region in world.regions}),
    }
    return world


def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint:
    """Generate deterministic historical events from factions and settlements."""
    target_year = end_year or world.history_end_year
    rng = random.Random(world.seed + target_year)
    events: list[HistoricalEvent] = []
    for index, faction in enumerate(world.factions):
        settlement = next((item for item in world.settlements if item.faction_id == faction.id), None)
        anchor_region_id = settlement.region_id if settlement is not None else faction.origin_region_id
        if index % 2 == 0:
            event_type = "migration"
            summary = f"{faction.id} pushed settlers beyond {anchor_region_id}."
            consequences = {"new_frontier": anchor_region_id, "pressure": round(rng.uniform(0.2, 0.6), 3)}
        else:
            event_type = "trade_route"
            summary = f"{faction.id} established a trade route through {anchor_region_id}."
            consequences = {"trade_value": round(rng.uniform(0.3, 0.9), 3)}
        events.append(
            HistoricalEvent(
                year=target_year - 180 + index * 21,
                event_type=event_type,
                factions=[faction.id],
                regions=[anchor_region_id],
                summary=summary,
                consequences=consequences,
            )
        )
    if len(world.factions) >= 2:
        first, second = world.factions[:2]
        events.append(
            HistoricalEvent(
                year=target_year - 62,
                event_type="war",
                factions=[first.id, second.id],
                regions=[first.origin_region_id, second.origin_region_id],
                summary=f"{first.id} and {second.id} fought over contested uplands.",
                consequences={"winner": first.id, "loser": second.id, "casualties": "moderate"},
            )
        )
        first.traits["influence"] = round(first.traits["influence"] + 0.08, 3)
        second.traits["influence"] = round(max(0.1, second.traits["influence"] - 0.05), 3)
    if world.settlements:
        settlement = world.settlements[0]
        events.append(
            HistoricalEvent(
                year=target_year - 19,
                event_type="disaster",
                factions=[settlement.faction_id],
                regions=[settlement.region_id],
                summary=f"Flooding reshaped the approaches to {settlement.center_name}.",
                consequences={"infrastructure_loss": 0.2, "rebuild_pressure": 0.4},
            )
        )
        settlement.population = max(120, settlement.population - 20)
    events.sort(key=lambda event: (event.year, event.event_type, ",".join(event.factions)))
    world.historical_events = events
    world.history_end_year = target_year
    return world


def _ground_for_biome(biome_id: str) -> str:
    return {
        "coast": "sand",
        "desert": "sand",
        "mountain": "stone",
        "plains": "grass",
        "swamp": "mud",
        "temperate_forest": "moss",
    }.get(biome_id, "grass")


def _set_tile(typed_tiles: list[list[dict[str, Any]]], x: int, y: int, **updates: Any) -> None:
    if 0 <= y < len(typed_tiles) and 0 <= x < len(typed_tiles[0]):
        typed_tiles[y][x].update(updates)


def generate_settlement_layout(world: WorldBlueprint, region_id: str) -> SettlementLayout:
    """Generate a deterministic 80x60 settlement layout for a populated region."""
    return generate_settlement_layout_v2(world, region_id)


def _build_typed_tiles(layout: SettlementLayout) -> list[list[dict[str, Any]]]:
    typed_tiles = []
    for y in range(layout.height):
        row = []
        for x in range(layout.width):
            terrain = layout.terrain_tiles[y][x]
            row.append(
                {
                    "terrain": terrain,
                    "structure": "road" if terrain in {"road", "cobble"} else "ground",
                    "passable": terrain not in {"wall", "water"},
                    "building_id": None,
                }
            )
        typed_tiles.append(row)

    for building in layout.buildings:
        x0, y0 = building["x"], building["y"]
        width, height = building["width"], building["height"]
        for y in range(y0, y0 + height):
            for x in range(x0, x0 + width):
                if y in (y0, y0 + height - 1) or x in (x0, x0 + width - 1):
                    _set_tile(typed_tiles, x, y, terrain="wall", structure="wall", passable=False, building_id=building["id"])
                else:
                    _set_tile(typed_tiles, x, y, terrain="floor", structure="floor", passable=True, building_id=building["id"])
        for door in building["doors"]:
            _set_tile(typed_tiles, door["x"], door["y"], terrain="door", structure="door", passable=True, building_id=building["id"])

    _set_tile(
        typed_tiles,
        layout.center_feature["x"],
        layout.center_feature["y"],
        terrain=layout.center_feature["kind"],
        structure="feature",
        passable=False,
        building_id=None,
    )
    return typed_tiles


def realize_region(world: WorldBlueprint, region_id: str, detail_level: str = "settlement") -> RegionSnapshot:
    """Realize a region into a playable local snapshot."""
    if detail_level != "settlement":
        raise ValueError(f"Unsupported detail level: {detail_level}")
    region = _region_lookup(world, region_id)
    layout = generate_settlement_layout(world, region_id)
    return RegionSnapshot(
        region_id=region_id,
        biome_id=region["biome_id"],
        width=layout.width,
        height=layout.height,
        layout=layout,
        typed_tiles=_build_typed_tiles(layout),
        metadata={
            "macro_region_id": region_id,
            "controller_faction_id": region.get("controller_faction_id"),
            "settlement_id": region.get("settlement_id"),
            "explainability": deepcopy(region.get("explainability", {})),
        },
    )


def validate_region_snapshot(snapshot: RegionSnapshot) -> list[str]:
    """Validate structural guarantees for a realized region snapshot."""
    errors: list[str] = []
    road_tiles = set(snapshot.layout.road_tiles)
    for building in snapshot.layout.buildings:
        if not building["doors"]:
            errors.append(f"building:{building['id']}:missing-door")
        for door in building["doors"]:
            if not any(tuple(point) in road_tiles for point in door["adjacent"]):
                errors.append(f"building:{building['id']}:door-not-connected")
        required = set(building["required_furniture"])
        placed = {item["kind"] for item in snapshot.layout.furniture if item["building_id"] == building["id"]}
        missing = sorted(required - placed)
        if missing:
            errors.append(f"building:{building['id']}:missing-furniture:{','.join(missing)}")
    for npc in snapshot.layout.npc_spawns:
        tile = snapshot.typed_tiles[npc["y"]][npc["x"]]
        if not tile["passable"]:
            errors.append(f"npc:{npc['id']}:spawn-blocked")
        if tile["building_id"] != npc["building_id"]:
            errors.append(f"npc:{npc['id']}:wrong-building")
    return errors


def initialize_simulation(world: WorldBlueprint, start_region_id: str | None = None) -> WorldBlueprint:
    """Initialize the global runtime snapshot for an already simulated world."""
    return initialize_simulation_v2(world, start_region_id)


def tick_global(world: WorldBlueprint, hours: int) -> GlobalTickResult:
    """Advance the always-global runtime snapshot."""
    return tick_global_v2(world, hours)


def snapshot_world(world: WorldBlueprint) -> dict[str, Any]:
    """Serialize the current world blueprint."""
    return world.to_dict()


def load_world_snapshot(data: dict[str, Any]) -> WorldBlueprint:
    """Deserialize a world snapshot created by snapshot_world."""
    return WorldBlueprint.from_dict(data)
