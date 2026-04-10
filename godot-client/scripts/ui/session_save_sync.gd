extends RefCounted
class_name SessionSaveSync



var _owner


func _init(owner) -> void:
	_owner = owner


func on_quick_save_requested() -> void:
	save_campaign(_owner.QUICKSAVE_SLOT, false)


func open_save_load_panel() -> void:
	_owner.save_load_panel.open_panel("Loading saves...")
	_owner.save_load_panel.set_default_slot(
		GameState.last_save_slot if not GameState.last_save_slot.is_empty() else _owner.QUICKSAVE_SLOT
	)
	refresh_save_list()


func on_save_requested(slot_name: String) -> void:
	save_campaign(slot_name, true)


func save_session(slot_name: String, keep_panel_open: bool) -> void:
	save_campaign(slot_name, keep_panel_open)


func save_campaign(slot_name: String, keep_panel_open: bool) -> void:
	if GameState.campaign_id.is_empty():
		if _owner != null and _owner.has_method("_append_narrative_system_text"):
			_owner._append_narrative_system_text("[color=red]No active campaign to save.[/color]")
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
	if _owner != null and _owner.has_method("_append_narrative_system_text"):
		_owner._append_narrative_system_text("[color=green]Saved to %s.[/color]" % slot_name)
	remember_player_id()
	remember_resume_player_id()
	remember_save_slot(slot_name)
	if keep_panel_open and _owner.save_load_panel.visible:
		refresh_save_list()


func refresh_save_list() -> void:
	var player_id := str(GameState.player.get("name", "")).strip_edges()
	if player_id.is_empty():
		player_id = ProfileStorage.preferred_resume_player_id()
	if player_id.is_empty():
		_owner.save_load_panel.set_status("No active adventurer is available for save browsing.")
		_owner.save_load_panel.set_save_summaries([])
		return
	_owner.save_load_panel.set_busy(true)
	Backend.list_player_campaign_saves(player_id, on_save_list_loaded)


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
	Backend.load_campaign(save_id, on_campaign_load_completed.bind(save_id))


func on_delete_save_requested(save_id: String) -> void:
	if save_id.strip_edges().is_empty():
		return
	_owner.save_load_panel.set_busy(true)
	_owner.save_load_panel.set_status("Deleting %s..." % save_id)
	Backend.delete_campaign_save(save_id, on_delete_save_completed.bind(save_id))


func on_delete_save_completed(data, save_id: String) -> void:
	_owner.save_load_panel.set_busy(false)
	if data == null:
		return
	_owner.save_load_panel.set_status("Deleted %s." % save_id)
	refresh_save_list()


func on_save_load_closed() -> void:
	if _owner != null and _owner.has_method("_sync_shell_state"):
		_owner._sync_shell_state()


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
	if _owner != null and _owner.has_method("_load_narrative_history"):
		_owner._load_narrative_history([])
	GameState.update_from_response(data)
	GameState.seed_campaign_resume_narrative(str(data.get("narrative", "")))
	if _owner != null and _owner.has_method("_load_narrative_history"):
		_owner._load_narrative_history(GameState.narrative_history)
	GameState.last_save_slot = requested_save_id
	remember_player_id()
	remember_resume_player_id()
	remember_save_slot(requested_save_id)
	_owner.save_load_panel.close_panel()
	if _owner != null and _owner.has_method("_append_narrative_system_text"):
		_owner._append_narrative_system_text("[color=green]Loaded %s.[/color]" % GameState.last_save_slot)
	_owner._set_waiting(false)
