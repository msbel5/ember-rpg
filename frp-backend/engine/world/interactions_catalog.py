"""Load data-driven interaction rules."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple

from engine.data._shared import load_registry_list

from .interactions_types import InteractionRule, InteractionType


@lru_cache(maxsize=1)
def load_interaction_rules() -> Dict[Tuple[str, InteractionType], InteractionRule]:
    rules: Dict[Tuple[str, InteractionType], InteractionRule] = {}
    for entry in load_registry_list("interaction_rules.json"):
        target_type = str(entry["target_type"])
        interaction_type = InteractionType[str(entry["interaction_type"]).upper()]
        rules[(target_type, interaction_type)] = {
            "skill": entry.get("skill"),
            "dc_range": tuple(entry.get("dc_range", [0, 0])),
            "ap_cost": int(entry.get("ap_cost", 0)),
            "requirements": list(entry.get("requirements", [])),
        }
    return rules
