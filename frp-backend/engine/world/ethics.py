"""
Ember RPG -- Ethics & Cultural Values System (Sprint 3, Module 6)
FR-25..FR-28: Faction moral codes, cultural values, action evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# All faction/ethics data loaded from data/factions.json
# ---------------------------------------------------------------------------
def _load_factions() -> dict:
    from engine.data._shared import factions_registry
    return factions_registry()


_FACTIONS_DATA: dict = _load_factions()
REACTION_LEVELS: dict[str, int] = _FACTIONS_DATA.get("reaction_levels", {})
ACTION_TYPES: list[str] = _FACTIONS_DATA.get("action_types", [])
FACTION_ETHICS: dict[str, dict[str, str]] = _FACTIONS_DATA.get("ethics", {})
FACTION_VALUES: dict[str, dict[str, int]] = _FACTIONS_DATA.get("values", {})
_CONSEQUENCE_MAP: dict[str, Optional[str]] = _FACTIONS_DATA.get("consequences", {})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ActionEvaluation:
    """Result of evaluating a player action against a faction's ethics."""
    faction: str
    action_type: str
    reaction_level: str
    rep_change: int
    consequence: Optional[str]


def evaluate_action(faction: str, action_type: str) -> tuple[int, Optional[str]]:
    """Evaluate an action against a faction's ethical code.

    Returns:
        (rep_change, consequence) -- rep_change is an integer from
        REACTION_LEVELS, consequence is a human-readable string or None.

    Raises:
        KeyError: if faction or action_type is unknown.
    """
    if faction not in FACTION_ETHICS:
        raise KeyError(f"Unknown faction: {faction!r}")
    ethics = FACTION_ETHICS[faction]
    if action_type not in ethics:
        raise KeyError(f"Unknown action type: {action_type!r}")
    reaction = ethics[action_type]
    rep_change = REACTION_LEVELS[reaction]
    consequence = _CONSEQUENCE_MAP.get(reaction)
    return rep_change, consequence


def evaluate_action_full(faction: str, action_type: str) -> ActionEvaluation:
    """Like evaluate_action but returns a full ActionEvaluation dataclass."""
    rep_change, consequence = evaluate_action(faction, action_type)
    reaction = FACTION_ETHICS[faction][action_type]
    return ActionEvaluation(
        faction=faction,
        action_type=action_type,
        reaction_level=reaction,
        rep_change=rep_change,
        consequence=consequence,
    )


def get_faction_context(faction: str) -> dict:
    """Build a context dict suitable for injection into LLM prompts.

    Contains the faction's values, ethical stances, top values, and a
    one-line personality summary.
    """
    if faction not in FACTION_ETHICS:
        raise KeyError(f"Unknown faction: {faction!r}")

    values = FACTION_VALUES[faction]
    ethics = FACTION_ETHICS[faction]

    # Top 3 values
    sorted_values = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    top_values = [v[0] for v in sorted_values[:3]]

    # Classify actions into categories for the LLM
    crimes = [a for a, r in ethics.items() if REACTION_LEVELS[r] <= -30]
    honored_acts = [a for a, r in ethics.items() if REACTION_LEVELS[r] >= 5]

    personality_parts = []
    if values.get("order", 0) >= 70:
        personality_parts.append("lawful")
    if values.get("wealth", 0) >= 70:
        personality_parts.append("profit-driven")
    if values.get("nature", 0) >= 70:
        personality_parts.append("nature-loving")
    if values.get("faith", 0) >= 70:
        personality_parts.append("devout")
    if values.get("honor", 0) >= 70:
        personality_parts.append("honour-bound")
    if values.get("tradition", 0) >= 70:
        personality_parts.append("traditional")
    if values.get("art", 0) >= 70:
        personality_parts.append("artistic")
    if not personality_parts:
        personality_parts.append("pragmatic")
    personality = ", ".join(personality_parts)

    return {
        "faction": faction,
        "values": values,
        "top_values": top_values,
        "crimes": crimes,
        "honored_actions": honored_acts,
        "personality": personality,
        "ethics_summary": {
            action: {"reaction": reaction, "rep_change": REACTION_LEVELS[reaction]}
            for action, reaction in ethics.items()
        },
    }


def get_all_factions() -> list[str]:
    """Return a sorted list of all registered faction ids."""
    return sorted(FACTION_ETHICS.keys())


def compare_factions(faction_a: str, faction_b: str) -> dict:
    """Compare two factions' ethical stances on all action types.

    Returns a dict mapping action_type to {faction_a: reaction, faction_b: reaction, agreement: bool}.
    """
    if faction_a not in FACTION_ETHICS:
        raise KeyError(f"Unknown faction: {faction_a!r}")
    if faction_b not in FACTION_ETHICS:
        raise KeyError(f"Unknown faction: {faction_b!r}")

    comparison: dict[str, dict] = {}
    for action in ACTION_TYPES:
        r_a = FACTION_ETHICS[faction_a][action]
        r_b = FACTION_ETHICS[faction_b][action]
        comparison[action] = {
            faction_a: r_a,
            faction_b: r_b,
            "agreement": r_a == r_b,
        }
    return comparison
