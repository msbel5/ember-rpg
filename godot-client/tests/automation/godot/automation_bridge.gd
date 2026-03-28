extends Node

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")
const AutomationState = preload("res://tests/automation/godot/automation_state.gd")

const KEY_NAME_MAP := {
	"enter": KEY_ENTER,
	"tab": KEY_TAB,
	"escape": KEY_ESCAPE,
	"esc": KEY_ESCAPE,
	"space": KEY_SPACE,
	"left": KEY_LEFT,
	"up": KEY_UP,
	"right": KEY_RIGHT,
	"down": KEY_DOWN,
	"home": KEY_HOME,
	"f5": KEY_F5,
	"f9": KEY_F9,
	"f12": KEY_F12,
}

var state: RefCounted
var current_scene_root: Node
var playback_viewport: SubViewport
var _recording: bool = false
var _record_folder: String = ""
var _record_frame_index: int = 0
var _record_interval: float = 0.5
var _record_timer: float = 0.0


func configure(new_state: RefCounted) -> void:
	state = new_state
	await _ensure_playback_viewport()
	await _load_scene(state.initial_scene)
	_write_json(state.status_file, state.status_payload({"status": "ok"}))


func poll_once() -> void:
	if state == null:
		return
	if state.command_file.is_empty() or not FileAccess.file_exists(state.command_file):
		return

	var payload = _read_json(state.command_file)
	if payload.is_empty():
		return

	var seq = int(payload.get("seq", -1))
	if seq <= state.last_seq:
		return
	state.last_seq = seq

	var result = await _dispatch_command(payload)
	result["seq"] = seq
	_write_json(state.result_file, result)


func tick_recording(delta: float) -> void:
	if not _recording or playback_viewport == null:
		return
	_record_timer += delta
	if _record_timer < _record_interval:
		return
	_record_timer = 0.0
	var image = playback_viewport.get_texture().get_image()
	if image != null and image.get_width() > 0:
		var frame_name = "frame_%04d" % _record_frame_index
		ScreenshotCapture.capture_image(image, _record_folder, frame_name)
		_record_frame_index += 1


func playback_steps(steps: Array) -> Array:
	var results: Array = []
	for entry in steps:
		if entry is Dictionary:
			var result = await _dispatch_command(entry)
			results.append(result)
	return results


func _load_scene(scene_path: String) -> void:
	if current_scene_root != null and is_instance_valid(current_scene_root):
		current_scene_root.queue_free()
		await get_tree().process_frame

	var packed = load(scene_path)
	if packed == null:
		push_error("Automation bridge could not load scene: %s" % scene_path)
		_write_json(state.status_file, state.status_payload({"status": "error", "message": "Failed to load scene %s" % scene_path}))
		state.quit_requested = true
		return

	current_scene_root = packed.instantiate()
	playback_viewport.add_child(current_scene_root)
	await _settle_frames(3)


func _dispatch_command(command: Dictionary) -> Dictionary:
	var action = str(command.get("action", "")).strip_edges()
	match action:
		"activate_window":
			return {"status": "gap", "message": "Headless bridge has no desktop window to activate."}
		"mouse_move":
			_dispatch_mouse_move(Vector2(command.get("x", 0), command.get("y", 0)))
		"mouse_down":
			_dispatch_mouse_button(str(command.get("button", "left")), true)
		"mouse_up":
			_dispatch_mouse_button(str(command.get("button", "left")), false)
		"mouse_click":
			var click_position = Vector2(command.get("x", 0), command.get("y", 0))
			_dispatch_mouse_move(click_position)
			_dispatch_mouse_button(str(command.get("button", "left")), true)
			_dispatch_mouse_button(str(command.get("button", "left")), false)
		"key_down":
			_dispatch_key(str(command.get("key", "")), true)
		"key_up":
			_dispatch_key(str(command.get("key", "")), false)
		"key_press":
			_dispatch_key(str(command.get("key", "")), true)
			_dispatch_key(str(command.get("key", "")), false)
		"key_hold":
			_dispatch_key(str(command.get("key", "")), true)
			await get_tree().create_timer(float(command.get("duration_ms", 0)) / 1000.0).timeout
			_dispatch_key(str(command.get("key", "")), false)
		"text":
			_dispatch_text(str(command.get("text", "")))
		"capture_viewport":
			var tag = str(command.get("tag", "automation_capture")).strip_edges()
			var capture_result = _capture_viewport_with_fallback(tag)
			var capture_path = str(capture_result.get("path", ""))
			if capture_path.is_empty():
				return {"status": "error", "message": "Viewport capture failed."}
			return {
				"status": "ok",
				"path": capture_path,
				"synthetic": bool(capture_result.get("synthetic", false)),
			}
		"record_start":
			_record_folder = str(command.get("folder", "recording")).strip_edges()
			_record_interval = float(command.get("interval", 0.5))
			_record_frame_index = 0
			_record_timer = 0.0
			_recording = true
			DirAccess.make_dir_recursive_absolute("user://screenshots/%s" % _record_folder)
			return {"status": "ok", "message": "Recording started to %s at %.1fs intervals" % [_record_folder, _record_interval]}
		"record_stop":
			_recording = false
			return {"status": "ok", "frame_count": _record_frame_index, "folder": _record_folder}
		"close":
			_recording = false
			state.quit_requested = true
		_:
			return {"status": "error", "message": "Unsupported automation action %s" % action}

	await _settle_frames(2)
	return {"status": "ok"}


func _dispatch_mouse_move(position: Vector2) -> void:
	state.cursor_position = Vector2i(position)
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	_push_input(event)


func _dispatch_mouse_button(button_name: String, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	var button_index = _button_index_for_name(button_name)
	var position = Vector2(state.cursor_position)
	event.position = position
	event.global_position = position
	event.button_index = button_index
	event.pressed = pressed
	_push_input(event)


func _dispatch_key(key_name: String, pressed: bool) -> void:
	var event := InputEventKey.new()
	var keycode = _keycode_for_name(key_name)
	event.keycode = keycode
	event.physical_keycode = keycode
	event.unicode = keycode if keycode < 128 else 0
	event.pressed = pressed
	_push_input(event)


func _dispatch_text(text: String) -> void:
	for character in text:
		var event := InputEventKey.new()
		var codepoint = character.unicode_at(0)
		event.keycode = codepoint
		event.physical_keycode = codepoint
		event.unicode = codepoint
		event.pressed = true
		_push_input(event)
		var release_event := InputEventKey.new()
		release_event.keycode = codepoint
		release_event.physical_keycode = codepoint
		release_event.unicode = codepoint
		release_event.pressed = false
		_push_input(release_event)


func _settle_frames(count: int) -> void:
	for _index in range(max(count, 1)):
		await get_tree().process_frame


func _ensure_playback_viewport() -> void:
	if playback_viewport != null and is_instance_valid(playback_viewport):
		return
	playback_viewport = SubViewport.new()
	playback_viewport.name = "AutomationPlaybackViewport"
	playback_viewport.size = Vector2i(
		int(ProjectSettings.get_setting("display/window/size/viewport_width", 1280)),
		int(ProjectSettings.get_setting("display/window/size/viewport_height", 720))
	)
	playback_viewport.disable_3d = true
	playback_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	playback_viewport.gui_disable_input = false
	get_tree().root.add_child(playback_viewport)
	await _settle_frames(2)


func _push_input(event: InputEvent) -> void:
	if playback_viewport != null and is_instance_valid(playback_viewport):
		playback_viewport.push_input(event, true)
	else:
		Input.parse_input_event(event)


func _capture_viewport_with_fallback(tag: String) -> Dictionary:
	# Try real viewport capture first
	if playback_viewport != null and is_instance_valid(playback_viewport):
		await _settle_frames(2)
		var image = playback_viewport.get_texture().get_image()
		if image != null and image.get_width() > 0 and image.get_height() > 0:
			# Check if image is not all-black (renderer actually drew something)
			var has_content = false
			for sample_x in [image.get_width() / 4, image.get_width() / 2, image.get_width() * 3 / 4]:
				for sample_y in [image.get_height() / 4, image.get_height() / 2, image.get_height() * 3 / 4]:
					var pixel = image.get_pixel(clampi(sample_x, 0, image.get_width() - 1), clampi(sample_y, 0, image.get_height() - 1))
					if pixel.r > 0.01 or pixel.g > 0.01 or pixel.b > 0.01:
						has_content = true
						break
				if has_content:
					break
			if has_content:
				var real_path = ScreenshotCapture.capture_image(image, "phase2/headless", tag)
				if not real_path.is_empty():
					return {"path": real_path, "synthetic": false}

	# Fallback to synthetic image
	var fallback = Image.create(
		max(playback_viewport.size.x if playback_viewport != null else 1280, 1),
		max(playback_viewport.size.y if playback_viewport != null else 720, 1),
		false,
		Image.FORMAT_RGBA8
	)
	fallback.fill(Color(0.07, 0.08, 0.1, 1.0))
	_draw_cursor_marker(fallback, state.cursor_position)
	var fallback_path = ScreenshotCapture.capture_image(fallback, "phase2/headless", "%s_synthetic" % tag)
	return {"path": fallback_path, "synthetic": true}


func _draw_cursor_marker(image: Image, cursor: Vector2i) -> void:
	var center_x = clampi(cursor.x, 0, image.get_width() - 1)
	var center_y = clampi(cursor.y, 0, image.get_height() - 1)
	for delta in range(-4, 5):
		var x = clampi(center_x + delta, 0, image.get_width() - 1)
		var y = clampi(center_y + delta, 0, image.get_height() - 1)
		image.set_pixel(x, center_y, Color(0.9, 0.2, 0.2, 1.0))
		image.set_pixel(center_x, y, Color(0.9, 0.2, 0.2, 1.0))


func _button_index_for_name(button_name: String) -> MouseButton:
	match button_name.strip_edges().to_lower():
		"left":
			return MOUSE_BUTTON_LEFT
		"right":
			return MOUSE_BUTTON_RIGHT
		"middle":
			return MOUSE_BUTTON_MIDDLE
	return MOUSE_BUTTON_LEFT


func _keycode_for_name(key_name: String) -> Key:
	var normalized = key_name.strip_edges().to_lower()
	if normalized.is_empty():
		return KEY_NONE
	if KEY_NAME_MAP.has(normalized):
		return KEY_NAME_MAP[normalized]
	if normalized.length() == 1:
		var codepoint = normalized.unicode_at(0)
		return codepoint
	return OS.find_keycode_from_string(normalized)


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text = FileAccess.get_file_as_string(path)
	if text.strip_edges().is_empty():
		return {}
	var parsed = JSON.parse_string(text)
	if parsed is Dictionary:
		return parsed
	return {}


func _write_json(path: String, payload: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(payload))
	file.close()
