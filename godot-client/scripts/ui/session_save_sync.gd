extends RefCounted
class_name SessionSaveSync

const ProfileStorage = preload("res://scripts/ui/profile_storage.gd")


var _owner


func _init(owner) -> void:
	_owner = owner


func on_quick_save_requested() -> void:
	save_session(_owner.QUICKSAVE_SLOT, false)


func open_save_load_panel() -> void:
	_owner.save_load_panel.open_panel("Loading saves...")
	_owner.save_load_panel.set_default_slot(
		GameState.last_save_slot if not GameState.last_save_slot.is_empty() else _owner.QUICKSAVE_SLOT
	)
	refresh_save_list()


func on_save_requested(slot_name: String) -> void:
	save_session(slot_name, true)


func save_session(slot_name: String, keep_panel_open: bool) -> void:
	if GameState.has_active_campaign():
		save_campaign(slot_name, keep_panel_open)
		return
	if GameState.session_id.is_empty():
		_owner.narrative_panel.append_system_text("[color=red]No active session to save.[/color]")
		return
	var normalized_slot := slot_name.strip_edges()
	if normalized_slot.is_empty():
		normalized_slot = GameState.last_save_slot if not GameState.last_save_slot.is_empty() else _owner.QUICKSAVE_SLOT
	if keep_panel_open:
		_owner.save_load_panel.set_status("Saving %s..." % normalized_slot)
	_owner._set_waiting(true)
	Backend.save_game(GameState.session_id, on_save_completed.bind(keep_panel_open), normalized_slot)


func save_campaign(slot_name: String, keep_panel_open: bool) -> void:
	if GameState.campaign_id.is_empty():
		_owner.narrative_panel.append_system_text("[color=red]No active campaign to save.[/color]")
		return
	var normalized_slot := slot_name.strip_edges()
	if normalized_slot.is_empty():
		normalized_slot = GameState.last_save_slot if not GameState.last_save_slot.is_empty() else _owner.QUICKSAVE_SLOT
	if keep_panel_open:
		_owner.save_load_panel.set_status("Saving %s..." % normalized_slot)
	_owner._set_waiting(true)
	Backend.save_campaign(GameState.campaign_id, on_save_completed.bind(keep_panel_open), normalized_slot)


func on_save_completed(data, keep_panel_open: bool) -> void:
	_owner._set_waiting(false)
	if data == null:
		return
	var slot_name := str(data.get("slot_name", data.get("save_id", _owner.QUICKSAVE_SLOT)))
	GameState.last_save_slot = slot_name
	_owner.save_load_panel.set_default_slot(slot_name)
	_owner.save_load_panel.set_status("Saved %s." % slot_name)
	_owner.narrative_panel.append_system_text("[color=green]Saved to %s.[/color]" % slot_name)
	remember_player_id()
	remember_resume_player_id()
	remember_save_slot(slot_name)
	if keep_panel_open and _owner.save_load_panel.visible:
		refresh_save_list()


func refresh_save_list() -> void:
	if GameState.has_active_campaign():
		if GameState.campaign_id.is_empty():
			_owner.save_load_panel.set_status("No active campaign is available for save browsing.")
			_owner.save_load_panel.set_save_summaries([])
			return
		_owner.save_load_panel.set_busy(true)
		Backend.list_campaign_saves(GameState.campaign_id, on_save_list_loaded)
		return
	if GameState.player.is_empty():
		_owner.save_load_panel.set_status("No active adventurer is available for save browsing.")
		_owner.save_load_panel.set_save_summaries([])
		return
	_owner.save_load_panel.set_busy(true)
	Backend.list_saves(on_save_list_loaded)


func on_save_list_loaded(data) -> void:
	_owner.save_load_panel.set_busy(false)
	if data == null or not (data is Array):
		_owner.save_load_panel.set_status("Failed to load save slots.")
		_owner.save_load_panel.set_save_summaries([])
		return
	_owner.save_load_panel.set_save_summaries(data)
	_owner.save_load_panel.set_status("%d save slot(s) ready." % data.size())


func on_load_requested(save_id: String) -> void:
	if save_id.strip_edges().is_empty():
		return
	_owner.save_load_panel.set_status("Loading %s..." % save_id)
	_owner._set_waiting(true)
	if GameState.has_active_campaign():
		Backend.load_campaign(save_id, on_campaign_load_completed.bind(save_id))
	else:
		Backend.load_game(save_id, on_load_completed.bind(save_id))


func on_load_completed(data, requested_save_id: String) -> void:
	if data == null:
		_owner._set_waiting(false)
		return
	var session_data = data.get("session_data", {})
	if not (session_data is Dictionary):
		_owner._set_waiting(false)
		_owner.save_load_panel.set_status("Invalid save payload received.")
		return
	GameState.reset()
	_owner.narrative_panel.load_history([])
	GameState.update_from_response(session_data)
	GameState.last_save_slot = str(data.get("slot_name", requested_save_id))
	remember_player_id()
	remember_resume_player_id()
	_owner.save_load_panel.close_panel()
	_owner.narrative_panel.append_system_text("[color=green]Loaded %s.[/color]" % GameState.last_save_slot)
	if GameState.session_id.is_empty():
		_owner._set_waiting(false)
		return
	_owner._pending_sync_callbacks = 3
	Backend.get_session(GameState.session_id, on_loaded_session_resynced)
	Backend.get_map(GameState.session_id, _owner._world_sync.on_map_resynced)
	Backend.get_inventory(GameState.session_id, _owner._world_sync.on_inventory_resynced)


func on_loaded_session_resynced(data) -> void:
	if data != null:
		GameState.update_from_response(data)
	_owner._world_sync.complete_followup_sync()


func on_delete_save_requested(save_id: String) -> void:
	if save_id.strip_edges().is_empty():
		return
	_owner.save_load_panel.set_busy(true)
	_owner.save_load_panel.set_status("Deleting %s..." % save_id)
	Backend.delete_save(save_id, on_delete_save_completed.bind(save_id))


func on_delete_save_completed(data, save_id: String) -> void:
	_owner.save_load_panel.set_busy(false)
	if data == null:
		return
	_owner.save_load_panel.set_status("Deleted %s." % save_id)
	refresh_save_list()


func on_save_load_closed() -> void:
	_owner.command_bar.focus_input()


func remember_player_id() -> void:
	var player_name := str(GameState.player.get("name", "")).strip_edges()
	if not player_name.is_empty():
		ProfileStorage.store_last_player_id(player_name)
		ProfileStorage.store_last_adapter_id(GameState.adapter_id)


func remember_resume_player_id() -> void:
	var player_name := str(GameState.player.get("name", "")).strip_edges()
	if not player_name.is_empty():
		ProfileStorage.store_last_resume_player_id(player_name)


func remember_save_slot(save_id: String) -> void:
	save_id = save_id.strip_edges()
	if not save_id.is_empty():
		ProfileStorage.store_last_campaign_save_id(save_id)


func on_campaign_load_completed(data, requested_save_id: String) -> void:
	if data == null:
		_owner._set_waiting(false)
		return
	GameState.reset()
	_owner.narrative_panel.load_history([])
	GameState.update_from_response(data)
	GameState.seed_campaign_resume_narrative(str(data.get("narrative", "")))
	_owner.narrative_panel.load_history(GameState.narrative_history)
	GameState.last_save_slot = requested_save_id
	remember_player_id()
	remember_resume_player_id()
	remember_save_slot(requested_save_id)
	_owner.save_load_panel.close_panel()
	_owner.narrative_panel.append_system_text("[color=green]Loaded %s.[/color]" % GameState.last_save_slot)
	_owner._set_waiting(false)
