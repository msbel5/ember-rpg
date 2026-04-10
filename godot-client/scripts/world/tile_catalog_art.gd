extends RefCounted
class_name TileCatalogArt

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")

static func variant_tile_image(
	tile_name: String,
	variant: int,
	tile_size: int,
	tile_palette: Dictionary,
	interactive_tile_names: Array,
	primary_tile_root: String,
	fallback_tile_root: String,
	texture_aliases: Dictionary,
) -> Image:
	var loaded = _load_generated_tile_image(tile_name, texture_aliases)
	if loaded != null:
		if loaded.get_width() != tile_size or loaded.get_height() != tile_size:
			loaded.resize(tile_size, tile_size, Image.INTERPOLATE_NEAREST)
		return _variantize_image(tile_name, loaded, variant, true, tile_size)

	loaded = _load_third_party_tile_image(tile_name, primary_tile_root, fallback_tile_root)
	if loaded != null:
		if loaded.get_width() != tile_size or loaded.get_height() != tile_size:
			loaded.resize(tile_size, tile_size, Image.INTERPOLATE_NEAREST)
		return _variantize_image(tile_name, loaded, variant, false, tile_size)

	var image = Image.create(tile_size, tile_size, false, Image.FORMAT_RGBA8)
	_draw_tile(image, 0, tile_size, tile_palette[tile_name], variant)
	if interactive_tile_names.has(tile_name) or tile_name in ["door", "well", "fountain", "tree"]:
		_draw_interactive_icon(image, tile_name)
	return image


static func load_image_file(resource_path: String) -> Image:
	var image = Image.new()
	if image.load(ProjectSettings.globalize_path(resource_path)) != OK:
		return null
	return image


static func _load_third_party_tile_image(tile_name: String, primary_tile_root: String, fallback_tile_root: String) -> Image:
	for root in [primary_tile_root, fallback_tile_root]:
		var third_party_path := "%s/%s.png" % [root, tile_name]
		if FileAccess.file_exists(third_party_path):
			return load_image_file(third_party_path)
	return null


static func _load_generated_tile_image(tile_name: String, texture_aliases: Dictionary) -> Image:
	var lookup_name = texture_aliases.get(tile_name, tile_name)
	var relative_path = AssetManifest.resolve_relative_path("tiles", lookup_name)
	if relative_path.is_empty():
		relative_path = "tiles/%s.png" % lookup_name
	var asset_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/tiles/%s.png" % lookup_name)
	if asset_path.is_empty() or not FileAccess.file_exists(asset_path):
		return null
	return load_image_file(asset_path)


static func _draw_tile(target_image: Image, offset_x: int, tile_size: int, base_color: Color, variant: int = 0) -> void:
	var fill_color = base_color
	if variant == 1:
		fill_color = fill_color.lightened(0.08)
	elif variant == 2:
		fill_color = fill_color.darkened(0.08)

	target_image.fill_rect(Rect2i(offset_x, 0, tile_size, tile_size), fill_color.darkened(0.12))
	target_image.fill_rect(Rect2i(offset_x + 1, 1, tile_size - 2, tile_size - 2), fill_color)
	target_image.fill_rect(Rect2i(offset_x + 2, 2, tile_size - 4, tile_size - 4), fill_color.lightened(0.05))
	for step_y in range(2 + variant, tile_size - 1, 4):
		for step_x in range(2 + ((variant + step_y) % 2), tile_size - 1, 4):
			target_image.set_pixel(offset_x + step_x, step_y, fill_color.lightened(0.12))


static func _variantize_image(tile_name: String, source: Image, variant: int, apply_grade: bool = true, tile_size: int = 32) -> Image:
	var image = source.duplicate()
	if apply_grade:
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
	_apply_tile_pattern(tile_name, image, variant, tile_size)
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
				"sand":
					pixel = pixel.lightened(0.06)
					pixel = pixel.lerp(Color(0.72, 0.63, 0.41, pixel.a), 0.28)
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


static func _apply_tile_pattern(tile_name: String, image: Image, variant: int, tile_size: int) -> void:
	match tile_name:
		"grass", "swamp":
			for x in range(1 + variant, tile_size, 5):
				for y in range(2, tile_size - 1, 2):
					var blade = image.get_pixel(x, y)
					if blade.a > 0.0:
						image.set_pixel(x, y, blade.darkened(0.18))
			for y in range(3 + variant, tile_size, 6):
				image.fill_rect(Rect2i((variant + y) % 5, y, 3, 1), Color(0.22, 0.28, 0.14, 0.24 if tile_name == "grass" else 0.32))
		"dirt_path":
			for y in range(tile_size):
				for x in [5, 10]:
					var rut = image.get_pixel(x, y)
					if rut.a > 0.0:
						image.set_pixel(x, y, rut.darkened(0.16))
		"sand":
			for y in range(2 + variant, tile_size, 6):
				for x in range((y + variant) % 5, tile_size, 5):
					var grain = image.get_pixel(x, y)
					if grain.a > 0.0:
						image.set_pixel(x, y, grain.darkened(0.10))
		"cobblestone", "stone_floor", "marble", "brick", "dark_stone":
			for point in [Vector2i(2 + variant, 3), Vector2i(11, 5 + variant), Vector2i(6, 11)]:
				if point.x < tile_size and point.y < tile_size:
					var accent = image.get_pixel(point.x, point.y)
					if accent.a > 0.0:
						image.set_pixel(point.x, point.y, accent.darkened(0.18))
			image.fill_rect(Rect2i(0, tile_size - 2, tile_size, 1), Color(0.14, 0.12, 0.12, 0.08))
			if tile_name == "marble":
				for step in range(2, tile_size, 5):
					image.fill_rect(Rect2i(step, maxi(step / 2, 0), 2, 1), Color(0.84, 0.84, 0.86, 0.10))
		"wood_floor", "tavern_floor":
			for y in range(3, tile_size, 4):
				image.fill_rect(Rect2i(0, y, tile_size, 1), Color(0.24, 0.14, 0.08, 0.18))
			for x in range(2 + variant, tile_size, 6):
				image.fill_rect(Rect2i(x, 2, 1, tile_size - 4), Color(0.74, 0.56, 0.34, 0.10))
		"wall":
			for y in range(3, tile_size, 4):
				image.fill_rect(Rect2i(0, y, tile_size, 1), Color(0.10, 0.10, 0.12, 0.28))
			for x in range(2 + variant, tile_size, 5):
				image.fill_rect(Rect2i(x, 2, 1, tile_size - 4), Color(0.12, 0.12, 0.14, 0.16))


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
