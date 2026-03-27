extends RefCounted
class_name ResponseNormalizer

const INVENTORY_COMMAND_MARKERS := [
	"inventory",
	"inv",
	"pick up",
	"pickup",
	"take ",
	"loot",
	"drop ",
	"equip",
	"unequip",
	"use ",
	"consume",
	"drink ",
	"buy ",
	"sell ",
	"trade",
	"craft",
	"wear ",
	"remove ",
]


static func normalize_combat(data: Dictionary) -> Dictionary:
	if data.has("combat_state") and data["combat_state"] is Dictionary:
		return data["combat_state"]
	if data.has("combat") and data["combat"] is Dictionary:
		return data["combat"]
	return {}


static func normalize_map(data: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	if data.has("map_data") and data["map_data"] is Dictionary:
		return _merge_and_normalize_map(data["map_data"], current_map)
	if data.has("map") and data["map"] is Dictionary:
		return _merge_and_normalize_map(data["map"], current_map)
	return {}


static func normalize_entities(data: Dictionary) -> Dictionary:
	if data.has("world_entities") and data["world_entities"] is Array and not data["world_entities"].is_empty():
		return group_world_entities(data["world_entities"])
	if data.has("entities"):
		if data["entities"] is Dictionary:
			return data["entities"]
		if data["entities"] is Array:
			return group_entity_list(data["entities"])
	if data.has("world_entities") and data["world_entities"] is Array:
		return group_world_entities(data["world_entities"])
	return {}


static func group_entity_list(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": guess_entity_template(entry),
			"position": entry.get("position", [0, 0]),
			"role": entry.get("role", ""),
			"context_actions": context_actions_for(entry),
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped


static func group_world_entities(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("entity_type", "npc")).to_lower()
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": guess_entity_template(entry),
			"position": entry.get("position", [0, 0]),
			"context_actions": context_actions_for(entry),
			"is_hostile": str(entry.get("disposition", "")).to_lower() == "hostile",
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type == "creature" or normalized["is_hostile"]:
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped


static func guess_entity_template(entry: Dictionary) -> String:
	var explicit_template = str(entry.get("template", "")).strip_edges().to_lower()
	if not explicit_template.is_empty():
		return explicit_template
	var role = str(entry.get("role", entry.get("job", ""))).to_lower()
	if not role.is_empty():
		return role.replace(" ", "_")
	var name_hint = str(entry.get("name", "")).to_lower()
	for candidate in ["merchant", "guard", "blacksmith", "priest", "beggar", "goblin", "skeleton", "orc", "wolf", "rat", "spider"]:
		if name_hint.contains(candidate):
			return candidate
	var entity_type = str(entry.get("type", entry.get("entity_type", "warrior"))).to_lower()
	if entity_type == "item":
		return "chest"
	return "warrior"


static func context_actions_for(entry: Dictionary) -> Array:
	if entry.has("context_actions") and entry["context_actions"] is Array:
		return entry["context_actions"]
	var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
	if entity_type == "item":
		return ["examine", "pick up"]
	if entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
		return ["attack", "examine"]
	var role = str(entry.get("role", entry.get("job", ""))).to_lower()
	if ["merchant", "innkeeper", "blacksmith"].has(role):
		return ["talk", "trade", "examine"]
	return ["talk", "examine"]


static func player_position_from(player_data: Dictionary, fallback: Vector2i = Vector2i.ZERO) -> Vector2i:
	if player_data.has("position") and player_data["position"] is Array and player_data["position"].size() >= 2:
		return Vector2i(int(player_data["position"][0]), int(player_data["position"][1]))
	return fallback


static func facing_to_int(facing: String, fallback: int = 2) -> int:
	match facing.to_lower():
		"north":
			return 0
		"east":
			return 1
		"south":
			return 2
		"west":
			return 3
	return fallback


static func command_requires_inventory_refresh(text: String) -> bool:
	var lower = text.to_lower().strip_edges()
	if lower.is_empty():
		return false
	for marker in INVENTORY_COMMAND_MARKERS:
		if lower == marker or lower.begins_with(marker) or lower.contains(marker):
			return true
	return false


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
			return "wood_floor"
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
			return "wood_floor"
	return tile_name
