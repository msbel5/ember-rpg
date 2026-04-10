extends SceneTree

const GameStateScript = preload("res://autoloads/game_state.gd")
const BackendScript = preload("res://autoloads/backend.gd")
const RuntimeAutomationBridgeScript = preload("res://autoloads/runtime_automation_bridge.gd")

const BACKEND_HEALTH_PATH := "/game/health/campaign-client"
const TITLE_SCENE := "res://scenes/title_screen.tscn"
const TITLE_NEW_GAME_PATH := "TitleMenu/FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/NewGameButton"
const CREATION_ROOT_PATH := "CharacterCreation"
const NAME_INPUT_PATH := "CharacterCreation/VBox/CreationBody/FormPane/FormScroll/FormContent/IdentitySection/NameInput"
const FANTASY_CARD_PATH := "CharacterCreation/VBox/CreationBody/FormPane/FormScroll/FormContent/IdentitySection/GenreCards/FantasyCard"
const NEXT_BUTTON_PATH := "CharacterCreation/VBox/ButtonRow/NextButton"
const ANSWER_0_PATH := "CharacterCreation/VBox/CreationBody/FormPane/FormScroll/FormContent/QuestionSection/AnswerButtons/AnswerButton0"
const START_BUTTON_PATH := "CharacterCreation/VBox/ButtonRow/StartButton"
const CREATION_STEP_TIMEOUT := 6.0
const GAME_SESSION_TIMEOUT := 6.0

var failures: int = 0
var _first_frame_ms: int = -1
var _tick_index_at_second_two: int = -1


func _initialize() -> void:
	await _ensure_autoloads()
	await _run_acceptance()
	await _cleanup_runtime()
	if failures == 0:
		print("Vertical slice acceptance passed.")
	quit(failures)


func _ensure_autoloads() -> void:
	await _ensure_singleton("GameState", GameStateScript)
	await _ensure_singleton("Backend", BackendScript)
	await _ensure_singleton("RuntimeAutomationBridge", RuntimeAutomationBridgeScript)
	await _settle_frames(4)


func _ensure_singleton(node_name: String, script_resource: Script) -> Node:
	var existing = root.get_node_or_null(node_name)
	if existing != null:
		return existing
	var instance = script_resource.new()
	instance.name = node_name
	root.add_child(instance)
	await process_frame
	return instance


func _run_acceptance() -> void:
	await _load_title_screen()
	await _assert_backend_health_ready()
	await _wait_for_title_catalog_ready()
	await _ac01_open_creation_within_budget()
	await _complete_creation_flow()
	await _ac02_arrive_in_game_session()
	await _ac03_and_ac04_verify_spawn_frame()
	await _ac05_toggle_tactical_pause()
	await _ac06_verify_tick_advances_after_resume()


func _load_title_screen() -> void:
	_game_state().reset()
	_backend().close_runtime_socket("vertical_slice_acceptance")
	var error = change_scene_to_file(TITLE_SCENE)
	_assert_true(error == OK, "Title screen scene loads for the acceptance run")
	await _settle_frames(8)


func _assert_backend_health_ready() -> void:
	var response = await _http_get_json("%s%s" % [_backend().get_base_url(), BACKEND_HEALTH_PATH])
	_assert_true(bool(response.get("ok", false)), "Campaign backend health endpoint responds during acceptance")
	_assert_true(bool(response.get("websocket_transport", false)), "Campaign backend reports websocket transport ready")


func _wait_for_title_catalog_ready() -> void:
	var ready = await _wait_until(func() -> bool:
		var scene = current_scene
		if scene == null:
			return false
		var catalog = scene.get("_catalog")
		return catalog is Dictionary and not catalog.is_empty()
	, 6.0)
	_assert_true(ready, "Title screen loads the creation catalog before New Game is measured")


func _ac01_open_creation_within_budget() -> void:
	var started_ms = Time.get_ticks_msec()
	var result = await _bridge().execute_command({
		"action": "activate_node",
		"node_path": TITLE_NEW_GAME_PATH,
	})
	_assert_true(str(result.get("status", "")) == "ok", "Automation bridge activates New Game on the title screen")
	var visible = await _wait_until(func() -> bool:
		var state = await _bridge().execute_command({
			"action": "query_state",
			"node_path": CREATION_ROOT_PATH,
		})
		return bool(state.get("node_visible", false))
	, 0.5)
	var elapsed_ms = Time.get_ticks_msec() - started_ms
	_assert_true(visible, "Creation wizard becomes visible after activating New Game")
	_assert_true(elapsed_ms <= 500, "Creation wizard opens within 500ms once backend and catalog are ready")


func _complete_creation_flow() -> void:
	await _bridge().execute_command({
		"action": "set_text_node",
		"node_path": NAME_INPUT_PATH,
		"text": "GatePilot",
	})
	await _bridge().execute_command({
		"action": "activate_node",
		"node_path": FANTASY_CARD_PATH,
	})
	await _bridge().execute_command({
		"action": "activate_node",
		"node_path": NEXT_BUTTON_PATH,
	})
	var question_ready = await _wait_until(func() -> bool:
		var state = await _bridge().execute_command({
			"action": "query_state",
			"node_path": ANSWER_0_PATH,
		})
		return bool(state.get("node_visible", false))
	, CREATION_STEP_TIMEOUT)
	_assert_true(question_ready, "Creation questionnaire appears after identity confirmation")

	for _i in range(5):
		await _bridge().execute_command({
			"action": "activate_node",
			"node_path": ANSWER_0_PATH,
		})
		await _settle_frames(10)

	var history_visible = await _wait_until(func() -> bool:
		var wizard = _creation_wizard()
		return wizard != null and int(wizard.current_step()) == int(wizard.STEP_HISTORY)
	, CREATION_STEP_TIMEOUT)
	_assert_true(history_visible, "Creation flow reaches the history reveal after the final question")

	await _bridge().execute_command({"action": "activate_node", "node_path": NEXT_BUTTON_PATH})
	await _bridge().execute_command({"action": "activate_node", "node_path": NEXT_BUTTON_PATH})
	await _settle_frames(6)
	var roll_visible = await _wait_until(func() -> bool:
		var wizard = _creation_wizard()
		return wizard != null and int(wizard.current_step()) == int(wizard.STEP_ROLL)
	, CREATION_STEP_TIMEOUT)
	_assert_true(roll_visible, "Creation flow advances from history to the roll step")

	await _bridge().execute_command({"action": "activate_node", "node_path": NEXT_BUTTON_PATH})
	await _settle_frames(6)
	var build_visible = await _wait_until(func() -> bool:
		var wizard = _creation_wizard()
		return wizard != null and int(wizard.current_step()) == int(wizard.STEP_BUILD)
	, CREATION_STEP_TIMEOUT)
	_assert_true(build_visible, "Creation flow advances from roll to the build step")

	await _bridge().execute_command({"action": "activate_node", "node_path": NEXT_BUTTON_PATH})
	await _settle_frames(6)
	var dossier_visible = await _wait_until(func() -> bool:
		var state = await _bridge().execute_command({
			"action": "query_state",
			"node_path": START_BUTTON_PATH,
		})
		return bool(state.get("node_visible", false))
	, CREATION_STEP_TIMEOUT)
	_assert_true(dossier_visible, "Creation flow reaches the dossier step before finalize")

	await _bridge().execute_command({"action": "activate_node", "node_path": START_BUTTON_PATH})
	await _settle_frames(6)


func _ac02_arrive_in_game_session() -> void:
	var changed = await _wait_until(func() -> bool:
		return current_scene != null and current_scene.name == "GameSession" and not String(_game_state().campaign_id).strip_edges().is_empty()
	, GAME_SESSION_TIMEOUT)
	_assert_true(changed, "Finalize creation transitions to GameSession with a live campaign id")
	_first_frame_ms = Time.get_ticks_msec()


func _ac03_and_ac04_verify_spawn_frame() -> void:
	await _sleep_until_first_frame_offset(2.0)
	var runtime_state = await _bridge().execute_command({"action": "query_runtime_state"})
	_tick_index_at_second_two = int(runtime_state.get("tick_index", -1))
	_assert_true(bool(runtime_state.get("spawn_frame_verified", false)), "Runtime probe verifies the first-frame spawn baseline")
	_assert_true((runtime_state.get("spawn_frame_missing", []) as Array).is_empty(), "Runtime probe reports no missing first-frame spawn requirements")
	_assert_true(_has_nearby_named_npc(runtime_state), "Spawn frame contains a nearby named NPC within 8 tiles")
	_assert_true(_has_nearby_service_or_furniture(runtime_state), "Spawn frame contains nearby furniture or a service NPC within 8 tiles")


func _ac05_toggle_tactical_pause() -> void:
	var before = await _bridge().execute_command({"action": "query_runtime_state"})
	_assert_true(str(before.get("shell_mode", "")) == "exploration", "Game session begins in exploration shell mode before pause")
	var result = await _bridge().execute_command({
		"action": "key_press",
		"key": "space",
	})
	_assert_true(str(result.get("status", "")) == "ok", "Automation bridge sends Space to the game session viewport")
	var paused = await _wait_until(func() -> bool:
		var state = await _bridge().execute_command({"action": "query_runtime_state"})
		return str(state.get("shell_mode", "")) == "tactical_pause"
	, 1.0)
	_assert_true(paused, "Space toggles the shell into tactical pause within one second")

	# Resume immediately so the no-input tick window can still prove ambient flow.
	await _bridge().execute_command({"action": "key_press", "key": "space"})
	var resumed = await _wait_until(func() -> bool:
		var state = await _bridge().execute_command({"action": "query_runtime_state"})
		return str(state.get("shell_mode", "")) == "exploration"
	, 1.0)
	_assert_true(resumed, "A second Space press resumes exploration so the live tick can advance")


func _ac06_verify_tick_advances_after_resume() -> void:
	await _sleep_until_first_frame_offset(12.2)
	var runtime_state = await _bridge().execute_command({"action": "query_runtime_state"})
	var later_tick = int(runtime_state.get("tick_index", -1))
	if later_tick <= _tick_index_at_second_two:
		push_warning("[ACCEPTANCE] tick loop stalled")
	_assert_true(later_tick > _tick_index_at_second_two, "Tick index advances after the world idles without further automation input")


func _creation_wizard():
	if current_scene == null:
		return null
	return current_scene.get_node_or_null(CREATION_ROOT_PATH)


func _game_state() -> Node:
	return root.get_node_or_null("GameState")


func _backend() -> Node:
	return root.get_node_or_null("Backend")


func _bridge() -> Node:
	return root.get_node_or_null("RuntimeAutomationBridge")


func _has_nearby_named_npc(runtime_state: Dictionary) -> bool:
	var player_tile = runtime_state.get("player_tile", [])
	if not (player_tile is Array) or player_tile.size() < 2:
		return false
	var player = Vector2i(int(player_tile[0]), int(player_tile[1]))
	for entity in runtime_state.get("entities", []):
		if not (entity is Dictionary):
			continue
		if str(entity.get("bucket", "")) != "npcs":
			continue
		if str(entity.get("name", "")).strip_edges().is_empty():
			continue
		if _within_radius(player, entity.get("position", [])):
			return true
	return false


func _has_nearby_service_or_furniture(runtime_state: Dictionary) -> bool:
	var player_tile = runtime_state.get("player_tile", [])
	if not (player_tile is Array) or player_tile.size() < 2:
		return false
	var player = Vector2i(int(player_tile[0]), int(player_tile[1]))
	for entity in runtime_state.get("entities", []):
		if not (entity is Dictionary):
			continue
		if not _within_radius(player, entity.get("position", [])):
			continue
		if str(entity.get("bucket", "")) == "furniture":
			return true
		if str(entity.get("bucket", "")) == "npcs":
			var combined = ("%s %s" % [str(entity.get("name", "")), str(entity.get("role", ""))]).to_lower()
			for token in ["merchant", "shop", "inn", "smith", "trader", "vendor", "barkeep", "keeper"]:
				if combined.contains(token):
					return true
	return false


func _within_radius(player: Vector2i, position) -> bool:
	if not (position is Array) or position.size() < 2:
		return false
	var target = Vector2i(int(position[0]), int(position[1]))
	return maxi(absi(target.x - player.x), absi(target.y - player.y)) <= 8


func _sleep_until_first_frame_offset(seconds: float) -> void:
	if _first_frame_ms < 0:
		return
	var deadline_ms = _first_frame_ms + int(seconds * 1000.0)
	var remaining_ms = deadline_ms - Time.get_ticks_msec()
	if remaining_ms > 0:
		await create_timer(float(remaining_ms) / 1000.0).timeout


func _wait_until(predicate: Callable, timeout_seconds: float) -> bool:
	var deadline = Time.get_ticks_msec() + int(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() <= deadline:
		if await predicate.call():
			return true
		await _settle_frames(2)
	return false


func _settle_frames(frame_count: int) -> void:
	for _i in range(maxi(frame_count, 1)):
		await process_frame


func _http_get_json(url: String) -> Dictionary:
	var http := HTTPRequest.new()
	root.add_child(http)
	var err = http.request(url)
	if err != OK:
		http.queue_free()
		return {}
	var result = await http.request_completed
	http.queue_free()
	if int(result[1]) >= 400:
		return {}
	var parsed = JSON.parse_string((result[3] as PackedByteArray).get_string_from_utf8())
	return parsed if parsed is Dictionary else {}


func _cleanup_runtime() -> void:
	if current_scene != null:
		current_scene.queue_free()
		await _settle_frames(2)
	if _backend() != null:
		_backend().close_runtime_socket("vertical_slice_acceptance_complete")
		if _backend().has_method("test_cleanup"):
			_backend().test_cleanup()
	if root.get_node_or_null("BackendRuntime") != null and root.get_node("BackendRuntime").has_method("test_cleanup"):
		root.get_node("BackendRuntime").test_cleanup()
	if _bridge() != null and _bridge().has_method("test_cleanup"):
		_bridge().test_cleanup()
	await _settle_frames(2)


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)