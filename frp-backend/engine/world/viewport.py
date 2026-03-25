"""
Ember RPG -- Viewport / Camera (Sprint 1, FR-03 / FR-05)

Handles camera positioning, coordinate transforms, and fog of war.
FOV computed via simple shadow casting (recursive).
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional, Set, Tuple


class Viewport:
    """
    Camera that tracks a rectangular view of the world map.

    Coordinates:
        World: (wx, wy) — absolute tile position on the map.
        Screen: (sx, sy) — position relative to the viewport's top-left corner.

    The viewport is centred on a world position. Scrolling moves the centre.
    """

    def __init__(self, width: int = 40, height: int = 20) -> None:
        self.width = width
        self.height = height
        # Centre of the viewport in world coordinates
        self.center_x: int = 0
        self.center_y: int = 0

        # Fog of war
        self.fog_of_war: Set[Tuple[int, int]] = set()   # tiles ever seen
        self.visible: Set[Tuple[int, int]] = set()       # tiles currently in LOS

    # ------------------------------------------------------------------
    # Camera control
    # ------------------------------------------------------------------

    def center_on(self, x: int, y: int) -> None:
        """Centre the viewport on world position (x, y)."""
        self.center_x = x
        self.center_y = y

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll the viewport by (dx, dy) tiles."""
        self.center_x += dx
        self.center_y += dy

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    @property
    def left(self) -> int:
        """World x of the viewport's left edge."""
        return self.center_x - self.width // 2

    @property
    def top(self) -> int:
        """World y of the viewport's top edge."""
        return self.center_y - self.height // 2

    def world_to_screen(self, wx: int, wy: int) -> Tuple[int, int]:
        """Convert world coordinates to screen (viewport-relative) coordinates."""
        sx = wx - self.left
        sy = wy - self.top
        return (sx, sy)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[int, int]:
        """Convert screen coordinates back to world coordinates."""
        wx = sx + self.left
        wy = sy + self.top
        return (wx, wy)

    def in_bounds(self, wx: int, wy: int) -> bool:
        """Check if a world position is within the current viewport rectangle."""
        sx, sy = self.world_to_screen(wx, wy)
        return 0 <= sx < self.width and 0 <= sy < self.height

    # ------------------------------------------------------------------
    # Fog of war queries
    # ------------------------------------------------------------------

    def is_visible(self, x: int, y: int) -> bool:
        """True if tile is currently visible (within LOS this turn)."""
        return (x, y) in self.visible

    def is_explored(self, x: int, y: int) -> bool:
        """True if tile has ever been seen (in fog_of_war set)."""
        return (x, y) in self.fog_of_war

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        """Serialize viewport state for save/load."""
        return {
            "width": self.width,
            "height": self.height,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "fog_of_war": [list(p) for p in self.fog_of_war],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Viewport":
        """Deserialize viewport from a dict."""
        vp = cls(width=data.get("width", 40), height=data.get("height", 20))
        vp.center_x = data.get("center_x", 0)
        vp.center_y = data.get("center_y", 0)
        vp.fog_of_war = {tuple(p) for p in data.get("fog_of_war", [])}
        # visible is recomputed each turn, so we don't persist it
        return vp

    # ------------------------------------------------------------------
    # Field of View (FOV) computation
    # ------------------------------------------------------------------

    def compute_fov(
        self,
        is_blocking: Callable[[int, int], bool],
        player_x: int,
        player_y: int,
        radius: int = 8,
    ) -> None:
        """
        Compute field of view from (player_x, player_y) using recursive
        shadow casting. Updates self.visible and self.fog_of_war.

        Args:
            is_blocking: Callable(x, y) -> bool. Returns True if tile blocks LOS
                         (e.g. walls). Should return False for out-of-bounds.
            player_x, player_y: Origin of the FOV.
            radius: Sight radius in tiles.
        """
        self.visible.clear()

        # The origin is always visible
        self.visible.add((player_x, player_y))
        self.fog_of_war.add((player_x, player_y))

        # Multipliers for the 8 octants.
        # Each octant is defined by (xx, xy, yx, yy) where:
        #   world_dx = col * xx + row * xy
        #   world_dy = col * yx + row * yy
        _mult = [
            (1, 0, 0, 1),
            (0, 1, 1, 0),
            (0, -1, 1, 0),
            (-1, 0, 0, 1),
            (-1, 0, 0, -1),
            (0, -1, -1, 0),
            (0, 1, -1, 0),
            (1, 0, 0, -1),
        ]

        for xx, xy, yx, yy in _mult:
            self._cast_light(
                is_blocking, player_x, player_y, radius,
                1, 1.0, 0.0, xx, xy, yx, yy,
            )

    def _cast_light(
        self,
        is_blocking: Callable[[int, int], bool],
        cx: int,
        cy: int,
        radius: int,
        row: int,
        start: float,
        end: float,
        xx: int,
        xy: int,
        yx: int,
        yy: int,
    ) -> None:
        """Recursive shadow-casting for one octant."""
        if start < end:
            return

        radius_sq = radius * radius
        new_start = 0.0

        for j in range(row, radius + 1):
            dx, dy = -j - 1, -j
            blocked = False

            while dx <= 0:
                dx += 1
                # Translate from octant-local to world coordinates
                mx = cx + dx * xx + dy * xy
                my = cy + dx * yx + dy * yy

                # Slopes for this cell
                l_slope = (dx - 0.5) / (dy + 0.5)
                r_slope = (dx + 0.5) / (dy - 0.5)

                if start < r_slope:
                    continue
                elif end > l_slope:
                    break

                # Check radius (Euclidean)
                ddx = mx - cx
                ddy = my - cy
                if ddx * ddx + ddy * ddy <= radius_sq:
                    self.visible.add((mx, my))
                    self.fog_of_war.add((mx, my))

                if blocked:
                    if is_blocking(mx, my):
                        new_start = r_slope
                        continue
                    else:
                        blocked = False
                        start = new_start
                else:
                    if is_blocking(mx, my) and j < radius:
                        blocked = True
                        self._cast_light(
                            is_blocking, cx, cy, radius,
                            j + 1, start, l_slope,
                            xx, xy, yx, yy,
                        )
                        new_start = r_slope

            if blocked:
                break

    # ------------------------------------------------------------------
    # Simple raycasting alternative (Bresenham-based)
    # ------------------------------------------------------------------

    def compute_fov_simple(
        self,
        is_blocking: Callable[[int, int], bool],
        player_x: int,
        player_y: int,
        radius: int = 8,
    ) -> None:
        """
        Simpler FOV using raycasting to perimeter points.
        Less accurate than shadow casting but easier to reason about.
        """
        self.visible.clear()
        self.visible.add((player_x, player_y))
        self.fog_of_war.add((player_x, player_y))

        # Cast rays to every point on the perimeter circle
        steps = max(8, radius * 6)  # enough rays to cover the circle
        for i in range(steps):
            angle = 2.0 * math.pi * i / steps
            tx = player_x + round(math.cos(angle) * radius)
            ty = player_y + round(math.sin(angle) * radius)
            self._cast_ray(is_blocking, player_x, player_y, tx, ty, radius)

    def _cast_ray(
        self,
        is_blocking: Callable[[int, int], bool],
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        radius: int,
    ) -> None:
        """Bresenham ray from (x0,y0) toward (x1,y1), marking visible tiles."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        cx, cy = x0, y0

        while True:
            dist_sq = (cx - x0) ** 2 + (cy - y0) ** 2
            if dist_sq > radius * radius:
                break

            self.visible.add((cx, cy))
            self.fog_of_war.add((cx, cy))

            if is_blocking(cx, cy) and (cx, cy) != (x0, y0):
                break

            if cx == x1 and cy == y1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy
