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
	var entity_name := _normalized_entity_token(entity)
	var actions = entity.get("context_actions", [])
	if actions is Array and not actions.is_empty():
		for raw_action in actions:
			var command := command_for_context_action(
				str(raw_action).strip_edges().to_lower(),
				entity_name,
				str(entity.get("bucket", "npc")),
			)
			if not command.is_empty():
				return command
	var bucket := str(entity.get("bucket", "npc")).strip_edges().to_lower()
	match bucket:
		"enemy":
			return "attack %s" % entity_name
		"item":
			return "pick up %s" % entity_name
		"furniture":
			return "examine %s" % entity_name
		_:
			return "talk %s" % entity_name


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
	var normalized_bucket := bucket.strip_edges().to_lower()
	match action:
		"talk":
			return "talk %s" % entity_name
		"trade":
			return "trade %s" % entity_name
		"attack":
			return "attack %s" % entity_name
		"pick up", "take", "loot":
			return "pick up %s" % entity_name
		"examine":
			return "examine %s" % entity_name
		"open":
			return "open %s" % entity_name
		"use":
			return "use %s" % entity_name
	if normalized_bucket == "enemy":
		return "attack %s" % entity_name
	if normalized_bucket == "item":
		return "pick up %s" % entity_name
	if normalized_bucket == "furniture":
		return "examine %s" % entity_name
	return "talk %s" % entity_name


# --- context menu construction ---------------------------------------------

static func build_entity_menu_items(entity: Dictionary) -> Array[Dictionary]:
	var items: Array[Dictionary] = []
	var display_name := str(entity.get("name", "target")).strip_edges()
	var entity_name := _normalized_entity_token(entity)
	var bucket := str(entity.get("bucket", "npc")).strip_edges().to_lower()
	var seen_commands: Dictionary = {}
	var actions = entity.get("context_actions", [])
	if actions is Array:
		for raw_action in actions:
			var action := str(raw_action).strip_edges().to_lower()
			if action.is_empty():
				continue
			var command := command_for_context_action(action, entity_name, bucket)
			if command.is_empty() or seen_commands.has(command):
				continue
			items.append({"label": _label_for_menu_action(action, display_name), "command": command})
			seen_commands[command] = true

	match bucket:
		"enemy":
			_append_menu_item(items, seen_commands, "Attack %s" % display_name, "attack %s" % entity_name)
			_append_menu_item(items, seen_commands, "Examine %s" % display_name, "examine %s" % entity_name)
		"item":
			_append_menu_item(items, seen_commands, "Take %s" % display_name, "pick up %s" % entity_name)
			_append_menu_item(items, seen_commands, "Examine %s" % display_name, "examine %s" % entity_name)
		"furniture":
			_append_menu_item(items, seen_commands, "Examine %s" % display_name, "examine %s" % entity_name)
		_:
			_append_menu_item(items, seen_commands, "Talk to %s" % display_name, "talk %s" % entity_name)
			_append_menu_item(items, seen_commands, "Examine %s" % display_name, "examine %s" % entity_name)
			_append_menu_item(items, seen_commands, "Attack %s" % display_name, "attack %s" % entity_name)
	return items


static func build_ground_menu_items(tile_name: String, tile_position: Vector2i) -> Array[Dictionary]:
	var items: Array[Dictionary] = [
		{"label": "Move here", "command": "move to %d,%d" % [tile_position.x, tile_position.y]},
		{"label": "Search area", "command": "search area"},
		{"label": "Rest", "command": "rest"},
	]
	if tile_name.is_empty():
		return items
	var tile_command := command_for_tile(tile_position, tile_name)
	if not tile_command.is_empty() and not tile_command.begins_with("move to"):
		items.append({
			"label": _label_for_tile_menu_command(tile_command, tile_name),
			"command": tile_command,
		})
	return items


# --- hover / focus helpers -------------------------------------------------

static func describe_hover(entity: Dictionary, tile_name: String, tile_position: Vector2i) -> String:
	if not entity.is_empty():
		var entity_name := str(entity.get("name", "Unknown")).strip_edges()
		var actions = entity.get("context_actions", [])
		var left_action := "Select"
		var bucket := str(entity.get("bucket", "npc")).strip_edges().to_lower()
		if bucket == "npc":
			left_action = "Talk"
		elif bucket == "enemy":
			left_action = "Attack" if GameState.is_in_combat() else "Select"
		if actions is Array and not actions.is_empty():
			var labels: Array[String] = []
			for raw_action in actions:
				var action := str(raw_action).strip_edges()
				if action.is_empty():
					continue
				labels.append(_hover_action_label(action))
			return "%s  |  Left: %s  |  Right: act menu  |  %s" % [entity_name, left_action, ", ".join(labels)]
		return "%s  |  Left: %s  |  Right: act menu" % [entity_name, left_action]
	if tile_name.is_empty():
		return "Unknown ground"
	return "%s  |  Left: focus  |  Right: %s" % [display_tile_name(tile_name), command_for_tile(tile_position, tile_name)]


static func display_tile_name(tile_name: String) -> String:
	return tile_name.replace("_", " ").capitalize()


static func display_entity_name(entry: Dictionary) -> String:
	var raw_name := str(entry.get("name", entry.get("id", ""))).strip_edges()
	var words := raw_name.split(" ", false)
	if words.size() == 2 and str(words[0]).to_lower() == str(words[1]).to_lower():
		return str(words[0])
	return raw_name


# --- internal helpers ------------------------------------------------------

static func _normalized_entity_token(entity: Dictionary) -> String:
	var entity_name := str(entity.get("name", "")).strip_edges().to_lower()
	if entity_name.is_empty():
		return "target"
	return entity_name


static func _append_menu_item(items: Array[Dictionary], seen_commands: Dictionary, label: String, command: String) -> void:
	if label.strip_edges().is_empty() or command.strip_edges().is_empty() or seen_commands.has(command):
		return
	items.append({"label": label, "command": command})
	seen_commands[command] = true


static func _label_for_menu_action(action: String, entity_name: String) -> String:
	match action:
		"talk":
			return "Talk to %s" % entity_name
		"trade":
			return "Trade with %s" % entity_name
		"attack":
			return "Attack %s" % entity_name
		"pick up", "take", "loot":
			return "Take %s" % entity_name
		"examine":
			return "Examine %s" % entity_name
		"open":
			return "Open %s" % entity_name
		"use":
			return "Use %s" % entity_name
	return "Interact with %s" % entity_name


static func _label_for_tile_menu_command(command: String, tile_name: String) -> String:
	if command.begins_with("open "):
		return "Open %s" % display_tile_name(tile_name)
	if command.begins_with("examine "):
		return "Examine %s" % display_tile_name(tile_name)
	return "Use %s" % display_tile_name(tile_name)


static func _hover_action_label(action: String) -> String:
	match action.strip_edges().to_lower():
		"pick up", "take", "loot":
			return "take"
		"talk", "trade", "attack", "examine", "open", "use", "rest":
			return action.strip_edges().to_lower()
	return action.strip_edges().to_lower()
