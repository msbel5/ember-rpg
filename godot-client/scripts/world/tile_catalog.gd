extends RefCounted
class_name TileCatalog

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")
const TILE_SIZE := 16
const DEFAULT_MAP_SIZE := Vector2i(48, 36)
const TILE_VARIANT_COUNT := 3
const TILE_ORDER := [
	"grass",
	"stone_floor",
	"marble",
	"brick",
	"dark_stone",
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
	var loaded = _load_tile_image(tile_name)
	if loaded != null:
		if loaded.get_width() != TILE_SIZE or loaded.get_height() != TILE_SIZE:
			loaded.resize(TILE_SIZE, TILE_SIZE, Image.INTERPOLATE_NEAREST)
		return _variantize_image(tile_name, loaded, variant)

	var image = Image.create(TILE_SIZE, TILE_SIZE, false, Image.FORMAT_RGBA8)
	_draw_tile(image, 0, TILE_PALETTE[tile_name], variant)
	if INTERACTIVE_TILE_NAMES.has(tile_name) or tile_name in ["door", "well", "fountain", "tree"]:
		_draw_interactive_icon(image, tile_name)
	return image


static func _variantize_image(tile_name: String, source: Image, variant: int) -> Image:
	var image = source.duplicate()
	_apply_tile_grade(tile_name, image)
	if variant == 0:
		return image
	for y in range(image.get_height()):
		for x in range(image.get_width()):
			var pixel = image.get_pixel(x, y)
			if pixel.a <= 0.0:
				continue
			if variant == 1:
				if (x + y) % 4 == 0:
					pixel = pixel.lightened(0.07)
				elif (x * 2 + y) % 5 == 0:
					pixel = pixel.darkened(0.03)
			elif variant == 2:
				if (x + y * 2) % 3 == 0:
					pixel = pixel.darkened(0.08)
				elif (x * 3 + y) % 5 == 0:
					pixel = pixel.lightened(0.04)
			image.set_pixel(x, y, pixel)
	_apply_tile_pattern(tile_name, image, variant)
	if INTERACTIVE_TILE_NAMES.has(tile_name) or tile_name in ["door", "well", "fountain", "tree"]:
		_draw_interactive_icon(image, tile_name)
	return image


static func _load_tile_image(tile_name: String) -> Image:
	var lookup_name = TILE_TEXTURE_ALIASES.get(tile_name, tile_name)
	var relative_path = AssetManifest.resolve_relative_path("tiles", lookup_name)
	if relative_path.is_empty():
		relative_path = "tiles/%s.png" % lookup_name
	var asset_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/tiles/%s.png" % lookup_name)
	if asset_path.is_empty() or not FileAccess.file_exists(asset_path):
		return null

	var image = Image.new()
	if image.load(ProjectSettings.globalize_path(asset_path)) != OK:
		return null
	return image


static func _apply_tile_grade(tile_name: String, image: Image) -> void:
	for y in range(image.get_height()):
		for x in range(image.get_width()):
			var pixel = image.get_pixel(x, y)
			if pixel.a <= 0.0:
				continue
			match tile_name:
				"grass":
					pixel = pixel.darkened(0.20)
					pixel = pixel.lerp(Color(0.12, 0.18, 0.11, pixel.a), 0.44)
				"dirt_path":
					pixel = pixel.lightened(0.02)
					pixel = pixel.lerp(Color(0.54, 0.38, 0.20, pixel.a), 0.12)
				"cobblestone", "stone_floor", "marble":
					pixel = pixel.lightened(0.10)
				"brick", "dark_stone":
					pixel = pixel.lightened(0.04)
				"wood_floor", "table", "chair", "bench", "bed", "bookshelf", "crate", "barrel":
					pixel = pixel.lightened(0.04)
				"tavern_floor":
					pixel = pixel.lightened(0.06)
				"wall":
					pixel = pixel.darkened(0.12)
					pixel = pixel.lerp(Color(0.24, 0.26, 0.31, pixel.a), 0.20)
				"swamp":
					pixel = pixel.darkened(0.08)
					pixel = pixel.lerp(Color(0.12, 0.20, 0.12, pixel.a), 0.30)
				"water", "well", "fountain":
					pixel = pixel.lightened(0.05)
			image.set_pixel(x, y, pixel)


static func _apply_tile_pattern(tile_name: String, image: Image, variant: int) -> void:
	match tile_name:
		"grass", "swamp":
			for x in range(1 + variant, TILE_SIZE, 5):
				for y in range(2, TILE_SIZE - 1, 2):
					var blade = image.get_pixel(x, y)
					if blade.a > 0.0:
						image.set_pixel(x, y, blade.darkened(0.18))
			for y in range(3 + variant, TILE_SIZE, 6):
				image.fill_rect(Rect2i((variant + y) % 5, y, 3, 1), Color(0.22, 0.28, 0.14, 0.24 if tile_name == "grass" else 0.32))
		"dirt_path":
			for y in range(TILE_SIZE):
				for x in [5, 10]:
					var rut = image.get_pixel(x, y)
					if rut.a > 0.0:
						image.set_pixel(x, y, rut.darkened(0.16))
		"cobblestone", "stone_floor", "marble", "brick", "dark_stone":
			for point in [Vector2i(2 + variant, 3), Vector2i(11, 5 + variant), Vector2i(6, 11)]:
				if point.x < TILE_SIZE and point.y < TILE_SIZE:
					var accent = image.get_pixel(point.x, point.y)
					if accent.a > 0.0:
						image.set_pixel(point.x, point.y, accent.darkened(0.18))
			image.fill_rect(Rect2i(0, TILE_SIZE - 2, TILE_SIZE, 1), Color(0.14, 0.12, 0.12, 0.08))
			if tile_name == "marble":
				for step in range(2, TILE_SIZE, 5):
					image.fill_rect(Rect2i(step, maxi(step / 2, 0), 2, 1), Color(0.84, 0.84, 0.86, 0.10))
		"wood_floor", "tavern_floor":
			for y in range(3, TILE_SIZE, 4):
				image.fill_rect(Rect2i(0, y, TILE_SIZE, 1), Color(0.24, 0.14, 0.08, 0.18))
			for x in range(2 + variant, TILE_SIZE, 6):
				image.fill_rect(Rect2i(x, 2, 1, TILE_SIZE - 4), Color(0.74, 0.56, 0.34, 0.10))
		"wall":
			for y in range(3, TILE_SIZE, 4):
				image.fill_rect(Rect2i(0, y, TILE_SIZE, 1), Color(0.10, 0.10, 0.12, 0.28))
			for x in range(2 + variant, TILE_SIZE, 5):
				image.fill_rect(Rect2i(x, 2, 1, TILE_SIZE - 4), Color(0.12, 0.12, 0.14, 0.16))


static func _draw_interactive_icon(image: Image, tile_name: String) -> void:
	match tile_name:
		"door":
			image.fill_rect(Rect2i(5, 3, 6, 10), Color(0.30, 0.17, 0.08))
			image.fill_rect(Rect2i(6, 4, 4, 8), Color(0.68, 0.48, 0.18))
			image.set_pixel(9, 8, Color(0.94, 0.82, 0.46))
		"well", "fountain":
			for y in range(4, 12):
				for x in range(4, 12):
					var dx = x - 7.5
					var dy = y - 7.5
					var distance = dx * dx + dy * dy
					if distance <= 16.0:
						image.set_pixel(x, y, Color(0.22, 0.62, 0.78))
					elif distance <= 22.0:
						image.set_pixel(x, y, Color(0.60, 0.66, 0.74))
			if tile_name == "fountain":
				image.fill_rect(Rect2i(7, 2, 2, 4), Color(0.74, 0.90, 1.0))
		"tree":
			image.fill_rect(Rect2i(7, 8, 2, 5), Color(0.42, 0.24, 0.12))
			for y in range(2, 10):
				for x in range(3, 13):
					var dx = x - 8
					var dy = y - 6
					if dx * dx + dy * dy <= 16:
						image.set_pixel(x, y, Color(0.20, 0.48, 0.16))
		"barrel", "crate", "chest":
			image.fill_rect(Rect2i(4, 5, 8, 7), Color(0.60, 0.42, 0.20))
			image.fill_rect(Rect2i(5, 6, 6, 5), Color(0.72, 0.52, 0.26))
			image.fill_rect(Rect2i(4, 8, 8, 1), Color(0.32, 0.20, 0.10))
			if tile_name == "chest":
				image.fill_rect(Rect2i(7, 5, 2, 2), Color(0.96, 0.84, 0.40))
		"anvil":
			image.fill_rect(Rect2i(5, 6, 6, 3), Color(0.52, 0.52, 0.58))
			image.fill_rect(Rect2i(6, 9, 4, 2), Color(0.40, 0.40, 0.44))
			image.fill_rect(Rect2i(7, 11, 2, 2), Color(0.24, 0.24, 0.26))
		"altar":
			image.fill_rect(Rect2i(4, 5, 8, 5), Color(0.74, 0.74, 0.80))
			image.fill_rect(Rect2i(6, 3, 4, 2), Color(0.92, 0.82, 0.50))
		"bed":
			image.fill_rect(Rect2i(3, 4, 10, 7), Color(0.60, 0.24, 0.30))
			image.fill_rect(Rect2i(3, 4, 3, 3), Color(0.88, 0.88, 0.82))
		"bench", "table", "chair", "bookshelf":
			image.fill_rect(Rect2i(4, 5, 8, 6), Color(0.56, 0.38, 0.22))
			if tile_name == "chair":
				image.fill_rect(Rect2i(5, 3, 6, 2), Color(0.50, 0.34, 0.18))
			elif tile_name == "bookshelf":
				image.fill_rect(Rect2i(4, 3, 8, 9), Color(0.42, 0.24, 0.18))
				image.fill_rect(Rect2i(5, 4, 6, 1), Color(0.80, 0.30, 0.26))


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
