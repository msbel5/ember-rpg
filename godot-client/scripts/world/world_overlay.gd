extends Control
class_name WorldOverlay

## Deprecated: static background images removed — tilemap is the sole world surface now
const ATMOSPHERE_THEME := {
	"fantasy_ember": {
		"wash": Color(0.10, 0.08, 0.04, 0.10),
		"top": Color(0.56, 0.32, 0.14, 0.11),
		"bottom": Color(0.06, 0.10, 0.16, 0.18),
		"edge": Color(0.04, 0.02, 0.01, 0.28),
		"mote": Color(0.98, 0.84, 0.60, 0.28),
		"focus": Color(0.92, 0.72, 0.42, 0.055),
		"line": Color(0.84, 0.62, 0.38, 0.055),
	},
	"scifi_frontier": {
		"wash": Color(0.02, 0.08, 0.12, 0.10),
		"top": Color(0.16, 0.46, 0.66, 0.11),
		"bottom": Color(0.02, 0.04, 0.08, 0.18),
		"edge": Color(0.00, 0.04, 0.08, 0.28),
		"mote": Color(0.62, 0.88, 1.00, 0.26),
		"focus": Color(0.38, 0.86, 1.00, 0.055),
		"line": Color(0.44, 0.82, 0.96, 0.06),
	},
}

var adapter_id: String = "fantasy_ember"
var background_key: String = ""
var placeholder_active: bool = false
var motes: Array = []
var _time: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	set_process(true)


func _process(delta: float) -> void:
	_time += delta
	queue_redraw()


func configure(next_adapter_id: String, next_background_key: String, next_motes: Array, is_placeholder: bool) -> void:
	adapter_id = next_adapter_id
	background_key = next_background_key
	motes = next_motes.duplicate(true)
	placeholder_active = is_placeholder
	queue_redraw()


func _draw() -> void:
	if size.x <= 0.0 or size.y <= 0.0:
		return
	var palette = ATMOSPHERE_THEME.get(adapter_id, ATMOSPHERE_THEME["fantasy_ember"])
	var wash: Color = palette.get("wash", Color(0.0, 0.0, 0.0, 0.0))
	var top: Color = palette.get("top", Color(0.0, 0.0, 0.0, 0.0))
	var bottom: Color = palette.get("bottom", Color(0.0, 0.0, 0.0, 0.0))
	var edge: Color = palette.get("edge", Color(0.0, 0.0, 0.0, 0.0))
	var mote_color: Color = palette.get("mote", Color(1.0, 1.0, 1.0, 0.12))
	var focus: Color = palette.get("focus", Color(1.0, 1.0, 1.0, 0.0))
	var line: Color = palette.get("line", Color(1.0, 1.0, 1.0, 0.0))
	draw_rect(Rect2(Vector2.ZERO, size), wash, true)
	draw_rect(Rect2(0.0, size.y * 0.54, size.x, size.y * 0.46), Color(bottom.r, bottom.g, bottom.b, bottom.a * 0.55), true)
	var slice_count := 6
	var strip_height = size.y / float(slice_count)
	for index in range(slice_count):
		var weight = 1.0 - float(index) / float(slice_count)
		draw_rect(Rect2(0.0, strip_height * index, size.x, strip_height), Color(top.r, top.g, top.b, top.a * weight), true)
		draw_rect(
			Rect2(0.0, size.y - strip_height * (index + 1), size.x, strip_height),
			Color(bottom.r, bottom.g, bottom.b, bottom.a * weight),
			true
		)
	var edge_width = minf(size.x * 0.09, 64.0)
	for index in range(4):
		var edge_weight = 1.0 - float(index) / 4.0
		var left_rect = Rect2(index * edge_width / 4.0, 0.0, edge_width / 4.0, size.y)
		var right_rect = Rect2(size.x - edge_width + index * edge_width / 4.0, 0.0, edge_width / 4.0, size.y)
		draw_rect(left_rect, Color(edge.r, edge.g, edge.b, edge.a * edge_weight), true)
		draw_rect(right_rect, Color(edge.r, edge.g, edge.b, edge.a * edge_weight), true)
	_draw_focus_glow(focus)
	_draw_adapter_linework(line)
	for mote in motes:
		var x_origin = float(mote.get("x", 0.0))
		var y_origin = float(mote.get("y", 0.0))
		var speed = float(mote.get("speed", 1.0))
		var drift = float(mote.get("drift", 12.0))
		var radius = float(mote.get("radius", 2.0))
		var phase = float(mote.get("phase", 0.0))
		var alpha = float(mote.get("alpha", mote_color.a))
		var x = fposmod(x_origin + _time * speed * 18.0, size.x + 40.0) - 20.0
		var y = y_origin + sin(_time * speed + phase) * drift
		draw_circle(Vector2(x, y), radius, Color(mote_color.r, mote_color.g, mote_color.b, alpha))


func _draw_focus_glow(focus: Color) -> void:
	if focus.a <= 0.0:
		return
	var center = size / 2.0
	var max_radius = minf(size.x, size.y) * 0.34
	for band in range(5, 0, -1):
		var weight = float(band) / 5.0
		var radius = max_radius * (0.45 + weight * 0.18)
		draw_circle(center, radius, Color(focus.r, focus.g, focus.b, focus.a * weight * 0.7))


func _draw_adapter_linework(line: Color) -> void:
	if line.a <= 0.0:
		return
	if adapter_id == "scifi_frontier":
		for x in range(0, int(size.x), 48):
			draw_line(Vector2(x, 0), Vector2(x + 64, size.y), Color(line.r, line.g, line.b, line.a * 0.35), 1.0)
		for y in range(18, int(size.y), 36):
			draw_line(Vector2(0, y), Vector2(size.x, y), Color(line.r, line.g, line.b, line.a * 0.18), 1.0)
	else:
		var center = size / 2.0
		for ring in range(3):
			draw_arc(center, minf(size.x, size.y) * (0.18 + ring * 0.08), 0.0, TAU, 64, Color(line.r, line.g, line.b, line.a * (0.45 - ring * 0.10)), 1.0)


