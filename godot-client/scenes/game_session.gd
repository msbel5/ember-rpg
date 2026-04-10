extends Control

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")
const WorldViewWidget = preload("res://scripts/world/world_view.gd")
# ResponseNormalizer, EmberTheme, ProfileStorage, StatusBarWidget,
# DialogOverlay, CombatOverlay, SessionSaveSync, SessionWorldSync
# are all available globally via class_name — no preload needed.

const PROFILE_PATH := ProfileStorage.PROFILE_PATH
const QUICKSAVE_SLOT := "quicksave"

@onready var world_view: WorldViewWidget = $MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer
@onready var modal_host = $MainMargin/MainVBox/ContentSplit/ModalHost
@onready var instrument_rail = $MainMargin/MainVBox/InstrumentRail
@onready var save_load_panel = $OverlayCanvas/SaveLoadPanel

var is_waiting := false
var _pending_sync_callbacks := 0
var _dialog_overlay = null
var _combat_overlay_widget = null
var _save_sync
var _world_sync
var _queued_world_commands: Array[String] = []


func _ready() -> void:
	_save_sync = SessionSaveSync.new(self)
	_world_sync = SessionWorldSync.new(self)
	EmberTheme.apply_game_session(self)
	_install_status_bar()
	_install_dialog_overlay()
	_install_combat_overlay()
	_configure_modal_host()

	instrument_rail.command_submitted.connect(_submit_action)
	instrument_rail.quick_save_requested.connect(_save_sync.on_quick_save_requested)
	instrument_rail.saves_requested.connect(_save_sync.open_save_load_panel)
	if instrument_rail.has_signal("panel_requested"):
		instrument_rail.panel_requested.connect(_on_shell_panel_requested)
	world_view.command_requested.connect(_on_world_command_requested)
	world_view.command_sequence_requested.connect(_on_world_command_sequence_requested)
	world_view.focus_changed.connect(instrument_rail.set_focus_summary)
	world_view.focus_actions_changed.connect(instrument_rail.set_focus_actions)
	save_load_panel.save_requested.connect(_save_sync.on_save_requested)
	save_load_panel.load_requested.connect(_save_sync.on_load_requested)
	save_load_panel.delete_requested.connect(_save_sync.on_delete_save_requested)
	save_load_panel.refresh_requested.connect(_save_sync.refresh_save_list)
	save_load_panel.closed.connect(_save_sync.on_save_load_closed)

	GameState.state_updated.connect(_on_state_updated)
	GameState.combat_started.connect(_on_combat_started)
	GameState.combat_ended.connect(_on_combat_ended)
	GameState.dialog_state_changed.connect(_on_dialog_state_changed)
	GameState.level_up_occurred.connect(_on_level_up)
	Backend.request_error.connect(_on_backend_error)
	Backend.runtime_message_received.connect(_on_runtime_message_received)
	Backend.runtime_socket_disconnected.connect(_on_runtime_socket_disconnected)

	_save_sync.remember_player_id()
	_world_sync.initialize_runtime()
	instrument_rail.set_focus_summary(world_view.get_focus_summary())
	instrument_rail.set_focus_actions(world_view.get_focus_actions())
	_sync_dialog_overlay()
	_sync_shell_state()


func _install_status_bar() -> void:
	var main_vbox = $MainMargin/MainVBox
	if main_vbox == null:
		return
	var status_bar := StatusBarWidget.new()
	main_vbox.add_child(status_bar)
	main_vbox.move_child(status_bar, 0)


func _install_dialog_overlay() -> void:
	_dialog_overlay = DialogOverlay.new()
	var world_pane = $MainMargin/MainVBox/ContentSplit/WorldPane
	if world_pane != null:
		world_pane.add_child(_dialog_overlay)
		_dialog_overlay.command_requested.connect(_submit_action)
		_dialog_overlay.dialog_closed.connect(_on_dialog_overlay_closed)
		if _dialog_overlay.has_signal("structured_action_requested"):
			_dialog_overlay.structured_action_requested.connect(_on_structured_action_requested)
		if _dialog_overlay.has_signal("panel_requested"):
			_dialog_overlay.panel_requested.connect(_on_shell_panel_requested)


func _install_combat_overlay() -> void:
	_combat_overlay_widget = CombatOverlay.new()
	var overlay_canvas = $OverlayCanvas
	var world_pane = $MainMargin/MainVBox/ContentSplit/WorldPane
	if overlay_canvas != null:
		overlay_canvas.add_child(_combat_overlay_widget)
	if _combat_overlay_widget != null and world_pane != null and _combat_overlay_widget.has_method("attach_to_surface"):
		_combat_overlay_widget.attach_to_surface(world_pane)
		_combat_overlay_widget.command_requested.connect(_submit_action)
		if _combat_overlay_widget.has_signal("structured_action_requested"):
			_combat_overlay_widget.structured_action_requested.connect(_on_structured_action_requested)


func _configure_modal_host() -> void:
	if modal_host != null and modal_host.has_signal("host_closed"):
		modal_host.host_closed.connect(_on_modal_host_closed)
	_wire_modal_surfaces()
	_sync_pause_panel_views()


func _submit_action(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or is_waiting:
		return
	instrument_rail.remember_command(text)
	if GameState.campaign_id.is_empty():
		_append_narrative_system_text("[color=red]No active game. Start a new adventure.[/color]")
		return
	var hp := int(GameState.player.get("hp", 1))
	if hp <= 0 and not text.to_lower().begins_with("rest"):
		_append_narrative_system_text("[color=red]You have fallen. Type 'rest' to recover or start anew.[/color]")
		return
	_set_waiting(true)
	instrument_rail.clear_input()
	if not Backend.runtime_submit_command(GameState.campaign_id, text):
		Backend.submit_campaign_command(GameState.campaign_id, text, _on_campaign_action_response.bind(text))
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		_show_narrative_thinking_indicator()


func _submit_structured_action(shortcut: String, args: Dictionary, history_text: String = "") -> void:
	var normalized_shortcut := shortcut.strip_edges().to_lower()
	if normalized_shortcut.is_empty() or is_waiting:
		return
	if GameState.campaign_id.is_empty():
		_append_narrative_system_text("[color=red]No active game. Start a new adventure.[/color]")
		return
	var remember_text := history_text.strip_edges()
	if not remember_text.is_empty():
		instrument_rail.remember_command(remember_text)
	_set_waiting(true)
	instrument_rail.clear_input()
	if not Backend.runtime_submit_command(GameState.campaign_id, "", normalized_shortcut, args):
		Backend.submit_campaign_command(
			GameState.campaign_id,
			"",
			_on_campaign_action_response.bind(remember_text),
			normalized_shortcut,
			args,
		)
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		_show_narrative_thinking_indicator()


func _on_campaign_action_response(data, _issued_text: String) -> void:
	if data == null:
		_finish_turn_sync()
		return
	GameState.update_from_response(data)
	_finish_turn_sync()


func _set_waiting(waiting: bool) -> void:
	is_waiting = waiting
	instrument_rail.set_waiting(waiting)
	if _combat_overlay_widget != null and _combat_overlay_widget.has_method("set_waiting"):
		_combat_overlay_widget.set_waiting(waiting)
	var quest_panel = _panel_widget("quests")
	if quest_panel != null and quest_panel.has_method("set_waiting"):
		quest_panel.set_waiting(waiting)
	var settlement_panel = _panel_widget("town")
	if settlement_panel != null and settlement_panel.has_method("set_waiting"):
		settlement_panel.set_waiting(waiting)
	save_load_panel.set_busy(waiting)
	_sync_shell_state()


func _finish_turn_sync() -> void:
	_pending_sync_callbacks = 0
	_set_waiting(false)
	if not _queued_world_commands.is_empty():
		_submit_next_queued_world_command()
		return


func _on_state_updated() -> void:
	_save_sync.remember_player_id()
	_ensure_campaign_socket()
	_sync_pause_panel_views()
	_sync_shell_state()


func _ensure_campaign_socket() -> void:
	if GameState.runtime_transport == "ws":
		Backend.ensure_runtime_socket(GameState.campaign_id, GameState.ws_url, GameState.ws_path)
	elif _world_sync != null and _world_sync.has_method("initialize_runtime"):
		_world_sync.initialize_runtime()


func _on_dialog_state_changed(_payload: Dictionary) -> void:
	_sync_dialog_overlay()
	_sync_pause_panel_views()
	_sync_shell_state()


func _sync_dialog_overlay() -> void:
	if _dialog_overlay == null:
		return
	var dialog_payload := GameState.current_dialog_payload()
	if dialog_payload.is_empty():
		if _dialog_overlay.is_dialog_active():
			_dialog_overlay.hide_dialog()
		return
	if modal_host != null and modal_host.has_method("hide_host"):
		modal_host.hide_host()
	_dialog_overlay.show_dialog(
		str(dialog_payload.get("dialog_npc", "NPC")),
		str(dialog_payload.get("dialog_text", "")),
		dialog_payload.get("dialog_options", []),
	)


func _on_dialog_overlay_closed() -> void:
	_sync_shell_state()


func _on_combat_started() -> void:
	if modal_host != null and modal_host.has_method("hide_host"):
		modal_host.hide_host()
	_append_narrative_system_text("[color=red]Combat begins.[/color]")
	_sync_shell_state()


func _on_combat_ended() -> void:
	_append_narrative_system_text("[color=green]Combat ended.[/color]")
	_sync_shell_state()


func _on_level_up(new_level: int) -> void:
	_append_narrative_system_text("[color=yellow]Level up. You reached level %d.[/color]" % new_level)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return
	if event.keycode == KEY_F12:
		_capture_visual_proof("phase2/game", "game_session", event.shift_pressed)
		get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_F5 or (event.ctrl_pressed and event.keycode == KEY_S):
		_save_sync.on_quick_save_requested()
		get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_F9 or (event.ctrl_pressed and event.keycode == KEY_L):
		_save_sync.open_save_load_panel()
		get_viewport().set_input_as_handled()
		return
	if save_load_panel.visible:
		if event.keycode == KEY_ESCAPE:
			save_load_panel.close_panel()
			get_viewport().set_input_as_handled()
		return
	if _dialog_overlay != null and _dialog_overlay.is_dialog_active():
		return
	if event.keycode == KEY_SPACE and not GameState.is_in_combat():
		_toggle_tactical_pause()
		get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_ESCAPE:
		if modal_host != null and modal_host.has_method("active_panel_id") and not str(modal_host.active_panel_id()).is_empty():
			modal_host.hide_host()
			_sync_shell_state()
			get_viewport().set_input_as_handled()
			return
		if modal_host != null and modal_host.has_method("has_panel") and modal_host.has_panel("pause") and not GameState.is_in_combat():
			_on_shell_panel_requested("pause")
			get_viewport().set_input_as_handled()
			return
	if event.keycode == KEY_HOME or event.keycode == KEY_I:
		_on_shell_panel_requested("items")
		get_viewport().set_input_as_handled()
		return
	match event.keycode:
		KEY_C, KEY_H:
			_on_shell_panel_requested("hero")
			get_viewport().set_input_as_handled()
			return
		KEY_J:
			_on_shell_panel_requested("quests")
			get_viewport().set_input_as_handled()
			return
		KEY_M:
			_on_shell_panel_requested("map")
			get_viewport().set_input_as_handled()
			return
		KEY_T:
			_on_shell_panel_requested("town")
			get_viewport().set_input_as_handled()
			return
		KEY_O:
			if not GameState.is_in_combat():
				_on_shell_panel_requested("pause")
				get_viewport().set_input_as_handled()
			return
	if modal_host != null and modal_host.has_method("active_panel_id") and not str(modal_host.active_panel_id()).is_empty():
		return
	var direction := ""
	match event.keycode:
		KEY_UP, KEY_W:
			direction = "north"
		KEY_DOWN, KEY_S:
			direction = "south"
		KEY_LEFT, KEY_A:
			direction = "west"
		KEY_RIGHT, KEY_D:
			direction = "east"
	if direction != "":
		_submit_action("move %s" % direction)
		get_viewport().set_input_as_handled()


func _on_backend_error(message: String) -> void:
	_pending_sync_callbacks = 0
	_queued_world_commands.clear()
	_set_waiting(false)
	save_load_panel.set_status(message)
	_append_narrative_system_text("[color=red][%s][/color]" % message)


func _on_runtime_message_received(message: Dictionary) -> void:
	var message_type := str(message.get("type", "")).strip_edges().to_lower()
	if message_type == "pong":
		return
	if message_type == "error":
		_on_backend_error(str(message.get("message", "Runtime socket error")))
		return
	var snapshot = message.get("snapshot", {})
	if not (snapshot is Dictionary):
		return
	var payload: Dictionary = snapshot.duplicate(true)
	var narrative := str(message.get("narrative", "")).strip_edges()
	if not narrative.is_empty():
		payload["narrative"] = narrative
	GameState.update_from_response(payload)
	if message_type == "state":
		_finish_turn_sync()


func _on_runtime_socket_disconnected(_campaign_id: String, _reason: String) -> void:
	if GameState.has_active_campaign():
		_append_narrative_system_text("[color=orange]Runtime link dropped. Attempting to reconnect.[/color]")
		call_deferred("_ensure_campaign_socket")


func _toggle_tactical_pause() -> void:
	if GameState.campaign_id.is_empty():
		return
	var target_mode := "tactical_pause"
	if GameState.runtime_mode == "tactical_pause":
		target_mode = "exploration_realtime"
	if not Backend.set_runtime_mode(GameState.campaign_id, target_mode):
		_append_narrative_system_text("[color=orange]Live runtime pause is unavailable.[/color]")


func _on_world_command_requested(command_text: String) -> void:
	_queued_world_commands.clear()
	_submit_action(command_text)


func _on_world_command_sequence_requested(commands: Array[String]) -> void:
	_queued_world_commands.clear()
	for command in commands:
		var normalized := str(command).strip_edges()
		if not normalized.is_empty():
			_queued_world_commands.append(normalized)
	if not is_waiting:
		_submit_next_queued_world_command()


func _submit_next_queued_world_command() -> void:
	if _queued_world_commands.is_empty() or is_waiting:
		return
	var next_command: String = str(_queued_world_commands.pop_front())
	_submit_action(next_command)


func _on_travel_requested(request: Dictionary) -> void:
	var shortcut := str(request.get("shortcut", "travel"))
	var args = request.get("args", {})
	if not (args is Dictionary):
		return
	_submit_structured_action(shortcut, args, str(request.get("history_text", "")))


func _on_structured_action_requested(shortcut: String, args: Dictionary, history_text: String) -> void:
	_submit_structured_action(shortcut, args, history_text)


func _wire_modal_surfaces() -> void:
	if modal_host == null or not modal_host.has_method("available_panel_ids"):
		return
	for panel_id in modal_host.available_panel_ids():
		var child = modal_host.panel_node(panel_id)
		if child == null:
			continue
		if child.has_signal("command_requested"):
			var callable := Callable(self, "_submit_action")
			if not child.command_requested.is_connected(callable):
				child.command_requested.connect(callable)
		if child.has_signal("travel_requested"):
			var travel_callable := Callable(self, "_on_travel_requested")
			if not child.travel_requested.is_connected(travel_callable):
				child.travel_requested.connect(travel_callable)
		if child.has_signal("structured_action_requested"):
			var structured_callable := Callable(self, "_on_structured_action_requested")
			if not child.structured_action_requested.is_connected(structured_callable):
				child.structured_action_requested.connect(structured_callable)
		if child.has_signal("panel_requested"):
			var panel_callable := Callable(self, "_on_shell_panel_requested")
			if not child.panel_requested.is_connected(panel_callable):
				child.panel_requested.connect(panel_callable)
		if child.has_signal("close_requested"):
			var close_callable := Callable(self, "_on_modal_surface_close_requested")
			if not child.close_requested.is_connected(close_callable):
				child.close_requested.connect(close_callable)


func _on_shell_panel_requested(panel_id: String) -> void:
	if modal_host == null or str(panel_id).strip_edges().is_empty():
		return
	if is_waiting or save_load_panel.visible:
		_sync_shell_state()
		return
	var normalized := str(panel_id).strip_edges().to_lower()
	var allow_during_dialog := normalized == "narrative"
	if (GameState.has_active_dialog() and not allow_during_dialog) or GameState.is_in_combat():
		_sync_shell_state()
		return
	if not modal_host.has_panel(normalized):
		_sync_shell_state()
		return
	if normalized == "pause":
		if str(modal_host.active_panel_id()) == normalized:
			modal_host.hide_host()
		else:
			modal_host.show_panel(normalized)
	else:
		modal_host.toggle_panel(normalized)
	_sync_shell_state()


func _on_modal_host_closed() -> void:
	_sync_shell_state()


func _on_modal_surface_close_requested() -> void:
	if modal_host != null and modal_host.has_method("hide_host"):
		modal_host.hide_host()


func _sync_shell_state() -> void:
	if modal_host == null or instrument_rail == null:
		return
	_sync_pause_panel_views()
	var shell_mode := GameState.current_shell_mode()
	if shell_mode != "exploration" and not str(modal_host.active_panel_id()).is_empty():
		modal_host.hide_host()
	var available_ids: Array[String] = []
	if modal_host.has_method("available_panel_ids"):
		available_ids = modal_host.available_panel_ids()
	var panel_states := {}
	var interaction_locked: bool = is_waiting or save_load_panel.visible or GameState.has_active_dialog() or GameState.is_in_combat()
	for panel_id in ["hero", "items", "map", "quests", "town", "pause"]:
		var exists := available_ids.has(panel_id)
		panel_states[panel_id] = {
			"visible": exists,
			"enabled": exists and not interaction_locked,
			"tooltip": "",
		}
	if interaction_locked and GameState.has_active_dialog() and available_ids.has("narrative"):
		panel_states["hero"]["tooltip"] = "Panels close while dialog is active."
		panel_states["items"]["tooltip"] = "Panels close while dialog is active."
		panel_states["map"]["tooltip"] = "Panels close while dialog is active."
		panel_states["quests"]["tooltip"] = "Panels close while dialog is active."
		panel_states["town"]["tooltip"] = "Panels close while dialog is active."
		panel_states["pause"]["tooltip"] = "Pause intelligence is disabled while dialog or combat is active."
	var active_panel_id := str(modal_host.active_panel_id())
	instrument_rail.set_panel_actions(panel_states, active_panel_id)


func _sync_pause_panel_views() -> void:
	if modal_host == null or not modal_host.has_method("panel_node") or not modal_host.has_panel("pause"):
		return
	var pause_panel = modal_host.panel_node("pause")
	if pause_panel == null:
		return
	if pause_panel.has_method("set_advisor_view"):
		pause_panel.set_advisor_view(GameState.advisor_view)
	if pause_panel.has_method("set_knowledge_view"):
		pause_panel.set_knowledge_view(GameState.knowledge_view)
	if pause_panel.has_method("sync_from_game_state"):
		pause_panel.sync_from_game_state()
	if str(modal_host.active_panel_id()) == "pause" and pause_panel.has_method("open_menu"):
		pause_panel.open_menu()


func _capture_visual_proof(folder: String, prefix: String, include_world: bool) -> void:
	var frame_path := ScreenshotCapture.capture_viewport(get_viewport(), folder, "%s_frame" % prefix)
	var world_path := ""
	if include_world and world_view != null and world_view.has_method("capture_world_screenshot"):
		world_path = world_view.capture_world_screenshot(folder, "%s_world" % prefix)
	var parts: Array[String] = []
	if not frame_path.is_empty():
		parts.append("frame=%s" % frame_path)
	if not world_path.is_empty():
		parts.append("world=%s" % world_path)
	if parts.is_empty():
		_append_narrative_system_text("[color=red]Viewport capture failed.[/color]")
		return
	_append_narrative_system_text("[color=gray]Visual proof saved: %s[/color]" % " | ".join(parts))


func _on_save_completed(data, keep_panel_open: bool) -> void:
	_save_sync.on_save_completed(data, keep_panel_open)


func _panel_widget(panel_id: String):
	if modal_host == null or not modal_host.has_method("panel_node"):
		return null
	return modal_host.panel_node(panel_id)


func _append_narrative_system_text(text: String) -> void:
	var panel = _panel_widget("narrative")
	if panel != null and panel.has_method("append_system_text"):
		panel.append_system_text(text)


func _show_narrative_thinking_indicator() -> void:
	var panel = _panel_widget("narrative")
	if panel != null and panel.has_method("show_thinking_indicator"):
		panel.show_thinking_indicator()


func _load_narrative_history(lines: Array) -> void:
	var panel = _panel_widget("narrative")
	if panel != null and panel.has_method("load_history"):
		panel.load_history(lines)
