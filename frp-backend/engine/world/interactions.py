"""Context-sensitive interaction system facade."""
from __future__ import annotations

from typing import Any, Dict, List

from .interactions_catalog import load_interaction_rules
from .interactions_runtime import InteractionHandler as _InteractionHandler
from .interactions_runtime import available_interactions
from .interactions_types import InteractionResult, InteractionRule, InteractionType

INTERACTION_RULES = load_interaction_rules()


def get_available_interactions(
    tile: Dict[str, Any],
    entities_at_tile: List[Dict[str, Any]],
    player: Dict[str, Any],
) -> List[InteractionType]:
    return available_interactions(tile, entities_at_tile, player, INTERACTION_RULES)


class InteractionHandler(_InteractionHandler):
    def __init__(self):
        super().__init__(INTERACTION_RULES)


__all__ = [
    "INTERACTION_RULES",
    "InteractionHandler",
    "InteractionResult",
    "InteractionRule",
    "InteractionType",
    "get_available_interactions",
]
