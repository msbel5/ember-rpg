"""Load institution registries from data."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from engine.data._shared import load_json_path

_INSTITUTIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "institutions.json"


@lru_cache(maxsize=1)
def load_institutions_registry() -> Dict[str, Any]:
    return dict(load_json_path(_INSTITUTIONS_PATH))
