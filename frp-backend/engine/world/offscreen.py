"""
Offscreen simulation for Ember RPG.
FR-50..FR-52: Coarse-grained ticks for locations the player is not visiting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Re-use LocationStock from economy if available.
# The functions here operate on duck-typed stock objects or plain dicts.


def coarse_tick(
    location_stock: Dict[str, int],
    hours: int,
    consumption_rate: float = 0.02,
    needs_decay_rate: float = 0.5,
) -> Dict[str, Any]:
    """Simulate *hours* of offscreen activity at a location.

    Rules (per hour):
    - Every item stock is multiplied by ``(1 - consumption_rate)``
      (default 0.98 ≈ 2 % consumption per hour).
    - ``"needs"`` field (if present) decays by *needs_decay_rate* per hour
      (i.e. needs become less urgent when player is away — simplified).
    - No combat resolution happens offscreen.

    *location_stock* is mutated **in-place** and also returned.
    Returns dict with ``stock`` (the mutated dict) and ``hours_simulated``.
    """
    hours = max(0, hours)
    for _ in range(hours):
        for key in list(location_stock.keys()):
            if key == "needs":
                # Needs decay toward 0 (less urgent while player is away).
                val = location_stock[key]
                if isinstance(val, (int, float)):
                    location_stock[key] = round(val * (1 - needs_decay_rate), 4)
                continue
            val = location_stock[key]
            if isinstance(val, (int, float)):
                new_val = val * (1 - consumption_rate)
                location_stock[key] = int(new_val) if isinstance(val, int) else round(new_val, 4)

    return {"stock": location_stock, "hours_simulated": hours}


def catch_up_location(
    location: Dict[str, int],
    hours_away: int,
    cap: int = 72,
    consumption_rate: float = 0.02,
    needs_decay_rate: float = 0.5,
) -> Dict[str, Any]:
    """Run offscreen simulation for *hours_away*, capped at *cap* hours.

    This is the main entry-point called when the player returns to a location.
    Caps the simulation to avoid runaway loops for very long absences.
    """
    effective_hours = min(max(0, hours_away), cap)
    result = coarse_tick(
        location,
        effective_hours,
        consumption_rate=consumption_rate,
        needs_decay_rate=needs_decay_rate,
    )
    result["hours_requested"] = hours_away
    result["capped"] = hours_away > cap
    return result
