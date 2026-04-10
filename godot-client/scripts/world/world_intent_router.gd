extends RefCounted
class_name WorldIntentRouter


static func route_walk_or_interact(
	walker: WorldWalk,
	player_tile: Vector2i,
	target_tile: Vector2i,
	entity: Dictionary,
	map_data: Dictionary,
	tile_name_at: Callable,
	tile_in_bounds: Callable,
) -> Dictionary:
	walker.cancel()
	if player_tile == Vector2i.ZERO:
		return _direct_result(target_tile, entity, str(tile_name_at.call(target_tile)))

	if not entity.is_empty():
		var dist: int = abs(target_tile.x - player_tile.x) + abs(target_tile.y - player_tile.y)
		if dist <= 1:
			return {"command": WorldInteraction.command_for_entity(entity)}
		var adjacent := _find_adjacent(target_tile, player_tile, tile_name_at, tile_in_bounds)
		var entity_path := walker.compute_path(player_tile, adjacent, map_data)
		if entity_path.is_empty():
			return {"command": WorldInteraction.command_for_entity(entity)}
		return {
			"commands": [
				"move to %d,%d" % [adjacent.x, adjacent.y],
				WorldInteraction.command_for_entity(entity),
			]
		}

	var tile_name := str(tile_name_at.call(target_tile))
	var path := walker.compute_path(player_tile, target_tile, map_data)
	if path.is_empty():
		return {"command": WorldInteraction.command_for_tile(target_tile, tile_name)}
	var commands: Array[String] = ["move to %d,%d" % [target_tile.x, target_tile.y]]
	if tile_name in WorldInteraction.INTERACTIVE_TILE_NAMES:
		commands.append(WorldInteraction.command_for_tile(target_tile, tile_name))
	return {"commands": commands}


static func _direct_result(target_tile: Vector2i, entity: Dictionary, tile_name: String) -> Dictionary:
	if not entity.is_empty():
		return {"command": WorldInteraction.command_for_entity(entity)}
	return {"command": WorldInteraction.command_for_tile(target_tile, tile_name)}


static func _find_adjacent(
	target: Vector2i,
	from: Vector2i,
	tile_name_at: Callable,
	tile_in_bounds: Callable,
) -> Vector2i:
	var best := target
	var best_dist := 99999
	for dir in [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]:
		var candidate: Vector2i = target + dir
		if not bool(tile_in_bounds.call(candidate)):
			continue
		var tile_name := str(tile_name_at.call(candidate))
		if tile_name in ["wall", "water", "void"]:
			continue
		var dist: int = abs(candidate.x - from.x) + abs(candidate.y - from.y)
		if dist < best_dist:
			best = candidate
			best_dist = dist
	return best


static func _commands_for_path(from_tile: Vector2i, path: Array[Vector2i]) -> Array[String]:
	var commands: Array[String] = []
	var previous := from_tile
	for tile in path:
		var delta := tile - previous
		match delta:
			Vector2i(0, -1):
				commands.append("move north")
			Vector2i(0, 1):
				commands.append("move south")
			Vector2i(-1, 0):
				commands.append("move west")
			Vector2i(1, 0):
				commands.append("move east")
			_:
				commands.append("move to %d,%d" % [tile.x, tile.y])
		previous = tile
	return commands
