"""Deterministic terrain generation backed by OpenSimplex-style noise."""

from __future__ import annotations

import math
import random
from typing import Any, Optional

from .models import TectonicPlate, WorldBlueprint, WorldProfile

try:  # pragma: no cover - exercised in integration, not unit-level behavior
    from opensimplex import OpenSimplex
except ImportError:  # pragma: no cover - deterministic fallback for dev envs
    OpenSimplex = None  # type: ignore[assignment]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_grid(grid: list[list[float]], digits: int = 3) -> list[list[float]]:
    return [[round(value, digits) for value in row] for row in grid]


def _fallback_noise(seed: int, x: float, y: float) -> float:
    value = math.sin((seed + 1) * 12.9898 + x * 78.233 + y * 37.719) * 43758.5453
    return value - math.floor(value)


class _NoiseField:
    def __init__(self, seed: int):
        self.seed = seed
        self._simplex = OpenSimplex(seed=seed) if OpenSimplex is not None else None

    def value(self, x: float, y: float, scale: float = 1.0, octaves: int = 1) -> float:
        amplitude = 1.0
        frequency = 1.0
        total = 0.0
        weight = 0.0
        for _ in range(max(octaves, 1)):
            if self._simplex is not None:
                sample = self._simplex.noise2(x / scale * frequency, y / scale * frequency)
                normalized = (sample + 1.0) / 2.0
            else:
                normalized = _fallback_noise(self.seed + int(frequency * 1000), x / scale * frequency, y / scale * frequency)
            total += normalized * amplitude
            weight += amplitude
            amplitude *= 0.5
            frequency *= 2.0
        return total / max(weight, 1e-6)


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


def _compute_elevation(seed: int, profile: WorldProfile, plates: list[TectonicPlate], plate_map: list[list[int]]) -> list[list[float]]:
    crust_by_index = {index: plate.crust_type for index, plate in enumerate(plates)}
    field = _NoiseField(seed)
    elevation: list[list[float]] = []
    for y in range(profile.world_height):
        row = []
        latitude = abs((y / max(1, profile.world_height - 1)) - 0.5)
        for x in range(profile.world_width):
            plate_index = plate_map[y][x]
            crust_type = crust_by_index[plate_index]
            boundary_neighbors = _count_boundary_neighbors(plate_map, x, y)
            continental_base = 0.56 if crust_type == "continental" else 0.15
            boundary_boost = boundary_neighbors * (0.085 if crust_type == "continental" else 0.028)
            macro = field.value(x, y, scale=10.0, octaves=3)
            local = field.value(x + 97, y + 41, scale=4.0, octaves=2)
            ruggedness = (macro - 0.5) * 0.16 + (local - 0.5) * 0.06
            row.append(_clamp(continental_base + boundary_boost + ruggedness - latitude * 0.05))
        elevation.append(row)
    return _round_grid(elevation)


def _compute_temperature(seed: int, profile: WorldProfile, elevation: list[list[float]]) -> list[list[float]]:
    field = _NoiseField(seed + 101)
    height = len(elevation)
    temperature: list[list[float]] = []
    for y in range(height):
        latitude_heat = 1.0 - abs((y / max(1, height - 1)) * 2 - 1)
        row = []
        for x in range(len(elevation[0])):
            micro = (field.value(x, y, scale=12.0, octaves=2) - 0.5) * 0.08
            row.append(_clamp(latitude_heat * 0.95 - elevation[y][x] * 0.30 + 0.05 + micro))
        temperature.append(row)
    return _round_grid(temperature)


def _compute_moisture(seed: int, elevation: list[list[float]], temperature: list[list[float]]) -> list[list[float]]:
    field = _NoiseField(seed + 202)
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
                    rain_shadow += 0.05
            micro = (field.value(x, y, scale=9.0, octaves=2) - 0.5) * 0.12
            row.append(_clamp(0.2 + water_bonus * 0.78 - rain_shadow - temperature[y][x] * 0.04 + micro))
        moisture.append(row)
    return _round_grid(moisture)


def _lowest_neighbor(elevation: list[list[float]], x: int, y: int, visited: set[tuple[int, int]]) -> Optional[tuple[int, int]]:
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


def _compute_drainage_and_rivers(seed: int, elevation: list[list[float]], moisture: list[list[float]]) -> tuple[list[list[float]], list[dict[str, Any]]]:
    height = len(elevation)
    width = len(elevation[0])
    field = _NoiseField(seed + 303)
    drainage = [
        [
            _clamp(0.24 + moisture[y][x] * 0.82 - elevation[y][x] * 0.10 + (field.value(x, y, scale=7.0) - 0.5) * 0.08)
            for x in range(width)
        ]
        for y in range(height)
    ]

    candidates = []
    for y in range(height):
        for x in range(width):
            if elevation[y][x] > 0.56 and moisture[y][x] > 0.50:
                candidates.append((elevation[y][x] + moisture[y][x] + field.value(x, y, scale=5.0) * 0.1, x, y))
    candidates.sort(reverse=True)

    river_paths: list[dict[str, Any]] = []
    used_sources: set[tuple[int, int]] = set()
    for _, x, y in candidates:
        if len(river_paths) >= 4 or (x, y) in used_sources:
            break
        visited: set[tuple[int, int]] = set()
        path: list[tuple[int, int]] = []
        current = (x, y)
        for _ in range(40):
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


def _majority(values: list[str]) -> str:
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


def generate_world_blueprint(seed: int, profile: WorldProfile, biome_registry: dict[str, dict[str, Any]]) -> WorldBlueprint:
    plates, plate_map = _build_tectonic_plates(seed, profile)
    elevation = _compute_elevation(seed, profile, plates, plate_map)
    temperature = _compute_temperature(seed, profile, elevation)
    moisture = _compute_moisture(seed, elevation, temperature)
    drainage, river_paths = _compute_drainage_and_rivers(seed, elevation, moisture)
    biomes = [
        [
            _classify_biome(elevation[y][x], temperature[y][x], moisture[y][x], drainage[y][x])
            for x in range(profile.world_width)
        ]
        for y in range(profile.world_height)
    ]

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
            biome_id = _majority([biomes[y][x] for x, y in cells])
            water_access = "coast" if any(elevation[y][x] < 0.3 for x, y in cells) else "inland"
            river_present = any((x, y) in river_tiles for x, y in cells)
            boundary_hits = sum(1 for x, y in cells if _count_boundary_neighbors(plate_map, x, y) > 0)
            settlement_score = round(
                _clamp(
                    biome_registry[biome_id]["settlement_weight"]
                    + (0.12 if river_present or water_access == "coast" else 0.0)
                    + (0.05 if avg_drainage > 0.58 else 0.0)
                ),
                3,
            )
            suitability = round(_clamp(settlement_score + (0.06 if avg_temperature > 0.25 else -0.04)), 3)
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
                    "settlement_suitability": suitability,
                    "river_present": river_present,
                    "vegetation_density": round(_clamp(avg_moisture * 0.8 + (0.15 if biome_id == "temperate_forest" else 0.0)), 3),
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
