"""Deterministic macro-world generation helpers."""
from __future__ import annotations

import math
import random
from typing import Any, Iterable, Optional

from .models import TectonicPlate, WorldBlueprint, WorldProfile
from .registries import load_world_biomes, load_world_profiles, validate_world_registries
from .terrain_generator import generate_world_blueprint
from .world_seed import WorldSeed


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def round_grid(grid: list[list[float]], digits: int = 3) -> list[list[float]]:
    return [[round(value, digits) for value in row] for row in grid]


def noise(seed: int, x: int, y: int) -> float:
    value = math.sin((seed + 1) * 12.9898 + x * 78.233 + y * 37.719) * 43758.5453
    return value - math.floor(value)


def plate_seed_points(seed: int, profile: WorldProfile) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [
        (rng.randrange(profile.world_width), rng.randrange(profile.world_height))
        for _ in range(profile.plate_count)
    ]


def nearest_seed_index(seeds: list[tuple[int, int]], x: int, y: int) -> int:
    best_index = 0
    best_distance = None
    for index, (sx, sy) in enumerate(seeds):
        distance = (sx - x) ** 2 + (sy - y) ** 2
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def build_tectonic_plates(seed: int, profile: WorldProfile) -> tuple[list[TectonicPlate], list[list[int]]]:
    rng = random.Random(seed)
    seeds = plate_seed_points(seed, profile)
    plate_cells: list[list[tuple[int, int]]] = [[] for _ in range(profile.plate_count)]
    plate_map: list[list[int]] = []
    for y in range(profile.world_height):
        row = []
        for x in range(profile.world_width):
            plate_index = nearest_seed_index(seeds, x, y)
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


def count_boundary_neighbors(plate_map: list[list[int]], x: int, y: int) -> int:
    height = len(plate_map)
    width = len(plate_map[0])
    current = plate_map[y][x]
    count = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height and plate_map[ny][nx] != current:
            count += 1
    return count


def compute_elevation(
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
            boundary_neighbors = count_boundary_neighbors(plate_map, x, y)
            base = 0.55 if crust_type == "continental" else 0.16
            boundary_boost = boundary_neighbors * (0.09 if crust_type == "continental" else 0.03)
            ruggedness = (noise(seed, x, y) - 0.5) * 0.18
            latitude_shaping = abs((y / max(1, profile.world_height - 1)) - 0.5) * 0.05
            row.append(clamp(base + boundary_boost + ruggedness - latitude_shaping))
        elevation.append(row)
    return round_grid(elevation)


def compute_temperature(profile: WorldProfile, elevation: list[list[float]]) -> list[list[float]]:
    height = len(elevation)
    temperature: list[list[float]] = []
    for y in range(height):
        latitude_heat = 1.0 - abs((y / max(1, height - 1)) * 2 - 1)
        row = []
        for x in range(len(elevation[0])):
            row.append(clamp(latitude_heat * 0.95 - elevation[y][x] * 0.28 + 0.05))
        temperature.append(row)
    return round_grid(temperature)


def compute_moisture(elevation: list[list[float]], temperature: list[list[float]]) -> list[list[float]]:
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
            row.append(clamp(0.18 + water_bonus * 0.8 - rain_shadow - temperature[y][x] * 0.05))
        moisture.append(row)
    return round_grid(moisture)


def lowest_neighbor(
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


def compute_drainage_and_rivers(
    seed: int, elevation: list[list[float]], moisture: list[list[float]]
) -> tuple[list[list[float]], list[dict[str, Any]]]:
    height = len(elevation)
    width = len(elevation[0])
    drainage = [
        [clamp(0.25 + moisture[y][x] * 0.85 - elevation[y][x] * 0.15) for x in range(width)]
        for y in range(height)
    ]

    candidates = []
    for y in range(height):
        for x in range(width):
            if elevation[y][x] > 0.58 and moisture[y][x] > 0.52:
                candidates.append((elevation[y][x] + moisture[y][x] + noise(seed + 77, x, y) * 0.1, x, y))
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
            neighbor = lowest_neighbor(elevation, cx, cy, visited)
            if neighbor is None:
                break
            current = neighbor
        if len(path) >= 4:
            used_sources.add((x, y))
            river_paths.append({"source": [x, y], "path": [list(node) for node in path]})
    return round_grid(drainage), river_paths


def classify_biome(elevation: float, temperature: float, moisture: float, drainage: float) -> str:
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


def majority(values: Iterable[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def terrain_driver(avg_elevation: float, boundary_hits: int, river_present: bool) -> str:
    if avg_elevation >= 0.68:
        return "plate_boundary_mountains"
    if river_present and avg_elevation <= 0.45:
        return "river_basin"
    if boundary_hits > 0:
        return "tectonic_uplift"
    return "coastal_lowlands" if avg_elevation < 0.35 else "upland_continent"


def climate_driver(avg_temperature: float, avg_moisture: float, water_access: str) -> str:
    if water_access == "coast":
        return "marine_influence"
    if avg_moisture >= 0.7:
        return "humid_belt"
    if avg_temperature >= 0.65 and avg_moisture <= 0.25:
        return "dry_interior"
    return "temperate_band"


def generate_world(seed: int, profile_id: str) -> WorldBlueprint:
    validate_world_registries()
    profiles = load_world_profiles()
    if profile_id not in profiles:
        raise ValueError(f"Unknown profile_id: {profile_id}")
    profile = WorldProfile.from_dict(profiles[profile_id])
    canonical_seed = int(WorldSeed(seed))
    return generate_world_blueprint(canonical_seed, profile, load_world_biomes())


__all__ = [
    "generate_world",
]
