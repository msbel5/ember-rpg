## Texture generation and visual property lookups for entities.
## Extracted from entity_layer.gd for SOLID compliance.
extends RefCounted
class_name EntityVisuals

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

const ADAPTER_BUCKET_TINTS := {
	"fantasy_ember": {
		"player": Color(1.00, 0.95, 0.86),
		"npc": Color(1.00, 0.90, 0.72),
		"enemy": Color(0.96, 0.54, 0.42),
		"item": Color(0.88, 1.00, 0.84),
		"furniture": Color(0.78, 0.72, 0.62),
	},
	"scifi_frontier": {
		"player": Color(0.76, 0.95, 1.00),
		"npc": Color(0.76, 1.00, 0.92),
		"enemy": Color(1.00, 0.58, 0.76),
		"item": Color(0.94, 1.00, 0.72),
		"furniture": Color(0.68, 0.74, 0.82),
	},
}


static func adapter_bucket_tint(bucket: String, adapter_id: String) -> Color:
	var norm_adapter := adapter_id.strip_edges().to_lower()
	var norm_bucket := bucket.strip_edges().to_lower()
	var palette = ADAPTER_BUCKET_TINTS.get(norm_adapter, ADAPTER_BUCKET_TINTS["fantasy_ember"])
	return palette.get(norm_bucket, Color.WHITE)


static func display_size(bucket: String) -> int:
	match bucket.strip_edges().to_lower():
		"player": return 36
		"enemy": return 28
		"npc": return 26
		"furniture": return 24
		"item": return 20
		_: return 24


static func body_modulate(bucket: String, adapter_id: String, using_fallback: bool) -> Color:
	if using_fallback:
		return adapter_bucket_tint(bucket, adapter_id)
	var tint := adapter_bucket_tint(bucket, adapter_id)
	var blend := 0.08 if bucket == "player" else 0.16
	return Color.WHITE.lerp(tint, blend)


static func body_lift(bucket: String) -> float:
	var extra := maxf(float(display_size(bucket) - TileCatalog.TILE_SIZE), 0.0)
	return 4.0 + extra * 0.42


static func shadow_alpha(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"item": return 0.18
		"furniture": return 0.26
		"player": return 0.34
		_: return 0.28


static func shadow_scale(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player": return 1.42
		"enemy", "npc": return 1.16
		"furniture": return 1.15
		"item": return 0.70
		_: return 0.95


static func aura_scale(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player": return 1.34
		"enemy": return 1.18
		"npc": return 1.08
		"furniture": return 0.92
		_: return 0.0


static func aura_modulate(bucket: String, adapter_id: String) -> Color:
	var alpha := 0.0
	match bucket.strip_edges().to_lower():
		"player": alpha = 0.22
		"enemy": alpha = 0.18
		"npc": alpha = 0.14
		"furniture": alpha = 0.08
		_: alpha = 0.0
	if alpha <= 0.0:
		return Color(1.0, 1.0, 1.0, 0.0)
	var tint := adapter_bucket_tint(bucket, adapter_id).lightened(0.28)
	return Color(tint.r, tint.g, tint.b, alpha)


static func idle_amplitude(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player": return 1.00
		"enemy": return 0.82
		"npc": return 0.68
		"furniture": return 0.18
		"item": return 0.28
		_: return 0.52


static func idle_speed(bucket: String) -> float:
	match bucket.strip_edges().to_lower():
		"player": return 2.3
		"enemy": return 2.0
		"item": return 1.6
		_: return 1.8


static func z_bias(bucket: String) -> int:
	match bucket.strip_edges().to_lower():
		"item": return 1
		"furniture": return 2
		"npc": return 3
		"enemy": return 4
		"player": return 5
		_: return 0


static func name_label_color(bucket: String) -> Color:
	match bucket:
		"player": return Color(1.0, 1.0, 1.0)
		"npc": return Color(0.80, 0.68, 0.26)
		"enemy": return Color(0.96, 0.30, 0.30)
		"item": return Color(0.40, 0.85, 0.40)
		_: return Color(0.70, 0.70, 0.70)


static func build_circle_texture(color: Color) -> Texture2D:
	var ts := TileCatalog.TILE_SIZE
	var image := Image.create(ts, ts, false, Image.FORMAT_RGBA8)
	for y in range(ts):
		for x in range(ts):
			var dx := x - (ts / 2.0) + 0.5
			var dy := y - (ts / 2.0) + 0.5
			if sqrt(dx * dx + dy * dy) <= 5.5:
				image.set_pixel(x, y, color)
	return ImageTexture.create_from_image(image)


static func build_diamond_texture(color: Color) -> Texture2D:
	var ts := TileCatalog.TILE_SIZE
	var image := Image.create(ts, ts, false, Image.FORMAT_RGBA8)
	var mid := int(ts / 2)
	for y in range(ts):
		for x in range(ts):
			if abs(x - mid) + abs(y - mid) <= 5:
				image.set_pixel(x, y, color)
	return ImageTexture.create_from_image(image)


static func build_square_texture(color: Color) -> Texture2D:
	var ts := TileCatalog.TILE_SIZE
	var image := Image.create(ts, ts, false, Image.FORMAT_RGBA8)
	image.fill_rect(Rect2i(3, 3, ts - 6, ts - 6), color)
	return ImageTexture.create_from_image(image)


static func build_shadow_texture() -> Texture2D:
	var ts := TileCatalog.TILE_SIZE
	var image := Image.create(ts, int(ts / 2), false, Image.FORMAT_RGBA8)
	var center := Vector2(float(image.get_width()) / 2.0, float(image.get_height()) / 2.0)
	for y in range(image.get_height()):
		for x in range(image.get_width()):
			var nx := (float(x) - center.x) / maxf(center.x - 1.0, 1.0)
			var ny := (float(y) - center.y) / maxf(center.y - 1.0, 1.0)
			var dist := nx * nx + ny * ny
			if dist <= 1.0:
				image.set_pixel(x, y, Color(0.0, 0.0, 0.0, clampf(1.0 - dist, 0.0, 1.0) * 0.7))
	return ImageTexture.create_from_image(image)


static func build_marker_textures() -> Dictionary:
	return {
		"player": build_circle_texture(Color(0.18, 0.78, 0.92)),
		"npc": build_circle_texture(Color(0.92, 0.78, 0.30)),
		"enemy": build_diamond_texture(Color(0.84, 0.24, 0.24)),
		"item": build_square_texture(Color(0.38, 0.82, 0.46)),
		"furniture": build_square_texture(Color(0.62, 0.54, 0.42)),
	}
