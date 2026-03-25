"""
Ember RPG -- World Tick Scheduler (Sprint 2, FR-01..FR-04)

Drives the living-world simulation forward in discrete 1-hour ticks.
Subsystems (NPC needs, weather, economy, etc.) register themselves and
are executed in insertion order on every tick.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, List


@dataclass
class WorldEvent:
    """A single event produced by a subsystem during a tick."""

    event_type: str
    description: str
    data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# Type alias for subsystem callables.
# Each subsystem receives (hours: int) and returns a list of WorldEvent.
SubsystemFn = Callable[[int], List[WorldEvent]]


class WorldTickScheduler:
    """
    Advances the game world by a given number of hours, running every
    registered subsystem in order and collecting the events they produce.

    Usage::

        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("npc_needs", npc_needs_tick_fn)
        scheduler.register_subsystem("weather", weather_tick_fn)
        events = scheduler.advance(hours=1)   # player action tick
        events = scheduler.advance(hours=8)   # rest tick
    """

    def __init__(self) -> None:
        # Ordered list of (name, callable) pairs.
        self._subsystems: list[tuple[str, SubsystemFn]] = []
        # Accumulated history of all events across ticks.
        self.history: list[WorldEvent] = []
        # Running total of elapsed game hours.
        self.elapsed_hours: int = 0

    # ------------------------------------------------------------------
    # Subsystem management
    # ------------------------------------------------------------------

    def register_subsystem(self, name: str, fn: SubsystemFn) -> None:
        """Register a subsystem by *name*.  Duplicates are rejected."""
        for existing_name, _ in self._subsystems:
            if existing_name == name:
                raise ValueError(f"Subsystem '{name}' is already registered")
        self._subsystems.append((name, fn))

    def unregister_subsystem(self, name: str) -> bool:
        """Remove a subsystem by name.  Returns True if it existed."""
        for i, (existing_name, _) in enumerate(self._subsystems):
            if existing_name == name:
                self._subsystems.pop(i)
                return True
        return False

    @property
    def subsystem_names(self) -> list[str]:
        return [name for name, _ in self._subsystems]

    # ------------------------------------------------------------------
    # Tick execution
    # ------------------------------------------------------------------

    def advance(self, hours: int = 1) -> list[WorldEvent]:
        """
        Run all subsystems for *hours* game-hours and return the
        collected :class:`WorldEvent` list.

        FR-01: Player action triggers 1-hour tick (caller passes hours=1).
        FR-02: Resting triggers 8-hour tick (caller passes hours=8).
        FR-03: Subsystems execute in registration order.
        FR-04: Events from every subsystem are aggregated.
        """
        if hours < 1:
            raise ValueError("hours must be >= 1")

        tick_events: list[WorldEvent] = []

        for _name, fn in self._subsystems:
            try:
                events = fn(hours)
                if events:
                    tick_events.extend(events)
            except Exception as exc:
                tick_events.append(
                    WorldEvent(
                        event_type="subsystem_error",
                        description=f"Subsystem '{_name}' raised: {exc}",
                        data={"subsystem": _name, "error": str(exc)},
                    )
                )

        self.elapsed_hours += hours
        self.history.extend(tick_events)
        return tick_events

    def action_tick(self) -> list[WorldEvent]:
        """Convenience: advance 1 hour (player took an action)."""
        return self.advance(hours=1)

    def rest_tick(self) -> list[WorldEvent]:
        """Convenience: advance 8 hours (player rested)."""
        return self.advance(hours=8)
