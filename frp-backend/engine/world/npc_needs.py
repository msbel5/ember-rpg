"""
Ember RPG -- NPC Needs System (Sprint 2, FR-05..FR-09)

Every NPC has five fundamental needs on a 0-100 scale.  Needs decay
over time and drive emotional state plus behaviour modifiers that
affect gameplay (shop prices, willingness to talk, bribe susceptibility).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Decay rates per game-hour for each need.
DECAY_RATES: dict[str, float] = {
    "safety": 0.5,
    "commerce": 0.5,
    "social": 1.0,
    "sustenance": 2.0,
    "duty": 1.0,
}


@dataclass
class NPCNeeds:
    """
    Five-axis need model for a single NPC.

    All values are clamped to [0, 100].
    """

    safety: float = 80.0
    commerce: float = 80.0
    social: float = 80.0
    sustenance: float = 80.0
    duty: float = 80.0

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, value))

    def _get(self, need: str) -> float:
        if not hasattr(self, need):
            raise ValueError(f"Unknown need: {need}")
        return getattr(self, need)

    def _set(self, need: str, value: float) -> None:
        if not hasattr(self, need):
            raise ValueError(f"Unknown need: {need}")
        setattr(self, need, self._clamp(value))

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def tick(self, hours: int = 1) -> None:
        """
        Decay all needs by their per-hour rate multiplied by *hours*.

        FR-06: sustenance -2/hr, social -1/hr, safety -0.5/hr,
               duty -1/hr, commerce -0.5/hr.
        """
        for need_name, rate in DECAY_RATES.items():
            current = self._get(need_name)
            self._set(need_name, current - rate * hours)

    def satisfy(self, need: str, amount: float) -> None:
        """
        Increase *need* by *amount*, clamped to [0, 100].

        FR-07: satisfy(need, amount) increases a need.
        """
        current = self._get(need)
        self._set(need, current + amount)

    # ------------------------------------------------------------------
    # Derived state (FR-08, FR-09)
    # ------------------------------------------------------------------

    def emotional_state(self) -> str:
        """
        Return the NPC's dominant emotional state based on current needs.

        FR-08 priority (checked top-to-bottom, first match wins):
          - "terrified"  if safety < 10
          - "desperate"  if any need < 10
          - "distressed" if any need < 20
          - "content"    if all needs > 60
          - "uneasy"     otherwise (default)
        """
        if self.safety < 10:
            return "terrified"

        all_values = [self.safety, self.commerce, self.social,
                      self.sustenance, self.duty]

        if any(v < 10 for v in all_values):
            return "desperate"
        if any(v < 20 for v in all_values):
            return "distressed"
        if all(v > 60 for v in all_values):
            return "content"
        return "uneasy"

    def behavior_modifiers(self) -> dict:
        """
        Return gameplay-relevant modifiers derived from current needs.

        FR-09:
          - price_mult:          1.0 normally; rises when commerce is low
          - will_talk:           True unless social < 15 or safety < 15
          - will_trade:          True unless commerce < 10 or safety < 15
          - bribe_susceptibility: 0.0..1.0 -- higher when duty is low
        """
        # Price multiplier: increases as commerce need drops.
        # At commerce 100 -> 1.0x; at commerce 0 -> 1.5x
        price_mult = 1.0 + 0.5 * (1.0 - self.commerce / 100.0)

        will_talk = self.social >= 15 and self.safety >= 15
        will_trade = self.commerce >= 10 and self.safety >= 15

        # Bribe susceptibility: inverse of duty, scaled 0..1
        bribe_susceptibility = max(0.0, min(1.0, 1.0 - self.duty / 100.0))

        return {
            "price_mult": round(price_mult, 3),
            "will_talk": will_talk,
            "will_trade": will_trade,
            "bribe_susceptibility": round(bribe_susceptibility, 3),
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "safety": self.safety,
            "commerce": self.commerce,
            "social": self.social,
            "sustenance": self.sustenance,
            "duty": self.duty,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCNeeds":
        return cls(
            safety=data.get("safety", 80.0),
            commerce=data.get("commerce", 80.0),
            social=data.get("social", 80.0),
            sustenance=data.get("sustenance", 80.0),
            duty=data.get("duty", 80.0),
        )
