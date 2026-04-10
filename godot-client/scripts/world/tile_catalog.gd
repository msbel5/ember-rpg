extends RefCounted
class_name TileCatalog

const TileCatalogArt = preload("res://scripts/world/tile_catalog_art.gd")
const TILE_SIZE := 32
const PRIMARY_TILE_ROOT := "res://assets/third_party/pixel_crawler/extracted/tiles"
const FALLBACK_TILE_ROOT := "res://assets/third_party/lpc/extracted/tiles"
const DEFAULT_MAP_SIZE := Vector2i(48, 36)
const TILE_VARIANT_COUNT := 3
const TILE_ORDER := [
	"grass",
	"stone_floor",
	"marble",
	"brick",
	"dark_stone",
	"sand",
	"dirt_path",
	"water",
	"wall",
	"door",
	"wood_floor",
	"tavern_floor",
	"cobblestone",
	"swamp",
	"tree",
	"well",
	"fountain",
	"barrel",
	"chest",
	"anvil",
	"bed",
	"bench",
	"table",
	"chair",
	"bookshelf",
	"crate",
	"altar",
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
	"marble": Color(0.74, 0.74, 0.76),
	"brick": Color(0.50, 0.28, 0.22),
	"dark_stone": Color(0.24, 0.26, 0.30),
	"sand": Color(0.70, 0.59, 0.37),
	"dirt_path": Color(0.48, 0.32, 0.18),
	"water": Color(0.16, 0.30, 0.52),
	"wall": Color(0.22, 0.24, 0.28),
	"door": Color(0.78, 0.60, 0.24),
	"wood_floor": Color(0.52, 0.36, 0.22),
	"tavern_floor": Color(0.58, 0.40, 0.26),
	"cobblestone": Color(0.40, 0.40, 0.43),
	"swamp": Color(0.14, 0.24, 0.14),
	"tree": Color(0.12, 0.34, 0.14),
	"well": Color(0.28, 0.56, 0.62),
	"fountain": Color(0.34, 0.68, 0.80),
	"barrel": Color(0.48, 0.30, 0.18),
	"chest": Color(0.68, 0.52, 0.22),
	"anvil": Color(0.34, 0.34, 0.38),
	"bed": Color(0.54, 0.22, 0.28),
	"bench": Color(0.50, 0.34, 0.20),
	"table": Color(0.56, 0.38, 0.24),
	"chair": Color(0.52, 0.36, 0.22),
	"bookshelf": Color(0.48, 0.26, 0.20),
	"crate": Color(0.58, 0.42, 0.22),
	"altar": Color(0.62, 0.62, 0.70),
}
const ADAPTER_WORLD_TINT := {
	"fantasy_ember": Color(1.00, 0.95, 0.90),
	"scifi_frontier": Color(0.84, 0.96, 1.00),
}
const TILE_TEXTURE_ALIASES := {
	"wall": "stone_wall",
	"barrel": "chest",
	"crate": "chest",
	"bed": "wood_floor",
	"bench": "wood_floor",
	"table": "wood_floor",
	"chair": "wood_floor",
	"bookshelf": "wood_floor",
	"altar": "marble",
}


static func build_tileset() -> Dictionary:
	var atlas_image = Image.create(TILE_SIZE * TILE_ORDER.size() * TILE_VARIANT_COUNT, TILE_SIZE, false, Image.FORMAT_RGBA8)
	for tile_index in range(TILE_ORDER.size()):
		var tile_name = TILE_ORDER[tile_index]
		for variant in range(TILE_VARIANT_COUNT):
			var tile_image = _variant_tile_image(tile_name, variant)
			atlas_image.blit_rect(
				tile_image,
				Rect2i(0, 0, tile_image.get_width(), tile_image.get_height()),
				Vector2i((tile_index * TILE_VARIANT_COUNT + variant) * TILE_SIZE, 0)
			)

	var atlas_texture = ImageTexture.create_from_image(atlas_image)
	var tile_set = TileSet.new()
	tile_set.tile_size = Vector2i(TILE_SIZE, TILE_SIZE)

	var atlas_source = TileSetAtlasSource.new()
	atlas_source.texture = atlas_texture
	atlas_source.texture_region_size = Vector2i(TILE_SIZE, TILE_SIZE)

	var atlas_coords := {}
	for tile_index in range(TILE_ORDER.size()):
		var variants: Array = []
		for variant in range(TILE_VARIANT_COUNT):
			var coords = Vector2i(tile_index * TILE_VARIANT_COUNT + variant, 0)
			atlas_source.create_tile(coords)
			variants.append(coords)
		atlas_coords[TILE_ORDER[tile_index]] = variants

	tile_set.add_source(atlas_source, 0)
	return {
		"tile_set": tile_set,
		"source_id": 0,
		"atlas": atlas_coords,
	}


static func render_tile_name(tile_name: String, tile_position: Vector2i, rows: Array) -> String:
	var neighboring_built = _neighbor_count(rows, tile_position, [
		"cobblestone", "stone_floor", "marble", "brick", "dark_stone", "wood_floor", "tavern_floor", "wall", "door", "well", "fountain"
	])
	var neighboring_paths = _neighbor_count(rows, tile_position, [
		"dirt_path", "cobblestone", "stone_floor", "marble", "brick", "dark_stone"
	])
	var neighboring_wet = _neighbor_count(rows, tile_position, ["water", "swamp"])
	match tile_name:
		"grass":
			if neighboring_built >= 3:
				if posmod(tile_position.x * 3 + tile_position.y * 5, 11) == 0:
					return "marble"
				if posmod(tile_position.x + tile_position.y * 2, 5) == 0:
					return "stone_floor"
				if posmod(tile_position.x * 2 + tile_position.y, 7) <= 1:
					return "cobblestone"
				return "dirt_path"
			if neighboring_built >= 1:
				if posmod(tile_position.x * 2 + tile_position.y * 3, 6) == 0:
					return "stone_floor"
				if posmod(tile_position.x + tile_position.y, 4) <= 1:
					return "dirt_path"
			if neighboring_paths >= 2 and posmod(tile_position.x * 5 + tile_position.y, 5) == 0:
				return "dirt_path"
			if neighboring_wet >= 2 and posmod(tile_position.x + tile_position.y * 3, 7) == 0:
				return "swamp"
		"dirt_path":
			if neighboring_built >= 3 and posmod(tile_position.x * 3 + tile_position.y, 4) == 0:
				return "cobblestone"
		"cobblestone":
			if neighboring_built >= 3:
				if posmod(tile_position.x + tile_position.y, 21) == 0:
					return "marble"
				if posmod(tile_position.x * 5 + tile_position.y * 2, 17) == 0:
					return "dark_stone"
				if posmod(tile_position.x * 3 + tile_position.y, 13) == 0:
					return "stone_floor"
		"stone_floor":
			if posmod(tile_position.x * 2 + tile_position.y * 3, 15) == 0:
				return "dark_stone"
			if posmod(tile_position.x + tile_position.y * 2, 19) == 0:
				return "marble"
		"wood_floor":
			if posmod(tile_position.x * 5 + tile_position.y, 14) == 0:
				return "tavern_floor"
	return tile_name


static func variant_index_for_position(tile_name: String, tile_position: Vector2i) -> int:
	var normalized = tile_name.strip_edges().to_lower()
	var seed = normalized.hash() + tile_position.x * 92821 + tile_position.y * 68917
	return posmod(seed, TILE_VARIANT_COUNT)


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


static func _draw_tile(target_image: Image, offset_x: int, base_color: Color, variant: int = 0) -> void:
	var fill_color = base_color
	if variant == 1:
		fill_color = fill_color.lightened(0.08)
	elif variant == 2:
		fill_color = fill_color.darkened(0.08)

	target_image.fill_rect(Rect2i(offset_x, 0, TILE_SIZE, TILE_SIZE), fill_color.darkened(0.12))
	target_image.fill_rect(Rect2i(offset_x + 1, 1, TILE_SIZE - 2, TILE_SIZE - 2), fill_color)
	target_image.fill_rect(Rect2i(offset_x + 2, 2, TILE_SIZE - 4, TILE_SIZE - 4), fill_color.lightened(0.05))
	for step_y in range(2 + variant, TILE_SIZE - 1, 4):
		for step_x in range(2 + ((variant + step_y) % 2), TILE_SIZE - 1, 4):
			target_image.set_pixel(offset_x + step_x, step_y, fill_color.lightened(0.12))


static func _variant_tile_image(tile_name: String, variant: int) -> Image:
	return TileCatalogArt.variant_tile_image(
		tile_name,
		variant,
		TILE_SIZE,
		TILE_PALETTE,
		INTERACTIVE_TILE_NAMES,
		PRIMARY_TILE_ROOT,
		FALLBACK_TILE_ROOT,
		TILE_TEXTURE_ALIASES
	)


static func _neighbor_count(rows: Array, tile_position: Vector2i, tile_names: Array) -> int:
	var count := 0
	var directions = [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]
	for direction in directions:
		var target = tile_position + direction
		if target.y < 0 or target.y >= rows.size():
			continue
		var row = rows[target.y]
		if not (row is Array) or target.x < 0 or target.x >= row.size():
			continue
		var neighbor_name = resolve_tile_name(row[target.x])
		if tile_names.has(neighbor_name):
			count += 1
	return count
