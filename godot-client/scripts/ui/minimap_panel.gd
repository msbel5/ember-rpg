extends PanelContainer
class_name MinimapPanelWidget

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

@onready var map_texture: TextureRect = $MinimapMargin/MinimapVBox/MapTexture
@onready var summary_label: Label = $MinimapMargin/MinimapVBox/SummaryLabel
@onready var intel_text: RichTextLabel = $MinimapMargin/MinimapVBox/IntelText


func _ready() -> void:
	map_texture.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	GameState.state_updated.connect(_refresh)
	GameState.map_loaded.connect(_refresh_from_map)
	_refresh()


func _refresh_from_map(_map_data: Dictionary) -> void:
	_refresh()


func _refresh() -> void:
	var map_data = GameState.map_data
	if map_data.is_empty():
		map_texture.texture = null
		summary_label.text = "No live survey. Map feed is offline."
		intel_text.text = "[b]Scene Read[/b]  Awaiting a live terrain feed.\n[b]Intel[/b]  Contacts and threats will appear here."
		return
	var width = int(map_data.get("width", 0))
	var height = int(map_data.get("height", 0))
	var tiles = map_data.get("tiles", [])
	if width <= 0 or height <= 0 or tiles.is_empty():
		map_texture.texture = null
		summary_label.text = "Placeholder map loaded. Awaiting live campaign terrain." if bool(map_data.get("placeholder", false)) else "No live survey. Map feed is offline."
		intel_text.text = "[b]Scene Read[/b]  Placeholder silhouettes only.\n[b]Intel[/b]  The client is waiting for authored terrain."
		return

	var image = Image.create(width, height, false, Image.FORMAT_RGBA8)
	for y in range(tiles.size()):
		var row = tiles[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			image.set_pixel(x, y, _color_for_tile(TileCatalog.resolve_tile_name(row[x])))

	_plot_entities(image, GameState.entities.get("furniture", []), Color(0.72, 0.54, 0.30))
	_plot_entities(image, GameState.entities.get("npcs", []), Color(0.96, 0.84, 0.44))
	_plot_entities(image, GameState.entities.get("enemies", []), Color(0.96, 0.34, 0.30))
	_plot_entities(image, GameState.entities.get("items", []), Color(0.62, 0.94, 0.62))

	var player_pos = GameState.player_map_pos
	if player_pos.x >= 0 and player_pos.x < width and player_pos.y >= 0 and player_pos.y < height:
		image.set_pixel(player_pos.x, player_pos.y, Color(0.95, 0.28, 0.20))

	map_texture.texture = ImageTexture.create_from_image(image)
	var npc_count = GameState.entities.get("npcs", []).size()
	var enemy_count = GameState.entities.get("enemies", []).size()
	var item_count = GameState.entities.get("items", []).size()
	var scene_label = GameState.scene.capitalize()
	var scene_read = _scene_read(map_data)
	if bool(map_data.get("placeholder", false)):
		summary_label.text = "Placeholder map  %dx%d  |  %s\n%s  |  %d locals  %d threats  %d loot" % [width, height, scene_label, scene_read, npc_count, enemy_count, item_count]
	else:
		summary_label.text = "%s  |  %s\n%s  |  %d locals  %d threats  %d loot" % [GameState.get_display_location(), scene_label, scene_read, npc_count, enemy_count, item_count]
	intel_text.text = _build_intel_text(map_data)


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
	var scene_read = _scene_read(map_data)
	var contact_text = _entity_digest(GameState.entities.get("npcs", []), "Talk", 3)
	var threat_text = _entity_digest(GameState.entities.get("enemies", []), "Attack", 2)
	var loot_text = _entity_digest(GameState.entities.get("items", []), "Take", 2)
	var landmark_text = _entity_digest(GameState.entities.get("furniture", []), "Inspect", 3)
	return "[b]Scene Read[/b]  %s\n[b]Contacts[/b]  %s\n[b]Pressure[/b]  %s%s" % [
		scene_read,
		contact_text if not contact_text.is_empty() else "No named contacts on the current survey.",
		threat_text if not threat_text.is_empty() else "No immediate hostile marker.",
		"  |  Loot: %s" % loot_text if not loot_text.is_empty() else ("  |  Landmarks: %s" % landmark_text if not landmark_text.is_empty() else ""),
	]


func _scene_read(map_data: Dictionary) -> String:
	if bool(map_data.get("placeholder", false)):
		return "Placeholder survey with a fallback plaza silhouette."
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
	for furniture in GameState.entities.get("furniture", []):
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
