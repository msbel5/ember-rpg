extends TileMapLayer

const TileCatalog = preload("res://scripts/world/tile_catalog.gd")

var _source_id: int = 0
var _atlas: Dictionary = {}
var _map_size: Vector2i = Vector2i.ZERO


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_ensure_tileset()


func render_map(map_payload: Dictionary) -> void:
	_ensure_tileset()
	clear()
	modulate = TileCatalog.adapter_world_tint(_current_adapter_id())

	var payload = map_payload
	if payload.is_empty() or not payload.has("tiles"):
		payload = TileCatalog.build_placeholder_map()

	var rows = payload.get("tiles", [])
	_map_size = Vector2i(int(payload.get("width", 0)), int(payload.get("height", 0)))
	for y in range(rows.size()):
		var row = rows[y]
		if not (row is Array):
			continue
		for x in range(row.size()):
			var tile_name = TileCatalog.resolve_tile_name(row[x])
			var render_tile_name = TileCatalog.render_tile_name(tile_name, Vector2i(x, y), rows)
			var atlas_options = _atlas.get(render_tile_name, _atlas.get(tile_name, _atlas.get("grass", [Vector2i.ZERO])))
			var atlas_coords = atlas_options[TileCatalog.variant_index_for_position(render_tile_name, Vector2i(x, y)) % atlas_options.size()]
			set_cell(Vector2i(x, y), _source_id, atlas_coords)


func get_map_size() -> Vector2i:
	return _map_size


func _ensure_tileset() -> void:
	if tile_set != null and not _atlas.is_empty():
		return

	var built = TileCatalog.build_tileset()
	tile_set = built["tile_set"]
	_source_id = int(built["source_id"])
	_atlas = built["atlas"]


func _current_adapter_id() -> String:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		var game_state = loop.root.get_node_or_null("GameState")
		if game_state != null:
			return str(game_state.adapter_id)
	return "fantasy_ember"
