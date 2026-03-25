"""
Ember RPG -- Ethics & Cultural Values System (Sprint 3, Module 6)
FR-25..FR-28: Faction moral codes, cultural values, action evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Reaction severity scale
# ---------------------------------------------------------------------------
REACTION_LEVELS: dict[str, int] = {
    "unthinkable": -100,
    "serious_crime": -50,
    "crime": -30,
    "distasteful": -10,
    "tolerated": -5,
    "acceptable": 0,
    "valued": 5,
    "honored": 15,
}

# ---------------------------------------------------------------------------
# Action types recognised by the ethics engine
# ---------------------------------------------------------------------------
ACTION_TYPES = [
    "KILL_CITIZEN",
    "THEFT",
    "ASSAULT",
    "TRADE",
    "KILL_ENEMY",
    "BETRAYAL",
    "HELP_POOR",
    "DESECRATE",
]

# ---------------------------------------------------------------------------
# FACTION_ETHICS -- per-faction moral reactions to each action type
# Key: faction_id -> action_type -> reaction_level (str from REACTION_LEVELS)
# ---------------------------------------------------------------------------
FACTION_ETHICS: dict[str, dict[str, str]] = {
    "harbor_guard": {
        "KILL_CITIZEN": "serious_crime",
        "THEFT": "crime",
        "ASSAULT": "crime",
        "TRADE": "valued",
        "KILL_ENEMY": "honored",
        "BETRAYAL": "unthinkable",
        "HELP_POOR": "valued",
        "DESECRATE": "distasteful",
    },
    "thieves_guild": {
        "KILL_CITIZEN": "distasteful",
        "THEFT": "valued",
        "ASSAULT": "tolerated",
        "TRADE": "acceptable",
        "KILL_ENEMY": "acceptable",
        "BETRAYAL": "unthinkable",
        "HELP_POOR": "tolerated",
        "DESECRATE": "acceptable",
    },
    "merchant_guild": {
        "KILL_CITIZEN": "serious_crime",
        "THEFT": "serious_crime",
        "ASSAULT": "crime",
        "TRADE": "honored",
        "KILL_ENEMY": "acceptable",
        "BETRAYAL": "crime",
        "HELP_POOR": "valued",
        "DESECRATE": "distasteful",
    },
    "forest_elves": {
        "KILL_CITIZEN": "unthinkable",
        "THEFT": "crime",
        "ASSAULT": "crime",
        "TRADE": "acceptable",
        "KILL_ENEMY": "tolerated",
        "BETRAYAL": "serious_crime",
        "HELP_POOR": "honored",
        "DESECRATE": "unthinkable",
    },
    "mountain_dwarves": {
        "KILL_CITIZEN": "serious_crime",
        "THEFT": "crime",
        "ASSAULT": "tolerated",
        "TRADE": "valued",
        "KILL_ENEMY": "honored",
        "BETRAYAL": "unthinkable",
        "HELP_POOR": "acceptable",
        "DESECRATE": "serious_crime",
    },
    "temple_order": {
        "KILL_CITIZEN": "unthinkable",
        "THEFT": "serious_crime",
        "ASSAULT": "crime",
        "TRADE": "acceptable",
        "KILL_ENEMY": "tolerated",
        "BETRAYAL": "serious_crime",
        "HELP_POOR": "honored",
        "DESECRATE": "unthinkable",
    },
}

# ---------------------------------------------------------------------------
# FACTION_VALUES -- cultural value weights per faction (0-100)
# ---------------------------------------------------------------------------
FACTION_VALUES: dict[str, dict[str, int]] = {
    "harbor_guard": {
        "order": 90,
        "commerce": 40,
        "tradition": 60,
        "nature": 20,
        "wealth": 30,
        "art": 15,
        "honor": 85,
        "faith": 45,
    },
    "thieves_guild": {
        "order": 10,
        "commerce": 55,
        "tradition": 30,
        "nature": 10,
        "wealth": 90,
        "art": 40,
        "honor": 20,
        "faith": 5,
    },
    "merchant_guild": {
        "order": 60,
        "commerce": 95,
        "tradition": 35,
        "nature": 15,
        "wealth": 85,
        "art": 50,
        "honor": 45,
        "faith": 25,
    },
    "forest_elves": {
        "order": 40,
        "commerce": 15,
        "tradition": 80,
        "nature": 95,
        "wealth": 10,
        "art": 75,
        "honor": 70,
        "faith": 60,
    },
    "mountain_dwarves": {
        "order": 70,
        "commerce": 60,
        "tradition": 90,
        "nature": 30,
        "wealth": 75,
        "art": 65,
        "honor": 80,
        "faith": 50,
    },
    "temple_order": {
        "order": 75,
        "commerce": 20,
        "tradition": 70,
        "nature": 45,
        "wealth": 10,
        "art": 55,
        "honor": 60,
        "faith": 95,
    },
}

# ---------------------------------------------------------------------------
# Consequence descriptions keyed by reaction level
# ---------------------------------------------------------------------------
_CONSEQUENCE_MAP: dict[str, Optional[str]] = {
    "unthinkable": "Faction declares you an enemy. All members attack on sight.",
    "serious_crime": "Bounty placed on your head. Faction reputation severely damaged.",
    "crime": "Guards alerted. Possible arrest or fine.",
    "distasteful": "Faction members express disapproval. Minor reputation loss.",
    "tolerated": None,
    "acceptable": None,
    "valued": None,
    "honored": None,
}


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
