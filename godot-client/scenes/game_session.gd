extends Control

const ResponseNormalizer = preload("res://scripts/net/response_normalizer.gd")

@onready var world_view: SubViewportContainer = $MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer
@onready var narrative_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/NarrativePanel
@onready var command_bar = $MainMargin/MainVBox/CommandBar
@onready var quest_summary: Label = $MainMargin/MainVBox/ContentSplit/Sidebar/QuestPanel/QuestMargin/QuestVBox/QuestSummary
@onready var combat_hud: PanelContainer = $OverlayCanvas/CombatHUD
@onready var combat_list: VBoxContainer = $OverlayCanvas/CombatHUD/CombatMargin/CombatVBox/CombatantList
@onready var combat_round: Label = $OverlayCanvas/CombatHUD/CombatMargin/CombatVBox/RoundLabel

var is_waiting: bool = false
var _pending_sync_callbacks: int = 0


func _ready() -> void:
	combat_hud.visible = false
	command_bar.command_submitted.connect(_submit_action)
	world_view.command_requested.connect(_on_world_command_requested)

	GameState.state_updated.connect(_on_state_updated)
	GameState.combat_started.connect(_on_combat_started)
	GameState.combat_ended.connect(_on_combat_ended)
	GameState.level_up_occurred.connect(_on_level_up)
	Backend.request_error.connect(_on_backend_error)

	_refresh_combat_hud()
	_refresh_quest_summary()

	if GameState.session_id != "" and GameState.map_data.is_empty():
		_enter_scene(GameState.location if not GameState.location.is_empty() else "Harbor Town")

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


func _finish_turn_sync() -> void:
	_pending_sync_callbacks = 0
	_set_waiting(false)
	command_bar.focus_input()


func _on_state_updated() -> void:
	_refresh_combat_hud()
	_refresh_quest_summary()


func _refresh_quest_summary() -> void:
	quest_summary.text = "%d active, %d available" % [GameState.active_quests.size(), GameState.quest_offers.size()]


func _refresh_combat_hud() -> void:
	if not GameState.is_in_combat():
		combat_hud.visible = false
		return

	combat_hud.visible = true
	var combat_state = GameState.combat_state
	combat_round.text = "Round %d" % int(combat_state.get("round", 1))
	for child in combat_list.get_children():
		child.queue_free()

	for combatant in combat_state.get("combatants", []):
		var row = HBoxContainer.new()
		var name_label = Label.new()
		name_label.text = str(combatant.get("name", "?"))
		name_label.custom_minimum_size.x = 120
		row.add_child(name_label)

		var hp_progress = ProgressBar.new()
		hp_progress.max_value = maxi(int(combatant.get("max_hp", 1)), 1)
		hp_progress.value = int(combatant.get("hp", 0))
		hp_progress.custom_minimum_size.x = 140
		hp_progress.show_percentage = false
		row.add_child(hp_progress)

		var hp_text = Label.new()
		hp_text.text = "%d/%d" % [int(combatant.get("hp", 0)), int(combatant.get("max_hp", 1))]
		row.add_child(hp_text)

		if bool(combatant.get("dead", false)):
			name_label.add_theme_color_override("font_color", Color(0.9, 0.2, 0.2))

		combat_list.add_child(row)


func _on_combat_started() -> void:
	narrative_panel.append_system_text("[color=red]Combat begins.[/color]")


func _on_combat_ended() -> void:
	combat_hud.visible = false
	narrative_panel.append_system_text("[color=green]Combat ended.[/color]")


func _on_level_up(new_level: int) -> void:
	narrative_panel.append_system_text("[color=yellow]Level up. You reached level %d.[/color]" % new_level)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
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
