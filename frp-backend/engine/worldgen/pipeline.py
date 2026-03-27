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
    plates, plate_map = _build_tectonic_plates(seed, profile)
    elevation = _compute_elevation(seed, profile, plates, plate_map)
    temperature = _compute_temperature(profile, elevation)
    moisture = _compute_moisture(elevation, temperature)
    drainage, river_paths = _compute_drainage_and_rivers(seed, elevation, moisture)
    biomes = [
        [
            _classify_biome(elevation[y][x], temperature[y][x], moisture[y][x], drainage[y][x])
            for x in range(profile.world_width)
        ]
        for y in range(profile.world_height)
    ]

    biome_registry = load_world_biomes()
    river_tiles = {tuple(point) for river in river_paths for point in river["path"]}
    regions: list[dict[str, Any]] = []
    region_index = 0
    for region_y in range(0, profile.world_height, profile.region_size):
        for region_x in range(0, profile.world_width, profile.region_size):
            cells = [
                (x, y)
                for y in range(region_y, min(region_y + profile.region_size, profile.world_height))
                for x in range(region_x, min(region_x + profile.region_size, profile.world_width))
            ]
            avg_elevation = round(sum(elevation[y][x] for x, y in cells) / len(cells), 3)
            avg_temperature = round(sum(temperature[y][x] for x, y in cells) / len(cells), 3)
            avg_moisture = round(sum(moisture[y][x] for x, y in cells) / len(cells), 3)
            avg_drainage = round(sum(drainage[y][x] for x, y in cells) / len(cells), 3)
            biome_id = _majority(biomes[y][x] for x, y in cells)
            water_access = "coast" if any(elevation[y][x] < 0.3 for x, y in cells) else "inland"
            river_present = any((x, y) in river_tiles for x, y in cells)
            boundary_hits = sum(1 for x, y in cells if _count_boundary_neighbors(plate_map, x, y) > 0)
            settlement_score = round(
                _clamp(
                    biome_registry[biome_id]["settlement_weight"]
                    + (0.15 if river_present or water_access == "coast" else 0.0)
                ),
                3,
            )
            regions.append(
                {
                    "id": f"region_{region_index:03d}",
                    "x": region_x,
                    "y": region_y,
                    "width": min(profile.region_size, profile.world_width - region_x),
                    "height": min(profile.region_size, profile.world_height - region_y),
                    "biome_id": biome_id,
                    "avg_elevation": avg_elevation,
                    "avg_temperature": avg_temperature,
                    "avg_moisture": avg_moisture,
                    "avg_drainage": avg_drainage,
                    "water_access": water_access,
                    "resources": list(biome_registry[biome_id]["resources"]),
                    "fauna": list(biome_registry[biome_id]["fauna"]),
                    "settlement_score": settlement_score,
                    "river_present": river_present,
                    "explainability": {
                        "terrain_driver": _terrain_driver(avg_elevation, boundary_hits, river_present),
                        "climate_driver": _climate_driver(avg_temperature, avg_moisture, water_access),
                    },
                }
            )
            region_index += 1

    return WorldBlueprint(
        seed=seed,
        profile_id=profile.id,
        width=profile.world_width,
        height=profile.world_height,
        history_end_year=profile.history_end_year,
        tectonic_plates=plates,
        elevation=elevation,
        temperature=temperature,
        moisture=moisture,
        drainage=drainage,
        biomes=biomes,
        river_paths=river_paths,
        regions=regions,
        metadata={"profile_title": profile.title},
    )


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


def seed_civilizations(world: WorldBlueprint) -> WorldBlueprint:
    """Seed faction and settlement candidates from sapient lineages."""
    species_registry = load_species_templates()
    cultures = load_culture_templates()
    world.factions = []
    world.settlements = []
    for lineage in sorted(world.species_lineages, key=lambda item: item.species_id):
        if not lineage.sapient or not lineage.home_regions:
            continue
        region = _region_lookup(world, lineage.home_regions[0])
        template = species_registry[lineage.species_id]
        culture_id = template["culture_hint"]
        culture = cultures[culture_id]
        faction_id = f"{lineage.species_id}-{region['id']}-{world.seed % 997}"
        world.factions.append(
            FactionSeed(
                id=faction_id,
                culture_id=culture_id,
                species_id=lineage.species_id,
                origin_region_id=region["id"],
                traits={
                    "influence": round(0.45 + region["settlement_score"] * 0.4, 3),
                    "cohesion": round(0.55 + len(culture["institution_bias"]) * 0.03, 3),
                },
            )
        )
        settlement_type = {"dwarf": "stronghold", "elf": "grove", "dragon": "eyrie"}.get(
            lineage.species_id, "city"
        )
        focus = sorted(
            culture["institution_bias"].keys(),
            key=lambda key: (-culture["institution_bias"][key], key),
        )[:3]
        settlement = {
            "id": f"settlement-{lineage.species_id}-{region['id']}",
            "faction_id": faction_id,
            "region_id": region["id"],
            "settlement_type": settlement_type,
            "population": int(180 + region["settlement_score"] * 220),
            "center_name": f"{template['name']} {settlement_type.title()}",
            "building_focus": focus,
        }
        region["controller_faction_id"] = faction_id
        region["settlement_id"] = settlement["id"]
        world.settlements.append(SettlementSeed.from_dict(settlement))
    return world


def simulate_history(world: WorldBlueprint, end_year: int | None = None) -> WorldBlueprint:
    """Generate deterministic historical events from factions and settlements."""
    target_year = end_year or world.history_end_year
    rng = random.Random(world.seed + target_year)
    events: list[HistoricalEvent] = []
    for index, faction in enumerate(world.factions):
        settlement = next(item for item in world.settlements if item.faction_id == faction.id)
        if index % 2 == 0:
            event_type = "migration"
            summary = f"{faction.id} pushed settlers beyond {settlement.region_id}."
            consequences = {"new_frontier": settlement.region_id, "pressure": round(rng.uniform(0.2, 0.6), 3)}
        else:
            event_type = "trade_route"
            summary = f"{faction.id} established a trade route through {settlement.region_id}."
            consequences = {"trade_value": round(rng.uniform(0.3, 0.9), 3)}
        events.append(
            HistoricalEvent(
                year=target_year - 180 + index * 21,
                event_type=event_type,
                factions=[faction.id],
                regions=[settlement.region_id],
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
    region = _region_lookup(world, region_id)
    settlement = next((item for item in world.settlements if item.region_id == region_id), None)
    if settlement is None:
        raise ValueError(f"Region {region_id} has no settlement")

    width, height = 80, 60
    ground = _ground_for_biome(region["biome_id"])
    terrain_tiles = [[ground for _ in range(width)] for _ in range(height)]
    road_tiles: set[tuple[int, int]] = set()

    def road_at(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            terrain_tiles[y][x] = "road"
            road_tiles.add((x, y))

    def connect_vertical(x: int, start_y: int, end_y: int) -> None:
        step = 1 if end_y >= start_y else -1
        for y in range(start_y, end_y + step, step):
            road_at(x, y)

    wave = [0, 0, 1, 1, 2, 1, 0, 0, -1, -1, 0, 0]
    main_road_y: dict[int, int] = {}
    for x in range(width):
        y = 30 + wave[x % len(wave)]
        main_road_y[x] = y
        road_at(x, y)
        road_at(x, min(height - 1, y + 1))

    center_kind = "fountain" if region["biome_id"] == "coast" else "well"
    center_feature = {"kind": center_kind, "x": 40, "y": 30}
    for y in range(26, 35):
        for x in range(36, 45):
            terrain_tiles[y][x] = "cobble"
            road_tiles.add((x, y))

    building_templates = load_building_templates()
    load_furniture_templates()
    placements = [
        ("blacksmith", 10, 10, "south"),
        ("tavern", 18, 34, "north"),
        ("temple", 52, 10, "south"),
        ("house", 60, 34, "north"),
    ]

    buildings: list[dict[str, Any]] = []
    furniture: list[dict[str, Any]] = []
    npc_spawns: list[dict[str, Any]] = []

    for index, (kind, x, y, door_side) in enumerate(placements):
        template = building_templates[kind]
        bw, bh = template["footprint"]
        building_id = f"{kind}_{index}"
        for ty in range(y, y + bh):
            for tx in range(x, x + bw):
                terrain_tiles[ty][tx] = "wall" if ty in (y, y + bh - 1) or tx in (x, x + bw - 1) else "floor"

        if door_side == "south":
            door_x, door_y = x + bw // 2, y + bh - 1
            adjacent = (door_x, door_y + 1)
        else:
            door_x, door_y = x + bw // 2, y
            adjacent = (door_x, door_y - 1)
        connect_vertical(door_x, adjacent[1], main_road_y[door_x])
        terrain_tiles[door_y][door_x] = "door"

        required_kinds = [item["kind"] for item in template["required_furniture"]]
        buildings.append(
            {
                "id": building_id,
                "kind": kind,
                "x": x,
                "y": y,
                "width": bw,
                "height": bh,
                "doors": [{"x": door_x, "y": door_y, "adjacent": [adjacent]}],
                "required_furniture": required_kinds,
                "npc_roles": list(template["npc_roles"]),
            }
        )
        for item in template["required_furniture"]:
            furniture.append(
                {
                    "kind": item["kind"],
                    "x": x + item["anchor"][0],
                    "y": y + item["anchor"][1],
                    "building_id": building_id,
                }
            )
        for role_index, role in enumerate(template["npc_roles"]):
            npc_spawns.append(
                {
                    "id": f"{building_id}_{role}",
                    "role": role,
                    "x": x + 2 + min(role_index, max(0, bw - 4)),
                    "y": y + max(2, bh // 2),
                    "building_id": building_id,
                }
            )

    return SettlementLayout(
        width=width,
        height=height,
        terrain_tiles=terrain_tiles,
        road_tiles=sorted(road_tiles),
        buildings=buildings,
        furniture=furniture,
        npc_spawns=npc_spawns,
        center_feature=center_feature,
    )


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
    active_region_id = start_region_id
    if active_region_id is None:
        active_region_id = world.settlements[0].region_id if world.settlements else world.regions[0]["id"]
    region_states = {}
    for region in world.regions:
        population = sum(item.population for item in world.settlements if item.region_id == region["id"])
        region_states[region["id"]] = {
            "population": population,
            "resources": len(region.get("resources", [])),
            "stability": round(0.5 + region["settlement_score"] * 0.3, 3),
            "prosperity": round(50 + region["settlement_score"] * 25, 3),
            "resolution": "fine" if region["id"] == active_region_id else "coarse",
        }
    faction_states = {
        faction.id: {
            "culture_id": faction.culture_id,
            "influence": faction.traits.get("influence", 0.5),
            "cohesion": faction.traits.get("cohesion", 0.5),
        }
        for faction in world.factions
    }
    world.simulation_snapshot = SimulationSnapshot(
        current_year=world.history_end_year,
        current_hour=0,
        active_region_id=active_region_id,
        region_states=region_states,
        faction_states=faction_states,
        pending_events=[],
    )
    return world


def tick_global(world: WorldBlueprint, hours: int) -> GlobalTickResult:
    """Advance the always-global runtime snapshot."""
    if hours < 0:
        raise ValueError("hours must be >= 0")
    if world.simulation_snapshot is None:
        initialize_simulation(world)
    snapshot = SimulationSnapshot.from_dict(world.simulation_snapshot.to_dict())
    snapshot.current_hour += hours
    updated_regions = []
    generated_events: list[dict[str, Any]] = []
    active_region_id = snapshot.active_region_id
    for region_id, state in snapshot.region_states.items():
        updated_regions.append(region_id)
        is_active = region_id == active_region_id
        state["resolution"] = "fine" if is_active else "coarse"
        state["prosperity"] = round(state["prosperity"] + (0.08 if is_active else 0.03) * hours, 3)
        state["last_tick_hours"] = hours
    if active_region_id is not None:
        generated_events.append({"event_type": "active_region_update", "region_id": active_region_id, "hours": hours})
    inactive_region = next((region_id for region_id in snapshot.region_states if region_id != active_region_id), None)
    if inactive_region is not None:
        generated_events.append({"event_type": "inactive_region_shift", "region_id": inactive_region, "hours": hours})
    snapshot.pending_events.extend(generated_events)
    world.simulation_snapshot = snapshot
    active_region_snapshot = (
        {"region_id": active_region_id, "state": deepcopy(snapshot.region_states[active_region_id])}
        if active_region_id is not None
        else None
    )
    return GlobalTickResult(hours, updated_regions, generated_events, snapshot, active_region_snapshot)


def snapshot_world(world: WorldBlueprint) -> dict[str, Any]:
    """Serialize the current world blueprint."""
    return world.to_dict()


def load_world_snapshot(data: dict[str, Any]) -> WorldBlueprint:
    """Deserialize a world snapshot created by snapshot_world."""
    return WorldBlueprint.from_dict(data)
