extends RefCounted
class_name SessionShellSync


var _owner


func _init(owner) -> void:
	_owner = owner


func wire_modal_surfaces() -> void:
	if _owner.modal_host == null or not _owner.modal_host.has_method("available_panel_ids"):
		return
	for panel_id in _owner.modal_host.available_panel_ids():
		var child = _owner.modal_host.panel_node(panel_id)
		if child == null:
			continue
		if child.has_signal("command_requested"):
			var callable := Callable(_owner, "_submit_action")
			if not child.command_requested.is_connected(callable):
				child.command_requested.connect(callable)
		if child.has_signal("travel_requested"):
			var travel_callable := Callable(_owner, "_on_travel_requested")
			if not child.travel_requested.is_connected(travel_callable):
				child.travel_requested.connect(travel_callable)
		if child.has_signal("structured_action_requested"):
			var structured_callable := Callable(_owner, "_on_structured_action_requested")
			if not child.structured_action_requested.is_connected(structured_callable):
				child.structured_action_requested.connect(structured_callable)
		if child.has_signal("panel_requested"):
			var panel_callable := Callable(_owner, "_on_shell_panel_requested")
			if not child.panel_requested.is_connected(panel_callable):
				child.panel_requested.connect(panel_callable)
		if child.has_signal("close_requested"):
			var close_callable := Callable(_owner, "_on_modal_surface_close_requested")
			if not child.close_requested.is_connected(close_callable):
				child.close_requested.connect(close_callable)


func on_shell_panel_requested(panel_id: String) -> void:
	if _owner.modal_host == null or str(panel_id).strip_edges().is_empty():
		return
	if _owner.is_waiting or _owner.save_load_panel.visible:
		sync_shell_state()
		return
	var normalized := str(panel_id).strip_edges().to_lower()
	var allow_during_dialog := normalized == "narrative"
	if (GameState.has_active_dialog() and not allow_during_dialog) or GameState.is_in_combat():
		sync_shell_state()
		return
	if not _owner.modal_host.has_panel(normalized):
		sync_shell_state()
		return
	if normalized == "pause":
		if str(_owner.modal_host.active_panel_id()) == normalized:
			_owner.modal_host.hide_host()
		else:
			_owner.modal_host.show_panel(normalized)
	else:
		_owner.modal_host.toggle_panel(normalized)
	sync_shell_state()


func on_modal_host_closed() -> void:
	sync_shell_state()


func on_modal_surface_close_requested() -> void:
	if _owner.modal_host != null and _owner.modal_host.has_method("hide_host"):
		_owner.modal_host.hide_host()


func sync_shell_state() -> void:
	if _owner.modal_host == null or _owner.instrument_rail == null:
		return
	sync_pause_panel_views()
	var shell_mode := GameState.current_shell_mode()
	if shell_mode != "exploration" and not str(_owner.modal_host.active_panel_id()).is_empty():
		_owner.modal_host.hide_host()
	var available_ids: Array[String] = []
	if _owner.modal_host.has_method("available_panel_ids"):
		available_ids = _owner.modal_host.available_panel_ids()
	var panel_states := {}
	var interaction_locked: bool = _owner.is_waiting or _owner.save_load_panel.visible or GameState.has_active_dialog() or GameState.is_in_combat()
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
	var active_panel_id := str(_owner.modal_host.active_panel_id())
	_owner.instrument_rail.set_panel_actions(panel_states, active_panel_id)


func sync_pause_panel_views() -> void:
	if _owner.modal_host == null or not _owner.modal_host.has_method("panel_node") or not _owner.modal_host.has_panel("pause"):
		return
	var pause_panel = _owner.modal_host.panel_node("pause")
	if pause_panel == null:
		return
	if pause_panel.has_method("set_advisor_view"):
		pause_panel.set_advisor_view(GameState.advisor_view)
	if pause_panel.has_method("set_knowledge_view"):
		pause_panel.set_knowledge_view(GameState.knowledge_view)
	if pause_panel.has_method("sync_from_game_state"):
		pause_panel.sync_from_game_state()
	if str(_owner.modal_host.active_panel_id()) == "pause" and pause_panel.has_method("open_menu"):
		pause_panel.open_menu()


func panel_widget(panel_id: String):
	if _owner.modal_host == null or not _owner.modal_host.has_method("panel_node"):
		return null
	return _owner.modal_host.panel_node(panel_id)


func append_narrative_system_text(text: String) -> void:
	var panel = panel_widget("narrative")
	if panel != null and panel.has_method("append_system_text"):
		panel.append_system_text(text)


func show_narrative_thinking_indicator() -> void:
	var panel = panel_widget("narrative")
	if panel != null and panel.has_method("show_thinking_indicator"):
		panel.show_thinking_indicator()


func load_narrative_history(lines: Array) -> void:
	var panel = panel_widget("narrative")
	if panel != null and panel.has_method("load_history"):
		panel.load_history(lines)
