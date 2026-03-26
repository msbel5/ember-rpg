"""
Module 10: Proximity Rules (FR-42..FR-45)
Handles distance checks, interaction ranges, and A* pathfinding.
"""
import math
from typing import Optional, List, Set, Tuple
from engine.map import MapData, TileType


# Interaction range constants (in tiles)
RANGE_MELEE = 1       # examine, trade, pickup, melee attack
RANGE_SOCIAL = 3      # talk, persuade, bribe, deceive, intimidate (3 tiles = conversation distance)
RANGE_SHOUT = 5       # yell, shout (across a room)
RANGE_RANGED = 5      # ranged attack (bow, spell)
RANGE_LOOK = 999      # look has unlimited range
MAX_MOVE_PER_TURN = 5 # max tiles per click-to-move


def distance(pos_a: list, pos_b: list) -> float:
    """Chebyshev distance (king-move distance) between two tile positions."""
    return max(abs(pos_a[0] - pos_b[0]), abs(pos_a[1] - pos_b[1]))


def manhattan_distance(pos_a: list, pos_b: list) -> int:
    """Manhattan distance between two positions."""
    return abs(pos_a[0] - pos_b[0]) + abs(pos_a[1] - pos_b[1])


def in_range(player_pos: list, target_pos: list, max_range: int) -> bool:
    """Check if target is within interaction range of player."""
    return distance(player_pos, target_pos) <= max_range


def get_interaction_range(action_type: str) -> int:
    """Return required range for an action type."""
    ranges = {
        "talk": RANGE_SOCIAL,
        "social": RANGE_SOCIAL,
        "examine": RANGE_MELEE,
        "trade": RANGE_MELEE,
        "pickup": RANGE_MELEE,
        "attack_melee": RANGE_MELEE,
        "attack_ranged": RANGE_RANGED,
        "shout": RANGE_SHOUT,
        "look": RANGE_LOOK,
    }
    return ranges.get(action_type, RANGE_MELEE)


def check_proximity(player_pos: list, target_pos: list, action_type: str) -> Tuple[bool, str]:
    """
    Check if player can perform action on target at given positions.

    Returns:
        (allowed, message) — if not allowed, message explains why.
    """
    required = get_interaction_range(action_type)
    dist = distance(player_pos, target_pos)

    if dist <= required:
        return True, ""

    return False, f"Too far away ({int(dist)} tiles). Move closer to interact (need {required} or less)."


def has_line_of_sight(map_data: Optional[MapData], pos_a: list, pos_b: list) -> bool:
    """
    Check line of sight between two positions using Bresenham's line algorithm.
    Returns True if no walls block the path.
    If map_data is None, assume clear line of sight.
    """
    if map_data is None:
        return True

    x0, y0 = pos_a[0], pos_a[1]
    x1, y1 = pos_b[0], pos_b[1]

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        if (x0, y0) != tuple(pos_a) and (x0, y0) != tuple(pos_b):
            tile = map_data.get_tile(x0, y0)
            if tile == TileType.WALL:
                return False

        if x0 == x1 and y0 == y1:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy

    return True


def can_move_to(map_data: Optional[MapData], x: int, y: int) -> bool:
    """Check if a tile is walkable."""
    if map_data is None:
        return True
    return map_data.is_walkable(x, y)


def move_cardinal(position: list, direction: str, map_data: Optional[MapData] = None) -> Tuple[list, bool, str]:
    """
    Move one tile in a cardinal direction.

    Returns:
        (new_position, success, message)
    """
    deltas = {
        "north": (0, -1),
        "south": (0, 1),
        "east": (1, 0),
        "west": (-1, 0),
    }

    delta = deltas.get(direction.lower())
    if delta is None:
        return position, False, f"Unknown direction: {direction}"

    new_x = position[0] + delta[0]
    new_y = position[1] + delta[1]

    if map_data is not None:
        if new_x < 0 or new_y < 0 or new_x >= map_data.width or new_y >= map_data.height:
            return position, False, "You can't go that way — edge of the map."
        if not can_move_to(map_data, new_x, new_y):
            return position, False, "You can't go that way — blocked by a wall."

    return [new_x, new_y], True, ""


def astar_path(
    map_data: Optional[MapData],
    start: list,
    goal: list,
    max_steps: int = MAX_MOVE_PER_TURN,
    blocked_positions: Optional[Set[Tuple[int, int]]] = None,
) -> List[list]:
    """
    A* pathfinding from start to goal.
    Returns list of positions to walk (excluding start), capped at max_steps.
    Returns empty list if no path found.
    """
    if map_data is None:
        # Without map, return straight line path capped at max_steps
        path = []
        cx, cy = start[0], start[1]
        for _ in range(max_steps):
            if cx == goal[0] and cy == goal[1]:
                break
            dx = goal[0] - cx
            dy = goal[1] - cy
            # Move one step toward goal
            sx = (1 if dx > 0 else -1) if dx != 0 else 0
            sy = (1 if dy > 0 else -1) if dy != 0 else 0
            # Prefer axis with greater distance
            if abs(dx) >= abs(dy) and dx != 0:
                cx += sx
            elif dy != 0:
                cy += sy
            elif dx != 0:
                cx += sx
            path.append([cx, cy])
        return path

    # Full A* with map collision
    import heapq

    start_t = (start[0], start[1])
    goal_t = (goal[0], goal[1])

    blocked = set(blocked_positions or set())

    if goal_t in blocked:
        return []
    if not map_data.is_walkable(goal_t[0], goal_t[1]):
        # Find nearest walkable tile to goal
        return []

    open_set = []
    heapq.heappush(open_set, (0, start_t))
    came_from = {}
    g_score = {start_t: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal_t:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append([current[0], current[1]])
                current = came_from[current]
            path.reverse()
            return path[:max_steps]

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = current[0] + dx, current[1] + dy
            neighbor = (nx, ny)

            if not (0 <= nx < map_data.width and 0 <= ny < map_data.height):
                continue
            if not map_data.is_walkable(nx, ny):
                continue
            if neighbor in blocked:
                continue

            tentative_g = g_score[current] + 1

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + manhattan_distance([nx, ny], goal)
                heapq.heappush(open_set, (f, neighbor))

    return []  # No path found
