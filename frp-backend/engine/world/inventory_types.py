"""Shared inventory types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ItemShape:
    """Grid footprint of an item."""

    cells: Tuple[Tuple[int, int], ...]
    rigid: bool = True

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def rotated(self, degrees: int) -> "ItemShape":
        if degrees == 0:
            return self
        rotated_cells = list(self.cells)
        for _ in range(degrees // 90):
            rotated_cells = [(-col, row) for row, col in rotated_cells]
        min_row = min(row for row, _col in rotated_cells)
        min_col = min(col for _row, col in rotated_cells)
        normalized = tuple(sorted((row - min_row, col - min_col) for row, col in rotated_cells))
        return ItemShape(cells=normalized, rigid=self.rigid)

    def all_orientations(self) -> List["ItemShape"]:
        if not self.rigid:
            return [self]
        seen: set[Tuple[Tuple[int, int], ...]] = set()
        result: List[ItemShape] = []
        for degrees in (0, 90, 180, 270):
            rotated = self.rotated(degrees)
            if rotated.cells not in seen:
                seen.add(rotated.cells)
                result.append(rotated)
        return result

    def bounding_box(self) -> Tuple[int, int]:
        if not self.cells:
            return (0, 0)
        return (max(row for row, _col in self.cells) + 1, max(col for _row, col in self.cells) + 1)

    def to_dict(self) -> Dict:
        return {"cells": [list(cell) for cell in self.cells], "rigid": self.rigid}

    @classmethod
    def from_dict(cls, data: Dict) -> "ItemShape":
        cells = tuple(tuple(cell) for cell in data.get("cells", [(0, 0)]))
        return cls(cells=cells, rigid=data.get("rigid", True))


class StashTier(int, Enum):
    SIMPLE = 1
    ADVANCED = 2
    MAGICAL = 3
