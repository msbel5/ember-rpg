extends RefCounted
class_name ResponseMapNormalizer


static func normalize_map(data: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	if data.has("map_data") and data["map_data"] is Dictionary:
		return _merge_and_normalize_map(data["map_data"], current_map)
	if data.has("map") and data["map"] is Dictionary:
		return _merge_and_normalize_map(data["map"], current_map)
	return {}


static func campaign_region_to_map(region_payload: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	var normalized = current_map.duplicate(true) if not current_map.is_empty() else {}
	normalized["width"] = int(region_payload.get("width", current_map.get("width", 0)))
	normalized["height"] = int(region_payload.get("height", current_map.get("height", 0)))
	normalized["metadata"] = {
		"map_type": "campaign_region",
		"region_id": str(region_payload.get("region_id", "")),
		"biome_id": str(region_payload.get("biome_id", "")),
	}
	var layout = region_payload.get("layout", {})
	if layout is Dictionary:
		var center_feature = layout.get("center_feature", {})
		if center_feature is Dictionary and center_feature.has("x") and center_feature.has("y"):
			normalized["spawn_point"] = [int(center_feature.get("x", 1)), mini(int(center_feature.get("y", 1)) + 2, normalized["height"] - 1)]
	var typed_tiles = region_payload.get("typed_tiles", [])
	if typed_tiles is Array and not typed_tiles.is_empty():
		var tile_rows: Array = []
		for row in typed_tiles:
			if not (row is Array):
				continue
			var normalized_row: Array = []
			for cell in row:
				if cell is Dictionary:
					normalized_row.append(str(cell.get("terrain", "grass")))
				else:
					normalized_row.append(_normalize_tile_symbol(cell, "campaign_region"))
			tile_rows.append(normalized_row)
		normalized["tiles"] = tile_rows
	return normalized


static func _merge_and_normalize_map(map_payload: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	var normalized = current_map.duplicate(true) if not current_map.is_empty() else {}
	normalized.merge(map_payload, true)
	if normalized.has("tiles") and normalized["tiles"] is Array:
		normalized["tiles"] = _normalize_tile_rows(normalized["tiles"], _map_type_from_payload(normalized))
	return normalized


static func _map_type_from_payload(map_payload: Dictionary) -> String:
	if map_payload.has("metadata") and map_payload["metadata"] is Dictionary:
		return str(map_payload["metadata"].get("map_type", "")).to_lower()
	if map_payload.has("map_type"):
		return str(map_payload.get("map_type", "")).to_lower()
	return ""


static func _normalize_tile_rows(rows: Array, map_type: String) -> Array:
	var normalized_rows: Array = []
	for row in rows:
		if not (row is Array):
			normalized_rows.append(row)
			continue
		var normalized_row: Array = []
		for cell in row:
			normalized_row.append(_normalize_tile_symbol(cell, map_type))
		normalized_rows.append(normalized_row)
	return normalized_rows


static func _normalize_tile_symbol(raw_value, map_type: String) -> String:
	var tile_name = str(raw_value).strip_edges().to_lower()
	if tile_name.is_empty():
		return "grass"
	match tile_name:
		"#", "wall":
			return "wall"
		"~", "water":
			return "water"
		"t":
			return "wall"
		"d":
			return "door"
		">", "<":
			return "stone_floor"
		",":
			return "stone_floor" if map_type == "dungeon" else "dirt_path"
		"=":
			return "cobblestone" if map_type == "town" else "dirt_path"
		".":
			if map_type == "dungeon":
				return "stone_floor"
			return "grass"
		"corridor":
			return "stone_floor"
		"door":
			return "door"
		"road":
			return "cobblestone"
		"cobble", "cobblestone":
			return "cobblestone"
		"floor", "wood_floor", "stone_floor":
			return tile_name
		"well", "fountain", "tree":
			return tile_name
	return tile_name
