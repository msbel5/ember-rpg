"""Authored-NPC selection helpers for settlement population generation."""

from __future__ import annotations

from typing import Any

from .registries import load_authored_npc_location_index
from .world_seed import stable_seed_from_parts

COASTAL_AUTHORED_LOCATIONS = {"harbor_town", "river_port", "coastal_fort", "cliff_city"}
MOUNTAIN_AUTHORED_LOCATIONS = {"mining_camp", "mountain_hold"}
ROLE_FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
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


def role_family_candidates(role: str) -> tuple[str, ...]:
    normalized = str(role).strip().lower()
    aliases = ROLE_FAMILY_ALIASES.get(normalized)
    if aliases:
        return aliases
    return (normalized,)


def choose_authored_location_id(
    *,
    settlement_id: str,
    buildings: list[dict[str, Any]],
    center_feature: dict[str, Any],
    seed: int,
    population_hint: int,
    role_demand: dict[str, int],
) -> str | None:
    location_index = load_authored_npc_location_index()
    if not location_index:
        return None
    best_location_id: str | None = None
    best_score: tuple[float, float, str] | None = None
    for location_id, role_map in location_index.items():
        covered_slots = 0
        missing_slots = 0
        for role, count in role_demand.items():
            available = sum(len(role_map.get(candidate, ())) for candidate in set(role_family_candidates(role)))
            covered_slots += min(available, count)
            missing_slots += max(0, count - available)
        if covered_slots <= 0:
            continue
        heuristic = float(covered_slots * 10 - missing_slots * 3)
        if str(center_feature.get("kind", "")).strip().lower() == "fountain":
            heuristic += 2.5 if location_id in COASTAL_AUTHORED_LOCATIONS else -0.5
        elif location_id in COASTAL_AUTHORED_LOCATIONS:
            heuristic -= 1.0
        if role_demand.get("smith") or role_demand.get("quartermaster"):
            if location_id in MOUNTAIN_AUTHORED_LOCATIONS:
                heuristic += 1.25
        tiebreak = float(stable_seed_from_parts(seed, settlement_id, location_id, population_hint) % 10000) / 10000.0
        score = (heuristic, tiebreak, location_id)
        if best_score is None or score > best_score:
            best_location_id = location_id
            best_score = score
    return best_location_id


def authored_npc_for_role(
    *,
    settlement_id: str,
    requested_role: str,
    used_authored_ids: set[str],
    location_id: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        npc
        for npc in authored_candidates_for_role(requested_role=requested_role, location_id=location_id)
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


def authored_candidates_for_role(
    *,
    requested_role: str,
    location_id: str | None = None,
) -> list[dict[str, Any]]:
    role_candidates = set(role_family_candidates(requested_role))
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


__all__ = [
    "authored_npc_for_role",
    "choose_authored_location_id",
    "role_family_candidates",
]
