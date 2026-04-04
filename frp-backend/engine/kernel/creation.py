"""Kernel-native character creation facade.

This module preserves the historical `engine.kernel.creation` import path
while delegating catalog/static helpers and stateful creation flow to
focused modules.
"""
from __future__ import annotations

from .creation_catalog import (
    ABILITY_ORDER,
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    DEFAULT_CLASS_ID,
    MECHANICS_VERSION,
    assign_stats_to_class,
    get_creation_catalog,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
    roll_stat_array,
)
from .creation_state import CreationState

__all__ = [
    "ABILITY_ORDER",
    "CLASS_DEFAULT_SKILLS",
    "CLASS_SKILL_COUNTS",
    "CLASS_SKILL_OPTIONS",
    "CreationState",
    "DEFAULT_CLASS_ID",
    "MECHANICS_VERSION",
    "assign_stats_to_class",
    "get_creation_catalog",
    "recommended_alignment_from_axes",
    "recommended_skills_for_class",
    "roll_stat_array",
]
