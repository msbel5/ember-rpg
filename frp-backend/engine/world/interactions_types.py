"""Types shared by the interaction runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, TypeAlias

from engine.world.skill_checks import SkillCheckResult


class InteractionType(Enum):
    TALK = auto()
    TRADE = auto()
    ATTACK = auto()
    EXAMINE = auto()
    PICK_UP = auto()
    OPEN = auto()
    LOCK_PICK = auto()
    FORCE_OPEN = auto()
    CRAFT = auto()
    CLIMB = auto()
    SWIM = auto()
    READ = auto()
    PRAY = auto()
    USE = auto()
    PUSH = auto()
    PULL = auto()
    SEARCH = auto()
    STEAL = auto()
    SNEAK = auto()
    INTIMIDATE = auto()
    PERSUADE = auto()
    BRIBE = auto()
    CHOP = auto()
    MINE = auto()
    FISH = auto()
    DISARM_TRAP = auto()
    SET_TRAP = auto()
    BURY = auto()
    REST = auto()
    DRINK = auto()
    FILL = auto()
    CLOSE = auto()
    FOLLOW = auto()
    HIRE = auto()
    FLEE = auto()
    LOOT = auto()
    KICK = auto()


InteractionRule: TypeAlias = Dict[str, Any]


@dataclass
class InteractionResult:
    """Outcome of performing an interaction."""

    success: bool
    narrative_prompt: str
    skill_check: Optional[SkillCheckResult] = None
    ap_cost: int = 0
    state_changes: Dict[str, Any] = field(default_factory=dict)
