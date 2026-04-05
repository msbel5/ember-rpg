"""Deterministic NPC population helpers for settlement layouts."""

from __future__ import annotations

import copy
import random
from typing import Any

from .registries import load_authored_npc_location_index, load_npc_templates
from .world_seed import stable_seed_from_parts

_COASTAL_AUTHORED_LOCATIONS = {"harbor_town", "river_port", "coastal_fort", "cliff_city"}
_MOUNTAIN_AUTHORED_LOCATIONS = {"mining_camp", "mountain_hold"}
_ROLE_FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
    "smith": ("blacksmith", "smith", "miner"),
    "innkeeper": ("innkeeper",),
    "bard": ("bard",),
    "merchant": ("merchant", "quartermaster", "ferryman"),
    "priest": ("priest", "healer"),
    "guard": ("guard", "magistrate", "jailer"),
    "resident": ("resident", "commoner", "worker"),
    "mayor": ("mayor", "magistrate"),
    "scribe": ("scribe", "sage"),
    "alchemist": ("alchemist", "healer", "witch", "sage"),
    "baker": ("baker", "commoner"),
    "stablehand": ("stablehand", "commoner", "ranger", "scout"),
    "quartermaster": ("quartermaster", "merchant"),
    "jailer": ("jailer", "guard", "magistrate"),
}
_RUNTIME_NPC_PASSTHROUGH_KEYS = (
    "location_id",
    "named_npc_id",
    "identity_source",
    "memory_id",
    "authored_role",
    "authored_location_id",
    "faction_alignment",
    "personality",
    "dialogue_snippets",
    "relationship_modifiers",
)


def _role_template(role: str) -> dict[str, Any]:
    templates = load_npc_templates()
    return templates.get(role) or templates["resident"]


def _role_family_candidates(role: str) -> tuple[str, ...]:
    normalized = str(role).strip().lower()
    aliases = _ROLE_FAMILY_ALIASES.get(normalized)
    if aliases:
        return aliases
    return (normalized,)


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


def _role_demand(buildings: list[dict[str, Any]], population_hint: int) -> dict[str, int]:
    demand: dict[str, int] = {}
    slot_count = 0
    for building in buildings:
        roles = list(building.get("npc_roles", []))
        if not roles and building["kind"] == "house":
            roles = ["resident"]
        for role in roles:
            normalized = str(role).strip().lower()
            demand[normalized] = demand.get(normalized, 0) + 1
            slot_count += 1
    desired_population = max(10, min(16, max(2, population_hint // 24)))
    extra_residents = max(0, desired_population - slot_count)
    if extra_residents > 0:
        demand["resident"] = demand.get("resident", 0) + extra_residents
    return demand


def _choose_authored_location_id(
    *,
    settlement_id: str,
    buildings: list[dict[str, Any]],
    center_feature: dict[str, Any],
    seed: int,
    population_hint: int,
) -> str | None:
    location_index = load_authored_npc_location_index()
    if not location_index:
        return None
    demand = _role_demand(buildings, population_hint)
    best_location_id: str | None = None
    best_score: tuple[float, float, str] | None = None
    for location_id, role_map in location_index.items():
        covered_slots = 0
        missing_slots = 0
        for role, count in demand.items():
            available = sum(len(role_map.get(candidate, ())) for candidate in set(_role_family_candidates(role)))
            covered_slots += min(available, count)
            missing_slots += max(0, count - available)
        if covered_slots <= 0:
            continue
        heuristic = float(covered_slots * 10 - missing_slots * 3)
        if str(center_feature.get("kind", "")).strip().lower() == "fountain":
            heuristic += 2.5 if location_id in _COASTAL_AUTHORED_LOCATIONS else -0.5
        elif location_id in _COASTAL_AUTHORED_LOCATIONS:
            heuristic -= 1.0
        if demand.get("smith") or demand.get("quartermaster"):
            if location_id in _MOUNTAIN_AUTHORED_LOCATIONS:
                heuristic += 1.25
        tiebreak = float(stable_seed_from_parts(seed, settlement_id, location_id, population_hint) % 10000) / 10000.0
        score = (heuristic, tiebreak, location_id)
        if best_score is None or score > best_score:
            best_location_id = location_id
            best_score = score
    return best_location_id


def _authored_candidates_for_role(
    *,
    requested_role: str,
    location_id: str | None = None,
) -> list[dict[str, Any]]:
    role_candidates = set(_role_family_candidates(requested_role))
    location_index = load_authored_npc_location_index()
    if location_id:
        role_map = location_index.get(str(location_id).strip().lower(), {})
        candidates: list[dict[str, Any]] = []
        for role in sorted(role_candidates):
            for npc in role_map.get(role, ()):
                candidates.append(dict(npc))
        return candidates

    candidates_by_id: dict[str, dict[str, Any]] = {}
    for role_map in location_index.values():
        for role in role_candidates:
            for npc in role_map.get(role, ()):
                npc_id = str(npc.get("id", "")).strip()
                if npc_id and npc_id not in candidates_by_id:
                    candidates_by_id[npc_id] = dict(npc)
    return list(candidates_by_id.values())


def _authored_npc_for_role(
    *,
    settlement_id: str,
    requested_role: str,
    used_authored_ids: set[str],
    location_id: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        npc
        for npc in _authored_candidates_for_role(requested_role=requested_role, location_id=location_id)
        if str(npc.get("id", "")).strip() and str(npc.get("id", "")).strip() not in used_authored_ids
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            stable_seed_from_parts(
                settlement_id,
                requested_role,
                location_id or "",
                str(item.get("id", "")),
            ),
            str(item.get("id", "")),
        ),
    )


def _schedule_anchor(entries: list[dict[str, Any]], hour: int) -> dict[str, Any]:
    if not entries:
        return {"position": [0, 0], "activity": "idle", "building_kind": "unknown"}
    chosen = dict(entries[0])
    for entry in entries:
        if int(entry.get("hour", 0)) <= int(hour) % 24:
            chosen = dict(entry)
    return chosen


def _authored_schedule_entries(
    authored_schedule: list[dict[str, Any]],
    fallback_schedule: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not authored_schedule:
        return [dict(entry) for entry in fallback_schedule]
    entries: list[dict[str, Any]] = []
    ordered = sorted(authored_schedule, key=lambda item: int(item.get("hour", 0)))
    for authored_entry in ordered:
        anchor = _schedule_anchor(fallback_schedule, int(authored_entry.get("hour", 0)))
        entry = {
            "hour": int(authored_entry.get("hour", 0)),
            "position": list(anchor.get("position", [0, 0])),
            "activity": str(authored_entry.get("activity", anchor.get("activity", "idle"))),
            "building_kind": str(anchor.get("building_kind", "unknown")),
        }
        location = str(authored_entry.get("location", "")).strip().lower()
        if location:
            entry["location"] = location
        entries.append(entry)
    return entries


def _spawn_payload(
    *,
    settlement_id: str,
    building: dict[str, Any],
    role: str,
    role_index: int,
    home_building: dict[str, Any],
    home_anchor: tuple[int, int],
    work_position: tuple[int, int],
    leisure: tuple[int, int],
    rng: random.Random,
    authored_npc: dict[str, Any] | None,
    authored_location_id: str | None,
) -> dict[str, Any]:
    template = _role_template(role)
    base_schedule = _schedule_entries(home_anchor, work_position, leisure, str(template.get("activity", "work")))
    inventory = _build_inventory(role, rng)
    context_actions = _context_actions(role)
    npc_id = f"{settlement_id}_{building['id']}_{role}_{role_index}"
    location_id = authored_location_id or settlement_id
    payload = {
        "id": npc_id,
        "role": role,
        "template": str(template.get("sprite_template", role)).strip().lower(),
        "x": work_position[0],
        "y": work_position[1],
        "building_id": building["id"],
        "home_building_id": home_building["id"],
        "work_building_id": building["id"],
        "inventory": inventory,
        "context_actions": context_actions,
        "disposition": "friendly",
        "location_id": location_id,
    }
    if authored_npc is None:
        given = rng.choice(template.get("first_names", ["Ari", "Bren", "Cora"]))
        family = rng.choice(template.get("surnames", ["Vale", "Thorn", "Drift"]))
        payload.update(
            {
                "name": f"{given} {family}",
                "schedule": base_schedule,
                "traits": _build_traits(role, rng),
                "named_npc_id": None,
                "identity_source": "generated",
                "memory_id": npc_id,
            }
        )
        return payload

    personality = dict(authored_npc.get("personality", {}))
    named_npc_id = str(authored_npc.get("id", "")).strip() or None
    payload.update(
        {
            "name": str(authored_npc.get("name", npc_id)),
            "schedule": _authored_schedule_entries(list(authored_npc.get("schedule", [])), base_schedule),
            "traits": sorted({str(item) for item in list(personality.get("traits", [])) if str(item).strip()}),
            "named_npc_id": named_npc_id,
            "identity_source": "authored",
            "memory_id": named_npc_id or npc_id,
            "authored_role": str(authored_npc.get("role", role)).strip().lower(),
            "authored_location_id": authored_location_id,
            "faction_alignment": str(authored_npc.get("faction_alignment", "")).strip().lower(),
            "personality": copy.deepcopy(personality),
            "dialogue_snippets": copy.deepcopy(dict(authored_npc.get("dialogue_snippets", {}))),
            "relationship_modifiers": copy.deepcopy(dict(authored_npc.get("relationship_modifiers", {}))),
        }
    )
    return payload


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
    authored_location_id = _choose_authored_location_id(
        settlement_id=settlement_id,
        buildings=buildings,
        center_feature=center_feature,
        seed=seed,
        population_hint=population_hint,
    )
    used_authored_ids: set[str] = set()
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
            authored_npc = None
            if role != "resident":
                authored_npc = _authored_npc_for_role(
                    settlement_id=settlement_id,
                    requested_role=role,
                    used_authored_ids=used_authored_ids,
                    location_id=authored_location_id,
                )
            if authored_npc is not None and authored_npc.get("id"):
                used_authored_ids.add(str(authored_npc["id"]))
            npcs.append(
                _spawn_payload(
                    settlement_id=settlement_id,
                    building=building,
                    role=role,
                    role_index=role_index,
                    home_building=home_building,
                    home_anchor=home_anchor,
                    work_position=work_position,
                    leisure=leisure,
                    rng=rng,
                    authored_npc=authored_npc,
                    authored_location_id=authored_location_id,
                )
            )

    desired_population = max(10, min(16, max(2, population_hint // 24)))
    resident_counter = 0
    while len(npcs) < desired_population and houses:
        home_building = houses[resident_counter % len(houses)]
        home_anchor = _interior_anchor(home_building, resident_counter % 3)
        npcs.append(
            _spawn_payload(
                settlement_id=settlement_id,
                building=home_building,
                role="resident",
                role_index=resident_counter,
                home_building=home_building,
                home_anchor=home_anchor,
                work_position=home_anchor,
                leisure=leisure_target,
                rng=rng,
                authored_npc=None,
                authored_location_id=authored_location_id,
            )
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
        state = {
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
        for key in _RUNTIME_NPC_PASSTHROUGH_KEYS:
            if key in npc:
                state[key] = copy.deepcopy(npc.get(key))
        runtime.append(state)
    return runtime


__all__ = ["generate_npc_population", "runtime_npc_state"]
