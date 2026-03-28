"""Procedural quest offer generation from deterministic world state."""

from __future__ import annotations

import random
from typing import Any

from .registries import load_quest_templates
from .world_seed import stable_seed_from_parts


def _pick_giver(npcs: list[dict[str, Any]], preferred_roles: list[str]) -> dict[str, Any] | None:
    for role in preferred_roles:
        for npc in npcs:
            if npc.get("role") == role:
                return npc
    return npcs[0] if npcs else None


def _reward_for(kind: str, severity: float, rng: random.Random) -> tuple[int, int]:
    base_gold = {
        "fetch": 25,
        "kill": 55,
        "escort": 45,
        "deliver": 30,
        "investigate": 35,
        "defend": 65,
    }.get(kind, 25)
    base_xp = {
        "fetch": 35,
        "kill": 70,
        "escort": 55,
        "deliver": 40,
        "investigate": 50,
        "defend": 80,
    }.get(kind, 35)
    scale = 1.0 + severity * 0.7
    return (int(base_gold * scale) + rng.randint(0, 12), int(base_xp * scale) + rng.randint(0, 16))


def generate_quest_offers(
    *,
    world_seed: int,
    region: dict[str, Any],
    settlement_state: dict[str, Any],
    npcs: list[dict[str, Any]],
    day: int,
    limit: int = 6,
) -> list[dict[str, Any]]:
    templates = load_quest_templates()
    rng = random.Random(stable_seed_from_parts(world_seed, "quest", region["id"], day))
    economy = settlement_state.get("economy", {})
    resources = economy.get("resources", {})
    alerts = list(settlement_state.get("alerts", []))
    needs = settlement_state.get("needs", {})
    fauna = list(region.get("fauna", []))

    candidate_specs: list[tuple[str, dict[str, Any], float]] = [
        ("defend", {"target": fauna[0] if fauna else "raiders"}, 0.9 if "bandit_raid" in alerts else 0.5),
        ("kill", {"target": fauna[0] if fauna else "wolves"}, 0.7 if fauna else 0.45),
        ("deliver", {"resource": "food"}, 0.6 if int(resources.get("food", 0)) < 40 else 0.35),
        ("fetch", {"resource": "ore"}, 0.55 if int(resources.get("ore", 0)) < 28 else 0.3),
        ("investigate", {"site": region.get("biome_id", "the outskirts")}, 0.5),
        ("escort", {"destination": settlement_state.get("name", "the next outpost")}, 0.45),
    ]

    offers: list[dict[str, Any]] = []
    for index, (kind, payload, severity) in enumerate(candidate_specs):
        template = templates[kind]
        giver = _pick_giver(npcs, list(template.get("preferred_roles", [])))
        gold, xp = _reward_for(kind, severity + float(needs.get("security", 1)) * 0.03, rng)
        giver_name = giver.get("name", "Settlement Contact") if giver else "Settlement Contact"
        giver_entity_id = giver.get("id", "") if giver else ""
        title = str(template["title"]).format(**payload)
        description = str(template["description"]).format(**payload, settlement_name=settlement_state.get("name", "the settlement"))
        offers.append(
            {
                "id": f"{region['id']}_{kind}_{day}_{index}",
                "quest_id": f"{region['id']}_{kind}_{day}_{index}",
                "title": title,
                "description": description,
                "kind": kind,
                "status": "available",
                "giver_entity_id": giver_entity_id,
                "giver_name": giver_name,
                "reward_gold": gold,
                "reward_xp": xp,
                "deadline": day * 24 + 24 + index * 6,
            }
        )
        if len(offers) >= limit:
            break
    return offers
