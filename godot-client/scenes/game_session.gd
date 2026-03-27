extends Control

const ResponseNormalizer = preload("res://scripts/net/response_normalizer.gd")
const PROFILE_PATH := "user://client_profile.cfg"
const QUICKSAVE_SLOT := "quicksave"

@onready var world_view: SubViewportContainer = $MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer
@onready var narrative_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/NarrativePanel
@onready var command_bar = $MainMargin/MainVBox/CommandBar
@onready var quest_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/QuestPanel
@onready var combat_panel = $OverlayCanvas/CombatPanel
@onready var save_load_panel = $OverlayCanvas/SaveLoadPanel

var is_waiting: bool = false
var _pending_sync_callbacks: int = 0


func _ready() -> void:
	command_bar.command_submitted.connect(_submit_action)
	command_bar.quick_save_requested.connect(_on_quick_save_requested)
	command_bar.saves_requested.connect(_open_save_load_panel)
	world_view.command_requested.connect(_on_world_command_requested)
	quest_panel.command_requested.connect(_submit_action)
	combat_panel.command_requested.connect(_submit_action)
	save_load_panel.save_requested.connect(_on_save_requested)
	save_load_panel.load_requested.connect(_on_load_requested)
	save_load_panel.delete_requested.connect(_on_delete_save_requested)
	save_load_panel.refresh_requested.connect(_refresh_save_list)
	save_load_panel.closed.connect(_on_save_load_closed)

	GameState.state_updated.connect(_on_state_updated)
	GameState.combat_started.connect(_on_combat_started)
	GameState.combat_ended.connect(_on_combat_ended)
	GameState.level_up_occurred.connect(_on_level_up)
	Backend.request_error.connect(_on_backend_error)

	_remember_player_id()

	if GameState.session_id != "":
		if GameState.map_data.is_empty():
			_enter_scene(GameState.location if not GameState.location.is_empty() else "Harbor Town")
		elif not _map_has_tiles():
			_resync_existing_session()

	command_bar.focus_input()


func _enter_scene(location_name: String) -> void:
	var display_name = location_name.replace("_", " ").capitalize()
	narrative_panel.append_system_text("[color=gray]Entering %s...[/color]" % display_name)
	Backend.enter_scene(GameState.session_id, location_name, _on_scene_entered)


func _on_scene_entered(data) -> void:
	if data == null:
		narrative_panel.append_system_text("[color=red]Failed to enter scene.[/color]")
		return

	GameState.update_from_response(data)
	if (not data.has("player") or not data["player"].has("position")) and GameState.map_data.has("spawn_point"):
		var spawn_point = GameState.map_data.get("spawn_point", [])
		if spawn_point is Array and spawn_point.size() >= 2:
			GameState.player_map_pos = Vector2i(int(spawn_point[0]), int(spawn_point[1]))
	Backend.get_session(GameState.session_id, _on_scene_session_loaded)
	Backend.get_map(GameState.session_id, _on_map_loaded)
	Backend.get_inventory(GameState.session_id, _on_inventory_loaded)


func _on_scene_session_loaded(data) -> void:
	if data == null:
		return
	GameState.update_from_response(data)


func _on_map_loaded(data) -> void:
	if data == null:
		return
	GameState.update_from_response(data)


func _on_inventory_loaded(data) -> void:
	if data == null:
		return
	GameState.update_from_response(data)


func _submit_action(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or is_waiting:
		return
	if GameState.session_id.is_empty():
		narrative_panel.append_system_text("[color=red]No active session. Start a new adventure.[/color]")
		return

	var hp = int(GameState.player.get("hp", 1))
	if hp <= 0 and not text.to_lower().begins_with("rest"):
		narrative_panel.append_system_text("[color=red]You have fallen. Type 'rest' to recover or start anew.[/color]")
		return

	_set_waiting(true)
	narrative_panel.append_command(text)
	command_bar.clear_input()
	Backend.submit_action(GameState.session_id, text, _on_action_response.bind(text, GameState.location))
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		narrative_panel.show_thinking_indicator()


func _on_action_response(data, issued_text: String, previous_location: String) -> void:
	if data == null:
		_finish_turn_sync()
		return

	GameState.update_from_response(data)
	Backend.get_session(GameState.session_id, _on_session_resynced.bind(issued_text, previous_location))


func _on_session_resynced(data, issued_text: String, previous_location: String) -> void:
	if data != null:
		GameState.update_from_response(data)

	var needs_map_refresh = GameState.map_data.is_empty() or (not previous_location.is_empty() and GameState.location != previous_location)
	var needs_inventory_refresh = ResponseNormalizer.command_requires_inventory_refresh(issued_text) or GameState.inventory_items.is_empty()

	_pending_sync_callbacks = 0
	if needs_map_refresh:
		_pending_sync_callbacks += 1
		Backend.get_map(GameState.session_id, _on_map_resynced)
	if needs_inventory_refresh:
		_pending_sync_callbacks += 1
		Backend.get_inventory(GameState.session_id, _on_inventory_resynced)

	if _pending_sync_callbacks == 0:
		_finish_turn_sync()


func _set_waiting(waiting: bool) -> void:
	is_waiting = waiting
	command_bar.set_waiting(waiting)
	if combat_panel.has_method("set_waiting"):
		combat_panel.set_waiting(waiting)
	if quest_panel.has_method("set_waiting"):
		quest_panel.set_waiting(waiting)
	save_load_panel.set_busy(waiting)


func _finish_turn_sync() -> void:
	_pending_sync_callbacks = 0
	_set_waiting(false)
	if not save_load_panel.visible:
		command_bar.focus_input()


func _on_state_updated() -> void:
	_remember_player_id()


func _on_combat_started() -> void:
	narrative_panel.append_system_text("[color=red]Combat begins.[/color]")


func _on_combat_ended() -> void:
	narrative_panel.append_system_text("[color=green]Combat ended.[/color]")


func _on_level_up(new_level: int) -> void:
	narrative_panel.append_system_text("[color=yellow]Level up. You reached level %d.[/color]" % new_level)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return

	if event.keycode == KEY_F5 or (event.ctrl_pressed and event.keycode == KEY_S):
		_on_quick_save_requested()
		get_viewport().set_input_as_handled()
		return

	if event.keycode == KEY_F9 or (event.ctrl_pressed and event.keycode == KEY_L):
		_open_save_load_panel()
		get_viewport().set_input_as_handled()
		return

	if save_load_panel.visible:
		if event.keycode == KEY_ESCAPE:
			save_load_panel.close_panel()
			get_viewport().set_input_as_handled()
		return

	if event.keycode == KEY_HOME or event.keycode == KEY_I:
		_submit_action("inventory")
		get_viewport().set_input_as_handled()
		return

	if event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER:
		command_bar.focus_input()
		get_viewport().set_input_as_handled()
		return

	var direction = ""
	match event.keycode:
		KEY_UP:
			direction = "north"
		KEY_DOWN:
			direction = "south"
		KEY_LEFT:
			direction = "west"
		KEY_RIGHT:
			direction = "east"
	if direction != "":
		_submit_action("move %s" % direction)
		get_viewport().set_input_as_handled()
		return

	if not command_bar.has_input_focus():
		match event.keycode:
			KEY_W:
				direction = "north"
			KEY_S:
				direction = "south"
			KEY_A:
				direction = "west"
			KEY_D:
				direction = "east"
		if direction != "":
			_submit_action("move %s" % direction)
			get_viewport().set_input_as_handled()


func _on_backend_error(message: String) -> void:
	_pending_sync_callbacks = 0
	_set_waiting(false)
	save_load_panel.set_status(message)
	narrative_panel.append_system_text("[color=red][%s][/color]" % message)


func _on_map_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	_complete_followup_sync()


func _on_inventory_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	_complete_followup_sync()


func _complete_followup_sync() -> void:
	_pending_sync_callbacks = maxi(_pending_sync_callbacks - 1, 0)
	if _pending_sync_callbacks == 0:
		_finish_turn_sync()


func _on_world_command_requested(command_text: String) -> void:
	_submit_action(command_text)


func _resync_existing_session() -> void:
	if GameState.session_id.is_empty():
		return
	Backend.get_session(GameState.session_id, _on_scene_session_loaded)
	Backend.get_map(GameState.session_id, _on_map_loaded)
	Backend.get_inventory(GameState.session_id, _on_inventory_loaded)


func _on_quick_save_requested() -> void:
	_save_session(QUICKSAVE_SLOT, false)


func _open_save_load_panel() -> void:
	save_load_panel.open_panel("Loading saves...")
	save_load_panel.set_default_slot(GameState.last_save_slot if not GameState.last_save_slot.is_empty() else QUICKSAVE_SLOT)
	_refresh_save_list()


func _on_save_requested(slot_name: String) -> void:
	_save_session(slot_name, true)


func _save_session(slot_name: String, keep_panel_open: bool) -> void:
	if GameState.session_id.is_empty():
		narrative_panel.append_system_text("[color=red]No active session to save.[/color]")
		return
	var normalized_slot = slot_name.strip_edges()
	if normalized_slot.is_empty():
		normalized_slot = GameState.last_save_slot if not GameState.last_save_slot.is_empty() else QUICKSAVE_SLOT
	if keep_panel_open:
		save_load_panel.set_status("Saving %s..." % normalized_slot)
	_set_waiting(true)
	Backend.save_game(GameState.session_id, _on_save_completed.bind(keep_panel_open), normalized_slot)


func _on_save_completed(data, keep_panel_open: bool) -> void:
	_set_waiting(false)
	if data == null:
		return
	var slot_name = str(data.get("slot_name", data.get("save_id", QUICKSAVE_SLOT)))
	GameState.last_save_slot = slot_name
	save_load_panel.set_default_slot(slot_name)
	save_load_panel.set_status("Saved %s." % slot_name)
	narrative_panel.append_system_text("[color=green]Saved to %s.[/color]" % slot_name)
	_remember_player_id()
	if keep_panel_open and save_load_panel.visible:
		_refresh_save_list()


func _refresh_save_list() -> void:
	if GameState.player.is_empty():
		save_load_panel.set_status("No active adventurer is available for save browsing.")
		save_load_panel.set_save_summaries([])
		return
	save_load_panel.set_busy(true)
	Backend.list_saves(_on_save_list_loaded)


func _on_save_list_loaded(data) -> void:
	save_load_panel.set_busy(false)
	if data == null or not (data is Array):
		save_load_panel.set_status("Failed to load save slots.")
		save_load_panel.set_save_summaries([])
		return
	save_load_panel.set_save_summaries(data)
	save_load_panel.set_status("%d save slot(s) ready." % data.size())


func _on_load_requested(save_id: String) -> void:
	if save_id.strip_edges().is_empty():
		return
	save_load_panel.set_status("Loading %s..." % save_id)
	_set_waiting(true)
	Backend.load_game(save_id, _on_load_completed.bind(save_id))


func _on_load_completed(data, requested_save_id: String) -> void:
	if data == null:
		_set_waiting(false)
		return
	var session_data = data.get("session_data", {})
	if not (session_data is Dictionary):
		_set_waiting(false)
		save_load_panel.set_status("Invalid save payload received.")
		return

	GameState.reset()
	narrative_panel.load_history([])
	GameState.update_from_response(session_data)
	GameState.last_save_slot = str(data.get("slot_name", requested_save_id))
	_remember_player_id()
	save_load_panel.close_panel()
	narrative_panel.append_system_text("[color=green]Loaded %s.[/color]" % GameState.last_save_slot)

	if GameState.session_id.is_empty():
		_set_waiting(false)
		return

	_pending_sync_callbacks = 3
	Backend.get_session(GameState.session_id, _on_loaded_session_resynced)
	Backend.get_map(GameState.session_id, _on_map_resynced)
	Backend.get_inventory(GameState.session_id, _on_inventory_resynced)


func _on_loaded_session_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	_complete_followup_sync()


func _on_delete_save_requested(save_id: String) -> void:
	if save_id.strip_edges().is_empty():
		return
	save_load_panel.set_busy(true)
	save_load_panel.set_status("Deleting %s..." % save_id)
	Backend.delete_save(save_id, _on_delete_save_completed.bind(save_id))


func _on_delete_save_completed(data, save_id: String) -> void:
	save_load_panel.set_busy(false)
	if data == null:
		return
	save_load_panel.set_status("Deleted %s." % save_id)
	_refresh_save_list()


func _on_save_load_closed() -> void:
	command_bar.focus_input()


func _remember_player_id() -> void:
	var player_name = str(GameState.player.get("name", "")).strip_edges()
	if player_name.is_empty():
		return
	var profile = ConfigFile.new()
	profile.set_value("profile", "last_player_id", player_name)
	profile.save(PROFILE_PATH)


func _map_has_tiles() -> bool:
	return GameState.map_data.has("tiles") and GameState.map_data.get("tiles", []) is Array and not GameState.map_data.get("tiles", []).is_empty()
