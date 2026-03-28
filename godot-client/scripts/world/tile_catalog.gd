extends RefCounted
class_name TileCatalog

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")
const TILE_SIZE := 16
const DEFAULT_MAP_SIZE := Vector2i(48, 36)
const TILE_ORDER := [
	"grass",
	"stone_floor",
	"dirt_path",
	"water",
	"wall",
	"door",
	"wood_floor",
	"cobblestone",
	"tree",
	"well",
	"fountain",
]
const TILE_ALIASES := {
	"floor": "stone_floor",
	"stone": "stone_floor",
	"road": "dirt_path",
	"path": "dirt_path",
	"stone_wall": "wall",
	"building_wall": "wall",
	"building_floor": "wood_floor",
	"tavern_floor": "wood_floor",
	"dock_planks": "wood_floor",
	"bridge": "wood_floor",
}
# Interactive object tiles — these are terrain-embedded objects, not entities.
# They get their own palette entries so resolve_tile_name preserves the name
# and command_for_tile can generate examine commands for them.
const INTERACTIVE_TILE_NAMES := [
	"barrel", "chest", "anvil", "bed", "bench", "table",
	"chair", "bookshelf", "crate", "altar",
]
const TILE_PALETTE := {
	"grass": Color(0.20, 0.42, 0.20),
	"stone_floor": Color(0.45, 0.47, 0.50),
	"dirt_path": Color(0.48, 0.32, 0.18),
	"water": Color(0.16, 0.30, 0.52),
	"wall": Color(0.22, 0.24, 0.28),
	"door": Color(0.78, 0.60, 0.24),
	"wood_floor": Color(0.52, 0.36, 0.22),
	"cobblestone": Color(0.40, 0.40, 0.43),
	"tree": Color(0.12, 0.34, 0.14),
	"well": Color(0.28, 0.56, 0.62),
	"fountain": Color(0.34, 0.68, 0.80),
}
const ADAPTER_WORLD_TINT := {
	"fantasy_ember": Color(1.00, 0.95, 0.90),
	"scifi_frontier": Color(0.84, 0.96, 1.00),
}


static func build_tileset() -> Dictionary:
	var atlas_image = Image.create(TILE_SIZE * TILE_ORDER.size(), TILE_SIZE, false, Image.FORMAT_RGBA8)
	for tile_index in range(TILE_ORDER.size()):
		var tile_name = TILE_ORDER[tile_index]
		var tile_image = _load_tile_image(tile_name)
		if tile_image != null:
			if tile_image.get_width() != TILE_SIZE or tile_image.get_height() != TILE_SIZE:
				tile_image.resize(TILE_SIZE, TILE_SIZE, Image.INTERPOLATE_NEAREST)
			atlas_image.blit_rect(tile_image, Rect2i(0, 0, tile_image.get_width(), tile_image.get_height()), Vector2i(tile_index * TILE_SIZE, 0))
		else:
			_draw_tile(atlas_image, tile_index * TILE_SIZE, TILE_PALETTE[tile_name])

	var atlas_texture = ImageTexture.create_from_image(atlas_image)
	var tile_set = TileSet.new()
	tile_set.tile_size = Vector2i(TILE_SIZE, TILE_SIZE)

	var atlas_source = TileSetAtlasSource.new()
	atlas_source.texture = atlas_texture
	atlas_source.texture_region_size = Vector2i(TILE_SIZE, TILE_SIZE)

	var atlas_coords := {}
	for tile_index in range(TILE_ORDER.size()):
		var coords = Vector2i(tile_index, 0)
		atlas_source.create_tile(coords)
		atlas_coords[TILE_ORDER[tile_index]] = coords

	tile_set.add_source(atlas_source, 0)
	return {
		"tile_set": tile_set,
		"source_id": 0,
		"atlas": atlas_coords,
	}


static func build_placeholder_map(width: int = DEFAULT_MAP_SIZE.x, height: int = DEFAULT_MAP_SIZE.y) -> Dictionary:
	var tiles := []
	for y in range(height):
		var row: Array = []
		for x in range(width):
			var tile_name = "grass"
			if x == 0 or y == 0 or x == width - 1 or y == height - 1:
				tile_name = "wall"
			elif y == int(height / 2):
				tile_name = "dirt_path"
			elif x >= int(width / 2) - 1 and x <= int(width / 2) + 1 and y > 3 and y < height - 4:
				tile_name = "cobblestone"
			elif (x + y) % 13 == 0:
				tile_name = "stone_floor"
			elif x > width - 10 and y > 4 and y < 12:
				tile_name = "water"
			row.append(tile_name)
		tiles.append(row)

	return {
		"width": width,
		"height": height,
		"tiles": tiles,
		"spawn_point": [int(width / 2), int(height / 2)],
		"placeholder": true,
	}


static func resolve_tile_name(raw_value) -> String:
	var tile_name = str(raw_value).strip_edges().to_lower()
	if tile_name.is_empty():
		return "grass"
	if TILE_ALIASES.has(tile_name):
		return TILE_ALIASES[tile_name]
	if TILE_PALETTE.has(tile_name):
		return tile_name
	if INTERACTIVE_TILE_NAMES.has(tile_name):
		return tile_name
	return "grass"


static func adapter_world_tint(adapter_id: String) -> Color:
	var normalized = adapter_id.strip_edges().to_lower()
	if ADAPTER_WORLD_TINT.has(normalized):
		return ADAPTER_WORLD_TINT[normalized]
	return Color.WHITE


static func _draw_tile(target_image: Image, offset_x: int, base_color: Color) -> void:
	target_image.fill_rect(Rect2i(offset_x, 0, TILE_SIZE, TILE_SIZE), base_color.darkened(0.10))
	target_image.fill_rect(Rect2i(offset_x + 1, 1, TILE_SIZE - 2, TILE_SIZE - 2), base_color)
	target_image.fill_rect(Rect2i(offset_x + 2, 2, TILE_SIZE - 4, TILE_SIZE - 4), base_color.lightened(0.06))
	for step_y in range(2, TILE_SIZE - 1, 4):
		for step_x in range(2, TILE_SIZE - 1, 4):
			target_image.set_pixel(offset_x + step_x, step_y, base_color.lightened(0.14))


static func _load_tile_image(tile_name: String) -> Image:
	var relative_path = AssetManifest.resolve_relative_path("tiles", tile_name)
	if relative_path.is_empty():
		relative_path = "tiles/%s.png" % tile_name
	var asset_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/tiles/%s.png" % tile_name)
	if asset_path.is_empty() or not FileAccess.file_exists(asset_path):
		return null

	var image = Image.new()
	if image.load(ProjectSettings.globalize_path(asset_path)) != OK:
		return null
	return image
