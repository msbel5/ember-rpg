"""Focused GameSession package."""

from .constants import DEFAULT_EQUIPMENT_SLOTS, LEGACY_SLOT_ALIASES, TIMED_CONDITION_NAMES
from .core import GameSession

__all__ = [
    "DEFAULT_EQUIPMENT_SLOTS",
    "GameSession",
    "LEGACY_SLOT_ALIASES",
    "TIMED_CONDITION_NAMES",
]
