"""
Skill check system for Ember RPG.
FR-14..FR-16: d20 + ability modifier vs DC, contested checks, critical hits.

Based on PRD section 7: Non-Combat Skill Checks.
Ability modifier formula: (score - 10) // 2  (D&D-style).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Literal, Tuple


# ── Ability definitions ──────────────────────────────────────────────

ABILITIES: Dict[str, str] = {
    "MIG": "Might — break doors, bend bars, lift heavy objects, intimidate, grapple",
    "AGI": "Agility — pick locks, disarm traps, sneak, dodge, climb, balance, sleight of hand",
    "END": "Endurance — resist poison, hold breath, forced march, drink contest, survive cold",
    "MND": "Mind — identify magic items, recall lore, read ancient script, appraise value",
    "INS": "Insight — detect lies, spot hidden, track creatures, sense danger, medicine",
    "PRE": "Presence — persuade, bluff, haggle prices, inspire, calm animal, seduce",
}

# ── DC difficulty bands ──────────────────────────────────────────────

_DC_BANDS: list[Tuple[int, str]] = [
    (5, "trivial"),
    (8, "easy"),
    (12, "medium"),
    (15, "hard"),
    (20, "very hard"),
    (999, "nearly impossible"),
]


def get_dc_description(dc: int) -> str:
    """Return a human-readable difficulty label for a given DC value."""
    for threshold, label in _DC_BANDS:
        if dc <= threshold:
            return label
    return "nearly impossible"


# ── Modifier calculation ─────────────────────────────────────────────

def ability_modifier(score: int) -> int:
    """Compute the ability modifier from a raw ability score.

    Uses the D&D formula: (score - 10) // 2.
    A score of 10-11 yields +0, 12-13 yields +1, 8-9 yields -1, etc.
    """
    return (score - 10) // 2


# ── Skill check result ───────────────────────────────────────────────

@dataclass(frozen=True)
class SkillCheckResult:
    """Immutable outcome of a single d20 skill check."""
    roll: int             # Raw d20 result (1-20)
    modifier: int         # Ability modifier applied
    total: int            # roll + modifier
    dc: int               # Difficulty class that was tested against
    success: bool         # total >= dc (or critical override)
    margin: int           # total - dc (positive = beat, negative = failed by)
    critical: Literal["success", "failure", None]  # nat 20 / nat 1
    advantage: bool = False
    disadvantage: bool = False
    rolls: Tuple[int, ...] = ()


def passive_score(
    ability_score: int,
    *,
    proficiency_bonus: int = 0,
    expertise: bool = False,
    modifier_bonus: int = 0,
) -> int:
    """Compute passive score using D&D's 10 + modifiers formula."""
    prof = proficiency_bonus * 2 if expertise else proficiency_bonus
    return 10 + ability_modifier(ability_score) + prof + modifier_bonus


def roll_d20(
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    _rng: random.Random | None = None,
) -> Tuple[int, Tuple[int, ...]]:
    """Roll a d20 with optional advantage/disadvantage."""
    rng = _rng or random.Random()
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    if advantage or disadvantage:
        rolls = (rng.randint(1, 20), rng.randint(1, 20))
        return (max(rolls), rolls) if advantage else (min(rolls), rolls)

    roll = rng.randint(1, 20)
    return roll, (roll,)


# ── Core roll function ───────────────────────────────────────────────

def roll_check(
    ability_score: int,
    dc: int,
    *,
    proficiency_bonus: int = 0,
    expertise: bool = False,
    modifier_bonus: int = 0,
    advantage: bool = False,
    disadvantage: bool = False,
    auto_crit: bool = True,
    _rng: random.Random | None = None,
) -> SkillCheckResult:
    """Roll a d20 + ability modifier against a DC.

    Parameters
    ----------
    ability_score : int
        The raw ability score (e.g. 14 for a decent stat).
    dc : int
        The difficulty class to beat.
    _rng : random.Random, optional
        Injectable RNG for deterministic testing.

    Returns
    -------
    SkillCheckResult
    """
    rng = _rng or random.Random()
    roll, rolls = roll_d20(
        advantage=advantage,
        disadvantage=disadvantage,
        _rng=rng,
    )
    prof = proficiency_bonus * 2 if expertise else proficiency_bonus
    mod = ability_modifier(ability_score) + prof + modifier_bonus
    total = roll + mod

    # Determine critical status
    critical: Literal["success", "failure", None] = None
    if auto_crit and roll == 20:
        critical = "success"
    elif auto_crit and roll == 1:
        critical = "failure"

    # Nat 20 always succeeds, nat 1 always fails, else compare total vs dc
    if critical == "success":
        success = True
    elif critical == "failure":
        success = False
    else:
        success = total >= dc

    margin = total - dc

    return SkillCheckResult(
        roll=roll,
        modifier=mod,
        total=total,
        dc=dc,
        success=success,
        margin=margin,
        critical=critical,
        advantage=advantage and not disadvantage,
        disadvantage=disadvantage and not advantage,
        rolls=rolls,
    )


# ── Contested check ──────────────────────────────────────────────────

def contested_check(
    score_a: int,
    score_b: int,
    *,
    proficiency_bonus_a: int = 0,
    proficiency_bonus_b: int = 0,
    expertise_a: bool = False,
    expertise_b: bool = False,
    modifier_bonus_a: int = 0,
    modifier_bonus_b: int = 0,
    advantage_a: bool = False,
    disadvantage_a: bool = False,
    advantage_b: bool = False,
    disadvantage_b: bool = False,
    _rng: random.Random | None = None,
) -> Tuple[SkillCheckResult, SkillCheckResult, Literal["a", "b", "tie"]]:
    """Two entities roll opposing checks.  Higher total wins; tie = status quo.

    Parameters
    ----------
    score_a, score_b : int
        Ability scores for entity A and B respectively.
    _rng : random.Random, optional
        Injectable RNG for deterministic testing.

    Returns
    -------
    (result_a, result_b, winner)
        winner is "a", "b", or "tie".
    """
    rng = _rng or random.Random()

    roll_a, rolls_a = roll_d20(
        advantage=advantage_a,
        disadvantage=disadvantage_a,
        _rng=rng,
    )
    roll_b, rolls_b = roll_d20(
        advantage=advantage_b,
        disadvantage=disadvantage_b,
        _rng=rng,
    )

    mod_a = ability_modifier(score_a) + (proficiency_bonus_a * 2 if expertise_a else proficiency_bonus_a) + modifier_bonus_a
    mod_b = ability_modifier(score_b) + (proficiency_bonus_b * 2 if expertise_b else proficiency_bonus_b) + modifier_bonus_b

    total_a = roll_a + mod_a
    total_b = roll_b + mod_b

    # For contested checks, we still track criticals but success is relative
    crit_a: Literal["success", "failure", None] = None
    if roll_a == 20:
        crit_a = "success"
    elif roll_a == 1:
        crit_a = "failure"

    crit_b: Literal["success", "failure", None] = None
    if roll_b == 20:
        crit_b = "success"
    elif roll_b == 1:
        crit_b = "failure"

    # Determine winner
    if total_a > total_b:
        winner: Literal["a", "b", "tie"] = "a"
    elif total_b > total_a:
        winner = "b"
    else:
        winner = "tie"

    # Build results — dc is set to the opponent's total for margin calc
    result_a = SkillCheckResult(
        roll=roll_a, modifier=mod_a, total=total_a,
        dc=total_b, success=(winner == "a"),
        margin=total_a - total_b, critical=crit_a,
        advantage=advantage_a and not disadvantage_a,
        disadvantage=disadvantage_a and not advantage_a,
        rolls=rolls_a,
    )
    result_b = SkillCheckResult(
        roll=roll_b, modifier=mod_b, total=total_b,
        dc=total_a, success=(winner == "b"),
        margin=total_b - total_a, critical=crit_b,
        advantage=advantage_b and not disadvantage_b,
        disadvantage=disadvantage_b and not advantage_b,
        rolls=rolls_b,
    )

    return result_a, result_b, winner


def saving_throw(
    ability_score: int,
    dc: int,
    *,
    proficiency_bonus: int = 0,
    proficient: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
    modifier_bonus: int = 0,
    _rng: random.Random | None = None,
) -> SkillCheckResult:
    """Saving throw wrapper over roll_check for semantic clarity."""
    return roll_check(
        ability_score,
        dc,
        proficiency_bonus=proficiency_bonus if proficient else 0,
        modifier_bonus=modifier_bonus,
        advantage=advantage,
        disadvantage=disadvantage,
        _rng=_rng,
    )
