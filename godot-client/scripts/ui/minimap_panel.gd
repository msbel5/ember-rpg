extends PanelContainer
class_name MinimapPanelWidget

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

@onready var map_texture: TextureRect = $MinimapMargin/MinimapVBox/MapTexture
@onready var summary_label: Label = $MinimapMargin/MinimapVBox/SummaryLabel


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
		summary_label.text = "No map loaded"
		return
	var width = int(map_data.get("width", 0))
	var height = int(map_data.get("height", 0))
	var tiles = map_data.get("tiles", [])
	if width <= 0 or height <= 0 or tiles.is_empty():
		map_texture.texture = null
		summary_label.text = "Placeholder map loaded" if bool(map_data.get("placeholder", false)) else "No map loaded"
		return

	var image = Image.create(width, height, false, Image.FORMAT_RGBA8)
	for y in range(tiles.size()):
		var row = tiles[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			image.set_pixel(x, y, _color_for_tile(TileCatalog.resolve_tile_name(row[x])))

	var player_pos = GameState.player_map_pos
	if player_pos.x >= 0 and player_pos.x < width and player_pos.y >= 0 and player_pos.y < height:
		image.set_pixel(player_pos.x, player_pos.y, Color(0.95, 0.28, 0.20))

	map_texture.texture = ImageTexture.create_from_image(image)
	if bool(map_data.get("placeholder", false)):
		summary_label.text = "Placeholder map loaded  %dx%d" % [width, height]
	else:
		summary_label.text = "%s  %dx%d" % [GameState.get_display_location(), width, height]


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
		_:
			return Color(0.24, 0.50, 0.24)
