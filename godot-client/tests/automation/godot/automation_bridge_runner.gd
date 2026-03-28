extends SceneTree

const AutomationBridge = preload("res://tests/automation/godot/automation_bridge.gd")
const AutomationState = preload("res://tests/automation/godot/automation_state.gd")

var bridge
var state


func _initialize() -> void:
	state = _parse_state(OS.get_cmdline_user_args())
	bridge = AutomationBridge.new()
	root.add_child(bridge)
	await process_frame
	await bridge.configure(state)
	if state.quit_requested:
		quit(1)
		return
	while not state.quit_requested:
		await bridge.poll_once()
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
	automation_state.command_file = str(parsed.get("command-file", "user://automation/command.json"))
	automation_state.result_file = str(parsed.get("result-file", "user://automation/result.json"))
	automation_state.status_file = str(parsed.get("status-file", "user://automation/status.json"))
	automation_state.artifact_root = str(parsed.get("artifact-root", "user://automation"))
	return automation_state
