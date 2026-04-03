"""Data loader for externalized game constants.

Loads materials, quality tiers, and other game data from JSON files
in the data/ directory. No hardcoded game constants should exist in
kernel Python code -- everything comes from data files.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from engine.kernel.actor_items import MaterialDef

# Path to the data directory relative to the backend root.
_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"

# In-memory cache (loaded once per process).
_cache: dict[str, Any] = {}


def _load_json(filename: str) -> Any:
    """Load and cache a JSON file from the data directory."""
    if filename in _cache:
        return _cache[filename]
    path = _DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}. "
            f"All game constants must be defined in data/*.json files."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[filename] = data
    return data


def load_materials() -> dict[str, MaterialDef]:
    """Load all material definitions from data/materials.json."""
    raw = _load_json("materials.json")
    result: dict[str, MaterialDef] = {}
    for mat_id, entry in raw.items():
        result[mat_id] = MaterialDef(
            material_id=str(entry["material_id"]),
            label=str(entry["label"]),
            category=str(entry.get("category", "unknown")),
            density=float(entry.get("density", 1.0)),
            impact_yield=int(entry.get("impact_yield", 100)),
            impact_fracture=int(entry.get("impact_fracture", 200)),
            shear_yield=int(entry.get("shear_yield", 100)),
            shear_fracture=int(entry.get("shear_fracture", 200)),
            max_edge=int(entry.get("max_edge", 50)),
            tags=list(entry.get("tags", [])),
        )
    return result


def load_quality_tiers() -> dict[int, float]:
    """Load quality tier multipliers from data/quality_tiers.json."""
    raw = _load_json("quality_tiers.json")
    return {int(k): float(v["multiplier"]) for k, v in raw.items()}


def clear_cache() -> None:
    """Clear the data cache (useful for testing)."""
    _cache.clear()


__all__ = [
    "clear_cache",
    "load_materials",
    "load_quality_tiers",
]
