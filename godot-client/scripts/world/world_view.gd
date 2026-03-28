extends SubViewportContainer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")
const PovRendererConfig = preload("res://scripts/pov_renderer_config.gd")
const WorldOverlay = preload("res://scripts/world/world_overlay.gd")
const INTERACTIVE_TILE_NAMES := [
	"door", "well", "fountain", "tree", "chair", "table", "barrel",
	"bookshelf", "crate", "anvil", "bed", "bench", "chest", "altar"
]

signal command_requested(command_text: String)
signal focus_changed(summary: String)
signal focus_actions_changed(actions: Array)

@onready var world_viewport: SubViewport = $WorldViewport
@onready var terrain_layer: TileMapLayer = $WorldViewport/WorldRoot/TerrainLayer
@onready var entity_layer: Node2D = $WorldViewport/WorldRoot/EntityLayer
@onready var selection_layer = $WorldViewport/WorldRoot/SelectionLayer
@onready var world_camera: Camera2D = $WorldViewport/WorldRoot/WorldCamera
var _world_overlay: Control
var _placeholder_banner: Label
var _atmosphere_motes: Array = []
var _background_key: String = ""
var _focus_summary_text: String = "Focus: click a prop, person, or threat for the clearest next action."
var _focus_actions: Array = []


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_exited.connect(_on_mouse_exited)
	_world_overlay = WorldOverlay.new()
	_world_overlay.name = "WorldOverlay"
	add_child(_world_overlay)
	_placeholder_banner = Label.new()
	_placeholder_banner.name = "PlaceholderBanner"
	_placeholder_banner.visible = false
	_placeholder_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_placeholder_banner.position = Vector2(12, 12)
	_placeholder_banner.z_index = 100
	_placeholder_banner.text = "Placeholder map: waiting for campaign data"
	_placeholder_banner.add_theme_color_override("font_color", Color(1.0, 0.88, 0.42))
	_placeholder_banner.add_theme_font_size_override("font_size", 16)
	add_child(_placeholder_banner)

	if get_node_or_null("/root/GameState") != null:
		GameState.map_loaded.connect(_refresh_from_state)
		GameState.entities_loaded.connect(_refresh_from_state)
		GameState.state_updated.connect(_refresh_from_state)

	_refresh_from_state()


func refresh_from_state() -> void:
	_refresh_from_state()


func _refresh_from_state(_payload = null) -> void:
	var has_real_map := not GameState.map_data.is_empty()
	var map_payload: Dictionary = GameState.map_data if has_real_map else TileCatalog.build_placeholder_map()
	if map_payload.is_empty():
		map_payload = TileCatalog.build_placeholder_map()
	_update_placeholder_banner(not has_real_map or bool(map_payload.get("placeholder", false)))
	terrain_layer.render_map(map_payload)
	_update_attention_layers(map_payload)
	_rebuild_atmosphere(map_payload)
	_background_key = _resolve_background_key()
	if _world_overlay != null and _world_overlay.has_method("configure"):
		_world_overlay.configure(_current_adapter_id(), _background_key, _atmosphere_motes, _placeholder_banner.visible)

	var player_tile = GameState.player_map_pos
	if player_tile == Vector2i.ZERO and map_payload.has("spawn_point"):
		var spawn_point = map_payload.get("spawn_point", [])
		if spawn_point is Array and spawn_point.size() >= 2:
			player_tile = Vector2i(int(spawn_point[0]), int(spawn_point[1]))

	entity_layer.render_entities(player_tile, GameState.entities, _resolve_player_template())
	world_camera.focus_on_tiles(_camera_focus_tiles(player_tile), TileCatalog.TILE_SIZE)
	if selection_layer.has_method("set_selected_tile") and player_tile != Vector2i.ZERO:
		selection_layer.set_selected_tile(player_tile)
	_set_focus_summary(_default_focus_summary())
	_set_focus_actions(_default_focus_actions())


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_update_hover(event.position)
		return

	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			var tile_position = _screen_to_tile(event.position)
			if not _tile_in_bounds(tile_position):
				return
			if selection_layer.has_method("set_selected_tile"):
				selection_layer.set_selected_tile(tile_position)
			if selection_layer.has_method("flash_tile"):
				selection_layer.flash_tile(tile_position)
			var entity = entity_layer.get_entity_at_tile(tile_position)
			_set_focus_summary(_focus_summary(tile_position, entity))
			_set_focus_actions(_focus_actions_for(tile_position, entity))
			if not entity.is_empty():
				command_requested.emit(command_for_entity(entity))
			else:
				command_requested.emit(command_for_tile(tile_position))
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			world_camera.zoom_in()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			world_camera.zoom_out()
			accept_event()


func command_for_entity(entity: Dictionary) -> String:
	var entity_name = str(entity.get("name", "")).strip_edges().to_lower()
	if entity_name.is_empty():
		entity_name = "target"
	var actions = entity.get("context_actions", [])
	if actions is Array and not actions.is_empty():
		var primary_action = str(actions[0]).strip_edges().to_lower()
		match primary_action:
			"pick up":
				return "pick up %s" % entity_name
			"attack":
				return "attack %s" % entity_name
			"trade":
				return "trade %s" % entity_name
			"talk":
				return "talk %s" % entity_name
			"examine":
				return "examine %s" % entity_name
	var bucket = str(entity.get("bucket", "npc"))
	match bucket:
		"enemy":
			return "attack %s" % entity_name
		"item":
			return "pick up %s" % entity_name
		"furniture":
			return "examine %s" % entity_name
		_:
			return "talk %s" % entity_name


func command_for_tile(tile_position: Vector2i) -> String:
	var tile_name = _tile_name_at(tile_position)
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


func _resolve_player_template() -> String:
	if GameState.player.has("classes") and GameState.player["classes"] is Dictionary and not GameState.player["classes"].is_empty():
		var class_keys = GameState.player["classes"].keys()
		return str(class_keys[0]).to_lower()
	if GameState.player.has("player_class"):
		return str(GameState.player["player_class"]).to_lower()
	return "warrior"


func _screen_to_tile(screen_position: Vector2) -> Vector2i:
	var world_position = _screen_to_world(screen_position)
	return Vector2i(
		floori(world_position.x / TileCatalog.TILE_SIZE),
		floori(world_position.y / TileCatalog.TILE_SIZE)
	)


func _screen_to_world(screen_position: Vector2) -> Vector2:
	var viewport_size = Vector2(size)
	return world_camera.position + (screen_position - viewport_size / 2.0) / world_camera.zoom


func _update_hover(screen_position: Vector2) -> void:
	var tile_position = _screen_to_tile(screen_position)
	if not _tile_in_bounds(tile_position):
		tooltip_text = ""
		if selection_layer.has_method("clear_hover"):
			selection_layer.clear_hover()
		return
	if selection_layer.has_method("set_hover_tile"):
		selection_layer.set_hover_tile(tile_position)
	var entity = entity_layer.get_entity_at_tile(tile_position)
	tooltip_text = _describe_hover(tile_position, entity)
	_set_focus_summary(_focus_summary(tile_position, entity))
	_set_focus_actions(_focus_actions_for(tile_position, entity))


func _describe_hover(tile_position: Vector2i, entity: Dictionary) -> String:
	if _placeholder_banner != null and _placeholder_banner.visible:
		return _placeholder_banner.text
	if not entity.is_empty():
		var entity_name = str(entity.get("name", "Unknown")).strip_edges()
		var actions = entity.get("context_actions", [])
		if actions is Array and not actions.is_empty():
			return "%s  |  Click: %s  |  %s" % [entity_name, command_for_entity(entity), ", ".join(actions)]
		return "%s  |  Click: %s" % [entity_name, command_for_entity(entity)]
	var tile_name = _tile_name_at(tile_position)
	if tile_name.is_empty():
		return "Unknown ground"
	return "%s  |  Click: %s" % [_display_tile_name(tile_name), command_for_tile(tile_position)]


func _tile_in_bounds(tile_position: Vector2i) -> bool:
	var width = int(GameState.map_data.get("width", 0))
	var height = int(GameState.map_data.get("height", 0))
	if width <= 0 or height <= 0:
		return tile_position.x >= 0 and tile_position.y >= 0
	return tile_position.x >= 0 and tile_position.y >= 0 and tile_position.x < width and tile_position.y < height


func _tile_name_at(tile_position: Vector2i) -> String:
	var tiles = GameState.map_data.get("tiles", [])
	if not (tiles is Array) or tile_position.y < 0 or tile_position.y >= tiles.size():
		return ""
	var row = tiles[tile_position.y]
	if not (row is Array) or tile_position.x < 0 or tile_position.x >= row.size():
		return ""
	return TileCatalog.resolve_tile_name(row[tile_position.x])


func capture_world_image() -> Image:
	return world_viewport.get_texture().get_image()


func capture_world_screenshot(folder: String, prefix: String) -> String:
	var image = capture_world_image()
	var screenshot_capture = preload("res://scripts/ui/screenshot_capture.gd")
	return screenshot_capture.capture_image(image, folder, prefix)


func _update_placeholder_banner(is_placeholder: bool) -> void:
	if _placeholder_banner == null:
		return
	_placeholder_banner.visible = is_placeholder
	if is_placeholder:
		_placeholder_banner.text = "Placeholder map: awaiting live campaign terrain"


func _on_mouse_exited() -> void:
	tooltip_text = ""
	if selection_layer.has_method("clear_hover"):
		selection_layer.clear_hover()
	_set_focus_summary(_default_focus_summary())
	_set_focus_actions(_default_focus_actions())


func get_atmosphere_state() -> Dictionary:
	return {
		"mote_count": _atmosphere_motes.size(),
		"placeholder": _placeholder_banner != null and _placeholder_banner.visible,
		"background_key": _background_key,
	}


func get_focus_summary() -> String:
	return _focus_summary_text


func get_focus_actions() -> Array:
	return _focus_actions.duplicate(true)


func _update_attention_layers(map_payload: Dictionary) -> void:
	if selection_layer == null:
		return
	if selection_layer.has_method("set_interest_tiles"):
		selection_layer.set_interest_tiles(_interactive_tile_positions(map_payload))
	if selection_layer.has_method("set_hostile_tiles"):
		selection_layer.set_hostile_tiles(_hostile_tile_positions())
	if selection_layer.has_method("set_ambient_tiles"):
		selection_layer.set_ambient_tiles(_ambient_tile_positions(map_payload))


func _interactive_tile_positions(map_payload: Dictionary) -> Array:
	var result: Array = []
	var rows = map_payload.get("tiles", [])
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			var tile_name = TileCatalog.resolve_tile_name(row[x])
			if INTERACTIVE_TILE_NAMES.has(tile_name):
				result.append(Vector2i(x, y))
	for entity in GameState.entities.get("furniture", []):
		if entity is Dictionary:
			result.append(_entity_tile(entity))
	return result


func _ambient_tile_positions(map_payload: Dictionary) -> Array:
	var result: Array = []
	var rows = map_payload.get("tiles", [])
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			var tile_name = TileCatalog.resolve_tile_name(row[x])
			if tile_name in ["well", "fountain"]:
				result.append(Vector2i(x, y))
	return result


func _hostile_tile_positions() -> Array:
	var result: Array = []
	for enemy in GameState.entities.get("enemies", []):
		if enemy is Dictionary:
			result.append(_entity_tile(enemy))
	return result


func _entity_tile(entry: Dictionary) -> Vector2i:
	var position_data = entry.get("position", [0, 0])
	if position_data is Array and position_data.size() >= 2:
		return Vector2i(int(position_data[0]), int(position_data[1]))
	return Vector2i.ZERO


func _camera_focus_tiles(player_tile: Vector2i) -> Array:
	var focus_tiles: Array = [player_tile]
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for entry in GameState.entities.get(bucket, []):
			if not (entry is Dictionary):
				continue
			var tile_position = _entity_tile(entry)
			if tile_position == Vector2i.ZERO:
				continue
			if abs(tile_position.x - player_tile.x) + abs(tile_position.y - player_tile.y) > 12:
				continue
			focus_tiles.append(tile_position)
			if focus_tiles.size() >= 10:
				return focus_tiles
	return focus_tiles


func _rebuild_atmosphere(map_payload: Dictionary) -> void:
	_atmosphere_motes.clear()
	var map_width = maxf(float(map_payload.get("width", 16)), 16.0)
	var map_height = maxf(float(map_payload.get("height", 12)), 12.0)
	var density = maxi(int((map_width * map_height) / 96.0), 10)
	density = mini(density, 28)
	for index in range(density):
		var scalar = float(index + 1)
		var x_seed = fposmod(map_width * 13.0 + scalar * 57.0, maxf(size.x, 320.0))
		var y_seed = fposmod(map_height * 11.0 + scalar * 31.0, maxf(size.y, 220.0))
		_atmosphere_motes.append({
			"x": x_seed,
			"y": y_seed,
			"speed": 0.35 + fposmod(scalar * 0.17, 0.85),
			"drift": 4.0 + fposmod(scalar * 1.3, 14.0),
			"radius": 1.2 + fposmod(scalar * 0.41, 1.8),
			"phase": scalar * 0.63,
			"alpha": 0.08 + fposmod(scalar * 0.019, 0.08),
		})


func _current_adapter_id() -> String:
	return str(GameState.adapter_id).strip_edges().to_lower()


func _display_tile_name(tile_name: String) -> String:
	return tile_name.replace("_", " ").capitalize()


func _default_focus_summary() -> String:
	var contact_name = _first_entity_name("npcs")
	var threat_name = _first_entity_name("enemies")
	var loot_count = GameState.entities.get("items", []).size()
	var parts: Array[String] = ["Focus: %s" % GameState.get_display_location()]
	if not contact_name.is_empty():
		parts.append("Start with %s" % contact_name)
	else:
		parts.append("%d locals on the survey" % GameState.entities.get("npcs", []).size())
	if not threat_name.is_empty():
		parts.append("%s is the nearest pressure" % threat_name)
	elif GameState.entities.get("enemies", []).size() > 0:
		parts.append("%d threat markers in range" % GameState.entities.get("enemies", []).size())
	else:
		parts.append("%d loot pings" % loot_count)
	return "  |  ".join(parts)


func _focus_summary(tile_position: Vector2i, entity: Dictionary) -> String:
	if _placeholder_banner != null and _placeholder_banner.visible:
		return "Focus: placeholder map. Waiting for live campaign terrain."
	if not entity.is_empty():
		var entity_name = _display_entity_name(entity)
		return "Focus: %s  |  Primary: %s" % [entity_name, command_for_entity(entity)]
	var tile_name = _tile_name_at(tile_position)
	if tile_name.is_empty():
		return _default_focus_summary()
	return "Focus: %s  |  Primary: %s" % [_display_tile_name(tile_name), command_for_tile(tile_position)]


func _set_focus_summary(text: String) -> void:
	var next_text = text.strip_edges()
	if next_text.is_empty():
		next_text = "Focus: click a prop, person, or threat for the clearest next action."
	if _focus_summary_text == next_text:
		return
	_focus_summary_text = next_text
	focus_changed.emit(_focus_summary_text)


func _default_focus_actions() -> Array:
	var actions: Array = []
	var contact = _first_entity("npcs")
	if not contact.is_empty():
		actions.append({
			"label": "Talk: %s" % _short_focus_label(_display_entity_name(contact)),
			"command": command_for_entity(contact),
		})
	var threat = _first_entity("enemies")
	if not threat.is_empty():
		actions.append({
			"label": "Scout: %s" % _short_focus_label(_display_entity_name(threat)),
			"command": "examine %s" % str(threat.get("name", "threat")).strip_edges().to_lower(),
		})
	var loot = _first_entity("items")
	if actions.size() < 2 and not loot.is_empty():
		actions.append({
			"label": "Loot: %s" % _short_focus_label(_display_entity_name(loot)),
			"command": command_for_entity(loot),
		})
	if actions.size() < 2:
		actions.append({
			"label": "Inventory",
			"command": "inventory",
		})
	if actions.size() < 2:
		actions.append({
			"label": "Look Around",
			"command": "look around",
		})
	return actions.slice(0, 2)


func _focus_actions_for(tile_position: Vector2i, entity: Dictionary) -> Array:
	if _placeholder_banner != null and _placeholder_banner.visible:
		return _default_focus_actions()
	if not entity.is_empty():
		var actions = entity.get("context_actions", [])
		var entity_name = str(entity.get("name", "target")).strip_edges().to_lower()
		var result: Array = []
		if actions is Array:
			for action in actions:
				var normalized_action = str(action).strip_edges().to_lower()
				if normalized_action.is_empty():
					continue
				result.append({
					"label": normalized_action.capitalize(),
					"command": _command_for_context_action(normalized_action, entity_name, str(entity.get("bucket", "npc"))),
				})
				if result.size() >= 2:
					return result
		result.append({
			"label": "Primary",
			"command": command_for_entity(entity),
		})
		result.append({
			"label": "Inventory",
			"command": "inventory",
		})
		return result
	var tile_name = _tile_name_at(tile_position)
	if tile_name.is_empty():
		return _default_focus_actions()
	var actions: Array = [{
		"label": "Primary",
		"command": command_for_tile(tile_position),
	}]
	if not str(actions[0].get("command", "")).begins_with("move to"):
		actions.append({
			"label": "Move There",
			"command": "move to %d,%d" % [tile_position.x, tile_position.y],
		})
	else:
		actions.append({
			"label": "Look Around",
			"command": "look around",
		})
	return actions


func _command_for_context_action(action: String, entity_name: String, bucket: String) -> String:
	match action:
		"talk":
			return "talk %s" % entity_name
		"trade":
			return "trade %s" % entity_name
		"attack":
			return "attack %s" % entity_name
		"pick up":
			return "pick up %s" % entity_name
		"examine":
			return "examine %s" % entity_name
	if bucket == "item":
		return "pick up %s" % entity_name
	return command_for_entity({"bucket": bucket, "name": entity_name})


func _first_entity(bucket: String) -> Dictionary:
	var entries = GameState.entities.get(bucket, [])
	for entry in entries:
		if entry is Dictionary:
			return entry
	return {}


func _first_entity_name(bucket: String) -> String:
	var entry = _first_entity(bucket)
	if entry.is_empty():
		return ""
	return _display_entity_name(entry)


func _short_focus_label(label: String) -> String:
	var trimmed = label.strip_edges()
	if trimmed.length() <= 14:
		return trimmed
	return trimmed.substr(0, 13) + "…"


func _display_entity_name(entry: Dictionary) -> String:
	var raw_name = str(entry.get("name", entry.get("id", ""))).strip_edges()
	var words = raw_name.split(" ", false)
	if words.size() == 2 and str(words[0]).to_lower() == str(words[1]).to_lower():
		return str(words[0])
	return raw_name


func _set_focus_actions(actions: Array) -> void:
	var next_actions = actions.duplicate(true)
	if next_actions.is_empty():
		next_actions = _default_focus_actions()
	_focus_actions = next_actions
	focus_actions_changed.emit(_focus_actions.duplicate(true))


func _resolve_background_key() -> String:
	var location_hint = GameState.get_display_location().to_lower()
	var resolved_path = PovRendererConfig.resolve_background(location_hint)
	if resolved_path.contains("harbor"):
		return "harbor"
	if resolved_path.contains("dungeon"):
		return "dungeon"
	if GameState.scene == "combat":
		return "dungeon"
	if _current_adapter_id() == "scifi_frontier":
		return "harbor"
	return "harbor"
