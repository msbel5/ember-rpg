extends SceneTree

const BackendProbe = preload("res://tests/doubles/backend_probe.gd")
const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")

var failures: int = 0


func _initialize() -> void:
	await _run_tests()
	if failures == 0:
		print("All Godot headless tests passed.")
	quit(failures)


func _run_tests() -> void:
	_test_backend_routes()
	_test_game_state_normalization()
	await _test_scene_instantiation()
	_test_asset_bootstrap()
	await _cleanup_test_nodes()


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)


func _game_state() -> Node:
	return root.get_node_or_null("GameState")


func _test_backend_routes() -> void:
	var probe = BackendProbe.new()
	var noop := func(_data = null) -> void:
		pass

	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available")
	if game_state == null:
		return
	game_state.reset()
	game_state.player = {"name": "Chaos"}

	probe.load_game("slot_a", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/session/load/slot_a", "load_game uses session load route")

	probe.list_saves(noop)
	_assert_true(probe.last_request.get("path", "") == "/game/saves/Chaos", "list_saves uses player-scoped route")

	probe.get_inventory("session_1", noop)
	_assert_true(probe.last_request.get("path", "") == "/game/session/session_1/inventory", "get_inventory uses inventory route")

	probe.save_game("session_1", noop, "campfire", "Chaos")
	var save_body = JSON.parse_string(str(probe.last_request.get("body", "{}")))
	_assert_true(probe.last_request.get("path", "") == "/game/session/session_1/save", "save_game uses session save route")
	_assert_true(save_body is Dictionary and save_body.get("player_id", "") == "Chaos", "save_game sends player_id")
	_assert_true(save_body is Dictionary and save_body.get("slot_name", "") == "campfire", "save_game sends optional slot_name")
	probe.free()


func _test_game_state_normalization() -> void:
	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available for normalization")
	if game_state == null:
		return
	game_state.reset()
	game_state.update_from_response({
		"scene": "combat",
		"combat": {
			"round": 2,
			"active": "Chaos",
			"ended": false,
			"combatants": [],
		},
		"player": {
			"name": "Chaos",
			"position": [7, 8],
			"facing": "east",
			"gold": 12,
			"inventory": [{"id": "bread", "name": "Bread"}],
		},
		"map": {
			"width": 48,
			"height": 48,
			"spawn_point": [5, 5],
		},
		"world_entities": [
			{"id": "guard_1", "entity_type": "npc", "name": "Guard", "position": [2, 3], "disposition": "friendly"},
			{"id": "rat_1", "entity_type": "creature", "name": "Rat", "position": [4, 5], "disposition": "hostile"},
			{"id": "bread_1", "entity_type": "item", "name": "Bread", "position": [6, 7]},
		],
		"ground_items": [{"id": "bread_1", "entity_type": "item"}],
		"active_quests": [{"quest_id": "q1"}],
		"quest_offers": [{"id": "offer_1"}],
	})

	_assert_true(game_state.is_in_combat(), "GameState normalizes combat payload from action response")
	_assert_true(game_state.combat_state.get("round", 0) == 2, "combat_state preserves round")
	_assert_true(game_state.player_map_pos == Vector2i(7, 8), "player position is sourced from backend")
	_assert_true(game_state.player_facing == 1, "player facing is normalized from string")
	_assert_true(int(game_state.map_data.get("width", 0)) == 48, "map payload is normalized into map_data")
	_assert_true(game_state.entities.get("npcs", []).size() == 1, "friendly world entities group as npcs")
	_assert_true(game_state.entities.get("enemies", []).size() == 1, "hostile world entities group as enemies")
	_assert_true(game_state.entities.get("items", []).size() == 1, "item world entities group as items")
	_assert_true(game_state.ground_items.size() == 1, "ground items are retained")
	_assert_true(game_state.active_quests.size() == 1 and game_state.quest_offers.size() == 1, "quest payloads are retained")


func _test_scene_instantiation() -> void:
	var game_state = _game_state()
	_assert_true(game_state != null, "GameState autoload is available for scenes")
	if game_state == null:
		return
	game_state.reset()

	var title_scene = load("res://scenes/title_screen.tscn")
	_assert_true(title_scene != null, "TitleScreen scene loads")
	if title_scene != null:
		var title_instance = title_scene.instantiate()
		root.add_child(title_instance)
		await process_frame
		_assert_true(is_instance_valid(title_instance), "TitleScreen instantiates")
		title_instance.free()
		await process_frame

	var session_scene = load("res://scenes/game_session.tscn")
	_assert_true(session_scene != null, "GameSession scene loads")
	if session_scene != null:
		var session_instance = session_scene.instantiate()
		root.add_child(session_instance)
		await process_frame
		_assert_true(is_instance_valid(session_instance), "GameSession instantiates without session bootstrap")
		session_instance.free()
		await process_frame


func _test_asset_bootstrap() -> void:
	var expected = OS.get_environment("HF_TOKEN").strip_edges()
	if expected.is_empty():
		expected = OS.get_environment("HUGGINGFACE_API_KEY").strip_edges()
	_assert_true(AssetBootstrap.resolve_hf_token() == expected, "AssetBootstrap resolves HF token with fallback")


func _cleanup_test_nodes() -> void:
	for child in root.get_children():
		if child.name in ["GameState", "Backend"]:
			continue
		child.free()
	await process_frame
