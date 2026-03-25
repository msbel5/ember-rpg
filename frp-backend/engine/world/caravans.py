"""
Caravan system for Ember RPG.
FR-53..FR-56: Trade caravans with routes, schedules, raids.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CaravanRoute:
    """Defines a caravan template."""
    name: str
    origin: str
    destination: str
    goods: Dict[str, int]          # item_id → quantity carried
    travel_hours: int              # hours for one trip
    frequency_hours: int           # hours between departures
    value: int                     # total gold value of cargo


@dataclass
class ActiveCaravan:
    """A caravan currently in transit."""
    caravan_id: str
    route_key: str
    departed_hour: int
    arrival_hour: int
    goods: Dict[str, int]
    raided: bool = False
    delayed_hours: int = 0


CARAVANS: Dict[str, CaravanRoute] = {
    "iron_caravan": CaravanRoute(
        name="Iron Caravan",
        origin="ironhold_mines",
        destination="riverside_market",
        goods={"iron_ore": 40, "coal": 20, "iron_bar": 10},
        travel_hours=8,
        frequency_hours=24,
        value=300,
    ),
    "food_caravan": CaravanRoute(
        name="Food Caravan",
        origin="greenfield_farms",
        destination="riverside_market",
        goods={"grain": 60, "bread": 20, "ale": 15, "herb": 10},
        travel_hours=6,
        frequency_hours=18,
        value=180,
    ),
    "luxury_caravan": CaravanRoute(
        name="Luxury Caravan",
        origin="silverpeak",
        destination="capital_city",
        goods={"silver_bar": 5, "silver_ring": 8, "glass_vial": 20, "cloth": 15},
        travel_hours=12,
        frequency_hours=48,
        value=800,
    ),
}


class CaravanManager:
    """Manages all active caravans and their lifecycle."""

    def __init__(self) -> None:
        self.active: Dict[str, ActiveCaravan] = {}
        self._next_id: int = 1
        # Track last departure hour per route to enforce frequency.
        self._last_departure: Dict[str, int] = {}

    # ── ticking ──────────────────────────────────────────────────────
    def tick(self, game_hour: int) -> List[Dict]:
        """Advance the caravan system by one game-hour tick.

        * Spawns new caravans when their frequency timer elapses.
        * Checks for arrivals.

        Returns a list of event dicts (arrivals / departures).
        """
        events: List[Dict] = []

        # 1. Spawn caravans whose frequency has elapsed.
        for key, route in CARAVANS.items():
            last = self._last_departure.get(key, -route.frequency_hours)
            if game_hour - last >= route.frequency_hours:
                cid = f"caravan_{self._next_id}"
                self._next_id += 1
                ac = ActiveCaravan(
                    caravan_id=cid,
                    route_key=key,
                    departed_hour=game_hour,
                    arrival_hour=game_hour + route.travel_hours,
                    goods=dict(route.goods),
                )
                self.active[cid] = ac
                self._last_departure[key] = game_hour
                events.append({
                    "type": "departure",
                    "caravan_id": cid,
                    "route": key,
                    "hour": game_hour,
                })

        # 2. Check arrivals.
        arrived_ids: List[str] = []
        for cid, ac in self.active.items():
            effective_arrival = ac.arrival_hour + ac.delayed_hours
            if game_hour >= effective_arrival:
                arrived_ids.append(cid)
                events.append({
                    "type": "arrival",
                    "caravan_id": cid,
                    "route": ac.route_key,
                    "destination": CARAVANS[ac.route_key].destination,
                    "goods_delivered": dict(ac.goods),
                    "raided": ac.raided,
                    "hour": game_hour,
                })
        for cid in arrived_ids:
            del self.active[cid]

        return events

    # ── raiding ──────────────────────────────────────────────────────
    def raid_caravan(self, caravan_id: str, loss_fraction: float = 0.5) -> Dict:
        """Raid an active caravan.

        * Delays arrival by 4‑8 hours.
        * Loses *loss_fraction* (default 50 %) of each good.

        Returns a summary dict. Raises ``KeyError`` if id not found.
        """
        ac = self.active[caravan_id]  # KeyError if missing
        delay = random.randint(4, 8)
        ac.delayed_hours += delay
        ac.raided = True

        lost_goods: Dict[str, int] = {}
        for item, qty in ac.goods.items():
            lost = max(1, int(qty * loss_fraction))
            lost_goods[item] = lost
            ac.goods[item] = max(0, qty - lost)

        return {
            "caravan_id": caravan_id,
            "delay_hours": delay,
            "goods_lost": lost_goods,
            "goods_remaining": dict(ac.goods),
        }

    # ── queries ──────────────────────────────────────────────────────
    def get_active_caravans(self) -> List[Dict]:
        return [
            {
                "caravan_id": ac.caravan_id,
                "route": ac.route_key,
                "departed": ac.departed_hour,
                "eta": ac.arrival_hour + ac.delayed_hours,
                "raided": ac.raided,
            }
            for ac in self.active.values()
        ]

    def to_dict(self) -> dict:
        """Serialize caravan manager for save/load."""
        return {
            "next_id": self._next_id,
            "last_departure": dict(self._last_departure),
            "active": {
                cid: {
                    "caravan_id": ac.caravan_id,
                    "route_key": ac.route_key,
                    "departed_hour": ac.departed_hour,
                    "arrival_hour": ac.arrival_hour,
                    "goods": dict(ac.goods),
                    "raided": ac.raided,
                    "delayed_hours": ac.delayed_hours,
                }
                for cid, ac in self.active.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CaravanManager":
        """Deserialize caravan manager from a dict."""
        cm = cls()
        cm._next_id = data.get("next_id", 1)
        cm._last_departure = dict(data.get("last_departure", {}))
        for cid, cd in data.get("active", {}).items():
            cm.active[cid] = ActiveCaravan(
                caravan_id=cd["caravan_id"],
                route_key=cd["route_key"],
                departed_hour=cd["departed_hour"],
                arrival_hour=cd["arrival_hour"],
                goods=dict(cd["goods"]),
                raided=cd.get("raided", False),
                delayed_hours=cd.get("delayed_hours", 0),
            )
        return cm
