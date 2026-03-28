"""Lightweight deterministic settlement economy simulation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_BASE_PRICES = {
    "food": 10,
    "ore": 18,
    "wood": 12,
    "gold": 1,
}


def _resource_seed(resources: list[str], token: str) -> int:
    return 1 if token in resources else 0


def initialize_region_economy(region: dict[str, Any], settlement: Any) -> dict[str, Any]:
    resources = list(region.get("resources", []))
    population = int(getattr(settlement, "population", 120))
    store = {
        "food": 36 + population // 3 + _resource_seed(resources, "grain") * 30 + _resource_seed(resources, "fish") * 18,
        "ore": 18 + _resource_seed(resources, "iron") * 26 + _resource_seed(resources, "copper") * 14,
        "wood": 20 + _resource_seed(resources, "timber") * 34 + _resource_seed(resources, "driftwood") * 8,
        "gold": 90 + population // 2,
    }
    return {
        "resources": store,
        "prices": _reprice(store),
        "trade_routes": _trade_routes(region, resources),
        "scarcity": _scarcity(store),
    }


def _trade_routes(region: dict[str, Any], resources: list[str]) -> list[dict[str, Any]]:
    routes = []
    if region.get("water_access") == "coast":
        routes.append({"kind": "harbor", "bonus": "food"})
    if "iron" in resources or "copper" in resources:
        routes.append({"kind": "ore_road", "bonus": "ore"})
    if "timber" in resources:
        routes.append({"kind": "logging_track", "bonus": "wood"})
    if not routes:
        routes.append({"kind": "wagon_route", "bonus": "food"})
    return routes


def _scarcity(resources: dict[str, int]) -> dict[str, float]:
    return {
        key: round(1.0 - min(amount / max({"food": 90, "ore": 60, "wood": 70, "gold": 140}[key], 1), 1.0), 3)
        for key, amount in resources.items()
    }


def _reprice(resources: dict[str, int]) -> dict[str, int]:
    prices: dict[str, int] = {}
    scarcity = _scarcity(resources)
    for key, base in _BASE_PRICES.items():
        modifier = 1.0 + scarcity[key] * 1.4
        prices[key] = max(1, int(round(base * modifier)))
    return prices


def tick_region_economy(economy_state: dict[str, Any], hours: int, weather: dict[str, Any], population: int) -> dict[str, Any]:
    state = deepcopy(economy_state)
    resources = state.get("resources", {})
    rainfall = float(weather.get("rainfall", 0.0))
    severe = bool(weather.get("severe", False))
    resources["food"] = max(0, int(resources.get("food", 0) + (2 if rainfall > 0.45 else 1) - max(1, population // 70) * max(hours, 1)))
    resources["ore"] = max(0, int(resources.get("ore", 0) + (1 if not severe else 0) * max(1, hours // 6)))
    resources["wood"] = max(0, int(resources.get("wood", 0) + max(1, hours // 8) - (1 if severe else 0)))
    resources["gold"] = max(0, int(resources.get("gold", 0) + max(1, hours) + resources["ore"] // 12))
    state["resources"] = resources
    state["prices"] = _reprice(resources)
    state["scarcity"] = _scarcity(resources)
    return state
