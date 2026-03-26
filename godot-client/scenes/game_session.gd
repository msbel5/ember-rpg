extends Control

const GameSessionHelpers = preload("res://scripts/game_session_helpers.gd")

@onready var world_view: SubViewportContainer = $MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer
@onready var narrative_panel: RichTextLabel = $MainMargin/MainVBox/ContentSplit/Sidebar/NarrativePanel/NarrativeMargin/NarrativeVBox/NarrativeLog
@onready var inventory_summary: Label = $MainMargin/MainVBox/ContentSplit/Sidebar/InventoryPanel/InventoryMargin/InventoryVBox/InventorySummary
@onready var minimap_summary: Label = $MainMargin/MainVBox/ContentSplit/Sidebar/MinimapPanel/MinimapMargin/MinimapVBox/MinimapSummary
@onready var quest_summary: Label = $MainMargin/MainVBox/ContentSplit/Sidebar/QuestPanel/QuestMargin/QuestVBox/QuestSummary
@onready var text_input: LineEdit = $MainMargin/MainVBox/CommandBar/InputRow/TextInput
@onready var send_btn: Button = $MainMargin/MainVBox/CommandBar/InputRow/SendButton
@onready var hp_bar: ProgressBar = $MainMargin/MainVBox/StatusBar/StatusRow/HPBar
@onready var hp_label: Label = $MainMargin/MainVBox/StatusBar/StatusRow/HPLabel
@onready var player_info: Label = $MainMargin/MainVBox/StatusBar/StatusRow/PlayerInfo
@onready var xp_bar: ProgressBar = $MainMargin/MainVBox/StatusBar/StatusRow/XPBar
@onready var location_label: Label = $MainMargin/MainVBox/StatusBar/StatusRow/LocationLabel
@onready var combat_hud: PanelContainer = $OverlayCanvas/CombatHUD
@onready var combat_list: VBoxContainer = $OverlayCanvas/CombatHUD/CombatMargin/CombatVBox/CombatantList
@onready var combat_round: Label = $OverlayCanvas/CombatHUD/CombatMargin/CombatVBox/RoundLabel

var is_waiting: bool = false
var _typing_queue: Array[String] = []
var _is_typing: bool = false
var _inventory_popup: PopupPanel = null


func _ready() -> void:
	combat_hud.visible = false
	text_input.text_submitted.connect(_on_text_submitted)
	send_btn.pressed.connect(_on_send_pressed)

	GameState.narrative_received.connect(_on_narrative)
	GameState.state_updated.connect(_on_state_updated)
	GameState.combat_started.connect(_on_combat_started)
	GameState.combat_ended.connect(_on_combat_ended)
	GameState.level_up_occurred.connect(_on_level_up)
	Backend.request_error.connect(_on_backend_error)

	if not GameState.narrative_history.is_empty():
		for line in GameState.narrative_history:
			_append_narrative(line)

	_refresh_player_status()
	_refresh_location()
	_refresh_combat_hud()
	_refresh_sidebar_placeholders()

	if GameState.session_id != "" and GameState.map_data.is_empty():
		_enter_scene(GameState.location if not GameState.location.is_empty() else "Harbor Town")

	text_input.grab_focus()


func _enter_scene(location_name: String) -> void:
	var display_name = location_name.replace("_", " ").capitalize()
	_append_narrative("[color=gray]Entering %s...[/color]" % display_name)
	Backend.enter_scene(GameState.session_id, location_name, _on_scene_entered)


func _on_scene_entered(data) -> void:
	if data == null:
		_append_narrative("[color=red]Failed to enter scene.[/color]")
		return

	GameState.update_from_response(data)
	if (not data.has("player") or not data["player"].has("position")) and GameState.map_data.has("spawn_point"):
		var spawn_point = GameState.map_data.get("spawn_point", [])
		if spawn_point is Array and spawn_point.size() >= 2:
			GameState.player_map_pos = Vector2i(int(spawn_point[0]), int(spawn_point[1]))
	if GameState.map_data.is_empty():
		Backend.get_map(GameState.session_id, _on_map_loaded)


func _on_map_loaded(data) -> void:
	if data == null:
		return
	GameState.update_from_response(data)


func _on_text_submitted(text: String) -> void:
	_submit_action(text)


func _on_send_pressed() -> void:
	_submit_action(text_input.text)


func _submit_action(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or is_waiting:
		return
	if GameState.session_id.is_empty():
		_append_narrative("[color=red]No active session. Start a new adventure.[/color]")
		return

	var hp = int(GameState.player.get("hp", 1))
	if hp <= 0 and not text.to_lower().begins_with("rest"):
		_append_narrative("[color=red]You have fallen. Type 'rest' to recover or start anew.[/color]")
		return

	_set_waiting(true)
	_append_narrative("[color=cyan]> %s[/color]" % text)
	text_input.text = ""
	Backend.submit_action(GameState.session_id, text, _on_action_response)
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		_append_narrative("[color=gray][The DM is thinking...][/color]")


func _on_action_response(data) -> void:
	_set_waiting(false)
	if data == null:
		return

	GameState.update_from_response(data)
	text_input.grab_focus()


func _set_waiting(waiting: bool) -> void:
	is_waiting = waiting
	send_btn.disabled = waiting
	text_input.editable = not waiting


func _on_narrative(text: String) -> void:
	_typing_queue.append(text)
	if not _is_typing:
		_process_typing_queue()


func _process_typing_queue() -> void:
	_is_typing = true
	while not _typing_queue.is_empty():
		var text = _typing_queue.pop_front()
		await _type_text(text)
	_is_typing = false


func _type_text(text: String) -> void:
	var index = 0
	var chars_added = 0
	while index < text.length():
		if text[index] == "[":
			var end_index = text.find("]", index)
			if end_index != -1:
				narrative_panel.append_text(text.substr(index, end_index - index + 1))
				index = end_index + 1
				continue
		narrative_panel.append_text(text[index])
		index += 1
		chars_added += 1
		if chars_added % 3 == 0:
			await get_tree().process_frame
	narrative_panel.append_text("\n\n")
	await get_tree().process_frame
	narrative_panel.scroll_to_line(narrative_panel.get_line_count())


func _append_narrative(text: String) -> void:
	narrative_panel.append_text(text + "\n\n")
	await get_tree().process_frame
	narrative_panel.scroll_to_line(narrative_panel.get_line_count())


func _on_state_updated() -> void:
	_refresh_player_status()
	_refresh_location()
	_refresh_combat_hud()
	_refresh_sidebar_placeholders()


func _refresh_player_status() -> void:
	var p = GameState.player
	if p.is_empty():
		return

	var player_name = str(p.get("name", "Unknown"))
	var level = int(p.get("level", 1))
	var player_class_name = _resolve_class_name(p)
	player_info.text = "%s  Lv.%d %s" % [player_name, level, player_class_name]

	var hp = int(p.get("hp", 0))
	var max_hp = maxi(int(p.get("max_hp", 1)), 1)
	hp_bar.max_value = max_hp
	hp_bar.value = hp
	hp_label.text = "%d/%d" % [hp, max_hp]

	var xp = int(p.get("xp", 0))
	xp_bar.max_value = 100
	xp_bar.value = xp % 100


func _resolve_class_name(player_data: Dictionary) -> String:
	if player_data.has("classes") and player_data["classes"] is Dictionary and not player_data["classes"].is_empty():
		var class_keys = player_data["classes"].keys()
		return str(class_keys[0]).capitalize()
	if player_data.has("player_class"):
		return str(player_data["player_class"]).capitalize()
	return "Adventurer"


func _refresh_location() -> void:
	location_label.text = GameState.get_display_location()


func _refresh_sidebar_placeholders() -> void:
	var inventory_count = GameState.inventory_items.size()
	var gold = int(GameState.player.get("gold", 0))
	inventory_summary.text = "%d item(s) cached, %d gold" % [inventory_count, gold]

	var width = int(GameState.map_data.get("width", 48))
	var height = int(GameState.map_data.get("height", 36))
	minimap_summary.text = "Viewport online, map %dx%d" % [width, height]

	quest_summary.text = "%d active, %d available" % [GameState.active_quests.size(), GameState.quest_offers.size()]


func _refresh_combat_hud() -> void:
	if not GameState.is_in_combat():
		combat_hud.visible = false
		return

	combat_hud.visible = true
	var cs = GameState.combat_state
	combat_round.text = "Round %d" % int(cs.get("round", 1))
	for child in combat_list.get_children():
		child.queue_free()

	var combatants = cs.get("combatants", [])
	for combatant in combatants:
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
	_on_narrative("[color=red]Combat begins.[/color]")


func _on_combat_ended() -> void:
	combat_hud.visible = false
	_on_narrative("[color=green]Combat ended.[/color]")


func _on_level_up(new_level: int) -> void:
	_append_narrative("[color=yellow]Level up. You reached level %d.[/color]" % new_level)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return

	if event.keycode == KEY_HOME or event.keycode == KEY_I:
		_toggle_inventory()
		get_viewport().set_input_as_handled()
		return

	if event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER:
		text_input.grab_focus()
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

	if not text_input.has_focus():
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


func _toggle_inventory() -> void:
	if _inventory_popup and _inventory_popup.visible:
		_inventory_popup.hide()
		return

	var inventory = GameState.inventory_items
	if inventory.is_empty() and GameState.player.has("inventory") and GameState.player["inventory"] is Array:
		inventory = GameState.player["inventory"]
	var gold = int(GameState.player.get("gold", 0))

	if _inventory_popup:
		_inventory_popup.queue_free()

	_inventory_popup = GameSessionHelpers.build_inventory_popup(inventory, gold)
	add_child(_inventory_popup)
	_inventory_popup.popup_centered()


func _on_backend_error(message: String) -> void:
	_set_waiting(false)
	_append_narrative("[color=red][%s][/color]" % message)
