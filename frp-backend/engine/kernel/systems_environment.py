from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord, WoundRecord
from engine.kernel.common import serialize_value
from engine.worldgen.models import RegionSnapshot

from .systems_infrastructure import make_wound


@dataclass
class FluidCell:
    x: int
    y: int
    fluid_type: str
    level: int

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class FluidState:
    cells: list[FluidCell] = field(default_factory=list)
    fluid_counts: dict[str, int] = field(default_factory=dict)
    pressure_enabled: bool = False
    muddy_floor_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class TemperatureState:
    ambient_band: str
    ambient_value: int = 10015
    hazardous: bool = False
    heat_sources: list[dict[str, Any]] = field(default_factory=list)
    cold_threshold: int = 10000
    heat_threshold: int = 10500
    tags: list[str] = field(default_factory=list)
    tile_states: dict[tuple[int, int], str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ambient_band": self.ambient_band,
            "ambient_value": self.ambient_value,
            "hazardous": self.hazardous,
            "heat_sources": serialize_value(self.heat_sources),
            "cold_threshold": self.cold_threshold,
            "heat_threshold": self.heat_threshold,
            "tags": list(self.tags),
            "tile_states": {f"{x},{y}": value for (x, y), value in self.tile_states.items()},
        }


def tick_fluids(fluid_state: FluidState, terrain: list[list[dict]]) -> FluidState:
    cells = [FluidCell(cell.x, cell.y, cell.fluid_type, max(0, min(7, int(cell.level)))) for cell in fluid_state.cells]
    by_coord: dict[tuple[int, int], list[FluidCell]] = {}
    for cell in cells:
        by_coord.setdefault((cell.x, cell.y), []).append(cell)

    consumed: set[tuple[int, int]] = set()
    for coord, group in by_coord.items():
        kinds = {cell.fluid_type for cell in group if cell.level > 0}
        if {"water", "magma"} <= kinds:
            x, y = coord
            terrain[y][x]["terrain"] = "obsidian"
            consumed.add(coord)

    if consumed:
        cells = [cell for cell in cells if (cell.x, cell.y) not in consumed]

    transfers: list[tuple[FluidCell, tuple[int, int]]] = []
    for cell in cells:
        if cell.level <= 1:
            continue
        for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1)):
            nx, ny = cell.x + dx, cell.y + dy
            if ny < 0 or ny >= len(terrain) or nx < 0 or nx >= len(terrain[0]):
                continue
            neighbor = next((other for other in cells if other.x == nx and other.y == ny and other.fluid_type == cell.fluid_type), None)
            neighbor_level = neighbor.level if neighbor is not None else 0
            if neighbor_level < cell.level:
                transfers.append((cell, (nx, ny)))
                break

    for cell, target in transfers:
        if cell.level <= 0:
            continue
        cell.level -= 1
        neighbor = next((other for other in cells if other.x == target[0] and other.y == target[1] and other.fluid_type == cell.fluid_type), None)
        if neighbor is None:
            cells.append(FluidCell(x=target[0], y=target[1], fluid_type=cell.fluid_type, level=1))
        else:
            neighbor.level = min(7, neighbor.level + 1)

    counts = {"water": 0, "magma": 0}
    for cell in cells:
        counts[cell.fluid_type] = counts.get(cell.fluid_type, 0) + max(0, int(cell.level))
    return FluidState(
        cells=[cell for cell in cells if cell.level > 0],
        fluid_counts=counts,
        pressure_enabled=counts.get("water", 0) > 8,
        muddy_floor_risk=any(cell.fluid_type == "water" and terrain[cell.y][cell.x].get("terrain") == "soil" for cell in cells),
    )


def check_drowning(actor: ActorRecord, fluid_state: FluidState) -> bool:
    cell = next((cell for cell in fluid_state.cells if cell.x == actor.position.x and cell.y == actor.position.y and cell.fluid_type == "water"), None)
    if cell is None or cell.level < 7:
        actor.raw_payload["suffocation_ticks"] = 0
        return False
    actor.raw_payload["suffocation_ticks"] = int(actor.raw_payload.get("suffocation_ticks", 0)) + 1
    if actor.raw_payload["suffocation_ticks"] >= 10:
        actor.alive = False
        return True
    return False


def check_magma_damage(actor: ActorRecord, fluid_state: FluidState) -> WoundRecord | None:
    cell = next((cell for cell in fluid_state.cells if cell.x == actor.position.x and cell.y == actor.position.y and cell.fluid_type == "magma" and cell.level > 0), None)
    if cell is None:
        return None
    wound = make_wound("magma", "fire", 25)
    if actor.body_state is not None:
        actor.body_state.apply_wound(wound)
    actor.conditions.append(ConditionRecord(condition_id="ignition", name="burning", severity=20))
    return wound


def tick_temperature(temp_state: TemperatureState, actors: list[ActorRecord]) -> list[dict]:
    events: list[dict] = []
    for actor in actors:
        if temp_state.ambient_value < temp_state.cold_threshold:
            actor.raw_payload["cold_ticks"] = int(actor.raw_payload.get("cold_ticks", 0)) + 1
            if actor.raw_payload["cold_ticks"] >= 3:
                events.append({"type": "frostbite", "actor_id": actor.identity.actor_id})
        else:
            actor.raw_payload["cold_ticks"] = 0
        if temp_state.ambient_value > temp_state.heat_threshold:
            actor.raw_payload["heat_ticks"] = int(actor.raw_payload.get("heat_ticks", 0)) + 1
            events.append({"type": "heat", "actor_id": actor.identity.actor_id})
            ignite_point = actor.raw_payload.get("organic_item_ignite_point")
            if ignite_point is not None and temp_state.ambient_value >= int(ignite_point):
                events.append({"type": "item_ignited", "actor_id": actor.identity.actor_id})
        else:
            actor.raw_payload["heat_ticks"] = 0
    updated_tile_states: dict[tuple[int, int], str] = {}
    for coord, state in temp_state.tile_states.items():
        if state == "water" and temp_state.ambient_value < temp_state.cold_threshold:
            updated_tile_states[coord] = "ice"
            events.append({"type": "freeze", "tile": coord})
        elif state == "ice" and temp_state.ambient_value >= temp_state.cold_threshold:
            updated_tile_states[coord] = "water"
            events.append({"type": "melt", "tile": coord})
        else:
            updated_tile_states[coord] = state
    temp_state.tile_states = updated_tile_states
    return events


def fluid_state_from_region(region_snapshot: RegionSnapshot) -> FluidState:
    cells: list[FluidCell] = []
    counts: dict[str, int] = {"water": 0, "magma": 0}
    for y, row in enumerate(region_snapshot.typed_tiles):
        for x, tile in enumerate(row):
            terrain = str(tile.get("terrain", ""))
            if terrain == "water":
                cells.append(FluidCell(x=x, y=y, fluid_type="water", level=7))
                counts["water"] += 7
            if terrain in {"lava", "magma"}:
                cells.append(FluidCell(x=x, y=y, fluid_type="magma", level=7))
                counts["magma"] += 7
    return FluidState(
        cells=cells,
        fluid_counts=counts,
        pressure_enabled=counts["water"] > 8,
        muddy_floor_risk=counts["water"] > 0 and any(str(tile.get("terrain", "")) == "floor" for row in region_snapshot.typed_tiles for tile in row),
    )


def temperature_state_from_region(region_snapshot: RegionSnapshot) -> TemperatureState:
    biome = str(region_snapshot.biome_id).lower()
    if "arctic" in biome or "ice" in biome or "tundra" in biome:
        return TemperatureState(ambient_band="cold", ambient_value=9990, hazardous=False, tags=["freezing_risk"])
    if "desert" in biome or "volcanic" in biome or "lava" in biome:
        return TemperatureState(ambient_band="hot", ambient_value=10600, hazardous=True, tags=["burn_risk"])
    return TemperatureState(ambient_band="temperate", ambient_value=10015, hazardous=False, tags=[])


__all__ = [
    "FluidCell",
    "FluidState",
    "TemperatureState",
    "check_drowning",
    "check_magma_damage",
    "fluid_state_from_region",
    "temperature_state_from_region",
    "tick_fluids",
    "tick_temperature",
]
