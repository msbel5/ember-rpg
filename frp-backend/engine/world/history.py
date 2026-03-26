"""
Ember RPG -- World History Seed (Sprint 3, Module 7)
FR-29..FR-32: Deterministic procedural world history generation.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from engine.data_loader import (
    get_history_all_factions,
    get_history_present_year,
    get_history_scholarly_roles,
    get_history_severity_levels,
    get_history_table,
)

@dataclass
class HistoryEvent:
    """A single event in the world's history."""
    year: int
    event_type: str  # war, fall, catastrophe, figure_born, figure_died, tension, founding
    name: str
    factions: list[str] = field(default_factory=list)
    outcome: str = ""
    consequences: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "event_type": self.event_type,
            "name": self.name,
            "factions": self.factions,
            "outcome": self.outcome,
            "consequences": self.consequences,
        }


@dataclass
class NotableFigure:
    """A notable historical figure."""
    name: str
    born_year: int
    died_year: Optional[int]
    faction: str
    role: str
    legacy: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "born_year": self.born_year,
            "died_year": self.died_year,
            "faction": self.faction,
            "role": self.role,
            "legacy": self.legacy,
        }


_WAR_NAMES = get_history_table("war_names")
_KINGDOM_NAMES = get_history_table("kingdom_names")
_CATASTROPHE_NAMES = get_history_table("catastrophe_names")
_FIGURE_FIRST_NAMES = get_history_table("figure_first_names")
_FIGURE_LAST_NAMES = get_history_table("figure_last_names")
_FIGURE_ROLES = get_history_table("figure_roles")
_LEGACY_TEMPLATES = get_history_table("legacy_templates")
_TENSION_TEMPLATES = get_history_table("tension_templates")
_WAR_OUTCOMES = get_history_table("war_outcomes")
_FALL_CAUSES = get_history_table("fall_causes")
_ALL_FACTIONS = get_history_all_factions()
_SCHOLARLY_ROLES = {role.lower() for role in get_history_scholarly_roles()}
_SEVERITY_LEVELS = get_history_severity_levels()


# ---------------------------------------------------------------------------
# History Seed Generator
# ---------------------------------------------------------------------------

class HistorySeed:
    """Generates a deterministic world history from a numeric seed."""

    def __init__(self) -> None:
        self.events: list[HistoryEvent] = []
        self.figures: list[NotableFigure] = []
        self.current_year: int = get_history_present_year()

    def generate(self, seed: int) -> "HistorySeed":
        """Generate full world history. Returns self for chaining."""
        rng = random.Random(seed)
        self.events = []
        self.figures = []

        self._generate_wars(rng)
        self._generate_fallen_kingdoms(rng)
        self._generate_catastrophe(rng)
        self._generate_notable_figures(rng)
        self._generate_current_tensions(rng)

        # Sort events chronologically
        self.events.sort(key=lambda e: e.year)
        return self

    # -- private generators --------------------------------------------------

    def _generate_wars(self, rng: random.Random) -> None:
        num_wars = rng.randint(3, 5)
        used_names: set[str] = set()
        for _ in range(num_wars):
            name = rng.choice([n for n in _WAR_NAMES if n not in used_names] or _WAR_NAMES)
            used_names.add(name)
            factions_involved = rng.sample(_ALL_FACTIONS, k=2)
            year = rng.randint(400, 950)
            winner = rng.choice(factions_involved)
            loser = [f for f in factions_involved if f != winner][0]
            outcome = rng.choice(_WAR_OUTCOMES).format(winner=winner, loser=loser)
            consequences = {
                "winner": winner,
                "loser": loser,
                "territory_changed": rng.choice([True, False]),
                "casualties": rng.choice(["light", "moderate", "heavy", "devastating"]),
            }
            self.events.append(HistoryEvent(
                year=year,
                event_type="war",
                name=name,
                factions=factions_involved,
                outcome=outcome,
                consequences=consequences,
            ))

    def _generate_fallen_kingdoms(self, rng: random.Random) -> None:
        num_fallen = rng.randint(2, 3)
        used_names: set[str] = set()
        for _ in range(num_fallen):
            name = rng.choice([n for n in _KINGDOM_NAMES if n not in used_names] or _KINGDOM_NAMES)
            used_names.add(name)
            year = rng.randint(200, 800)
            cause = rng.choice(_FALL_CAUSES)
            successor_faction = rng.choice(_ALL_FACTIONS)
            self.events.append(HistoryEvent(
                year=year,
                event_type="fall",
                name=f"Fall of {name}",
                factions=[successor_faction],
                outcome=f"{name} collapsed due to {cause}.",
                consequences={
                    "cause": cause,
                    "successor": successor_faction,
                    "ruins_remain": rng.choice([True, False]),
                },
            ))

    def _generate_catastrophe(self, rng: random.Random) -> None:
        name = rng.choice(_CATASTROPHE_NAMES)
        year = rng.randint(500, 900)
        affected = rng.sample(_ALL_FACTIONS, k=rng.randint(3, len(_ALL_FACTIONS)))
        self.events.append(HistoryEvent(
            year=year,
            event_type="catastrophe",
            name=name,
            factions=affected,
            outcome=f"{name} ravaged the known world, reshaping borders and alliances.",
            consequences={
                "affected_factions": affected,
                "recovery_years": rng.randint(20, 100),
                "magic_affected": rng.choice([True, False]),
            },
        ))

    def _generate_notable_figures(self, rng: random.Random) -> None:
        num_figures = rng.randint(5, 10)
        used_names: set[str] = set()
        war_events = [e for e in self.events if e.event_type == "war"]

        for _ in range(num_figures):
            first = rng.choice(_FIGURE_FIRST_NAMES)
            last = rng.choice(_FIGURE_LAST_NAMES)
            full_name = f"{first} {last}"
            # Avoid exact duplicates
            while full_name in used_names:
                first = rng.choice(_FIGURE_FIRST_NAMES)
                last = rng.choice(_FIGURE_LAST_NAMES)
                full_name = f"{first} {last}"
            used_names.add(full_name)

            faction = rng.choice(_ALL_FACTIONS)
            role = rng.choice(_FIGURE_ROLES)
            born = rng.randint(300, 950)
            lifespan = rng.randint(25, 90)
            died = born + lifespan if born + lifespan < self.current_year else None

            related_event = rng.choice(war_events).name if war_events and rng.random() < 0.5 else "great upheaval"
            legacy = rng.choice(_LEGACY_TEMPLATES).format(faction=faction, event=related_event)

            self.figures.append(NotableFigure(
                name=full_name,
                born_year=born,
                died_year=died,
                faction=faction,
                role=role,
                legacy=legacy,
            ))

            # Also record birth as an event
            self.events.append(HistoryEvent(
                year=born,
                event_type="figure_born",
                name=f"Birth of {full_name}",
                factions=[faction],
                outcome=f"{full_name} born into {faction}, destined to become {role}.",
                consequences={"figure_name": full_name, "role": role},
            ))

    def _generate_current_tensions(self, rng: random.Random) -> None:
        num_tensions = rng.randint(2, 4)
        used_pairs: set[tuple[str, str]] = set()
        for _ in range(num_tensions):
            pair = tuple(sorted(rng.sample(_ALL_FACTIONS, k=2)))
            attempts = 0
            while pair in used_pairs and attempts < 20:
                pair = tuple(sorted(rng.sample(_ALL_FACTIONS, k=2)))
                attempts += 1
            used_pairs.add(pair)
            a, b = pair
            template = rng.choice(_TENSION_TEMPLATES)
            name = template.format(a=a, b=b)
            self.events.append(HistoryEvent(
                year=self.current_year,
                event_type="tension",
                name=name,
                factions=[a, b],
                outcome="Ongoing -- no resolution in sight.",
                consequences={
                    "severity": rng.choice(_SEVERITY_LEVELS),
                    "war_risk": round(rng.uniform(0.05, 0.6), 2),
                },
            ))

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize history seed for save/load.

        Stores the full generated state so we don't need to re-run RNG.
        """
        return {
            "current_year": self.current_year,
            "events": [e.to_dict() for e in self.events],
            "figures": [f.to_dict() for f in self.figures],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HistorySeed":
        """Deserialize history seed from a dict."""
        hs = cls()
        hs.current_year = data.get("current_year", get_history_present_year())
        hs.events = [
            HistoryEvent(
                year=e["year"],
                event_type=e["event_type"],
                name=e["name"],
                factions=e.get("factions", []),
                outcome=e.get("outcome", ""),
                consequences=e.get("consequences", {}),
            )
            for e in data.get("events", [])
        ]
        hs.figures = [
            NotableFigure(
                name=f["name"],
                born_year=f["born_year"],
                died_year=f.get("died_year"),
                faction=f["faction"],
                role=f["role"],
                legacy=f["legacy"],
            )
            for f in data.get("figures", [])
        ]
        return hs

    # -- query API -----------------------------------------------------------

    def get_wars(self) -> list[HistoryEvent]:
        return [e for e in self.events if e.event_type == "war"]

    def get_fallen_kingdoms(self) -> list[HistoryEvent]:
        return [e for e in self.events if e.event_type == "fall"]

    def get_catastrophes(self) -> list[HistoryEvent]:
        return [e for e in self.events if e.event_type == "catastrophe"]

    def get_tensions(self) -> list[HistoryEvent]:
        return [e for e in self.events if e.event_type == "tension"]

    def get_figures(self) -> list[NotableFigure]:
        return list(self.figures)


# ---------------------------------------------------------------------------
# NPC knowledge filter
# ---------------------------------------------------------------------------

def get_npc_known_facts(
    npc_role: str,
    npc_age: int,
    faction: str,
    history: HistorySeed,
) -> list[HistoryEvent]:
    """Filter history events to what an NPC would plausibly know.

    Rules:
    - NPCs know events from their own faction regardless of age.
    - NPCs know events from the last (npc_age) years across all factions.
    - Scholars / sages / priests know events going back 500 years.
    - Commoners only know events from the last 50 years plus their faction lore.
    - Current tensions are always known.
    """
    present = history.current_year
    earliest_personal = present - npc_age

    is_scholarly = npc_role.lower() in _SCHOLARLY_ROLES
    general_horizon = present - 500 if is_scholarly else present - 50

    known: list[HistoryEvent] = []
    for event in history.events:
        # Current tensions are common knowledge
        if event.event_type == "tension":
            known.append(event)
            continue
        # Own faction history is always known
        if faction in event.factions:
            known.append(event)
            continue
        # Events within living memory
        if event.year >= earliest_personal:
            known.append(event)
            continue
        # Scholarly knowledge
        if is_scholarly and event.year >= general_horizon:
            known.append(event)
            continue

    return known


# ---------------------------------------------------------------------------
# LLM context builder
# ---------------------------------------------------------------------------

def get_history_context(history: HistorySeed) -> str:
    """Format full history into a string suitable for LLM prompt injection."""
    lines: list[str] = []
    lines.append("=== WORLD HISTORY ===")

    wars = history.get_wars()
    if wars:
        lines.append("\n-- Major Wars --")
        for w in wars:
            lines.append(f"  Year {w.year}: {w.name} ({', '.join(w.factions)})")
            lines.append(f"    Outcome: {w.outcome}")

    fallen = history.get_fallen_kingdoms()
    if fallen:
        lines.append("\n-- Fallen Kingdoms --")
        for f in fallen:
            lines.append(f"  Year {f.year}: {f.name}")
            lines.append(f"    {f.outcome}")

    cats = history.get_catastrophes()
    if cats:
        lines.append("\n-- Catastrophes --")
        for c in cats:
            lines.append(f"  Year {c.year}: {c.name}")
            lines.append(f"    {c.outcome}")

    figures = history.get_figures()
    if figures:
        lines.append("\n-- Notable Figures --")
        for fig in figures:
            death_str = f"died {fig.died_year}" if fig.died_year else "still living"
            lines.append(f"  {fig.name} ({fig.role}, {fig.faction}) born {fig.born_year}, {death_str}")
            lines.append(f"    {fig.legacy}")

    tensions = history.get_tensions()
    if tensions:
        lines.append("\n-- Current Tensions --")
        for t in tensions:
            lines.append(f"  {t.name}")
            sev = t.consequences.get("severity", "unknown")
            lines.append(f"    Severity: {sev}")

    return "\n".join(lines)
