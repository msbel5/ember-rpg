extends SceneTree

const AutomationBridge = preload("res://tests/automation/godot/automation_bridge.gd")
const AutomationState = preload("res://tests/automation/godot/automation_state.gd")

var failures: int = 0
var bridge
var state


func _initialize() -> void:
	await _run_tests()
	if failures == 0:
		print("All automation bridge tests passed.")
	quit(failures)


func _run_tests() -> void:
	await _setup_bridge()
	await _test_mouse_input()
	await _test_keyboard_input()
	await _test_text_input()
	await _test_viewport_capture()
	await _test_playback_steps()
	await _cleanup()


func _setup_bridge() -> void:
	var base_dir = ProjectSettings.globalize_path("user://automation_bridge_test")
	DirAccess.make_dir_recursive_absolute(base_dir)
	state = AutomationState.new()
	state.initial_scene = "res://tests/automation/godot/input_probe.tscn"
	state.command_file = base_dir.path_join("command.json")
	state.result_file = base_dir.path_join("result.json")
	state.status_file = base_dir.path_join("status.json")
	state.artifact_root = base_dir.path_join("artifacts")
	bridge = AutomationBridge.new()
	root.add_child(bridge)
	await process_frame
	await bridge.configure(state)
	var status = _read_json(state.status_file)
	_assert_true(bool(status.get("ready", false)), "automation bridge writes ready status")


func _test_mouse_input() -> void:
	_write_json(state.command_file, {"seq": 1, "action": "mouse_move", "x": 120, "y": 140})
	await bridge.poll_once()
	var probe = bridge.current_scene_root
	_assert_true(probe.mouse_move_count >= 1, "automation bridge forwards mouse_move input")
	_assert_true(state.cursor_position == Vector2i(120, 140), "automation bridge stores logical cursor position")

	_write_json(state.command_file, {"seq": 2, "action": "mouse_click", "x": 180, "y": 200, "button": "left"})
	await bridge.poll_once()
	_assert_true(probe.mouse_down_count >= 1 and probe.mouse_up_count >= 1, "automation bridge forwards mouse_click input")


func _test_keyboard_input() -> void:
	var probe = bridge.current_scene_root
	_write_json(state.command_file, {"seq": 3, "action": "key_down", "key": "a"})
	await bridge.poll_once()
	_assert_true(probe.last_key_down == "a", "automation bridge forwards key_down input")

	_write_json(state.command_file, {"seq": 4, "action": "key_up", "key": "a"})
	await bridge.poll_once()
	_assert_true(probe.last_key_up == "a", "automation bridge forwards key_up input")

	_write_json(state.command_file, {"seq": 5, "action": "key_hold", "key": "space", "duration_ms": 10})
	await bridge.poll_once()
	_assert_true(probe.key_down_count >= 2 and probe.key_up_count >= 2, "automation bridge forwards key_hold input")


func _test_text_input() -> void:
	var probe = bridge.current_scene_root
	probe.get_node("Margin/VBox/InputField").text = ""
	_write_json(state.command_file, {"seq": 6, "action": "text", "text": "Chaos"})
	await bridge.poll_once()
	_assert_true(probe.get_node("Margin/VBox/InputField").text == "Chaos", "automation bridge forwards text input")


func _test_viewport_capture() -> void:
	_write_json(state.command_file, {"seq": 7, "action": "capture_viewport", "tag": "probe"})
	await bridge.poll_once()
	var result = _read_json(state.result_file)
	var capture_path = str(result.get("path", ""))
	_assert_true(result.get("status", "") == "ok", "automation bridge reports viewport capture success")
	_assert_true(not capture_path.is_empty() and FileAccess.file_exists(capture_path), "automation bridge writes viewport capture artifacts")


func _test_playback_steps() -> void:
	var results = await bridge.playback_steps([
		{"action": "mouse_move", "x": 10, "y": 10},
		{"action": "capture_viewport", "tag": "playback"},
	])
	_assert_true(results.size() == 2, "automation bridge replays step arrays")
	_assert_true(str(results[1].get("status", "")) == "ok", "automation bridge playback returns per-step results")


func _cleanup() -> void:
	if bridge != null:
		bridge.queue_free()
	await process_frame


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)


func _write_json(path: String, payload: Dictionary) -> void:
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(payload))
	file.close()


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text = FileAccess.get_file_as_string(path)
	var parsed = JSON.parse_string(text)
	if parsed is Dictionary:
		return parsed
	return {}
