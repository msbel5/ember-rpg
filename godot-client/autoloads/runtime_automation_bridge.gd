extends Node

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")

const COMMAND_ENV := "EMBER_AUTOMATION_COMMAND_FILE"
const RESULT_ENV := "EMBER_AUTOMATION_RESULT_FILE"
const STATUS_ENV := "EMBER_AUTOMATION_STATUS_FILE"
const ARTIFACT_ENV := "EMBER_AUTOMATION_ARTIFACT_ROOT"

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

var _enabled := false
var _command_file := ""
var _result_file := ""
var _status_file := ""
var _artifact_root := ""
var _last_seq := -1
var _cursor_position := Vector2i.ZERO


func _ready() -> void:
	_command_file = _normalize_fs_path(OS.get_environment(COMMAND_ENV).strip_edges())
	_result_file = _normalize_fs_path(OS.get_environment(RESULT_ENV).strip_edges())
	_status_file = _normalize_fs_path(OS.get_environment(STATUS_ENV).strip_edges())
	_artifact_root = _normalize_fs_path(OS.get_environment(ARTIFACT_ENV).strip_edges())
	_enabled = not _command_file.is_empty() and not _result_file.is_empty() and not _status_file.is_empty()
	set_process(_enabled)
	if not _enabled:
		return
	_write_json(_status_file, _status_payload({
		"ready": false,
		"status": "booting",
		"message": "Preparing runtime automation bridge",
	}))
	await get_tree().process_frame
	await get_tree().process_frame
	_write_json(_status_file, _status_payload({"status": "ok"}))


func _process(_delta: float) -> void:
	if not _enabled:
		return
	_poll_once()


func _poll_once() -> void:
	if _command_file.is_empty() or not FileAccess.file_exists(_command_file):
		return
	var payload = _read_json(_command_file)
	if payload.is_empty():
		return
	var seq = int(payload.get("seq", -1))
	if seq <= _last_seq:
		return
	_last_seq = seq
	var result = await _dispatch_command(payload)
	result["seq"] = seq
	_write_json(_result_file, result)


func _dispatch_command(command: Dictionary) -> Dictionary:
	var action = str(command.get("action", "")).strip_edges()
	match action:
		"focus_node":
			var focus_target = _resolve_node(str(command.get("node_path", "")))
			if focus_target == null:
				return {"status": "error", "message": "Node not found for focus."}
			if not _focus_node(focus_target):
				return {"status": "error", "message": "Node does not support focus."}
		"activate_node":
			var activate_target = _resolve_node(str(command.get("node_path", "")))
			if activate_target == null:
				return {"status": "error", "message": "Node not found for activation."}
			if not await _activate_node(activate_target):
				return {"status": "error", "message": "Node does not support activation."}
		"set_text_node":
			var text_target = _resolve_node(str(command.get("node_path", "")))
			if text_target == null:
				return {"status": "error", "message": "Node not found for text update."}
			if not _set_text_on_node(text_target, str(command.get("text", ""))):
				return {"status": "error", "message": "Node does not support text updates."}
		"select_option_node":
			var option_target = _resolve_node(str(command.get("node_path", "")))
			if option_target == null:
				return {"status": "error", "message": "Node not found for option selection."}
			if not _select_option_on_node(option_target, str(command.get("option_text", ""))):
				return {"status": "error", "message": "Node does not support option selection."}
		"click_node":
			var click_target = _resolve_node(str(command.get("node_path", "")))
			if click_target == null:
				return {"status": "error", "message": "Node not found for logical click."}
			if not _click_node(
				click_target,
				str(command.get("button", "left")),
				float(command.get("normalized_x", 0.5)),
				float(command.get("normalized_y", 0.5))
			):
				return {"status": "error", "message": "Node does not support logical click."}
		"query_state":
			var target_path = str(command.get("node_path", "")).strip_edges()
			var target = _resolve_node(target_path) if not target_path.is_empty() else null
			var current_scene = _current_scene_root()
			var focus_owner = null
			if current_scene != null:
				focus_owner = current_scene.get_viewport().gui_get_focus_owner()
			var target_visible = false
			if target is CanvasItem:
				target_visible = (target as CanvasItem).is_visible_in_tree()
			return {
				"status": "ok",
				"scene_name": current_scene.name if current_scene != null else "",
				"node_exists": target != null,
				"node_visible": target_visible,
				"node_text": _node_text(target),
				"focused_node_path": _node_path_from_scene_root(focus_owner) if focus_owner != null else "",
			}
		"query_runtime_state":
			return _runtime_state_payload()
		"world_tile_click":
			var target_path = str(command.get("node_path", "")).strip_edges()
			if target_path.is_empty():
				target_path = "MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer"
			var world_target = _resolve_node(target_path)
			if world_target == null:
				return {"status": "error", "message": "World viewport node not found for tile click."}
			if not world_target.has_method("automation_click_tile"):
				return {"status": "error", "message": "Target node does not support tile automation clicks."}
			var tile: Vector2i = Vector2i(int(command.get("tile_x", 0)), int(command.get("tile_y", 0)))
			var button_name = str(command.get("button", "left"))
			if not bool(world_target.call("automation_click_tile", tile, button_name)):
				return {"status": "error", "message": "World tile click failed."}
			await get_tree().process_frame
			await get_tree().process_frame
			return {"status": "ok", "tile": [tile.x, tile.y], "button": button_name}
		"capture_viewport":
			var tag = str(command.get("tag", "runtime_capture")).strip_edges()
			var capture_path = _capture_viewport(tag)
			if capture_path.is_empty():
				return {"status": "error", "message": "Viewport capture failed."}
			var current_scene = _current_scene_root()
			return {
				"status": "ok",
				"path": capture_path,
				"scene_name": current_scene.name if current_scene != null else "",
			}
		"close":
			get_tree().quit()
		_:
			return {"status": "error", "message": "Unsupported automation action %s" % action}

	await get_tree().process_frame
	await get_tree().process_frame
	return {"status": "ok"}


func _current_scene_root() -> Node:
	var scene = get_tree().current_scene
	if scene == null or not is_instance_valid(scene):
		return null
	if scene == self:
		return null
	return scene


func _resolve_node(node_path: String) -> Node:
	var normalized = node_path.strip_edges()
	if normalized.is_empty():
		return null
	var current_scene = _current_scene_root()
	if current_scene == null:
		return null
	if normalized.begins_with("/root/"):
		return get_node_or_null(normalized)
	if normalized.begins_with("%s/" % current_scene.name):
		var relative_path = normalized.trim_prefix("%s/" % current_scene.name)
		return current_scene.get_node_or_null(NodePath(relative_path))
	if current_scene.has_node(NodePath(normalized)):
		return current_scene.get_node(NodePath(normalized))
	return current_scene.find_child(normalized, true, false)


func _focus_node(target: Node) -> bool:
	if target is Control:
		var control: Control = target
		control.grab_focus()
		return true
	return false


func _activate_node(target: Node) -> bool:
	if target is BaseButton:
		var button: BaseButton = target
		if button.disabled:
			return false
		button.grab_focus()
		button.pressed.emit()
		return true
	if target is LineEdit:
		var line_edit: LineEdit = target
		line_edit.grab_focus()
		line_edit.text_submitted.emit(line_edit.text)
		return true
	return _focus_node(target)


func _set_text_on_node(target: Node, text: String) -> bool:
	if target is LineEdit:
		var line_edit: LineEdit = target
		line_edit.grab_focus()
		line_edit.text = text
		line_edit.caret_column = line_edit.text.length()
		line_edit.text_changed.emit(line_edit.text)
		return true
	return false


func _select_option_on_node(target: Node, option_text: String) -> bool:
	if target is OptionButton:
		var option_button: OptionButton = target
		for index in range(option_button.item_count):
			if option_button.get_item_text(index) == option_text:
				option_button.select(index)
				option_button.item_selected.emit(index)
				return true
	return false


func _click_node(target: Node, button_name: String, normalized_x: float, normalized_y: float) -> bool:
	if not (target is Control):
		return false
	var control: Control = target
	var rect = control.get_global_rect()
	if rect.size.x <= 0.0 or rect.size.y <= 0.0:
		return false
	var clamped_x = clampf(normalized_x, 0.0, 1.0)
	var clamped_y = clampf(normalized_y, 0.0, 1.0)
	var position = rect.position + Vector2(rect.size.x * clamped_x, rect.size.y * clamped_y)
	_dispatch_mouse_move(position)
	_dispatch_mouse_button(button_name, true)
	_dispatch_mouse_button(button_name, false)
	return true


func _dispatch_mouse_move(position: Vector2) -> void:
	_cursor_position = Vector2i(position)
	var event := InputEventMouseMotion.new()
	event.position = position
	event.global_position = position
	_push_input(event)


func _dispatch_mouse_button(button_name: String, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	var position = Vector2(_cursor_position)
	event.position = position
	event.global_position = position
	event.button_index = _button_index_for_name(button_name)
	event.pressed = pressed
	_push_input(event)


func _push_input(event: InputEvent) -> void:
	var current_scene = _current_scene_root()
	if current_scene != null:
		var target_viewport = current_scene.get_viewport()
		if target_viewport != null:
			target_viewport.push_input(event, true)
			return
	Input.parse_input_event(event)


func _capture_viewport(tag: String) -> String:
	var current_scene = _current_scene_root()
	if current_scene == null:
		return ""
	var folder = "phase2/runtime"
	if not _artifact_root.is_empty():
		folder = "phase2/runtime"
	return ScreenshotCapture.capture_viewport(current_scene.get_viewport(), folder, tag)


func _button_index_for_name(button_name: String) -> MouseButton:
	match button_name.strip_edges().to_lower():
		"left":
			return MOUSE_BUTTON_LEFT
		"right":
			return MOUSE_BUTTON_RIGHT
		"middle":
			return MOUSE_BUTTON_MIDDLE
	return MOUSE_BUTTON_LEFT


func _node_path_from_scene_root(node: Node) -> String:
	var current_scene = _current_scene_root()
	if current_scene == null:
		return node.name
	var root_path = str(current_scene.get_path())
	var node_path = str(node.get_path())
	if node_path.begins_with(root_path):
		return node_path.trim_prefix(root_path).trim_prefix("/")
	return node_path


func _node_text(target: Node) -> String:
	if target == null:
		return ""
	if target is Label:
		return (target as Label).text
	if target is RichTextLabel:
		return (target as RichTextLabel).text
	if target is LineEdit:
		return (target as LineEdit).text
	if target is BaseButton:
		return (target as BaseButton).text
	return ""


func _normalize_fs_path(value: String) -> String:
	return value.replace("\\", "/")


func _runtime_state_payload() -> Dictionary:
	var game_state = get_node_or_null("/root/GameState")
	if game_state == null:
		return {"status": "ok", "scene_name": str(_current_scene_root().name if _current_scene_root() != null else "")}
	var modal_host = _resolve_node("MainMargin/MainVBox/ContentSplit/ModalHost")
	var active_panel_id := ""
	if modal_host != null and modal_host.has_method("active_panel_id"):
		active_panel_id = str(modal_host.call("active_panel_id"))
	var payload := {
		"status": "ok",
		"scene_name": str(_current_scene_root().name if _current_scene_root() != null else ""),
		"shell_mode": str(game_state.current_shell_mode()),
		"location": str(game_state.get_display_location()),
		"player_tile": [game_state.player_map_pos.x, game_state.player_map_pos.y],
		"dialog_active": bool(game_state.has_active_dialog()),
		"combat_active": bool(game_state.is_in_combat()),
		"travel_active": bool(game_state.has_active_travel()),
		"active_panel_id": active_panel_id,
		"map_size": [
			int(game_state.map_data.get("width", 0)),
			int(game_state.map_data.get("height", 0)),
		],
		"neighbor_tiles": _neighbor_tile_snapshot(game_state.player_map_pos, game_state.map_data, game_state.entities),
		"entities": _flatten_entities(game_state.entities),
		"ask_about_topic_count": _ask_about_topic_count(game_state.conversation_state),
	}
	if game_state.has_active_dialog():
		payload["dialog_npc"] = str(game_state.dialog_npc)
		payload["dialog_text"] = str(game_state.dialog_text)
		payload["dialog_options"] = game_state.dialog_options
	return payload


func _neighbor_tile_snapshot(player_tile: Vector2i, map_data: Dictionary, grouped_entities: Dictionary) -> Array:
	var snapshot: Array = []
	for dir in [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]:
		var tile: Vector2i = player_tile + dir
		snapshot.append({
			"tile": [tile.x, tile.y],
			"tile_name": _tile_name_at(map_data, tile),
			"occupied": _tile_has_entity(grouped_entities, tile),
		})
	return snapshot


func _flatten_entities(grouped_entities: Dictionary) -> Array:
	var flattened: Array = []
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for entry in grouped_entities.get(bucket, []):
			if not (entry is Dictionary):
				continue
			var pos = entry.get("position", [0, 0])
			var x: int = 0
			var y: int = 0
			if pos is Array and pos.size() >= 2:
				x = int(pos[0])
				y = int(pos[1])
			flattened.append({
				"id": str(entry.get("id", entry.get("entity_id", ""))),
				"name": str(entry.get("name", "")),
				"bucket": bucket,
				"position": [x, y],
			})
	return flattened


func _tile_name_at(map_data: Dictionary, tile: Vector2i) -> String:
	var rows = map_data.get("tiles", [])
	if not (rows is Array) or tile.y < 0 or tile.y >= rows.size():
		return ""
	var row = rows[tile.y]
	if not (row is Array) or tile.x < 0 or tile.x >= row.size():
		return ""
	var value = row[tile.x]
	if value == null:
		return ""
	return str(value)


func _tile_has_entity(grouped_entities: Dictionary, tile: Vector2i) -> bool:
	for bucket in ["npcs", "enemies", "items", "furniture"]:
		for entry in grouped_entities.get(bucket, []):
			if not (entry is Dictionary):
				continue
			var pos = entry.get("position", [])
			if pos is Array and pos.size() >= 2 and int(pos[0]) == tile.x and int(pos[1]) == tile.y:
				return true
	return false


func _ask_about_topic_count(conversation_state: Dictionary) -> int:
	var topic_ids = conversation_state.get("ask_about_topic_ids", [])
	return topic_ids.size() if topic_ids is Array else 0


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


func _status_payload(extra: Dictionary = {}) -> Dictionary:
	var payload := {
		"ready": true,
		"command_file": _command_file,
		"result_file": _result_file,
		"status_file": _status_file,
		"artifact_root": _artifact_root,
	}
	var current_scene = _current_scene_root()
	if current_scene != null:
		payload["scene_name"] = current_scene.name
	for key in extra.keys():
		payload[key] = extra[key]
	return payload
