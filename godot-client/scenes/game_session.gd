extends Control

@onready var narrative_panel: RichTextLabel = $MainLayout/ContentSplit/NarrativePanel
@onready var text_input: LineEdit = $MainLayout/InputBar/TextInput
@onready var send_btn: Button = $MainLayout/InputBar/SendButton
@onready var player_status: HBoxContainer = $MainLayout/PlayerStatus
@onready var hp_bar: ProgressBar = $MainLayout/PlayerStatus/HPBar
@onready var hp_label: Label = $MainLayout/PlayerStatus/HPLabel
@onready var player_info: Label = $MainLayout/PlayerStatus/PlayerInfo
@onready var xp_bar: ProgressBar = $MainLayout/PlayerStatus/XPBar
@onready var combat_hud: PanelContainer = $MainLayout/ContentSplit/MapPanel/CombatHUD
@onready var combat_list: VBoxContainer = $MainLayout/ContentSplit/MapPanel/CombatHUD/VBox/CombatantList
@onready var combat_round: Label = $MainLayout/ContentSplit/MapPanel/CombatHUD/VBox/RoundLabel
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
	GameState.entity_revealed.connect(_on_entity_revealed)
	Backend.request_error.connect(_on_backend_error)

	# Create tile map renderer in the map panel
	var renderer_script = load("res://scripts/tile_map_renderer.gd")
	tile_map_renderer = Control.new()
	tile_map_renderer.set_script(renderer_script)
	tile_map_renderer.set_anchors_preset(Control.PRESET_FULL_RECT)
	tile_map_renderer.entity_clicked.connect(_on_entity_clicked)
	tile_map_renderer.tile_clicked.connect(_on_tile_clicked)
	map_viewer.add_child(tile_map_renderer)

	# Always tile map mode — no POV (3D SubViewport coming later)

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

	# Set initial player position (center of map or spawn point)
	if data.has("map_data"):
		var md = data["map_data"]
		var cx: int = int(md.get("width", 20)) / int(2)
		var cy: int = int(md.get("height", 15)) / int(2)
		if md.has("spawn_point"):
			var sp = md["spawn_point"]
			cx = int(sp[0])
			cy = int(sp[1])
		GameState.player_map_pos = Vector2i(cx, cy)
		GameState.player_facing = 2

	# Fallback: reveal remaining hidden entities after narrative completes
	await get_tree().create_timer(3.0).timeout
	if tile_map_renderer:
		tile_map_renderer.reveal_all()

func _on_entity_clicked(_entity_id: String, entity_data: Dictionary) -> void:
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

	# Death check — HP 0 means you can't act
	var hp = GameState.player.get("hp", 1)
	if hp <= 0 and not text.to_lower().begins_with("rest"):
		_append_narrative("[color=red]You have fallen... Your vision fades to darkness.[/color]")
		_append_narrative("[color=gray](Type 'rest' to recover at the nearest shrine, or start a new adventure.)[/color]")
		return

	is_waiting = true
	_append_narrative("[color=cyan]> %s[/color]" % text)
	text_input.text = ""

	# Parse move commands to update player position for POV
	_parse_move_command(text)

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

	# Update POV with backend player position if available
	# ONLY accept non-zero positions (backend sends [0,0] when tracking not implemented)
	if data.has("player") and data["player"].has("position"):
		var pos = data["player"]["position"]
		var bx = int(pos[0])
		var by = int(pos[1])
		if bx > 0 or by > 0:  # Skip [0,0] placeholder
			GameState.player_map_pos = Vector2i(bx, by)
	if data.has("player") and data["player"].has("facing"):
		var facing_str = data["player"].get("facing", "")
		if facing_str != "":
			match facing_str:
				"north": GameState.player_facing = 0
				"east": GameState.player_facing = 1
				"south": GameState.player_facing = 2
				"west": GameState.player_facing = 3

	# Update tile map player marker
	if tile_map_renderer:
		tile_map_renderer.queue_redraw()
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
	# Type character by character, but preserve BBCode tags as whole units
	var i = 0
	var chars_added = 0
	while i < text.length():
		if text[i] == "[":
			# Find closing bracket — append entire tag at once
			var end = text.find("]", i)
			if end != -1:
				narrative_panel.append_text(text.substr(i, end - i + 1))
				i = end + 1
				continue
		narrative_panel.append_text(text[i])
		i += 1
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
	_refresh_pov()

func _refresh_pov() -> void:
	if tile_map_renderer:
		tile_map_renderer.queue_redraw()

func _parse_move_command(text: String) -> void:
	var lower = text.to_lower().strip_edges()

	# Direction-based moves: "move north", "go south", "move forward"
	var dir_map = {"north": Vector2i(0, -1), "south": Vector2i(0, 1),
		"east": Vector2i(1, 0), "west": Vector2i(-1, 0),
		"up": Vector2i(0, -1), "down": Vector2i(0, 1),
		"left": Vector2i(-1, 0), "right": Vector2i(1, 0)}
	var facing_map = {"north": 0, "south": 2, "east": 1, "west": 3,
		"up": 0, "down": 2, "left": 3, "right": 1}

	for dir_name in dir_map:
		if lower.contains(dir_name):
			var delta = dir_map[dir_name]
			GameState.player_facing = facing_map[dir_name]
			GameState.player_map_pos += delta
			# Clamp to map bounds
			GameState.player_map_pos.x = clampi(GameState.player_map_pos.x, 0, 19)
			GameState.player_map_pos.y = clampi(GameState.player_map_pos.y, 0, 14)
			return

	# "forward" uses current facing
	if lower.contains("forward"):
		var fv = [Vector2i(0,-1), Vector2i(1,0), Vector2i(0,1), Vector2i(-1,0)]
		GameState.player_map_pos += fv[GameState.player_facing]
		GameState.player_map_pos.x = clampi(GameState.player_map_pos.x, 0, 19)
		GameState.player_map_pos.y = clampi(GameState.player_map_pos.y, 0, 14)
		return

	# "move to X,Y" or "move to X Y"
	if lower.begins_with("move to ") or lower.begins_with("move "):
		var coord_str = lower.replace("move to ", "").replace("move ", "")
		var parts = coord_str.split(",")
		if parts.size() < 2:
			parts = coord_str.split(" ")
		if parts.size() >= 2:
			var tx = parts[0].strip_edges().to_int()
			var ty = parts[1].strip_edges().to_int()
			if tx >= 0 and ty >= 0:
				var new_pos = Vector2i(tx, ty)
				# Calculate facing direction BEFORE updating position
				var delta = new_pos - GameState.player_map_pos
				if abs(delta.x) > abs(delta.y):
					GameState.player_facing = 1 if delta.x > 0 else 3
				elif delta.y != 0:
					GameState.player_facing = 2 if delta.y > 0 else 0
				GameState.player_map_pos = new_pos

func _refresh_player_status() -> void:
	var p = GameState.player
	if p.is_empty():
		return

	var player_name = p.get("name", "Unknown")
	var level = p.get("level", 1)
	var classes = p.get("classes", {})
	var char_class = ""
	for c in classes:
		char_class = c.capitalize()
		break

	player_info.text = "Lv.%d %s  %s" % [level, char_class, player_name]

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
	pass  # Location label already updated above

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
	# Use typing queue so combat announcement doesn't interrupt narrative
	_on_narrative("[color=red]⚔ Combat begins![/color]")

func _on_combat_ended() -> void:
	combat_hud.visible = false
	_on_narrative("[color=green]Combat ended.[/color]")

func _on_level_up(new_level: int) -> void:
	_append_narrative("[color=yellow]✦ LEVEL UP! You are now level %d! ✦[/color]" % new_level)

func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return

	# HOME key or I — toggle inventory
	if event.keycode == KEY_HOME or event.keycode == KEY_I:
		_toggle_inventory()
		get_viewport().set_input_as_handled()
		return

	# ENTER key → focus text input to type command
	if event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER:
		text_input.grab_focus()
		get_viewport().set_input_as_handled()
		return

	# M key — toggle map visibility (only when not typing)
	if event.keycode == KEY_M and not text_input.has_focus():
		map_viewer.visible = not map_viewer.visible
		get_viewport().set_input_as_handled()

var _inventory_popup: PopupPanel = null

func _toggle_inventory() -> void:
	if _inventory_popup and _inventory_popup.visible:
		_inventory_popup.hide()
		return

	# Fetch inventory from GameState
	var inventory = GameState.player.get("inventory", [])
	var gold = GameState.player.get("gold", 0)

	if _inventory_popup:
		_inventory_popup.queue_free()

	_inventory_popup = PopupPanel.new()
	var vbox = VBoxContainer.new()
	vbox.custom_minimum_size = Vector2(300, 200)

	# Title
	var title = Label.new()
	title.text = "⚔ Inventory"
	title.add_theme_font_size_override("font_size", 18)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	vbox.add_child(title)

	# Gold
	var gold_label = Label.new()
	gold_label.text = "💰 Gold: %d" % gold
	gold_label.add_theme_color_override("font_color", Color(1, 0.9, 0.4))
	vbox.add_child(gold_label)

	# Separator
	var sep = HSeparator.new()
	vbox.add_child(sep)

	# Items
	if inventory.is_empty():
		var empty_label = Label.new()
		empty_label.text = "Your pack is empty."
		empty_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.6))
		vbox.add_child(empty_label)
	else:
		for item in inventory:
			var item_label = Label.new()
			var item_name = item if item is String else item.get("name", str(item))
			item_label.text = "• %s" % item_name
			vbox.add_child(item_label)

	_inventory_popup.add_child(vbox)
	add_child(_inventory_popup)
	_inventory_popup.popup_centered()

func _on_entity_revealed(entity_id: String) -> void:
	if tile_map_renderer:
		tile_map_renderer.reveal_entity(entity_id)

func _on_backend_error(message: String) -> void:
	_append_narrative("[color=red][%s][/color]" % message)
