"""
Module 3: NPC Schedules & Movement (FR-10..FR-14)
NPCs follow daily schedules, moving between locations based on time of day.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from engine.data_loader import get_default_schedules


class TimePeriod(Enum):
    """Five time periods in a game day."""
    DAWN = "dawn"           # 05:00 - 08:00
    MORNING = "morning"     # 08:00 - 12:00
    AFTERNOON = "afternoon" # 12:00 - 17:00
    EVENING = "evening"     # 17:00 - 21:00
    NIGHT = "night"         # 21:00 - 05:00


# Map hours to time periods
def hour_to_period(hour: int) -> TimePeriod:
    """Convert hour (0-23) to TimePeriod."""
    if 5 <= hour < 8:
        return TimePeriod.DAWN
    elif 8 <= hour < 12:
        return TimePeriod.MORNING
    elif 12 <= hour < 17:
        return TimePeriod.AFTERNOON
    elif 17 <= hour < 21:
        return TimePeriod.EVENING
    else:
        return TimePeriod.NIGHT


@dataclass
class NPCSchedule:
    """Schedule for one NPC — maps time periods to locations and positions."""
    npc_id: str
    npc_name: str
    # Where the NPC should be at each time period
    locations: Dict[str, str] = field(default_factory=dict)
    # Optional tile positions per time period (for zone-specific placement)
    positions: Dict[str, List[int]] = field(default_factory=dict)
    # Guard patrol route (list of [x, y] positions, cycled)
    patrol_route: Optional[List[List[int]]] = None
    # Current patrol index
    _patrol_index: int = 0

    def get_location(self, period: TimePeriod) -> str:
        """Get NPC's scheduled location for a time period."""
        return self.locations.get(period.value, "home")

    def get_position(self, period: TimePeriod) -> Optional[List[int]]:
        """Get NPC's scheduled position for a time period."""
        return self.positions.get(period.value)

    def next_patrol_position(self) -> Optional[List[int]]:
        """Get next position in patrol route and advance index."""
        if not self.patrol_route:
            return None
        pos = self.patrol_route[self._patrol_index % len(self.patrol_route)]
        self._patrol_index += 1
        return pos

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "npc_name": self.npc_name,
            "locations": dict(self.locations),
            "positions": {key: list(value) for key, value in self.positions.items()},
            "patrol_route": [list(pos) for pos in self.patrol_route] if self.patrol_route else None,
            "_patrol_index": self._patrol_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCSchedule":
        patrol_route = data.get("patrol_route") or []
        schedule = cls(
            npc_id=data.get("npc_id", ""),
            npc_name=data.get("npc_name", ""),
            locations=dict(data.get("locations", {})),
            positions={key: list(value) for key, value in data.get("positions", {}).items()},
            patrol_route=[list(pos) for pos in patrol_route] or None,
        )
        schedule._patrol_index = data.get("_patrol_index", 0)
        return schedule


DEFAULT_SCHEDULES = get_default_schedules()


@dataclass
class GameTime:
    """Tracks in-game time. Each action advances time by ~15 minutes."""
    hour: int = 8      # 0-23
    minute: int = 0     # 0-59
    day: int = 1        # Day counter
    _period: TimePeriod = field(init=False)

    def __post_init__(self):
        self._period = hour_to_period(self.hour)

    @property
    def period(self) -> TimePeriod:
        return self._period

    def advance(self, minutes: int = 15):
        """Advance game time by given minutes."""
        old_period = self._period
        self.minute += minutes
        while self.minute >= 60:
            self.minute -= 60
            self.hour += 1
        while self.hour >= 24:
            self.hour -= 24
            self.day += 1
        self._period = hour_to_period(self.hour)
        return old_period != self._period  # True if period changed

    def to_string(self) -> str:
        """Human-readable time string."""
        return f"Day {self.day}, {self.hour:02d}:{self.minute:02d} ({self._period.value})"

    def to_dict(self) -> dict:
        return {
            "hour": self.hour,
            "minute": self.minute,
            "day": self.day,
            "period": self._period.value,
            "display": self.to_string(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameTime":
        """Deserialize GameTime from a dict."""
        return cls(
            hour=data.get("hour", 8),
            minute=data.get("minute", 0),
            day=data.get("day", 1),
        )


class WorldTickScheduler:
    """
    Manages NPC schedules and moves NPCs when time period changes.

    Usage:
        scheduler = WorldTickScheduler()
        scheduler.register_npc("merchant_1", "Old Merchant", "merchant")
        moved = scheduler.tick(game_time)  # Returns list of NPCs that moved
    """

    def __init__(self):
        self._schedules: Dict[str, NPCSchedule] = {}
        self._last_period: Optional[TimePeriod] = None

    def register_npc(self, npc_id: str, npc_name: str, role: str,
                     custom_schedule: Optional[Dict[str, str]] = None,
                     patrol_route: Optional[List[List[int]]] = None):
        """Register an NPC with a schedule."""
        schedule_data = custom_schedule or DEFAULT_SCHEDULES.get(role, DEFAULT_SCHEDULES["merchant"])

        self._schedules[npc_id] = NPCSchedule(
            npc_id=npc_id,
            npc_name=npc_name,
            locations=schedule_data,
            patrol_route=patrol_route,
        )

    def tick(self, game_time: GameTime) -> List[Dict]:
        """
        Check if time period changed and move NPCs accordingly.

        Returns list of movement events:
        [{"npc_id": "...", "npc_name": "...", "from": "...", "to": "...", "period": "..."}]
        """
        current_period = game_time.period
        movements = []

        if self._last_period is not None and self._last_period != current_period:
            for npc_id, schedule in self._schedules.items():
                old_loc = schedule.get_location(self._last_period)
                new_loc = schedule.get_location(current_period)

                if old_loc != new_loc:
                    movements.append({
                        "npc_id": npc_id,
                        "npc_name": schedule.npc_name,
                        "from": old_loc,
                        "to": new_loc,
                        "period": current_period.value,
                    })

        self._last_period = current_period
        return movements

    def get_npcs_at_location(self, location: str, period: TimePeriod) -> List[str]:
        """Get list of NPC IDs scheduled to be at a location during a time period."""
        return [
            npc_id for npc_id, schedule in self._schedules.items()
            if schedule.get_location(period) == location
        ]

    def get_npc_location(self, npc_id: str, period: TimePeriod) -> Optional[str]:
        """Get where an NPC should be at a given time period."""
        schedule = self._schedules.get(npc_id)
        if schedule:
            return schedule.get_location(period)
        return None

    def advance_guard_patrols(self) -> List[Dict]:
        """Advance all guard patrol positions by one step."""
        movements = []
        for npc_id, schedule in self._schedules.items():
            if schedule.patrol_route:
                pos = schedule.next_patrol_position()
                if pos:
                    movements.append({
                        "npc_id": npc_id,
                        "npc_name": schedule.npc_name,
                        "patrol_position": pos,
                    })
        return movements
