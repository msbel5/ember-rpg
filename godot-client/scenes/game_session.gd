extends Control

@onready var narrative_panel: RichTextLabel = $MainLayout/ContentSplit/NarrativePanel
@onready var text_input: LineEdit = $MainLayout/InputBar/TextInput
@onready var send_btn: Button = $MainLayout/InputBar/SendButton
@onready var player_status: HBoxContainer = $MainLayout/PlayerStatus
@onready var hp_bar: ProgressBar = $MainLayout/PlayerStatus/HPBar
@onready var hp_label: Label = $MainLayout/PlayerStatus/HPLabel
@onready var player_info: Label = $MainLayout/PlayerStatus/PlayerInfo
@onready var xp_bar: ProgressBar = $MainLayout/PlayerStatus/XPBar
@onready var combat_hud: PanelContainer = $CombatHUD
@onready var combat_list: VBoxContainer = $CombatHUD/VBox/CombatantList
@onready var combat_round: Label = $CombatHUD/VBox/RoundLabel
@onready var map_viewer: Panel = $MainLayout/ContentSplit/MapPanel
@onready var location_label: Label = $MainLayout/ContentSplit/MapPanel/LocationLabel

var tile_map_renderer: Control = null
var is_waiting: bool = false

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

	# Create tile map renderer in the map panel
	var renderer_script = load("res://scripts/tile_map_renderer.gd")
	tile_map_renderer = Control.new()
	tile_map_renderer.set_script(renderer_script)
	tile_map_renderer.set_anchors_preset(Control.PRESET_FULL_RECT)
	tile_map_renderer.entity_clicked.connect(_on_entity_clicked)
	tile_map_renderer.tile_clicked.connect(_on_tile_clicked)
	map_viewer.add_child(tile_map_renderer)

	# Show initial narrative
	if not GameState.narrative_history.is_empty():
		for line in GameState.narrative_history:
			_append_narrative(line)

	_refresh_player_status()

	# Auto-enter the starting scene
	if GameState.session_id != "":
		_enter_scene("harbor_town")

	text_input.grab_focus()

func _enter_scene(location_name: String) -> void:
	print("[DEBUG] enter_scene called. session_id='%s', location='%s'" % [GameState.session_id, location_name])
	var display_name = location_name.replace("_", " ").capitalize()
	_append_narrative("[color=gray]Entering %s...[/color]" % display_name)
	Backend.enter_scene(GameState.session_id, location_name, _on_scene_entered)

func _on_scene_entered(data) -> void:
	if data == null:
		print("[DEBUG] scene_entered: data is NULL — backend returned error")
		_append_narrative("[color=red]Failed to enter scene.[/color]")
		return
	print("[DEBUG] scene_entered: got data, keys=%s" % str(data.keys()))
	GameState.update_from_response(data)

func _on_entity_clicked(entity_id: String, entity_data: Dictionary) -> void:
	var entity_name = entity_data.get("name", "Unknown")
	var actions = entity_data.get("context_actions", [])
	if actions.is_empty():
		_submit_action("examine %s" % entity_name.to_lower())
		return
	# Show context menu popup
	var popup = PopupMenu.new()
	popup.name = "EntityContextMenu"
	for i in range(actions.size()):
		popup.add_item(actions[i].capitalize(), i)
	add_child(popup)
	popup.id_pressed.connect(func(id: int):
		var action_name = actions[id]
		_submit_action("%s %s" % [action_name, entity_name.to_lower()])
		popup.queue_free()
	)
	popup.popup_on_parent(Rect2i(get_viewport().get_mouse_position(), Vector2i(120, 0)))
	popup.popup_hide.connect(popup.queue_free)

func _on_tile_clicked(tx: int, ty: int) -> void:
	_submit_action("move to %d,%d" % [tx, ty])

func _on_text_submitted(text: String) -> void:
	_submit_action(text)

func _on_send_pressed() -> void:
	_submit_action(text_input.text)

func _submit_action(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or is_waiting:
		return

	is_waiting = true
	_append_narrative("[color=cyan]> %s[/color]" % text)
	text_input.text = ""

	Backend.submit_action(GameState.session_id, text, _on_action_response)

	# Timeout indicator
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		_append_narrative("[color=gray][The DM is thinking...][/color]")

func _on_action_response(data) -> void:
	is_waiting = false
	if data == null:
		return

	GameState.update_from_response(data)
	text_input.grab_focus()

var _typing_queue: Array[String] = []
var _is_typing: bool = false

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
	# Type character by character with small delay
	var chars_added = 0
	for c in text:
		narrative_panel.append_text(c)
		chars_added += 1
		if chars_added % 3 == 0:  # Every 3 chars, scroll and tiny pause
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

func _refresh_player_status() -> void:
	var p = GameState.player
	if p.is_empty():
		return

	var name = p.get("name", "Unknown")
	var level = p.get("level", 1)
	var classes = p.get("classes", {})
	var char_class = ""
	for c in classes:
		char_class = c.capitalize()
		break

	player_info.text = "Lv.%d %s  %s" % [level, char_class, name]

	var hp = p.get("hp", 0)
	var max_hp = p.get("max_hp", 1)
	hp_bar.max_value = max_hp
	hp_bar.value = hp
	hp_label.text = "%d/%d" % [hp, max_hp]

	var xp = int(p.get("xp", 0))
	xp_bar.max_value = 100
	xp_bar.value = xp % 100

func _refresh_location() -> void:
	location_label.text = GameState.get_display_location()

func _refresh_combat_hud() -> void:
	if not GameState.is_in_combat():
		combat_hud.visible = false
		return

	combat_hud.visible = true
	var cs = GameState.combat_state
	combat_round.text = "Round %d" % cs.get("round", 1)

	# Clear old entries
	for child in combat_list.get_children():
		child.queue_free()

	# Add combatants
	var combatants = cs.get("combatants", [])
	for c in combatants:
		var hbox = HBoxContainer.new()

		var name_label = Label.new()
		name_label.text = c.get("name", "?")
		name_label.custom_minimum_size.x = 120
		hbox.add_child(name_label)

		var hp_progress = ProgressBar.new()
		hp_progress.max_value = c.get("max_hp", 1)
		hp_progress.value = c.get("hp", 0)
		hp_progress.custom_minimum_size.x = 150
		hp_progress.show_percentage = false
		hbox.add_child(hp_progress)

		var hp_text = Label.new()
		hp_text.text = " %d/%d" % [c.get("hp", 0), c.get("max_hp", 1)]
		hbox.add_child(hp_text)

		if c.get("dead", false):
			name_label.add_theme_color_override("font_color", Color.RED)

		combat_list.add_child(hbox)

func _on_combat_started() -> void:
	_append_narrative("[color=red]⚔ Combat begins![/color]")

func _on_combat_ended() -> void:
	combat_hud.visible = false
	_append_narrative("[color=green]Combat ended.[/color]")

func _on_level_up(new_level: int) -> void:
	_append_narrative("[color=yellow]✦ LEVEL UP! You are now level %d! ✦[/color]" % new_level)

func _on_backend_error(message: String) -> void:
	_append_narrative("[color=red][%s][/color]" % message)
