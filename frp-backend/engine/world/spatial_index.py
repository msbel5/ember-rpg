"""
Ember RPG -- Spatial Index (Sprint 1, FR-02)

O(1) grid-based lookup: what entities are at position (x, y)?
Inspired by Rimworld's ThingGrid.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from engine.world.entity import Entity, EntityType


class SpatialIndex:
    """
    Grid-backed spatial index for fast entity queries.

    Internal storage: dict mapping (x, y) -> list[Entity].
    All lookups are O(1) for a single cell, O(r^2) for radius queries.
    """

    def __init__(self) -> None:
        self._grid: Dict[Tuple[int, int], List[Entity]] = defaultdict(list)
        # Reverse map: entity.id -> position for fast move/remove
        self._positions: Dict[str, Tuple[int, int]] = {}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def add(self, entity: Entity) -> None:
        """Add an entity to the index at its current position."""
        pos = entity.position
        self._grid[pos].append(entity)
        self._positions[entity.id] = pos

    def remove(self, entity: Entity) -> None:
        """Remove an entity from the index."""
        pos = self._positions.get(entity.id)
        if pos is None:
            return
        cell = self._grid.get(pos, [])
        self._grid[pos] = [e for e in cell if e.id != entity.id]
        if not self._grid[pos]:
            del self._grid[pos]
        del self._positions[entity.id]

    def move(self, entity: Entity, new_x: int, new_y: int) -> None:
        """Move an entity to a new position, updating both the grid and the entity."""
        self.remove(entity)
        entity.position = (new_x, new_y)
        self.add(entity)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def at(self, x: int, y: int) -> List[Entity]:
        """Return all entities at (x, y). O(1)."""
        return list(self._grid.get((x, y), []))

    def blocking_at(self, x: int, y: int) -> bool:
        """Return True if any blocking entity occupies (x, y). O(1)."""
        for e in self._grid.get((x, y), []):
            if e.blocking:
                return True
        return False

    def in_radius(self, x: int, y: int, radius: float) -> List[Entity]:
        """
        Return all entities within Chebyshev distance *radius* of (x, y).
        Iterates over the bounding box, so cost is O((2r+1)^2).
        """
        r = int(math.ceil(radius))
        result: List[Entity] = []
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                cx, cy = x + dx, y + dy
                for e in self._grid.get((cx, cy), []):
                    # Chebyshev distance check
                    if max(abs(e.position[0] - x), abs(e.position[1] - y)) <= radius:
                        result.append(e)
        return result

    def entities_of_type(self, entity_type: EntityType) -> List[Entity]:
        """Return all entities of a given type. O(n) over all cells."""
        result: List[Entity] = []
        seen: Set[str] = set()
        for cell in self._grid.values():
            for e in cell:
                if e.entity_type == entity_type and e.id not in seen:
                    result.append(e)
                    seen.add(e.id)
        return result

    def all_entities(self) -> List[Entity]:
        """Return all entities in the index."""
        result: List[Entity] = []
        seen: Set[str] = set()
        for cell in self._grid.values():
            for e in cell:
                if e.id not in seen:
                    result.append(e)
                    seen.add(e.id)
        return result

    def count(self) -> int:
        """Return total number of tracked entities."""
        return len(self._positions)

    def get_position(self, entity_id: str) -> Optional[Tuple[int, int]]:
        """Get the tracked position for an entity by ID."""
        return self._positions.get(entity_id)

    def clear(self) -> None:
        """Remove all entities."""
        self._grid.clear()
        self._positions.clear()
