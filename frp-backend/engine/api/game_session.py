"""Compatibility wrapper for the focused GameSession package."""

from engine.api.session import (
    DEFAULT_EQUIPMENT_SLOTS,
    GameSession,
    LEGACY_SLOT_ALIASES,
    TIMED_CONDITION_NAMES,
)

__all__ = [
    "DEFAULT_EQUIPMENT_SLOTS",
    "GameSession",
    "LEGACY_SLOT_ALIASES",
    "TIMED_CONDITION_NAMES",
]
