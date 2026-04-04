"""Focused session package — mixin implementations for CampaignSession.

The canonical session type lives in ``engine.api.campaign_session``.
This package provides the mixin classes and constants that compose it.
"""

from .constants import DEFAULT_EQUIPMENT_SLOTS, LEGACY_SLOT_ALIASES, TIMED_CONDITION_NAMES

__all__ = [
    "DEFAULT_EQUIPMENT_SLOTS",
    "LEGACY_SLOT_ALIASES",
    "TIMED_CONDITION_NAMES",
]
