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
			var atlas_coords = _atlas.get(tile_name, _atlas.get("grass", Vector2i.ZERO))
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
