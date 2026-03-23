extends Control

## Storyboard POV Renderer — first-person view of the game world
## Deterministic: same position + facing + entities = same image
## Layered rendering with caching:
##   Layer 0: Sky/ceiling (location-based color)
##   Layer 1: Floor/ground plane
##   Layer 2: Walls/environment (distance-scaled rectangles)
##   Layer 3: Entities (cached sprites/silhouettes at tile positions)
##   Layer 4: Labels (entity names)

# --- Location color palettes ---
const PALETTES = {
	"tavern": {
		"sky": Color(0.12, 0.08, 0.05),      # dark wood ceiling
		"wall": Color(0.25, 0.18, 0.10),      # warm brown walls
		"floor": Color(0.20, 0.14, 0.08),     # dark wood floor
		"ambient": Color(0.9, 0.7, 0.3, 0.15) # warm candlelight
	},
	"forest": {
		"sky": Color(0.15, 0.25, 0.35),       # sky through canopy
		"wall": Color(0.10, 0.20, 0.08),      # dark green trees
		"floor": Color(0.18, 0.22, 0.10),     # forest floor
		"ambient": Color(0.4, 0.8, 0.3, 0.08) # green light filter
	},
	"dungeon": {
		"sky": Color(0.04, 0.04, 0.06),       # dark ceiling
		"wall": Color(0.15, 0.14, 0.16),      # grey stone
		"floor": Color(0.10, 0.09, 0.11),     # dark stone floor
		"ambient": Color(0.3, 0.3, 0.5, 0.10) # cold blue tint
	},
	"harbor": {
		"sky": Color(0.35, 0.55, 0.75),       # open sky
		"wall": Color(0.30, 0.25, 0.18),      # wooden buildings
		"floor": Color(0.45, 0.40, 0.30),     # cobblestone/sand
		"ambient": Color(0.9, 0.85, 0.6, 0.1) # warm sun
	},
	"cave": {
		"sky": Color(0.03, 0.03, 0.04),       # pitch black
		"wall": Color(0.12, 0.10, 0.08),      # rough stone
		"floor": Color(0.08, 0.07, 0.06),     # cave floor
		"ambient": Color(0.2, 0.15, 0.1, 0.05)# dim torchlight
	},
	"default": {
		"sky": Color(0.20, 0.25, 0.35),       # neutral sky
		"wall": Color(0.25, 0.22, 0.18),      # neutral walls
		"floor": Color(0.22, 0.20, 0.16),     # neutral floor
		"ambient": Color(0.5, 0.5, 0.5, 0.08) # neutral
	}
}

# Entity type colors for silhouettes
const ENTITY_COLORS = {
	"warrior": Color(0.2, 0.4, 0.8),
	"mage": Color(0.6, 0.2, 0.8),
	"rogue": Color(0.3, 0.3, 0.3),
	"priest": Color(0.9, 0.85, 0.5),
	"merchant": Color(0.8, 0.6, 0.2),
	"guard": Color(0.5, 0.5, 0.6),
	"innkeeper": Color(0.7, 0.5, 0.3),
	"quest_giver": Color(0.9, 0.8, 0.1),
	"blacksmith": Color(0.6, 0.3, 0.1),
	"beggar": Color(0.4, 0.35, 0.3),
	"goblin": Color(0.3, 0.5, 0.2),
	"skeleton": Color(0.85, 0.85, 0.8),
	"wolf": Color(0.4, 0.35, 0.3),
	"orc": Color(0.3, 0.4, 0.2),
	"spider": Color(0.2, 0.15, 0.2),
	"bandit": Color(0.4, 0.2, 0.2),
	"dragon": Color(0.7, 0.15, 0.1),
	"zombie": Color(0.3, 0.4, 0.3),
	# Items / Objects
	"notice_board": Color(0.5, 0.35, 0.15),
	"well": Color(0.3, 0.4, 0.5),
	"crate": Color(0.45, 0.35, 0.2),
	"barrel": Color(0.4, 0.3, 0.15),
	"chest": Color(0.6, 0.5, 0.1),
	"market_stall": Color(0.5, 0.4, 0.2),
	"fountain": Color(0.3, 0.5, 0.7),
	"campfire": Color(0.8, 0.4, 0.1),
	"default": Color(0.5, 0.5, 0.5),
}

# Templates that are objects/items (not humanoid NPCs)
const OBJECT_TEMPLATES = [
	"notice_board", "well", "crate", "barrel", "chest",
	"market_stall", "fountain", "campfire",
]

# Render state
var current_palette: Dictionary = {}
var player_pos: Vector2i = Vector2i(0, 0)
var player_facing: int = 0  # 0=N, 1=E, 2=S, 3=W
var visible_entities: Array = []
var revealed_ids: Dictionary = {}  # entity_id → reveal_alpha (0.0 to 1.0)
var entity_cache: Dictionary = {}  # cache key → rendered data
var _fade_active: bool = false
var _entity_hit_boxes: Array = []  # [{rect: Rect2, id: String, data: Dictionary}, ...]

# Facing direction vectors
const FACING_VECTORS = [
	Vector2i(0, -1),  # North
	Vector2i(1, 0),   # East
	Vector2i(0, 1),   # South
	Vector2i(-1, 0),  # West
]

const VIEW_DEPTH = 5  # how many tiles ahead we can see
const VIEW_WIDTH = 3  # tiles to left/right at closest distance

signal entity_clicked_pov(entity_id: String, entity_data: Dictionary)

func _ready() -> void:
	current_palette = PALETTES["default"]
	mouse_filter = Control.MOUSE_FILTER_STOP  # Receive mouse events
	focus_mode = Control.FOCUS_ALL  # Receive keyboard events
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
	queue_redraw()

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
	# Gradually increase alpha of fading-in entities
	var all_done = true
	for eid in revealed_ids:
		if revealed_ids[eid] < 1.0:
			revealed_ids[eid] = minf(revealed_ids[eid] + delta * 0.7, 1.0)  # ~1.4s fade
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

	# --- Layer 0: Sky / Ceiling ---
	draw_rect(Rect2(0, 0, w, h * 0.4), current_palette.get("sky", Color.BLACK))

	# --- Layer 1: Floor ---
	_draw_floor(w, h)

	# --- Layer 2: Walls / Environment ---
	_draw_walls(w, h)

	# --- Layer 3: Ambient light overlay ---
	var ambient = current_palette.get("ambient", Color(0.5, 0.5, 0.5, 0.05))
	draw_rect(Rect2(0, 0, w, h), ambient)

	# --- Layer 4: Entities (distance-sorted, back to front) ---
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
		var click_pos = event.position
		# Check hit boxes in reverse order (front entities drawn last = on top)
		for i in range(_entity_hit_boxes.size() - 1, -1, -1):
			var hb = _entity_hit_boxes[i]
			if hb["rect"].has_point(click_pos):
				entity_clicked_pov.emit(hb["id"], hb["data"])
				break

	# Arrow keys / WASD rotate facing (only when POV is visible)
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
