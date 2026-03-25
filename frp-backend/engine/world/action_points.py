"""
Action Point (AP) system for Ember RPG.
FR-07..FR-08: Class-based AP pools, action costs, terrain modifiers, armor penalties.

Based on PRD section 5.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


# ── Class AP pools ───────────────────────────────────────────────────

CLASS_AP: Dict[str, int] = {
    "warrior": 4,
    "rogue": 6,
    "mage": 3,
    "priest": 4,
}

# ── Action costs ─────────────────────────────────────────────────────
# Keys match the canonical action identifiers used by the interaction system.

ACTION_COSTS: Dict[str, int] = {
    # Movement
    "move_flat": 1,
    "move_rough": 2,
    # Combat
    "attack_melee": 2,
    "attack_ranged": 3,
    # Social / utility
    "talk": 1,
    "examine": 1,
    "trade": 1,
    "pick_up": 1,
    "open": 1,
    "close": 1,
    "lock_pick": 2,
    "force_open": 2,
    "search": 1,
    "read": 1,
    "use": 1,
    "push": 1,
    "pull": 1,
    "steal": 2,
    "sneak": 2,
    "intimidate": 1,
    "persuade": 1,
    "bribe": 1,
    "pray": 1,
    "drink": 1,
    "fill": 1,
    # Crafting
    "craft_simple": 5,
    "craft_complex": 15,
    # Resource gathering
    "chop": 3,
    "mine": 3,
    "fish": 3,
    "disarm_trap": 2,
    "set_trap": 3,
    "climb": 2,
    "swim": 2,
    "bury": 3,
    # Spells (tiered)
    "cast_spell_1": 1,
    "cast_spell_2": 2,
    "cast_spell_3": 3,
    # Rest consumes 0 AP (but 8 game-hours)
    "rest": 0,
}

# ── Armor weight penalties ───────────────────────────────────────────
# Extra AP cost added to every *movement* action based on equipped armor type.

ARMOR_WEIGHT_PENALTY: Dict[str, int] = {
    "none": 0,
    "cloth": 0,
    "leather": 0,
    "chain_mail": 1,
    "plate_armor": 2,
}


# ── AP Tracker ───────────────────────────────────────────────────────

@dataclass
class ActionPointTracker:
    """Tracks and manages action points for a single entity.

    Parameters
    ----------
    max_ap : int
        Maximum AP per turn (set from CLASS_AP).
    armor_type : str
        Currently equipped armor category (affects movement costs).
    """

    max_ap: int
    armor_type: str = "none"
    current_ap: int = field(init=False)

    def __post_init__(self) -> None:
        self.current_ap = self.max_ap

    # ── Queries ──────────────────────────────────────────────────

    def can_afford(self, cost: int) -> bool:
        """Return True if the entity has enough AP for the given cost."""
        return self.current_ap >= cost

    def movement_cost(self, base_cost: int) -> int:
        """Compute actual movement cost including armor weight penalty.

        Parameters
        ----------
        base_cost : int
            Terrain-based cost (1 for flat, 2 for rough, etc.).
        """
        penalty = ARMOR_WEIGHT_PENALTY.get(self.armor_type, 0)
        return base_cost + penalty

    def can_move(self, base_cost: int) -> bool:
        """Return True if the entity can afford to move on terrain with *base_cost*."""
        return self.can_afford(self.movement_cost(base_cost))

    # ── Mutations ────────────────────────────────────────────────

    def spend(self, cost: int) -> bool:
        """Deduct *cost* AP.  Returns True on success, False if insufficient AP."""
        if cost < 0:
            raise ValueError(f"AP cost must be non-negative, got {cost}")
        if self.current_ap < cost:
            return False
        self.current_ap -= cost
        return True

    def spend_movement(self, base_cost: int) -> bool:
        """Deduct movement AP including armor penalty.  Returns True on success."""
        return self.spend(self.movement_cost(base_cost))

    def refresh(self) -> None:
        """Restore AP to maximum (called at the start of each turn)."""
        self.current_ap = self.max_ap

    def set_armor(self, armor_type: str) -> None:
        """Update the equipped armor type (affects future movement costs)."""
        self.armor_type = armor_type

    def to_dict(self) -> dict:
        """Serialize AP tracker for save/load."""
        return {
            "max_ap": self.max_ap,
            "current_ap": self.current_ap,
            "armor_type": self.armor_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionPointTracker":
        """Deserialize AP tracker from a dict."""
        tracker = cls(max_ap=data.get("max_ap", 4), armor_type=data.get("armor_type", "none"))
        tracker.current_ap = data.get("current_ap", tracker.max_ap)
        return tracker
