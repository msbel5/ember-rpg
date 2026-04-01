"""Region realization and snapshot helpers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import RegionSnapshot, SettlementLayout, WorldBlueprint
from .settlement_generator import generate_settlement_layout as generate_settlement_layout_v2


def region_lookup(world: WorldBlueprint, region_id: str) -> dict[str, Any]:
    for region in world.regions:
        if region["id"] == region_id:
            return region
    raise ValueError(f"Unknown region_id: {region_id}")


def generate_settlement_layout(world: WorldBlueprint, region_id: str) -> SettlementLayout:
    return generate_settlement_layout_v2(world, region_id)


def realize_region(world: WorldBlueprint, region_id: str, detail_level: str = "settlement") -> RegionSnapshot:
    if detail_level != "settlement":
        raise ValueError(f"Unsupported detail level: {detail_level}")
    region = region_lookup(world, region_id)
    layout = generate_settlement_layout(world, region_id)
    return RegionSnapshot(
        region_id=region_id,
        biome_id=region["biome_id"],
        width=layout.width,
        height=layout.height,
        layout=layout,
        typed_tiles=build_typed_tiles(layout),
        metadata={
            "macro_region_id": region_id,
            "controller_faction_id": region.get("controller_faction_id"),
            "settlement_id": region.get("settlement_id"),
            "explainability": deepcopy(region.get("explainability", {})),
        },
    )


def validate_region_snapshot(snapshot: RegionSnapshot) -> list[str]:
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


def snapshot_world(world: WorldBlueprint) -> dict[str, Any]:
    return world.to_dict()


def load_world_snapshot(data: dict[str, Any]) -> WorldBlueprint:
    return WorldBlueprint.from_dict(data)


def build_typed_tiles(layout: SettlementLayout) -> list[list[dict[str, Any]]]:
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
                    set_tile(typed_tiles, x, y, terrain="wall", structure="wall", passable=False, building_id=building["id"])
                else:
                    set_tile(typed_tiles, x, y, terrain="floor", structure="floor", passable=True, building_id=building["id"])
        for door in building["doors"]:
            set_tile(typed_tiles, door["x"], door["y"], terrain="door", structure="door", passable=True, building_id=building["id"])

    set_tile(
        typed_tiles,
        layout.center_feature["x"],
        layout.center_feature["y"],
        terrain=layout.center_feature["kind"],
        structure="feature",
        passable=False,
        building_id=None,
    )
    return typed_tiles


def set_tile(typed_tiles: list[list[dict[str, Any]]], x: int, y: int, **updates: Any) -> None:
    if 0 <= y < len(typed_tiles) and 0 <= x < len(typed_tiles[0]):
        typed_tiles[y][x].update(updates)


__all__ = [
    "generate_settlement_layout",
    "load_world_snapshot",
    "realize_region",
    "snapshot_world",
    "validate_region_snapshot",
]
