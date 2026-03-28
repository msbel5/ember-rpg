"""Organic settlement realization for local 80x60 campaign maps."""

from __future__ import annotations

import random
from typing import Any

from .models import SettlementLayout, WorldBlueprint
from .npc_generator import generate_npc_population
from .registries import load_building_templates
from .world_seed import stable_seed_from_parts


def _region_lookup(world: WorldBlueprint, region_id: str) -> dict[str, Any]:
    for region in world.regions:
        if region["id"] == region_id:
            return region
    raise ValueError(f"Unknown region_id: {region_id}")


def _ground_for_biome(biome_id: str) -> str:
    return {
        "coast": "sand",
        "desert": "sand",
        "mountain": "stone_floor",
        "plains": "grass",
        "swamp": "swamp",
        "temperate_forest": "grass",
    }.get(biome_id, "grass")


def _carve_square(terrain_tiles: list[list[str]], x0: int, y0: int, width: int, height: int, fill: str) -> None:
    for y in range(max(0, y0), min(len(terrain_tiles), y0 + height)):
        for x in range(max(0, x0), min(len(terrain_tiles[0]), x0 + width)):
            terrain_tiles[y][x] = fill


def _can_place(buildings: list[dict[str, Any]], x: int, y: int, width: int, height: int, max_width: int, max_height: int) -> bool:
    if x < 2 or y < 2 or x + width >= max_width - 2 or y + height >= max_height - 2:
        return False
    for building in buildings:
        bx = int(building["x"])
        by = int(building["y"])
        bw = int(building["width"])
        bh = int(building["height"])
        if not (x + width + 2 <= bx or bx + bw + 2 <= x or y + height + 2 <= by or by + bh + 2 <= y):
            return False
    return True


def _place_building_tiles(terrain_tiles: list[list[str]], building: dict[str, Any]) -> None:
    x0 = int(building["x"])
    y0 = int(building["y"])
    width = int(building["width"])
    height = int(building["height"])
    floor_kind = str(building.get("floor_kind", "wood_floor"))
    for y in range(y0, y0 + height):
        for x in range(x0, x0 + width):
            if y in (y0, y0 + height - 1) or x in (x0, x0 + width - 1):
                terrain_tiles[y][x] = "wall"
            else:
                terrain_tiles[y][x] = floor_kind
    for door in building["doors"]:
        terrain_tiles[int(door["y"])][int(door["x"])] = "door"


def _door_for_plot(x: int, y: int, width: int, height: int, road_side: str) -> tuple[int, int, tuple[int, int]]:
    if road_side == "south":
        door = (x + width // 2, y + height - 1)
        adjacent = (door[0], door[1] + 1)
    elif road_side == "north":
        door = (x + width // 2, y)
        adjacent = (door[0], door[1] - 1)
    elif road_side == "east":
        door = (x + width - 1, y + height // 2)
        adjacent = (door[0] + 1, door[1])
    else:
        door = (x, y + height // 2)
        adjacent = (door[0] - 1, door[1])
    return (door[0], door[1], adjacent)


def _connect_to_road(terrain_tiles: list[list[str]], road_tiles: set[tuple[int, int]], start: tuple[int, int], target: tuple[int, int]) -> None:
    x, y = start
    tx, ty = target
    while x != tx:
        terrain_tiles[y][x] = "dirt_path" if terrain_tiles[y][x] in {"grass", "sand", "swamp"} else terrain_tiles[y][x]
        road_tiles.add((x, y))
        x += 1 if tx > x else -1
    while y != ty:
        terrain_tiles[y][x] = "dirt_path" if terrain_tiles[y][x] in {"grass", "sand", "swamp"} else terrain_tiles[y][x]
        road_tiles.add((x, y))
        y += 1 if ty > y else -1
    road_tiles.add((tx, ty))


def _nearest_road(road_tiles: set[tuple[int, int]], position: tuple[int, int]) -> tuple[int, int]:
    px, py = position
    return min(road_tiles, key=lambda item: abs(item[0] - px) + abs(item[1] - py))


def _building_order(building_templates: dict[str, dict[str, Any]], focus: list[str]) -> list[str]:
    priority = [
        "town_hall",
        "market_stall",
        "tavern",
        "blacksmith",
        "temple",
        "guard_post",
        "library",
        "alchemist",
        "bakery",
        "stable",
        "warehouse",
        "jail",
        "house",
        "house",
        "house",
        "house",
        "house",
    ]
    available = set(building_templates)
    ordered: list[str] = []
    for token in focus:
        mapped = {
            "market": "market_stall",
            "forge": "blacksmith",
            "archive": "library",
            "grove": "temple",
            "fabrication": "alchemist",
            "hangar": "stable",
            "sensorium": "library",
            "fortification": "guard_post",
        }.get(token, "")
        if mapped and mapped in available and mapped not in ordered:
            ordered.append(mapped)
    for kind in priority:
        if kind in available:
            ordered.append(kind)
    return ordered


def generate_settlement_layout(world: WorldBlueprint, region_id: str) -> SettlementLayout:
    region = _region_lookup(world, region_id)
    settlement = next((item for item in world.settlements if item.region_id == region_id), None)
    if settlement is None:
        raise ValueError(f"Region {region_id} has no settlement")

    seed = stable_seed_from_parts(world.seed, "settlement", region_id)
    rng = random.Random(seed)
    width, height = 80, 60
    ground = _ground_for_biome(region["biome_id"])
    terrain_tiles = [[ground for _ in range(width)] for _ in range(height)]
    road_tiles: set[tuple[int, int]] = set()
    main_road_y: dict[int, int] = {}

    def road_at(x: int, y: int, kind: str = "dirt_path") -> None:
        if 0 <= x < width and 0 <= y < height:
            terrain_tiles[y][x] = kind
            road_tiles.add((x, y))

    y = 30 + rng.choice([-1, 0, 1])
    for x in range(4, width - 4):
        if x % 6 == 0:
            y = max(18, min(height - 18, y + rng.choice([-1, 0, 1])))
        main_road_y[x] = y
        road_at(x, y)
        road_at(x, y + 1)

    square_x0, square_y0 = 36, 25
    _carve_square(terrain_tiles, square_x0, square_y0, 10, 10, "cobblestone")
    for y_index in range(square_y0, square_y0 + 10):
        for x_index in range(square_x0, square_x0 + 10):
            road_tiles.add((x_index, y_index))

    center_kind = "fountain" if region["biome_id"] == "coast" else "well"
    center_feature = {"kind": center_kind, "x": 40, "y": 30}

    branch_xs = [12, 22, 32, 48, 58, 68]
    for index, branch_x in enumerate(branch_xs):
        branch_y = main_road_y.get(branch_x, 30)
        target_y = 10 if index % 2 == 0 else height - 11
        step = -1 if target_y < branch_y else 1
        for cursor_y in range(branch_y, target_y + step, step):
            road_at(branch_x, cursor_y, "cobblestone" if abs(branch_x - 40) < 8 else "dirt_path")
            if index % 3 == 0 and branch_x + 1 < width:
                road_at(branch_x + 1, cursor_y)

    building_templates = load_building_templates()
    desired_kinds = _building_order(building_templates, list(settlement.building_focus))
    plot_candidates: list[tuple[int, int, str]] = []
    for x in range(8, width - 12, 6):
        if x not in main_road_y:
            continue
        road_y = main_road_y[x]
        plot_candidates.append((x - 4, road_y - 11, "south"))
        plot_candidates.append((x - 4, road_y + 3, "north"))
    for branch_x in branch_xs:
        for y_index in range(8, height - 12, 9):
            plot_candidates.append((branch_x - 10, y_index, "east"))
            plot_candidates.append((branch_x + 2, y_index, "west"))

    buildings: list[dict[str, Any]] = []
    furniture: list[dict[str, Any]] = []
    used_candidates: set[int] = set()
    building_index = 0

    for kind in desired_kinds:
        template = building_templates[kind]
        bw, bh = [int(value) for value in template["footprint"]]
        for candidate_index, (cx, cy, road_side) in enumerate(plot_candidates):
            if candidate_index in used_candidates:
                continue
            x = max(3, min(width - bw - 3, cx))
            y0 = max(3, min(height - bh - 3, cy))
            if not _can_place(buildings, x, y0, bw, bh, width, height):
                continue
            door_x, door_y, adjacent = _door_for_plot(x, y0, bw, bh, road_side)
            nearest = _nearest_road(road_tiles, adjacent)
            building_id = f"{kind}_{building_index}"
            building_index += 1
            floor_kind = str(template.get("floor_kind", "wood_floor" if kind in {"house", "tavern", "bakery", "stable"} else "stone_floor"))
            building = {
                "id": building_id,
                "kind": kind,
                "label": kind.replace("_", " ").title(),
                "x": x,
                "y": y0,
                "width": bw,
                "height": bh,
                "wall_material": str(template.get("wall_material", "stone")),
                "floor_kind": floor_kind,
                "doors": [{"x": door_x, "y": door_y, "adjacent": [adjacent], "faces": road_side}],
                "required_furniture": [item["kind"] for item in template["required_furniture"]],
                "npc_roles": list(template.get("npc_roles", [])),
            }
            buildings.append(building)
            _place_building_tiles(terrain_tiles, building)
            _connect_to_road(terrain_tiles, road_tiles, adjacent, nearest)
            for item in template["required_furniture"]:
                furniture.append(
                    {
                        "id": f"{building_id}_{item['kind']}_{len(furniture)}",
                        "kind": item["kind"],
                        "x": x + int(item["anchor"][0]),
                        "y": y0 + int(item["anchor"][1]),
                        "building_id": building_id,
                        "interaction_type": item.get("interaction_type", "examine"),
                    }
                )
            used_candidates.add(candidate_index)
            break
        if len(buildings) >= 13 and kind == "house":
            break

    for dx, dy, kind in [(-2, 0, "bench"), (2, 0, "bench"), (0, -2, "crate"), (0, 2, "barrel")]:
        fx = int(center_feature["x"]) + dx
        fy = int(center_feature["y"]) + dy
        if 0 <= fx < width and 0 <= fy < height:
            furniture.append(
                {
                    "id": f"square_{kind}_{fx}_{fy}",
                    "kind": kind,
                    "x": fx,
                    "y": fy,
                    "building_id": None,
                    "interaction_type": "examine",
                }
            )

    npc_spawns = generate_npc_population(
        settlement_id=settlement.id,
        buildings=buildings,
        center_feature=center_feature,
        seed=seed,
        population_hint=int(settlement.population),
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
