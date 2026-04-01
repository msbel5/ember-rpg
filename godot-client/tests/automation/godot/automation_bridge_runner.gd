extends SceneTree

const AutomationBridge = preload("res://tests/automation/godot/automation_bridge.gd")
const AutomationState = preload("res://tests/automation/godot/automation_state.gd")

var bridge
var state


func _initialize() -> void:
	state = _parse_state(OS.get_cmdline_user_args())
	_write_bootstrap_status("booting", "Automation bridge runner parsed startup arguments.")
	await _start_bridge()


func _start_bridge() -> void:
	bridge = AutomationBridge.new()
	root.add_child(bridge)
	await process_frame
	_write_bootstrap_status("configuring", "Bridge node attached. Beginning scene configuration.")
	await bridge.configure(state)
	if state.quit_requested:
		quit(1)
		return
	var _last_time = Time.get_ticks_msec()
	while not state.quit_requested:
		await bridge.poll_once()
		var now = Time.get_ticks_msec()
		var delta = (now - _last_time) / 1000.0
		_last_time = now
		bridge.tick_recording(delta)
		await process_frame
	quit(0)


func _parse_state(args: PackedStringArray):
	var parsed := {}
	var index := 0
	while index < args.size():
		var key = args[index]
		if key.begins_with("--") and index + 1 < args.size():
			parsed[key.trim_prefix("--")] = args[index + 1]
			index += 2
		else:
			index += 1

	var automation_state = AutomationState.new()
	automation_state.initial_scene = str(parsed.get("scene", "res://scenes/title_screen.tscn"))
	automation_state.command_file = _normalize_fs_path(str(parsed.get("command-file", "user://automation/command.json")))
	automation_state.result_file = _normalize_fs_path(str(parsed.get("result-file", "user://automation/result.json")))
	automation_state.status_file = _normalize_fs_path(str(parsed.get("status-file", "user://automation/status.json")))
	automation_state.artifact_root = _normalize_fs_path(str(parsed.get("artifact-root", "user://automation")))
	return automation_state


func _normalize_fs_path(value: String) -> String:
	return value.replace("\\", "/")


func _write_bootstrap_status(status: String, message: String) -> void:
	var path = str(state.status_file if state != null else "user://automation/status.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify({
		"ready": false,
		"status": status,
		"message": message,
		"status_file": path,
	}))
	file.close()
