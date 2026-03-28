"""Deterministic NPC population helpers for settlement layouts."""

from __future__ import annotations

import random
from typing import Any

from .registries import load_npc_templates


def _role_template(role: str) -> dict[str, Any]:
    templates = load_npc_templates()
    return templates.get(role) or templates["resident"]


def _interior_anchor(building: dict[str, Any], offset: int = 0) -> tuple[int, int]:
    x = int(building["x"])
    y = int(building["y"])
    width = int(building["width"])
    height = int(building["height"])
    return (x + min(2 + offset, max(2, width - 3)), y + max(2, height // 2))


def _schedule_entries(
    home_position: tuple[int, int],
    work_position: tuple[int, int],
    leisure_position: tuple[int, int],
    activity_prefix: str,
) -> list[dict[str, Any]]:
    return [
        {"hour": 0, "position": list(home_position), "activity": "sleep", "building_kind": "home"},
        {"hour": 6, "position": list(home_position), "activity": "wake", "building_kind": "home"},
        {"hour": 8, "position": list(work_position), "activity": f"{activity_prefix}_shift", "building_kind": "work"},
        {"hour": 12, "position": list(leisure_position), "activity": "meal", "building_kind": "leisure"},
        {"hour": 14, "position": list(work_position), "activity": f"{activity_prefix}_shift", "building_kind": "work"},
        {"hour": 18, "position": list(leisure_position), "activity": "socialize", "building_kind": "leisure"},
        {"hour": 21, "position": list(home_position), "activity": "rest", "building_kind": "home"},
    ]


def _build_inventory(role: str, rng: random.Random) -> list[dict[str, Any]]:
    template = _role_template(role)
    items = list(template.get("inventory", []))
    if role == "guard":
        items.append("whistle")
    elif role == "merchant" and rng.random() > 0.4:
        items.append("ledger")
    return [{"name": item.replace("_", " ").title(), "quantity": 1} for item in items]


def _build_traits(role: str, rng: random.Random) -> list[str]:
    template = _role_template(role)
    traits = list(template.get("traits", []))
    if rng.random() > 0.65:
        traits.append(rng.choice(["curious", "wary", "ambitious", "patient"]))
    return sorted(set(traits))


def _context_actions(role: str) -> list[str]:
    template = _role_template(role)
    actions = list(template.get("context_actions", []))
    return actions if actions else ["talk", "examine"]


def generate_npc_population(
    *,
    settlement_id: str,
    buildings: list[dict[str, Any]],
    center_feature: dict[str, Any],
    seed: int,
    population_hint: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    houses = [building for building in buildings if building["kind"] == "house"]
    leisure_target = (int(center_feature["x"]), int(center_feature["y"]) + 1)
    npcs: list[dict[str, Any]] = []
    home_index = 0

    for building in buildings:
        roles = list(building.get("npc_roles", []))
        if not roles and building["kind"] == "house":
            roles = ["resident"]
        for role_index, role in enumerate(roles):
            home_building = houses[home_index % len(houses)] if houses else building
            home_index += 1
            home_anchor = _interior_anchor(home_building, role_index % 2)
            work_position = _interior_anchor(building, role_index)
            if role == "guard":
                leisure = (int(center_feature["x"]) - 2 + (role_index % 4), int(center_feature["y"]) + 3)
            elif role in {"merchant", "innkeeper", "bard"}:
                leisure = (int(center_feature["x"]) + 1 + (role_index % 3), int(center_feature["y"]) - 1)
            else:
                leisure = leisure_target
            template = _role_template(role)
            given = rng.choice(template.get("first_names", ["Ari", "Bren", "Cora"]))
            family = rng.choice(template.get("surnames", ["Vale", "Thorn", "Drift"]))
            npc_id = f"{settlement_id}_{building['id']}_{role}_{role_index}"
            npcs.append(
                {
                    "id": npc_id,
                    "name": f"{given} {family}",
                    "role": role,
                    "template": str(template.get("sprite_template", role)).strip().lower(),
                    "x": work_position[0],
                    "y": work_position[1],
                    "building_id": building["id"],
                    "home_building_id": home_building["id"],
                    "work_building_id": building["id"],
                    "schedule": _schedule_entries(home_anchor, work_position, leisure, str(template.get("activity", "work"))),
                    "traits": _build_traits(role, rng),
                    "inventory": _build_inventory(role, rng),
                    "context_actions": _context_actions(role),
                    "disposition": "friendly",
                }
            )

    desired_population = max(10, min(16, max(2, population_hint // 24)))
    resident_counter = 0
    while len(npcs) < desired_population and houses:
        home_building = houses[resident_counter % len(houses)]
        home_anchor = _interior_anchor(home_building, resident_counter % 3)
        template = _role_template("resident")
        given = rng.choice(template.get("first_names", ["Ari", "Bren", "Cora"]))
        family = rng.choice(template.get("surnames", ["Vale", "Thorn", "Drift"]))
        npcs.append(
            {
                "id": f"{settlement_id}_{home_building['id']}_resident_extra_{resident_counter}",
                "name": f"{given} {family}",
                "role": "resident",
                "template": str(template.get("sprite_template", "resident")).strip().lower(),
                "x": home_anchor[0],
                "y": home_anchor[1],
                "building_id": home_building["id"],
                "home_building_id": home_building["id"],
                "work_building_id": home_building["id"],
                "schedule": _schedule_entries(home_anchor, leisure_target, leisure_target, "household"),
                "traits": _build_traits("resident", rng),
                "inventory": _build_inventory("resident", rng),
                "context_actions": _context_actions("resident"),
                "disposition": "friendly",
            }
        )
        resident_counter += 1
    return npcs


def runtime_npc_state(npcs: list[dict[str, Any]], current_hour: int) -> list[dict[str, Any]]:
    hour_of_day = current_hour % 24
    runtime: list[dict[str, Any]] = []
    for npc in npcs:
        chosen = npc["schedule"][0]
        for entry in npc.get("schedule", []):
            if int(entry.get("hour", 0)) <= hour_of_day:
                chosen = entry
        runtime.append(
            {
                "id": npc["id"],
                "name": npc["name"],
                "role": npc["role"],
                "template": npc.get("template", npc["role"]),
                "x": int(chosen["position"][0]),
                "y": int(chosen["position"][1]),
                "activity": chosen.get("activity", "idle"),
                "building_kind": chosen.get("building_kind", "unknown"),
                "home_building_id": npc.get("home_building_id"),
                "work_building_id": npc.get("work_building_id"),
                "building_id": npc.get("building_id"),
                "schedule": npc.get("schedule", []),
                "traits": list(npc.get("traits", [])),
                "inventory": list(npc.get("inventory", [])),
                "context_actions": list(npc.get("context_actions", ["talk", "examine"])),
                "disposition": npc.get("disposition", "friendly"),
            }
        )
    return runtime
