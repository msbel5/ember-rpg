## Handles entity/tile interaction commands and the right-click context menu.
## Extracted from world_view.gd to keep each file under 450 lines.
extends RefCounted
class_name WorldInteraction

const INTERACTIVE_TILE_NAMES := [
	"door", "well", "fountain", "tree", "chair", "table", "barrel",
	"bookshelf", "crate", "anvil", "bed", "bench", "chest", "altar",
]


# --- command generation ----------------------------------------------------

static func command_for_entity(entity: Dictionary) -> String:
	var entity_name := str(entity.get("name", "")).strip_edges().to_lower()
	if entity_name.is_empty():
		entity_name = "target"
	var actions = entity.get("context_actions", [])
	if actions is Array and not actions.is_empty():
		var primary_action := str(actions[0]).strip_edges().to_lower()
		match primary_action:
			"pick up":  return "pick up %s" % entity_name
			"attack":   return "attack %s" % entity_name
			"trade":    return "trade %s" % entity_name
			"talk":     return "talk %s" % entity_name
			"examine":  return "examine %s" % entity_name
	var bucket := str(entity.get("bucket", "npc"))
	match bucket:
		"enemy":     return "attack %s" % entity_name
		"item":      return "pick up %s" % entity_name
		"furniture": return "examine %s" % entity_name
		_:           return "talk %s" % entity_name


static func command_for_tile(tile_position: Vector2i, tile_name: String) -> String:
	match tile_name:
		"door":
			return "open door"
		"well", "fountain", "tree":
			return "examine %s" % tile_name
		"wall", "water":
			return "examine %s" % tile_name
		"chair", "table", "barrel", "bookshelf", "crate", "anvil", "bed", "bench", "chest", "altar":
			return "examine %s" % tile_name
	return "move to %d,%d" % [tile_position.x, tile_position.y]


static func command_for_context_action(action: String, entity_name: String, bucket: String) -> String:
	match action:
		"talk":     return "talk %s" % entity_name
		"trade":    return "trade %s" % entity_name
		"attack":   return "attack %s" % entity_name
		"pick up":  return "pick up %s" % entity_name
		"examine":  return "examine %s" % entity_name
	if bucket == "item":
		return "pick up %s" % entity_name
	return command_for_entity({"bucket": bucket, "name": entity_name})


# --- context menu construction ---------------------------------------------

static func build_entity_menu_items(entity: Dictionary) -> Array[Dictionary]:
	var items: Array[Dictionary] = []
	var entity_name := str(entity.get("name", "target")).strip_edges()
	var bucket := str(entity.get("bucket", "npc"))

	match bucket:
		"enemy":
			items.append({"label": "Attack %s" % entity_name, "id": 2})
			items.append({"label": "Examine %s" % entity_name, "id": 1})
		"npc":
			items.append({"label": "Talk to %s" % entity_name, "id": 0})
			items.append({"label": "Examine %s" % entity_name, "id": 1})
			items.append({"label": "Attack %s" % entity_name, "id": 2})
		"item":
			items.append({"label": "Use %s" % entity_name, "id": 4})
			items.append({"label": "Examine %s" % entity_name, "id": 1})
		"furniture":
			items.append({"label": "Use %s" % entity_name, "id": 4})
			items.append({"label": "Examine %s" % entity_name, "id": 1})
		_:
			items.append({"label": "Talk to %s" % entity_name, "id": 0})
			items.append({"label": "Examine %s" % entity_name, "id": 1})
	return items


static func build_ground_menu_items(tile_name: String) -> Array[Dictionary]:
	var items: Array[Dictionary] = [
		{"label": "Move here",    "id": 10},
		{"label": "Search area",  "id": 11},
		{"label": "Rest",         "id": 12},
	]
	if not tile_name.is_empty() and tile_name in INTERACTIVE_TILE_NAMES:
		items.append({"label": "Examine %s" % display_tile_name(tile_name), "id": 13})
	return items


static func resolve_context_command(
	id: int,
	entity: Dictionary,
	tile: Vector2i,
	tile_name: String,
) -> String:
	var entity_name := str(entity.get("name", "target")).strip_edges().to_lower()
	match id:
		0:  return "talk %s" % entity_name
		1:  return "examine %s" % entity_name
		2:  return "attack %s" % entity_name
		4:  return "pick up %s" % entity_name
		10: return "move to %d,%d" % [tile.x, tile.y]
		11: return "search area"
		12: return "rest"
		13: return "examine %s" % tile_name
	return ""


# --- hover / focus helpers -------------------------------------------------

static func describe_hover(entity: Dictionary, tile_name: String, tile_position: Vector2i) -> String:
	if not entity.is_empty():
		var entity_name := str(entity.get("name", "Unknown")).strip_edges()
		var actions = entity.get("context_actions", [])
		if actions is Array and not actions.is_empty():
			return "%s  |  Click: %s  |  %s" % [entity_name, command_for_entity(entity), ", ".join(actions)]
		return "%s  |  Click: %s" % [entity_name, command_for_entity(entity)]
	if tile_name.is_empty():
		return "Unknown ground"
	return "%s  |  Click: %s" % [display_tile_name(tile_name), command_for_tile(tile_position, tile_name)]


static func display_tile_name(tile_name: String) -> String:
	return tile_name.replace("_", " ").capitalize()


static func display_entity_name(entry: Dictionary) -> String:
	var raw_name := str(entry.get("name", entry.get("id", ""))).strip_edges()
	var words := raw_name.split(" ", false)
	if words.size() == 2 and str(words[0]).to_lower() == str(words[1]).to_lower():
		return str(words[0])
	return raw_name
