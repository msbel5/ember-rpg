"""
Hit-location and body-part tracking for Ember RPG.
FR-20..FR-24: d20-based hit location, per-part HP, armor coverage.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── d20 → body-part mapping ─────────────────────────────────────────
# Ranges are inclusive on both ends.
_HIT_TABLE: List[Tuple[int, int, str]] = [
    (1, 1, "head"),
    (2, 2, "neck"),
    (3, 5, "chest"),
    (6, 9, "torso"),
    (10, 12, "left_arm"),
    (13, 15, "right_arm"),
    (16, 17, "left_leg"),
    (18, 20, "right_leg"),
]

# Flat dict for quick access: d20_value → part
HIT_LOCATIONS: Dict[int, str] = {}
for _lo, _hi, _part in _HIT_TABLE:
    for _v in range(_lo, _hi + 1):
        HIT_LOCATIONS[_v] = _part


def roll_hit_location(roll: Optional[int] = None) -> str:
    """Return a body-part string for a d20 *roll* (1‑20).

    If *roll* is ``None`` a random d20 is rolled.
    Raises ``ValueError`` for out-of-range values.
    """
    if roll is None:
        roll = random.randint(1, 20)
    if roll < 1 or roll > 20:
        raise ValueError(f"Roll must be 1‑20, got {roll}")
    return HIT_LOCATIONS[roll]


# ── Per-part HP tracker ──────────────────────────────────────────────

DEFAULT_PART_HP: Dict[str, int] = {
    "head": 8,
    "neck": 6,
    "chest": 14,
    "torso": 12,
    "left_arm": 10,
    "right_arm": 10,
    "left_leg": 10,
    "right_leg": 10,
}

# Injury thresholds expressed as fraction of max HP remaining.
_INJURY_THRESHOLDS = [
    (0.0, "destroyed"),   # 0 %
    (0.25, "crippled"),   # ≤ 25 %
    (0.50, "wounded"),    # ≤ 50 %
    (0.75, "bruised"),    # ≤ 75 %
]


@dataclass
class BodyPartTracker:
    """Tracks HP for every body part of a creature."""

    max_hp: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_PART_HP))
    current_hp: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_PART_HP))

    # ── mutation ─────────────────────────────────────────────────────
    def apply_damage(self, part: str, amount: int) -> Dict:
        """Apply *amount* damage to *part*. Returns an info dict.

        Keys: part, damage_dealt, hp_before, hp_after, status.
        """
        if part not in self.current_hp:
            raise ValueError(f"Unknown body part: {part}")
        hp_before = self.current_hp[part]
        self.current_hp[part] = max(0, hp_before - amount)
        return {
            "part": part,
            "damage_dealt": amount,
            "hp_before": hp_before,
            "hp_after": self.current_hp[part],
            "status": self._status(part),
        }

    def heal(self, part: str, amount: int) -> None:
        """Heal *part* by *amount*, capped at max HP."""
        if part not in self.current_hp:
            raise ValueError(f"Unknown body part: {part}")
        self.current_hp[part] = min(self.max_hp[part], self.current_hp[part] + amount)

    # ── queries ──────────────────────────────────────────────────────
    def _status(self, part: str) -> str:
        ratio = self.current_hp[part] / self.max_hp[part]
        for threshold, label in _INJURY_THRESHOLDS:
            if ratio <= threshold:
                return label
        return "healthy"

    def get_injury_effects(self) -> Dict[str, str]:
        """Return ``{part: status}`` for every part that is not healthy."""
        return {
            part: self._status(part)
            for part in self.current_hp
            if self._status(part) != "healthy"
        }

    def is_alive(self) -> bool:
        """Creature dies if head, neck, chest, or torso is destroyed."""
        vital = ("head", "neck", "chest", "torso")
        return all(self.current_hp.get(p, 0) > 0 for p in vital)

    def to_dict(self) -> Dict:
        """Serialize body tracker for save/load."""
        return {
            "max_hp": dict(self.max_hp),
            "current_hp": dict(self.current_hp),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BodyPartTracker":
        """Deserialize body tracker from a dict."""
        return cls(
            max_hp=dict(data.get("max_hp", DEFAULT_PART_HP)),
            current_hp=dict(data.get("current_hp", DEFAULT_PART_HP)),
        )


# ── Armor coverage ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ArmorPiece:
    name: str
    covers: Tuple[str, ...]
    reduction: int  # flat damage reduction


ARMOR_COVERAGE: Dict[str, ArmorPiece] = {
    "helmet": ArmorPiece("Helmet", ("head", "neck"), 3),
    "chainmail": ArmorPiece("Chainmail", ("torso", "chest"), 5),
    "shield": ArmorPiece("Shield", ("left_arm",), 4),
    "greaves": ArmorPiece("Greaves", ("left_leg", "right_leg"), 3),
    "gauntlets": ArmorPiece("Gauntlets", ("left_arm", "right_arm"), 2),
    "breastplate": ArmorPiece("Breastplate", ("chest",), 6),
    "leather_cap": ArmorPiece("Leather Cap", ("head",), 1),
    "boots": ArmorPiece("Boots", ("left_leg", "right_leg"), 1),
}


def calculate_armor_reduction(
    hit_location: str,
    equipped_armor_list: List[str],
) -> int:
    """Return total flat damage reduction for *hit_location*.

    *equipped_armor_list* contains armor keys from ``ARMOR_COVERAGE``.
    Unknown keys are silently ignored.
    """
    total = 0
    for key in equipped_armor_list:
        piece = ARMOR_COVERAGE.get(key)
        if piece and hit_location in piece.covers:
            total += piece.reduction
    return total
