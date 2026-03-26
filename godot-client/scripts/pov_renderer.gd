extends Control

const PovRendererConfig = preload("res://scripts/pov_renderer_config.gd")

## Storyboard POV Renderer — first-person view of the game world
## Deterministic: same position + facing + entities = same image
## Layered rendering with caching:
##   Layer 0: Sky/ceiling (location-based color)
##   Layer 1: Floor/ground plane
##   Layer 2: Walls/environment (distance-scaled rectangles)
##   Layer 3: Entities (cached sprites/silhouettes at tile positions)
##   Layer 4: Labels (entity names)

const PALETTES = PovRendererConfig.PALETTES
const ENTITY_COLORS = PovRendererConfig.ENTITY_COLORS
const OBJECT_TEMPLATES = PovRendererConfig.OBJECT_TEMPLATES

# Render state
var current_palette: Dictionary = {}
var player_pos: Vector2i = Vector2i(0, 0)
var player_facing: int = 0  # 0=N, 1=E, 2=S, 3=W
var visible_entities: Array = []
var revealed_ids: Dictionary = {}  # entity_id → reveal_alpha (0.0 to 1.0)
var entity_cache: Dictionary = {}  # cache key → rendered data
var _fade_active: bool = false
var _entity_hit_boxes: Array = []  # [{rect: Rect2, id: String, data: Dictionary}, ...]
var _bg_texture: Texture2D = null  # AI-generated background (if available)
var _bg_alpha: float = 0.0        # crossfade alpha for background

const FACING_VECTORS = PovRendererConfig.FACING_VECTORS
const VIEW_DEPTH = PovRendererConfig.VIEW_DEPTH
const VIEW_WIDTH = PovRendererConfig.VIEW_WIDTH

signal entity_clicked_pov(entity_id: String, entity_data: Dictionary)

func _ready() -> void:
	current_palette = PALETTES["default"]
	mouse_filter = Control.MOUSE_FILTER_STOP  # Receive mouse events
	focus_mode = Control.FOCUS_ALL  # Receive keyboard events
	# Prevent arrow keys from navigating to other UI elements
	focus_neighbor_top = get_path()
	focus_neighbor_bottom = get_path()
	focus_neighbor_left = get_path()
	focus_neighbor_right = get_path()
	focus_next = get_path()
	focus_previous = get_path()
	GameState.map_loaded.connect(_on_map_loaded)
	GameState.entities_loaded.connect(_on_entities_loaded)
	GameState.entity_revealed.connect(_on_entity_revealed)

func set_location_type(location: String) -> void:
	var loc_lower = location.to_lower()
	current_palette = PALETTES["default"]
	for key in PALETTES:
		if loc_lower.contains(key):
			current_palette = PALETTES[key]
			break
	# Try to load AI-generated background for this location
	_load_ai_background(loc_lower)
	queue_redraw()

func _load_ai_background(location: String) -> void:
	_bg_texture = null
	_bg_alpha = 0.0
	var bg_path = PovRendererConfig.resolve_background(location)
	if bg_path != "" and ResourceLoader.exists(bg_path):
		_bg_texture = load(bg_path)
		_bg_alpha = 0.0
		_fade_active = true

func update_player(pos: Vector2i, facing: int) -> void:
	var moved = (pos != player_pos)
	player_pos = pos
	player_facing = clampi(facing, 0, 3)
	_recalculate_visible()
	# Auto-reveal entities in FOV when player moves
	if moved:
		_auto_reveal_fov_entities()
	queue_redraw()

func reveal_entity(entity_id: String) -> void:
	if not revealed_ids.has(entity_id):
		revealed_ids[entity_id] = 0.0  # Start at 0 alpha, will fade in
		_fade_active = true
	queue_redraw()

func reveal_all() -> void:
	for entity in visible_entities:
		var eid = entity.get("id", "")
		if eid != "" and not revealed_ids.has(eid):
			revealed_ids[eid] = 0.0
	_fade_active = true
	queue_redraw()

func _process(delta: float) -> void:
	if not _fade_active:
		return
	var all_done = true
	# Crossfade AI background
	if _bg_texture and _bg_alpha < 1.0:
		_bg_alpha = minf(_bg_alpha + delta * 0.5, 1.0)  # 2 second crossfade
		all_done = false
	# Gradually increase alpha of fading-in entities
	for eid in revealed_ids:
		if revealed_ids[eid] < 1.0:
			revealed_ids[eid] = minf(revealed_ids[eid] + delta * 0.7, 1.0)
			all_done = false
	if all_done:
		_fade_active = false
	queue_redraw()

func _on_map_loaded(_map_data: Dictionary) -> void:
	queue_redraw()

func _on_entities_loaded(entities_data: Dictionary) -> void:
	visible_entities.clear()
	for key in ["npcs", "items", "enemies"]:
		if entities_data.has(key):
			visible_entities.append_array(entities_data[key])
	queue_redraw()

func _on_entity_revealed(entity_id: String) -> void:
	reveal_entity(entity_id)

func _recalculate_visible() -> void:
	# Entities in FOV will be drawn; others ignored
	# FOV is a cone: VIEW_DEPTH ahead, expanding width
	pass  # Distance check done in _draw_entities

func _auto_reveal_fov_entities() -> void:
	# When player moves, reveal entities that are now in FOV
	var facing_vec = FACING_VECTORS[player_facing]
	var right_vec = FACING_VECTORS[(player_facing + 1) % 4]
	for entity in visible_entities:
		var eid = entity.get("id", "")
		if eid == "" or revealed_ids.has(eid):
			continue
		var pos = entity.get("position", [0, 0])
		var entity_pos = Vector2i(int(pos[0]), int(pos[1]))
		var delta = entity_pos - player_pos
		var forward = delta.x * facing_vec.x + delta.y * facing_vec.y
		var lateral = delta.x * right_vec.x + delta.y * right_vec.y
		# Reveal if in FOV cone (within 3 tiles for auto-reveal)
		if forward >= 1 and forward <= 3 and abs(lateral) <= forward:
			revealed_ids[eid] = 0.0
			_fade_active = true

func _draw() -> void:
	var rect = get_rect()
	var w = rect.size.x
	var h = rect.size.y
	if w <= 0 or h <= 0:
		return

	_entity_hit_boxes.clear()

	# --- Procedural background (always drawn as base) ---
	draw_rect(Rect2(0, 0, w, h * 0.4), current_palette.get("sky", Color.BLACK))
	_draw_floor(w, h)
	_draw_walls(w, h)
	var ambient = current_palette.get("ambient", Color(0.5, 0.5, 0.5, 0.05))
	draw_rect(Rect2(0, 0, w, h), ambient)

	# --- AI Background overlay (crossfades over procedural) ---
	if _bg_texture and _bg_alpha > 0.0:
		draw_texture_rect(
			_bg_texture,
			Rect2(0, 0, w, h),
			false,
			Color(1, 1, 1, _bg_alpha)
		)

	# --- Entities (distance-sorted, back to front) ---
	_draw_entities(w, h)

func _draw_floor(w: float, h: float) -> void:
	var floor_color = current_palette.get("floor", Color(0.2, 0.2, 0.2))
	# Perspective floor: trapezoid from horizon to bottom
	var horizon_y = h * 0.4
	var floor_top_left = Vector2(w * 0.2, horizon_y)
	var floor_top_right = Vector2(w * 0.8, horizon_y)
	var floor_bot_left = Vector2(0, h)
	var floor_bot_right = Vector2(w, h)

	var points = PackedVector2Array([floor_top_left, floor_top_right, floor_bot_right, floor_bot_left])
	var colors = PackedColorArray([
		floor_color * 0.6,  # far = darker
		floor_color * 0.6,
		floor_color,        # near = brighter
		floor_color,
	])
	draw_polygon(points, colors)

	# Floor grid lines for depth perception
	for i in range(1, VIEW_DEPTH + 1):
		var t = float(i) / float(VIEW_DEPTH)
		var y = horizon_y + (h - horizon_y) * t
		var x_shrink = (1.0 - t) * w * 0.3
		var line_color = Color(floor_color.r + 0.05, floor_color.g + 0.05, floor_color.b + 0.05, 0.3)
		draw_line(Vector2(x_shrink, y), Vector2(w - x_shrink, y), line_color, 1.0)

func _draw_walls(w: float, h: float) -> void:
	var wall_color = current_palette.get("wall", Color(0.25, 0.22, 0.18))
	var horizon_y = h * 0.4

	# Left wall (trapezoid)
	var lw_points = PackedVector2Array([
		Vector2(0, 0),                    # top-left
		Vector2(w * 0.2, 0),             # top-right (vanishing)
		Vector2(w * 0.2, horizon_y),     # bottom-right (vanishing)
		Vector2(0, h),                    # bottom-left
	])
	var lw_colors = PackedColorArray([
		wall_color * 0.7,
		wall_color * 0.5,
		wall_color * 0.5,
		wall_color * 0.8,
	])
	draw_polygon(lw_points, lw_colors)

	# Right wall (trapezoid)
	var rw_points = PackedVector2Array([
		Vector2(w * 0.8, 0),
		Vector2(w, 0),
		Vector2(w, h),
		Vector2(w * 0.8, horizon_y),
	])
	var rw_colors = PackedColorArray([
		wall_color * 0.5,
		wall_color * 0.7,
		wall_color * 0.8,
		wall_color * 0.5,
	])
	draw_polygon(rw_points, rw_colors)

	# Back wall
	var bw_points = PackedVector2Array([
		Vector2(w * 0.2, 0),
		Vector2(w * 0.8, 0),
		Vector2(w * 0.8, horizon_y),
		Vector2(w * 0.2, horizon_y),
	])
	draw_polygon(bw_points, PackedColorArray([
		wall_color * 0.4,
		wall_color * 0.4,
		wall_color * 0.5,
		wall_color * 0.5,
	]))

func _draw_entities(w: float, h: float) -> void:
	var horizon_y = h * 0.4
	var facing_vec = FACING_VECTORS[player_facing]
	var right_vec = FACING_VECTORS[(player_facing + 1) % 4]

	# Collect entities with distance info
	var draw_list: Array = []
	for entity in visible_entities:
		var eid = entity.get("id", "")
		if not revealed_ids.has(eid):
			continue  # Not yet revealed by DM
		var alpha = revealed_ids[eid]
		if alpha <= 0.0:
			continue

		var pos = entity.get("position", [0, 0])
		var entity_pos = Vector2i(int(pos[0]), int(pos[1]))
		var delta = entity_pos - player_pos

		# Project onto facing direction (forward distance) and right direction (lateral offset)
		var forward = delta.x * facing_vec.x + delta.y * facing_vec.y
		var lateral = delta.x * right_vec.x + delta.y * right_vec.y

		if forward < 1 or forward > VIEW_DEPTH:
			continue  # Behind us or too far
		if abs(lateral) > forward:
			continue  # Outside FOV cone

		draw_list.append({
			"entity": entity,
			"forward": forward,
			"lateral": lateral,
			"alpha": alpha,
		})

	# Sort back to front (furthest first)
	draw_list.sort_custom(func(a, b): return a["forward"] > b["forward"])

	for item in draw_list:
		_draw_single_entity(item, w, h, horizon_y)

func _draw_single_entity(item: Dictionary, w: float, h: float, horizon_y: float) -> void:
	var entity = item["entity"]
	var forward: int = item["forward"]
	var lateral: int = item["lateral"]
	var fade_alpha: float = item.get("alpha", 1.0)
	var template = entity.get("template", "default")
	var entity_name = entity.get("name", "?")

	# Distance factor: 1.0 = closest, 0.0 = furthest
	var dist_factor = 1.0 - (float(forward - 1) / float(VIEW_DEPTH))
	dist_factor = clampf(dist_factor, 0.1, 1.0)

	# Entity size scales with distance
	var entity_h = h * 0.35 * dist_factor
	var entity_w = entity_h * 0.4

	# Vertical position: feet on floor, rises with distance toward horizon
	var floor_y = horizon_y + (h - horizon_y) * dist_factor
	var entity_y = floor_y - entity_h

	# Horizontal position: center + lateral offset scaled by distance
	var center_x = w * 0.5
	var corridor_half_w = w * 0.3 * dist_factor  # visible corridor narrows with distance
	var entity_x = center_x + lateral * corridor_half_w - entity_w * 0.5

	# Get entity color with fade alpha
	var base_color = ENTITY_COLORS.get(template, ENTITY_COLORS["default"])
	var draw_color = Color(
		base_color.r * (0.4 + 0.6 * dist_factor),
		base_color.g * (0.4 + 0.6 * dist_factor),
		base_color.b * (0.4 + 0.6 * dist_factor),
		fade_alpha,
	)

	# --- Draw silhouette ---
	var is_object = template in OBJECT_TEMPLATES
	if is_object:
		_draw_object_silhouette(entity_x, entity_y, entity_w, entity_h, draw_color, fade_alpha)
	else:
		_draw_humanoid_silhouette(entity_x, entity_y, entity_w, entity_h, draw_color, fade_alpha)

	# --- Layer 4: Label ---
	if dist_factor > 0.3 and fade_alpha > 0.3:
		var font = ThemeDB.fallback_font
		var font_size = int(10 * dist_factor + 6)
		var label_pos = Vector2(entity_x + entity_w * 0.5, entity_y - 4)
		var text_size = font.get_string_size(entity_name, HORIZONTAL_ALIGNMENT_CENTER, -1, font_size)
		label_pos.x -= text_size.x * 0.5
		# Shadow
		draw_string(font, label_pos + Vector2(1, 1), entity_name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(0, 0, 0, 0.7 * fade_alpha))
		# Text
		var label_color = Color(1, 1, 0.85, dist_factor * fade_alpha)
		draw_string(font, label_pos, entity_name, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, label_color)

	# Store hit box for click detection
	if fade_alpha > 0.2:
		_entity_hit_boxes.append({
			"rect": Rect2(entity_x, entity_y, entity_w, entity_h),
			"id": entity.get("id", ""),
			"data": entity,
		})

func _draw_humanoid_silhouette(ex: float, ey: float, ew: float, eh: float, color: Color, alpha: float) -> void:
	# Head (circle)
	var head_radius = ew * 0.35
	var head_center = Vector2(ex + ew * 0.5, ey + head_radius)
	draw_circle(head_center, head_radius, color)
	# Body
	var body_top = ey + head_radius * 2
	var body_h = eh * 0.45
	draw_rect(Rect2(ex + ew * 0.15, body_top, ew * 0.7, body_h), color)
	# Legs
	var leg_top = body_top + body_h
	var leg_h = eh - (head_radius * 2 + body_h)
	var leg_w = ew * 0.25
	var leg_color = Color(color.r * 0.85, color.g * 0.85, color.b * 0.85, alpha)
	draw_rect(Rect2(ex + ew * 0.15, leg_top, leg_w, leg_h), leg_color)
	draw_rect(Rect2(ex + ew * 0.6, leg_top, leg_w, leg_h), leg_color)

func _draw_object_silhouette(ex: float, ey: float, ew: float, eh: float, color: Color, _alpha: float) -> void:
	# Objects are shorter, wider rectangles with a top detail
	var obj_h = eh * 0.5
	var obj_w = ew * 1.2
	var obj_x = ex - ew * 0.1  # slightly wider
	var obj_y = ey + eh - obj_h  # sits on ground
	# Main body
	draw_rect(Rect2(obj_x, obj_y, obj_w, obj_h), color)
	# Top edge highlight
	var highlight = Color(color.r + 0.1, color.g + 0.1, color.b + 0.1, color.a)
	draw_rect(Rect2(obj_x, obj_y, obj_w, obj_h * 0.15), highlight)
	# Dark base
	var dark = Color(color.r * 0.6, color.g * 0.6, color.b * 0.6, color.a)
	draw_rect(Rect2(obj_x, obj_y + obj_h * 0.85, obj_w, obj_h * 0.15), dark)

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Always reclaim focus when POV is clicked
		grab_focus()
		var click_pos = event.position
		# Check hit boxes in reverse order (front entities drawn last = on top)
		var hit_entity = false
		for i in range(_entity_hit_boxes.size() - 1, -1, -1):
			var hb = _entity_hit_boxes[i]
			if hb["rect"].has_point(click_pos):
				entity_clicked_pov.emit(hb["id"], hb["data"])
				hit_entity = true
				break
		get_viewport().set_input_as_handled()

	# Arrow keys / WASD rotate facing (only when POV is visible and focused)
	if event is InputEventKey and event.pressed and visible:
		var handled = true
		match event.keycode:
			KEY_LEFT, KEY_A:
				player_facing = (player_facing + 3) % 4  # turn left
			KEY_RIGHT, KEY_D:
				player_facing = (player_facing + 1) % 4  # turn right
			_:
				handled = false
		if handled:
			GameState.player_facing = player_facing
			_auto_reveal_fov_entities()
			queue_redraw()
			get_viewport().set_input_as_handled()
