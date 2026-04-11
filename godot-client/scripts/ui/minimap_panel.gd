extends PanelContainer
class_name MinimapPanelWidget

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

signal travel_requested(request: Dictionary)

@onready var map_texture: TextureRect = $MinimapMargin/MinimapVBox/MapTexture
@onready var summary_label: Label = $MinimapMargin/MinimapVBox/SummaryLabel
@onready var routes_label: Label = $MinimapMargin/MinimapVBox/RoutesLabel
@onready var routes_list: VBoxContainer = $MinimapMargin/MinimapVBox/RoutesList
@onready var intel_text: RichTextLabel = $MinimapMargin/MinimapVBox/IntelText

var _graph_nodes: Array = []
var _graph_texture_size: Vector2i = Vector2i.ZERO


func _ready() -> void:
	map_texture.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	map_texture.gui_input.connect(_on_map_texture_gui_input)
	var game_state = _game_state()
	if game_state != null:
		game_state.state_updated.connect(_refresh)
		game_state.map_loaded.connect(_refresh_from_map)
	_refresh()


func _refresh_from_map(_map_data: Dictionary) -> void:
	_refresh()


func _refresh() -> void:
	var game_state = _game_state()
	if game_state == null:
		return
	var world_graph = game_state.world_graph
	if world_graph is Dictionary and not world_graph.is_empty() and (world_graph.get("nodes", []) is Array) and not world_graph.get("nodes", []).is_empty():
		_refresh_world_graph(world_graph)
		return
	_refresh_local_map()


func _refresh_world_graph(world_graph: Dictionary) -> void:
	var dimensions = world_graph.get("dimensions", {})
	var columns := maxi(int(dimensions.get("columns", 0)), 1)
	var rows := maxi(int(dimensions.get("rows", 0)), 1)
	var scale := 14
	var image_width := columns * scale + 1
	var image_height := rows * scale + 1
	var image = Image.create(image_width, image_height, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.07, 0.08, 0.11))

	for region in world_graph.get("regions", []):
		if not (region is Dictionary):
			continue
		var grid_position = region.get("grid_position", [0, 0])
		if not (grid_position is Array) or grid_position.size() < 2:
			continue
		var rx = int(grid_position[0]) * scale
		var ry = int(grid_position[1]) * scale
		var region_color = _color_for_biome(str(region.get("biome_id", "")))
		for dy in range(scale - 1):
			for dx in range(scale - 1):
				image.set_pixel(rx + dx, ry + dy, region_color)
		if str(region.get("id", "")) == str(world_graph.get("active_region_id", "")):
			_draw_rect_outline(image, Rect2i(rx, ry, scale - 1, scale - 1), Color(0.95, 0.89, 0.32))

	for edge in world_graph.get("edges", []):
		if not (edge is Dictionary):
			continue
		var from_node = _find_node(world_graph, str(edge.get("from_settlement_id", "")))
		var to_node = _find_node(world_graph, str(edge.get("to_settlement_id", "")))
		if from_node.is_empty() or to_node.is_empty():
			continue
		_draw_line(
			image,
			_node_pixel(from_node, scale),
			_node_pixel(to_node, scale),
			Color(0.45, 0.52, 0.66),
		)

	_graph_nodes.clear()
	var reachable_regions: Dictionary = {}
	var game_state = _game_state()
	if game_state == null:
		return
	for option in game_state.travel_options:
		if option is Dictionary:
			reachable_regions[str(option.get("destination_region_id", ""))] = true
	var selected_node_id = game_state.selected_world_node if not game_state.selected_world_node.is_empty() else str(game_state.current_region_summary.get("settlement_node_id", ""))
	for node in world_graph.get("nodes", []):
		if not (node is Dictionary):
			continue
		var point = _node_pixel(node, scale)
		var region_id = str(node.get("region_id", ""))
		var node_color = Color(0.80, 0.80, 0.85)
		if region_id == str(world_graph.get("active_region_id", "")):
			node_color = Color(0.97, 0.80, 0.28)
		elif reachable_regions.has(region_id):
			node_color = Color(0.49, 0.90, 0.68)
		elif str(node.get("id", "")) == selected_node_id:
			node_color = Color(0.72, 0.64, 0.96)
		_draw_dot(image, point, node_color)
		_graph_nodes.append({
			"id": str(node.get("id", "")),
			"region_id": region_id,
			"name": str(node.get("name", "")),
			"point": point,
			"reachable": reachable_regions.has(region_id),
		})

	map_texture.texture = ImageTexture.create_from_image(image)
	_graph_texture_size = Vector2i(image_width, image_height)
	_refresh_route_buttons()
	if game_state.has_active_travel():
		summary_label.text = _active_travel_summary_text()
		intel_text.text = _build_active_travel_intel(world_graph)
	else:
		summary_label.text = "World Graph\nActive: %s\nRoutes: %d available" % [
			_current_region_label(world_graph),
			_canonical_travel_options().size(),
		]
		intel_text.text = _build_world_graph_intel(world_graph)


func _refresh_local_map() -> void:
	_graph_nodes.clear()
	_graph_texture_size = Vector2i.ZERO
	_refresh_route_buttons()
	var game_state = _game_state()
	if game_state == null:
		map_texture.texture = null
		summary_label.text = "No live survey. Map feed is offline."
		intel_text.text = "[b]Scene Read[/b]  Awaiting a live terrain feed."
		return
	var map_data = game_state.map_data
	if map_data.is_empty():
		map_texture.texture = null
		if game_state.has_active_travel():
			summary_label.text = _active_travel_summary_text()
			intel_text.text = _build_active_travel_intel({})
		else:
			summary_label.text = "No live survey. Map feed is offline."
			intel_text.text = "[b]Scene Read[/b]  Awaiting a live terrain feed."
		return
	var width = int(map_data.get("width", 0))
	var height = int(map_data.get("height", 0))
	var tiles = map_data.get("tiles", [])
	if width <= 0 or height <= 0 or tiles.is_empty():
		map_texture.texture = null
		summary_label.text = "Placeholder map loaded. Awaiting live campaign terrain." if bool(map_data.get("placeholder", false)) else "No live survey. Map feed is offline."
		intel_text.text = "[b]Scene Read[/b]  Placeholder silhouettes only."
		return

	var image = Image.create(width, height, false, Image.FORMAT_RGBA8)
	for y in range(tiles.size()):
		var row = tiles[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			image.set_pixel(x, y, _color_for_tile(TileCatalog.resolve_tile_name(row[x])))

	_plot_entities(image, game_state.entities.get("furniture", []), Color(0.72, 0.54, 0.30))
	_plot_entities(image, game_state.entities.get("npcs", []), Color(0.96, 0.84, 0.44))
	_plot_entities(image, game_state.entities.get("enemies", []), Color(0.96, 0.34, 0.30))
	_plot_entities(image, game_state.entities.get("items", []), Color(0.62, 0.94, 0.62))

	var player_pos = game_state.player_map_pos
	if player_pos.x >= 0 and player_pos.x < width and player_pos.y >= 0 and player_pos.y < height:
		image.set_pixel(player_pos.x, player_pos.y, Color(0.95, 0.28, 0.20))

	map_texture.texture = ImageTexture.create_from_image(image)
	var npc_count = game_state.entities.get("npcs", []).size()
	var enemy_count = game_state.entities.get("enemies", []).size()
	var item_count = game_state.entities.get("items", []).size()
	var scene_label = game_state.scene.capitalize()
	var scene_read = _scene_read(map_data)
	if game_state.has_active_travel():
		summary_label.text = _active_travel_summary_text()
		intel_text.text = _build_active_travel_intel({})
	elif bool(map_data.get("placeholder", false)):
		summary_label.text = "Placeholder map  %dx%d  |  %s\n%s  |  %d locals  %d threats  %d loot" % [width, height, scene_label, scene_read, npc_count, enemy_count, item_count]
		intel_text.text = _build_intel_text(map_data)
	else:
		summary_label.text = "%s  |  %s\nLocals %d  |  Threats %d  |  Loot %d" % [game_state.get_display_location(), scene_label, npc_count, enemy_count, item_count]
		intel_text.text = _build_intel_text(map_data)


func _refresh_route_buttons() -> void:
	for child in routes_list.get_children():
		child.queue_free()
	var game_state = _game_state()
	if game_state != null and game_state.has_active_travel():
		_refresh_active_travel_buttons()
		return
	var travel_options := _canonical_travel_options()
	routes_label.text = "Routes"
	routes_label.visible = not travel_options.is_empty()
	routes_list.visible = routes_label.visible
	for index in range(travel_options.size()):
		var option: Dictionary = travel_options[index]
		var button := Button.new()
		button.name = "RouteButton%d" % index
		button.text = "%s  ·  %sh" % [str(option.get("destination_name", "Unknown")), int(option.get("travel_hours", 0))]
		button.tooltip_text = "Travel route %s" % str(option.get("route_id", "unknown"))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(func() -> void:
			travel_requested.emit(_travel_start_request(option))
		)
		routes_list.add_child(button)


func _refresh_active_travel_buttons() -> void:
	routes_label.text = "Active Travel"
	routes_label.visible = true
	routes_list.visible = true
	var game_state = _game_state()
	if game_state == null:
		return
	var active_travel: Dictionary = game_state.travel_state
	if bool(active_travel.get("requires_resolution", false)):
		var resolve_button := Button.new()
		resolve_button.name = "ResolveEncounterButton"
		resolve_button.text = "Resolve Encounter"
		resolve_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		resolve_button.pressed.connect(func() -> void:
			travel_requested.emit({
				"shortcut": "travel",
				"args": {"action_id": "resolve_encounter"},
				"history_text": "resolve travel encounter",
			})
		)
		routes_list.add_child(resolve_button)
	if bool(active_travel.get("can_advance", false)):
		var advance_button := Button.new()
		advance_button.name = "ContinueTravelButton"
		advance_button.text = "Continue Travel"
		advance_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		advance_button.pressed.connect(func() -> void:
			travel_requested.emit({
				"shortcut": "travel",
				"args": {"action_id": "advance"},
				"history_text": "continue travel",
			})
		)
		routes_list.add_child(advance_button)


func _on_map_texture_gui_input(event: InputEvent) -> void:
	var game_state = _game_state()
	if game_state == null or game_state.has_active_travel():
		return
	if _graph_nodes.is_empty():
		return
	if not (event is InputEventMouseButton) or not event.pressed or event.button_index != MOUSE_BUTTON_LEFT:
		return
	var node = _node_at_event_position(event.position)
	if node.is_empty():
		return
	game_state.selected_world_node = str(node.get("id", ""))
	if bool(node.get("reachable", false)) and str(node.get("region_id", "")) != str(game_state.world_graph.get("active_region_id", "")):
		var option := _travel_option_for_node(node)
		if not option.is_empty():
			travel_requested.emit(_travel_start_request(option))
		return
	_refresh()


func _canonical_travel_options() -> Array:
	var canonical_options: Array = []
	var game_state = _game_state()
	if game_state == null:
		return canonical_options
	for option in game_state.travel_options:
		if option is Dictionary and not str(option.get("route_id", "")).strip_edges().is_empty():
			canonical_options.append(option)
	return canonical_options


func _travel_option_for_node(node: Dictionary) -> Dictionary:
	var node_id := str(node.get("id", "")).strip_edges()
	var region_id := str(node.get("region_id", "")).strip_edges()
	for option in _canonical_travel_options():
		if str(option.get("destination_settlement_id", "")).strip_edges() == node_id:
			return option
		if str(option.get("destination_region_id", "")).strip_edges() == region_id:
			return option
	return {}


func _travel_start_request(option: Dictionary) -> Dictionary:
	return {
		"shortcut": "travel",
		"args": {
			"action_id": "start",
			"route_id": str(option.get("route_id", "")),
			"destination_region_id": str(option.get("destination_region_id", "")),
			"destination_settlement_id": str(option.get("destination_settlement_id", "")),
		},
		"history_text": "travel %s" % str(option.get("destination_name", option.get("destination_region_id", ""))).to_lower(),
	}


func _active_travel_summary_text() -> String:
	var game_state = _game_state()
	if game_state == null:
		return "Travel status unavailable"
	var active_travel: Dictionary = game_state.travel_state
	var destination_name := str(active_travel.get("destination_name", active_travel.get("destination_region_id", "Unknown"))).strip_edges()
	return "Traveling to %s\n%d / %dh remaining" % [
		destination_name,
		int(active_travel.get("travel_hours_remaining", 0)),
		int(active_travel.get("travel_hours_total", 0)),
	]


func _build_active_travel_intel(world_graph: Dictionary) -> String:
	var game_state = _game_state()
	if game_state == null:
		return "[b]Travel[/b]  Status unavailable"
	var active_travel: Dictionary = game_state.travel_state
	var lines: Array[String] = [
		"[b]Travel[/b]  %s" % str(active_travel.get("status", "traveling")).replace("_", " ").capitalize(),
		"[b]Route[/b]  %s" % str(active_travel.get("route_id", "unknown")),
		"[b]Destination[/b]  %s" % str(active_travel.get("destination_name", active_travel.get("destination_region_id", "Unknown"))),
		"[b]Progress[/b]  %dh remaining of %dh" % [
			int(active_travel.get("travel_hours_remaining", 0)),
			int(active_travel.get("travel_hours_total", 0)),
		],
	]
	if bool(active_travel.get("requires_resolution", false)):
		lines.append("[b]Travel State[/b]  Encounter resolution required before the route can continue.")
	elif bool(active_travel.get("can_advance", false)):
		lines.append("[b]Travel State[/b]  Route is clear to continue.")
	else:
		lines.append("[b]Travel State[/b]  Waiting for the backend to expose the next legal step.")
	if world_graph is Dictionary and not world_graph.is_empty():
		lines.append("[b]Origin[/b]  %s" % _current_region_label(world_graph))
	return "\n".join(lines)


func _node_at_event_position(local_position: Vector2) -> Dictionary:
	if map_texture.texture == null or _graph_texture_size == Vector2i.ZERO:
		return {}
	var image_x = int(clampf(local_position.x / maxf(map_texture.size.x, 1.0) * float(_graph_texture_size.x), 0.0, float(_graph_texture_size.x - 1)))
	var image_y = int(clampf(local_position.y / maxf(map_texture.size.y, 1.0) * float(_graph_texture_size.y), 0.0, float(_graph_texture_size.y - 1)))
	for node in _graph_nodes:
		var point: Vector2i = node.get("point", Vector2i.ZERO)
		if abs(point.x - image_x) <= 4 and abs(point.y - image_y) <= 4:
			return node
	return {}


func _find_node(world_graph: Dictionary, node_id: String) -> Dictionary:
	for node in world_graph.get("nodes", []):
		if node is Dictionary and str(node.get("id", "")) == node_id:
			return node
	return {}


func _node_pixel(node: Dictionary, scale: int) -> Vector2i:
	var grid_position = node.get("grid_position", [0, 0])
	return Vector2i(
		int(grid_position[0]) * scale + int(scale / 2),
		int(grid_position[1]) * scale + int(scale / 2),
	)


func _draw_line(image: Image, start: Vector2i, finish: Vector2i, color: Color) -> void:
	var x0 = start.x
	var y0 = start.y
	var x1 = finish.x
	var y1 = finish.y
	var dx = absi(x1 - x0)
	var sx = 1 if x0 < x1 else -1
	var dy = -absi(y1 - y0)
	var sy = 1 if y0 < y1 else -1
	var error = dx + dy
	while true:
		if x0 >= 0 and y0 >= 0 and x0 < image.get_width() and y0 < image.get_height():
			image.set_pixel(x0, y0, color)
		if x0 == x1 and y0 == y1:
			break
		var e2 = error * 2
		if e2 >= dy:
			error += dy
			x0 += sx
		if e2 <= dx:
			error += dx
			y0 += sy


func _draw_dot(image: Image, point: Vector2i, color: Color) -> void:
	for dy in range(-2, 3):
		for dx in range(-2, 3):
			var px = point.x + dx
			var py = point.y + dy
			if px < 0 or py < 0 or px >= image.get_width() or py >= image.get_height():
				continue
			if abs(dx) + abs(dy) <= 3:
				image.set_pixel(px, py, color)


func _draw_rect_outline(image: Image, rect: Rect2i, color: Color) -> void:
	for x in range(rect.position.x, rect.position.x + rect.size.x):
		if x >= 0 and x < image.get_width():
			if rect.position.y >= 0 and rect.position.y < image.get_height():
				image.set_pixel(x, rect.position.y, color)
			var bottom = rect.position.y + rect.size.y - 1
			if bottom >= 0 and bottom < image.get_height():
				image.set_pixel(x, bottom, color)
	for y in range(rect.position.y, rect.position.y + rect.size.y):
		if y >= 0 and y < image.get_height():
			if rect.position.x >= 0 and rect.position.x < image.get_width():
				image.set_pixel(rect.position.x, y, color)
			var right = rect.position.x + rect.size.x - 1
			if right >= 0 and right < image.get_width():
				image.set_pixel(right, y, color)


func _build_world_graph_intel(world_graph: Dictionary) -> String:
	var game_state = _game_state()
	if game_state == null:
		return "[b]World Graph[/b]  No active macro state."
	var current_summary = game_state.current_region_summary
	var region_label = _current_region_label(world_graph)
	var alerts: Array[String] = []
	for raw_alert in current_summary.get("alerts", []):
		alerts.append(str(raw_alert))
		if alerts.size() >= 3:
			break
	var selected = _find_node(world_graph, game_state.selected_world_node)
	var selected_text = ""
	if not selected.is_empty():
		selected_text = "\n[b]Selected[/b]  %s  |  %s" % [
			str(selected.get("name", "")),
			str(selected.get("region_id", "")),
		]
	var reachable: Array[String] = []
	for option in game_state.travel_options:
		if option is Dictionary:
			reachable.append("%s (%sh)" % [
				str(option.get("destination_name", "Unknown")),
				int(option.get("travel_hours", 0)),
			])
	var reachable_text = ", ".join(reachable) if not reachable.is_empty() else "No reachable destinations."
	return "[b]World Graph[/b]  Active %s\n[b]Reachable[/b]  %s\n[b]Scene Read[/b]  %s%s%s" % [
		region_label,
		reachable_text,
		_scene_read(game_state.map_data) if not game_state.map_data.is_empty() else "No active local survey.",
		"\n[b]Alerts[/b]  %s" % ", ".join(alerts) if not alerts.is_empty() else "",
		selected_text,
	]


func _current_region_label(world_graph: Dictionary) -> String:
	var active_region_id = str(world_graph.get("active_region_id", ""))
	var active_node = {}
	for node in world_graph.get("nodes", []):
		if node is Dictionary and str(node.get("region_id", "")) == active_region_id:
			active_node = node
			break
	if active_node.is_empty():
		return active_region_id
	return "%s  |  %s" % [str(active_node.get("name", active_region_id)), active_region_id]


func _color_for_biome(biome_id: String) -> Color:
	match biome_id:
		"coast":
			return Color(0.18, 0.34, 0.54)
		"desert":
			return Color(0.63, 0.53, 0.26)
		"mountain":
			return Color(0.34, 0.35, 0.39)
		"swamp":
			return Color(0.21, 0.36, 0.27)
		"temperate_forest":
			return Color(0.22, 0.42, 0.24)
		_:
			return Color(0.34, 0.48, 0.25)


func _color_for_tile(tile_name: String) -> Color:
	match tile_name:
		"wall":
			return Color(0.14, 0.16, 0.20)
		"water":
			return Color(0.16, 0.34, 0.60)
		"dirt_path":
			return Color(0.54, 0.36, 0.22)
		"stone_floor", "cobblestone":
			return Color(0.58, 0.60, 0.64)
		"wood_floor":
			return Color(0.63, 0.44, 0.25)
		"door", "well", "fountain", "anvil", "altar":
			return Color(0.74, 0.72, 0.46)
		_:
			return Color(0.24, 0.50, 0.24)


func _plot_entities(image: Image, entries: Array, color: Color) -> void:
	for entry in entries:
		if not (entry is Dictionary):
			continue
		var position_data = entry.get("position", [0, 0])
		if not (position_data is Array) or position_data.size() < 2:
			continue
		var x = int(position_data[0])
		var y = int(position_data[1])
		if x < 0 or y < 0 or x >= image.get_width() or y >= image.get_height():
			continue
		image.set_pixel(x, y, color)


func _build_intel_text(map_data: Dictionary) -> String:
	var game_state = _game_state()
	if game_state == null:
		return "[b]Scene Read[/b]  Awaiting a live terrain feed."
	var scene_read = _scene_read(map_data)
	var contact_text = _entity_digest(game_state.entities.get("npcs", []), "Talk", 3)
	var threat_text = _entity_digest(game_state.entities.get("enemies", []), "Attack", 2)
	var loot_text = _entity_digest(game_state.entities.get("items", []), "Take", 2)
	var landmark_text = _entity_digest(game_state.entities.get("furniture", []), "Inspect", 3)
	return "[b]Scene Read[/b]  %s\n[b]Contacts[/b]  %s\n[b]Pressure[/b]  %s%s" % [
		scene_read,
		contact_text if not contact_text.is_empty() else "No named contacts on the current survey.",
		threat_text if not threat_text.is_empty() else "No immediate hostile marker.",
		"  |  Loot: %s" % loot_text if not loot_text.is_empty() else ("  |  Landmarks: %s" % landmark_text if not landmark_text.is_empty() else ""),
	]


func _scene_read(map_data: Dictionary) -> String:
	if bool(map_data.get("placeholder", false)):
		return "Placeholder survey with a fallback plaza silhouette."
	var game_state = _game_state()
	var tiles = map_data.get("tiles", [])
	var water_tiles := 0
	var built_tiles := 0
	var plaza_tiles := 0
	var green_tiles := 0
	var landmark_names: Array[String] = []
	for row in tiles:
		if not (row is Array):
			continue
		for raw_tile in row:
			var tile_name = TileCatalog.resolve_tile_name(raw_tile)
			match tile_name:
				"water", "swamp":
					water_tiles += 1
				"cobblestone", "stone_floor", "marble", "brick", "dark_stone", "wood_floor", "tavern_floor", "wall", "door":
					built_tiles += 1
				"well", "fountain", "altar", "anvil", "bed", "table", "chair", "bookshelf", "crate", "chest":
					landmark_names.append(tile_name.replace("_", " "))
				"grass":
					green_tiles += 1
			if tile_name in ["cobblestone", "marble", "brick"]:
				plaza_tiles += 1
	for furniture in [] if game_state == null else game_state.entities.get("furniture", []):
		if furniture is Dictionary:
			var name = str(furniture.get("name", "")).strip_edges().to_lower()
			if not name.is_empty():
				landmark_names.append(name)
	var scene_bits: Array[String] = []
	if plaza_tiles > 0:
		scene_bits.append("a paved civic core")
	elif built_tiles > green_tiles:
		scene_bits.append("a built-up district")
	else:
		scene_bits.append("open ground around the player")
	if water_tiles > 0:
		scene_bits.append("waterside pressure")
	elif green_tiles > 0:
		scene_bits.append("green outskirts around the route")
	var unique_landmarks: Array[String] = []
	for landmark in landmark_names:
		if unique_landmarks.has(landmark):
			continue
		unique_landmarks.append(landmark)
		if unique_landmarks.size() >= 2:
			break
	if not unique_landmarks.is_empty():
		scene_bits.append("landmarks: %s" % ", ".join(unique_landmarks))
	return ", ".join(scene_bits)


func _entity_digest(entries: Array, primary_action: String, limit: int) -> String:
	var parts: Array[String] = []
	for entry in entries:
		if not (entry is Dictionary):
			continue
		var label = _clean_label(str(entry.get("name", entry.get("id", ""))).strip_edges())
		if label.is_empty():
			continue
		parts.append("%s (%s)" % [label, primary_action])
		if parts.size() >= limit:
			break
	if parts.is_empty():
		return ""
	return ", ".join(parts)


func _clean_label(label: String) -> String:
	var trimmed = label.strip_edges()
	var words = trimmed.split(" ", false)
	if words.size() == 2 and str(words[0]).to_lower() == str(words[1]).to_lower():
		return str(words[0])
	return trimmed


func _game_state():
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		return loop.root.get_node_or_null("GameState")
	return null
