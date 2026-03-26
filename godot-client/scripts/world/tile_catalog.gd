extends RefCounted
class_name TileCatalog

const TILE_SIZE := 16
const DEFAULT_MAP_SIZE := Vector2i(48, 36)
const TILE_ORDER := [
	"grass",
	"stone_floor",
	"dirt_path",
	"water",
	"wall",
	"wood_floor",
	"cobblestone",
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
const TILE_PALETTE := {
	"grass": Color(0.20, 0.42, 0.20),
	"stone_floor": Color(0.45, 0.47, 0.50),
	"dirt_path": Color(0.48, 0.32, 0.18),
	"water": Color(0.16, 0.30, 0.52),
	"wall": Color(0.22, 0.24, 0.28),
	"wood_floor": Color(0.52, 0.36, 0.22),
	"cobblestone": Color(0.40, 0.40, 0.43),
}


static func build_tileset() -> Dictionary:
	var atlas_image = Image.create(TILE_SIZE * TILE_ORDER.size(), TILE_SIZE, false, Image.FORMAT_RGBA8)
	for tile_index in range(TILE_ORDER.size()):
		var tile_name = TILE_ORDER[tile_index]
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
	return "grass"


static func _draw_tile(target_image: Image, offset_x: int, base_color: Color) -> void:
	target_image.fill_rect(Rect2i(offset_x, 0, TILE_SIZE, TILE_SIZE), base_color.darkened(0.10))
	target_image.fill_rect(Rect2i(offset_x + 1, 1, TILE_SIZE - 2, TILE_SIZE - 2), base_color)
	target_image.fill_rect(Rect2i(offset_x + 2, 2, TILE_SIZE - 4, TILE_SIZE - 4), base_color.lightened(0.06))
	for step_y in range(2, TILE_SIZE - 1, 4):
		for step_x in range(2, TILE_SIZE - 1, 4):
			target_image.set_pixel(offset_x + step_x, step_y, base_color.lightened(0.14))
