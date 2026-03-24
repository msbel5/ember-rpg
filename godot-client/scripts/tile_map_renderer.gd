extends Control

# Tile Map Renderer — draws tile grid + entities from backend data
# Renders into the left panel of game_session

const TILE_SIZE = 32
const TILE_TEXTURES = {
	"stone_floor": "res://assets/tiles/stone_floor.png",
	"stone_wall": "res://assets/tiles/stone_wall.png",
	"grass": "res://assets/tiles/grass.png",
	"dirt_path": "res://assets/tiles/dirt_path.png",
	"water": "res://assets/tiles/water.png",
	"door": "res://assets/tiles/door.png",
	"chest": "res://assets/tiles/chest.png",
	"stairs": "res://assets/tiles/stairs.png",
	"cobblestone": "res://assets/tiles/cobblestone.png",
	"wood_floor": "res://assets/tiles/wood_floor.png",
	"sand": "res://assets/tiles/sand.png",
	"dark_stone": "res://assets/tiles/dark_stone.png",
	"tavern_floor": "res://assets/tiles/tavern_floor.png",
	# Fallbacks
	"wall": "res://assets/tiles/stone_wall.png",
	"floor": "res://assets/tiles/stone_floor.png",
	"road": "res://assets/tiles/dirt_path.png",
	"building_wall": "res://assets/tiles/stone_wall.png",
	"building_floor": "res://assets/tiles/tavern_floor.png",
	"dock_planks": "res://assets/tiles/wood_floor.png",
}

const SPRITE_TEXTURES = {
	"warrior": "res://assets/sprites/warrior.png",
	"mage": "res://assets/sprites/mage.png",
	"rogue": "res://assets/sprites/rogue.png",
	"priest": "res://assets/sprites/priest.png",
	"goblin": "res://assets/sprites/goblin.png",
	"skeleton": "res://assets/sprites/skeleton.png",
	"merchant": "res://assets/sprites/merchant.png",
	"quest_giver": "res://assets/sprites/quest_giver.png",
	"innkeeper": "res://assets/sprites/innkeeper.png",
	"guard": "res://assets/sprites/guard.png",
	"blacksmith": "res://assets/sprites/blacksmith.png",
	"healer": "res://assets/sprites/healer.png",
	"beggar": "res://assets/sprites/beggar.png",
	"spy": "res://assets/sprites/spy.png",
	"sage": "res://assets/sprites/sage.png",
	"wolf": "res://assets/sprites/wolf.png",
	"orc": "res://assets/sprites/orc.png",
	"spider": "res://assets/sprites/spider.png",
	"bandit": "res://assets/sprites/bandit.png",
	"dragon": "res://assets/sprites/dragon.png",
	"zombie": "res://assets/sprites/zombie.png",
}

var tile_cache: Dictionary = {}
var sprite_cache: Dictionary = {}
var entity_nodes: Array[Node] = []
var entity_containers: Dictionary = {}  # entity_id → Control node
var camera_offset: Vector2 = Vector2.ZERO
var map_width: int = 0
var map_height: int = 0
var fog_overlay: ColorRect = null

signal entity_clicked(entity_id: String, entity_data: Dictionary)
signal tile_clicked(tile_x: int, tile_y: int)

var player_marker: ColorRect = null
var _marker_pulse: float = 0.0

func _ready() -> void:
	GameState.map_loaded.connect(_on_map_loaded)
	GameState.entities_loaded.connect(_on_entities_loaded)
	_create_player_marker()

func _process(delta: float) -> void:
	if player_marker and map_width > 0:
		var pos = GameState.player_map_pos
		player_marker.position = camera_offset + Vector2(
			pos.x * TILE_SIZE + TILE_SIZE * 0.25,
			pos.y * TILE_SIZE + TILE_SIZE * 0.25
		)
		# Pulsing effect
		_marker_pulse += delta * 4.0
		var alpha = 0.6 + sin(_marker_pulse) * 0.3
		player_marker.color = Color(0, 0.9, 1.0, alpha)

func _create_player_marker() -> void:
	player_marker = ColorRect.new()
	player_marker.size = Vector2(TILE_SIZE * 0.5, TILE_SIZE * 0.5)
	player_marker.color = Color(0, 0.9, 1.0, 0.8)
	player_marker.z_index = 100
	player_marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(player_marker)

func _on_map_loaded(map_data: Dictionary) -> void:
	_clear_map()
	map_width = map_data.get("width", 0)
	map_height = map_data.get("height", 0)
	var tiles = map_data.get("tiles", [])

	# Center the map in the panel
	var panel_size = size
	var map_pixel_w = map_width * TILE_SIZE
	var map_pixel_h = map_height * TILE_SIZE
	camera_offset = Vector2(
		max(0, (panel_size.x - map_pixel_w) / 2),
		max(0, (panel_size.y - map_pixel_h) / 2)
	)

	for y in range(tiles.size()):
		var row = tiles[y]
		for x in range(row.size()):
			var tile_type = row[x]
			_draw_tile(x, y, tile_type)

	queue_redraw()

func _on_entities_loaded(entities_data: Dictionary) -> void:
	_clear_entities()

	var all_entities = []
	for key in ["npcs", "items", "enemies"]:
		if entities_data.has(key):
			all_entities.append_array(entities_data[key])

	for entity in all_entities:
		_draw_entity(entity)

func _draw_tile(x: int, y: int, tile_type: String) -> void:
	var tex_path = TILE_TEXTURES.get(tile_type, "res://assets/tiles/stone_floor.png")
	var tex = _load_texture(tex_path)
	if tex == null:
		return

	var sprite = TextureRect.new()
	sprite.texture = tex
	sprite.position = camera_offset + Vector2(x * TILE_SIZE, y * TILE_SIZE)
	sprite.size = Vector2(TILE_SIZE, TILE_SIZE)
	sprite.stretch_mode = TextureRect.STRETCH_SCALE
	add_child(sprite)

func _draw_entity(entity: Dictionary) -> void:
	var pos = entity.get("position", [0, 0])
	var template = entity.get("template", "warrior")
	var entity_id = entity.get("id", "")
	var entity_name = entity.get("name", "Unknown")

	var tex_path = SPRITE_TEXTURES.get(template, "res://assets/sprites/warrior.png")
	var tex = _load_texture(tex_path)
	if tex == null:
		return

	# Entity container
	var container = Control.new()
	container.position = camera_offset + Vector2(pos[0] * TILE_SIZE, pos[1] * TILE_SIZE)
	container.size = Vector2(TILE_SIZE, TILE_SIZE)
	container.set_meta("entity_id", entity_id)
	container.set_meta("entity_data", entity)

	# Sprite
	var sprite = TextureRect.new()
	sprite.texture = tex
	sprite.size = Vector2(TILE_SIZE, TILE_SIZE)
	sprite.stretch_mode = TextureRect.STRETCH_SCALE
	container.add_child(sprite)

	# Name label (small, above sprite)
	var label = Label.new()
	label.text = entity_name
	label.position = Vector2(-10, -14)
	label.add_theme_font_size_override("font_size", 8)
	label.add_theme_color_override("font_color", Color(1, 1, 0.8))
	container.add_child(label)

	# Click detection
	var button = Button.new()
	button.flat = true
	button.size = Vector2(TILE_SIZE, TILE_SIZE)
	button.modulate = Color(1, 1, 1, 0)  # invisible
	button.pressed.connect(_on_entity_pressed.bind(entity_id, entity))
	container.add_child(button)

	# Start invisible — will fade in when DM mentions this entity
	container.modulate = Color(1, 1, 1, 0)

	add_child(container)
	entity_nodes.append(container)
	entity_containers[entity_id] = container

func reveal_entity(entity_id: String) -> void:
	"""Fade in an entity when the DM narrative mentions it."""
	if not entity_containers.has(entity_id):
		return
	var container = entity_containers[entity_id]
	if not is_instance_valid(container):
		return
	# Fade in tween
	var tween = create_tween()
	tween.tween_property(container, "modulate", Color(1, 1, 1, 1), 1.0)

func reveal_all() -> void:
	"""Reveal all entities immediately."""
	for eid in entity_containers:
		var container = entity_containers[eid]
		if is_instance_valid(container):
			container.modulate = Color(1, 1, 1, 1)

func _on_entity_pressed(entity_id: String, entity_data: Dictionary) -> void:
	entity_clicked.emit(entity_id, entity_data)

func _load_texture(path: String) -> Texture2D:
	if tile_cache.has(path):
		return tile_cache[path]
	if ResourceLoader.exists(path):
		var tex = load(path)
		tile_cache[path] = tex
		return tex
	return null

func _clear_map() -> void:
	for child in get_children():
		if child == player_marker:
			continue  # Don't delete the player marker
		child.queue_free()
	entity_nodes.clear()

func _clear_entities() -> void:
	for node in entity_nodes:
		if is_instance_valid(node):
			node.queue_free()
	entity_nodes.clear()

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			var local_pos = event.position - camera_offset
			var tx = int(local_pos.x / TILE_SIZE)
			var ty = int(local_pos.y / TILE_SIZE)
			if tx >= 0 and tx < map_width and ty >= 0 and ty < map_height:
				tile_clicked.emit(tx, ty)
