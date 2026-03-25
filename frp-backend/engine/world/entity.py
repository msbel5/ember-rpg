"""
Ember RPG -- Entity System (Sprint 1, FR-01)

Unified Entity dataclass with optional components for NPCs, creatures,
items, buildings, and furniture. Every thing in the game world is an Entity.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from engine.world.npc_needs import NPCNeeds
from engine.world.body_parts import BodyPartTracker


class EntityType(Enum):
    """All entity categories in the game world."""
    NPC = "npc"
    CREATURE = "creature"
    ITEM = "item"
    BUILDING = "building"
    FURNITURE = "furniture"


# Dispositions ordered from hostile to friendly
DISPOSITIONS = ("hostile", "afraid", "neutral", "friendly")


@dataclass
class Entity:
    """
    A single thing in the game world — NPC, creature, item, building, or furniture.

    Required fields define identity and rendering.
    Optional component fields are attached based on entity_type.
    """

    # --- Identity ---
    id: str
    entity_type: EntityType
    name: str
    position: Tuple[int, int]
    glyph: str          # single ASCII character
    color: str           # terminal color name (e.g. "red", "green", "white")
    blocking: bool       # whether this entity blocks movement

    # --- Optional components (attached based on type) ---
    needs: Optional[NPCNeeds] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    skills: Optional[Dict[str, int]] = None
    body: Optional[BodyPartTracker] = None
    faction: Optional[str] = None
    schedule: Optional[Any] = None       # NPCSchedule or dict
    job: Optional[str] = None

    # --- State ---
    alive: bool = True
    hp: int = 10
    max_hp: int = 10
    disposition: str = "neutral"          # friendly / neutral / hostile / afraid
    ap: int = 4
    max_ap: int = 4

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_id() -> str:
        """Generate a unique entity ID."""
        return str(uuid.uuid4())[:8]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_hostile(self) -> bool:
        """Return True if this entity is hostile toward the player."""
        return self.disposition == "hostile"

    def is_friendly(self) -> bool:
        """Return True if this entity is friendly toward the player."""
        return self.disposition == "friendly"

    def is_alive(self) -> bool:
        """Return True if the entity is alive (hp > 0 and alive flag)."""
        return self.alive and self.hp > 0

    def is_npc(self) -> bool:
        return self.entity_type == EntityType.NPC

    def is_creature(self) -> bool:
        return self.entity_type == EntityType.CREATURE

    def is_item(self) -> bool:
        return self.entity_type == EntityType.ITEM

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def take_damage(self, amount: int) -> int:
        """Apply damage, return actual damage dealt. Marks dead if hp <= 0."""
        actual = min(amount, self.hp)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return actual

    def heal(self, amount: int) -> int:
        """Heal hp, capped at max_hp. Returns actual amount healed."""
        actual = min(amount, self.max_hp - self.hp)
        self.hp += actual
        return actual

    def spend_ap(self, cost: int) -> bool:
        """Spend action points. Returns False if insufficient AP."""
        if self.ap < cost:
            return False
        self.ap -= cost
        return True

    def reset_ap(self) -> None:
        """Reset AP to max at start of turn."""
        self.ap = self.max_ap

    def move_to(self, x: int, y: int) -> None:
        """Update position."""
        self.position = (x, y)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entity to a plain dict for save/load and API responses."""
        d: Dict[str, Any] = {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "position": list(self.position),
            "glyph": self.glyph,
            "color": self.color,
            "blocking": self.blocking,
            "alive": self.alive,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "disposition": self.disposition,
            "ap": self.ap,
            "max_ap": self.max_ap,
        }
        if self.needs is not None:
            d["needs"] = self.needs.to_dict()
        if self.inventory is not None:
            d["inventory"] = self.inventory
        if self.skills is not None:
            d["skills"] = self.skills
        if self.body is not None:
            d["body"] = self.body.to_dict()
        if self.faction is not None:
            d["faction"] = self.faction
        if self.schedule is not None:
            if hasattr(self.schedule, "to_dict"):
                d["schedule"] = self.schedule.to_dict()
            elif isinstance(self.schedule, dict):
                d["schedule"] = self.schedule
        if self.job is not None:
            d["job"] = self.job
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """Deserialize an Entity from a dict."""
        needs = None
        if "needs" in data:
            needs = NPCNeeds.from_dict(data["needs"])
        body = None
        if "body" in data:
            body = BodyPartTracker.from_dict(data["body"])
        schedule = data.get("schedule")
        if isinstance(schedule, dict) and "npc_id" in schedule and "npc_name" in schedule:
            from engine.world.schedules import NPCSchedule
            schedule = NPCSchedule.from_dict(schedule)
        return cls(
            id=data["id"],
            entity_type=EntityType(data["entity_type"]),
            name=data["name"],
            position=tuple(data["position"]),
            glyph=data["glyph"],
            color=data["color"],
            blocking=data["blocking"],
            needs=needs,
            inventory=data.get("inventory"),
            skills=data.get("skills"),
            body=body,
            faction=data.get("faction"),
            schedule=schedule,
            job=data.get("job"),
            alive=data.get("alive", True),
            hp=data.get("hp", 10),
            max_hp=data.get("max_hp", 10),
            disposition=data.get("disposition", "neutral"),
            ap=data.get("ap", 4),
            max_ap=data.get("max_ap", 4),
        )

    def __repr__(self) -> str:
        return (
            f"Entity(id={self.id!r}, type={self.entity_type.value}, "
            f"name={self.name!r}, pos={self.position}, glyph={self.glyph!r})"
        )
