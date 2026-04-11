extends SceneTree

const GameStateScript = preload("res://autoloads/game_state.gd")
const MinimapPanelScene = preload("res://scenes/components/minimap_panel.tscn")

var failures: int = 0
var _game_state
var _minimap


func _initialize() -> void:
	await _setup()
	await _test_active_travel_controls_render_from_travel_state()
	await _test_arrival_promotes_destination_region_without_explicit_selected_node()
	await _cleanup()
	if failures == 0:
		print("Frontend travel region transition tests passed.")
	quit(failures)


func _setup() -> void:
	_game_state = root.get_node_or_null("GameState")
	if _game_state == null:
		_game_state = GameStateScript.new()
		_game_state.name = "GameState"
		root.add_child(_game_state)
	await process_frame
	_game_state.reset()
	_game_state.update_from_response({
		"world_graph": {
			"active_region_id": "region_001",
			"dimensions": {"columns": 8, "rows": 6},
			"regions": [
				{"id": "region_001", "grid_position": [1, 0], "biome_id": "plains", "settlement_node_id": "node_region_001_00"},
				{"id": "region_006", "grid_position": [2, 1], "biome_id": "coast", "settlement_node_id": "node_region_006_01"},
			],
			"nodes": [
				{"id": "node_region_001_00", "region_id": "region_001", "name": "Dragon Eyrie", "grid_position": [1, 0], "biome_id": "plains"},
				{"id": "node_region_006_01", "region_id": "region_006", "name": "Harbor Reach", "grid_position": [2, 1], "biome_id": "coast"},
			],
			"edges": [
				{"id": "edge_0", "from_settlement_id": "node_region_001_00", "to_settlement_id": "node_region_006_01", "from_region_id": "region_001", "to_region_id": "region_006", "travel_hours": 4},
			],
		},
		"travel_options": [
			{"route_id": "edge_0", "destination_region_id": "region_006", "destination_settlement_id": "node_region_006_01", "destination_name": "Harbor Reach", "travel_hours": 4},
		],
		"current_region_summary": {"region_id": "region_001", "settlement_node_id": "node_region_001_00"},
	})
	_minimap = MinimapPanelScene.instantiate()
	root.add_child(_minimap)
	await process_frame


func _test_active_travel_controls_render_from_travel_state() -> void:
	_game_state.update_from_response({
		"travel_state": {
			"status": "traveling",
			"route_id": "edge_0",
			"origin_region_id": "region_001",
			"destination_region_id": "region_006",
			"destination_settlement_id": "node_region_006_01",
			"destination_name": "Harbor Reach",
			"travel_hours_total": 4,
			"travel_hours_remaining": 2,
			"danger_level": 1,
			"encounter_triggered": false,
			"paused_for_encounter": false,
			"encounter_resolved": true,
			"can_advance": true,
			"requires_resolution": false,
		},
	})
	await process_frame
	_assert_true(_minimap.routes_list.has_node("ContinueTravelButton"), "Minimap shows continue-travel controls while travel is active")
	_assert_true(_minimap.summary_label.text.contains("Traveling to Harbor Reach"), "Minimap summary reflects the active travel destination")
	_assert_true(_minimap.intel_text.text.contains("Route is clear to continue"), "Minimap intel reflects travel_state.can_advance truth")


func _test_arrival_promotes_destination_region_without_explicit_selected_node() -> void:
	_game_state.update_from_response({
		"travel_state": {},
		"world_graph": {
			"active_region_id": "region_006",
			"dimensions": {"columns": 8, "rows": 6},
			"regions": [
				{"id": "region_001", "grid_position": [1, 0], "biome_id": "plains", "settlement_node_id": "node_region_001_00"},
				{"id": "region_006", "grid_position": [2, 1], "biome_id": "coast", "settlement_node_id": "node_region_006_01"},
			],
			"nodes": [
				{"id": "node_region_001_00", "region_id": "region_001", "name": "Dragon Eyrie", "grid_position": [1, 0], "biome_id": "plains"},
				{"id": "node_region_006_01", "region_id": "region_006", "name": "Harbor Reach", "grid_position": [2, 1], "biome_id": "coast"},
			],
			"edges": [
				{"id": "edge_0", "from_settlement_id": "node_region_001_00", "to_settlement_id": "node_region_006_01", "from_region_id": "region_001", "to_region_id": "region_006", "travel_hours": 4},
			],
		},
		"travel_options": [
			{"route_id": "edge_0", "destination_region_id": "region_001", "destination_settlement_id": "node_region_001_00", "destination_name": "Dragon Eyrie", "travel_hours": 4},
		],
		"current_region_summary": {"region_id": "region_006", "settlement_node_id": "node_region_006_01"},
	})
	await process_frame
	_assert_true(not _minimap.routes_list.has_node("ContinueTravelButton"), "Minimap clears active travel controls after arrival")
	_assert_true(_minimap.summary_label.text.contains("Harbor Reach") and _minimap.summary_label.text.contains("region_006"), "Minimap promotes the destination region as the active world graph node after arrival")
	_assert_true(_minimap.intel_text.text.contains("Dragon Eyrie") and not _minimap.intel_text.text.contains("Route is clear to continue"), "Minimap rehydrates destination travel intel instead of stale in-transit state after arrival")
	_assert_true(_game_state.selected_world_node == "node_region_006_01", "GameState derives the destination selected_world_node from current_region_summary when none is provided")


func _cleanup() -> void:
	if _minimap != null:
		_minimap.queue_free()
	await process_frame


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)
