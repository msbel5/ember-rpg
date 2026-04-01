## Client-side walk animation controller.
## Computes a simple path from player to target tile, then animates
## the player sprite tile-by-tile while issuing one backend "move to"
## command for the final destination.  World ticks happen server-side
## when the backend processes the move command; this script only
## handles the visual walk so the player sees movement instead of a
## teleport.
extends RefCounted
class_name WorldWalk

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

const STEP_DURATION := 0.22  # seconds per tile
const MAX_PATH_LENGTH := 40  # don't animate absurdly long walks

signal walk_started(path: Array[Vector2i])
signal walk_step(tile: Vector2i, step_index: int)
signal walk_finished(destination: Vector2i)
signal walk_cancelled()

var is_walking: bool = false
var _path: Array[Vector2i] = []
var _step_index: int = 0


# --- public API -----------------------------------------------------------

func compute_path(
	from_tile: Vector2i,
	to_tile: Vector2i,
	map_data: Dictionary,
) -> Array[Vector2i]:
	"""Simple BFS pathfinding on the tile grid.  Walls and water block."""
	if from_tile == to_tile:
		return []
	var width := int(map_data.get("width", 0))
	var height := int(map_data.get("height", 0))
	if width <= 0 or height <= 0:
		return [to_tile]
	var tiles: Array = map_data.get("tiles", [])

	var open: Array[Vector2i] = [from_tile]
	var came_from: Dictionary = {_key(from_tile): Vector2i(-1, -1)}
	var directions := [
		Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0),
	]

	while not open.is_empty():
		var current: Vector2i = open.pop_front()
		if current == to_tile:
			return _reconstruct(came_from, to_tile, from_tile)
		for dir in directions:
			var neighbor := current + dir
			if neighbor.x < 0 or neighbor.y < 0 or neighbor.x >= width or neighbor.y >= height:
				continue
			if came_from.has(_key(neighbor)):
				continue
			if _is_blocked(tiles, neighbor):
				continue
			came_from[_key(neighbor)] = current
			open.append(neighbor)
			if open.size() > MAX_PATH_LENGTH * MAX_PATH_LENGTH:
				break
	# No path found — fall back to direct line
	return [to_tile]


func start_walk(path: Array[Vector2i]) -> void:
	if path.is_empty():
		return
	_path = path.duplicate()
	if _path.size() > MAX_PATH_LENGTH:
		_path.resize(MAX_PATH_LENGTH)
	_step_index = 0
	is_walking = true
	walk_started.emit(_path)


func advance_step() -> bool:
	"""Called each time the tween for one tile completes.
	Returns true if there are more steps, false when walk is done."""
	_step_index += 1
	if _step_index >= _path.size():
		is_walking = false
		walk_finished.emit(_path[_path.size() - 1])
		return false
	walk_step.emit(_path[_step_index], _step_index)
	return true


func cancel() -> void:
	if is_walking:
		is_walking = false
		_path.clear()
		walk_cancelled.emit()


func current_tile() -> Vector2i:
	if _path.is_empty() or _step_index >= _path.size():
		return Vector2i.ZERO
	return _path[_step_index]


func destination() -> Vector2i:
	if _path.is_empty():
		return Vector2i.ZERO
	return _path[_path.size() - 1]


func remaining_steps() -> int:
	return maxi(0, _path.size() - _step_index)


# --- internals -------------------------------------------------------------

func _is_blocked(tiles: Array, pos: Vector2i) -> bool:
	if pos.y < 0 or pos.y >= tiles.size():
		return true
	var row = tiles[pos.y]
	if not (row is Array) or pos.x < 0 or pos.x >= row.size():
		return true
	var name := TileCatalog.resolve_tile_name(row[pos.x])
	return name in ["wall", "water", "void", ""]


func _reconstruct(
	came_from: Dictionary,
	target: Vector2i,
	start: Vector2i,
) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	var current := target
	while current != start:
		path.append(current)
		var prev = came_from.get(_key(current), Vector2i(-1, -1))
		if prev == Vector2i(-1, -1):
			break
		current = prev
	path.reverse()
	return path


func _key(tile: Vector2i) -> int:
	return tile.x * 10000 + tile.y
