## Single authoritative combat surface for the gameplay shell.
## Added programmatically under OverlayCanvas as "CombatPanel".
extends PanelContainer
class_name CombatOverlay

signal command_requested(command_text: String)
signal combat_ended_ui()

var _round_label: Label
var _active_label: Label
var _summary_label: Label
var _turn_order_bar: HBoxContainer
var _combatant_list: VBoxContainer
var _attack_button: Button
var _defend_button: Button
var _use_button: Button
var _disengage_button: Button
var _flee_button: Button
var _owner_surface: Control
var _is_active: bool = false
var _is_waiting: bool = false


func _ready() -> void:
	name = "CombatPanel"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	_build_ui()
	if get_node_or_null("/root/GameState") != null:
		GameState.combat_started.connect(_on_combat_started)
		GameState.combat_ended.connect(_on_combat_ended)
		GameState.state_updated.connect(_on_state_updated)
	_update_layout()


func attach_to_surface(surface: Control) -> void:
	_owner_surface = surface
	if _owner_surface != null:
		_owner_surface.resized.connect(_update_layout)
		_owner_surface.visibility_changed.connect(_update_layout)
	_update_layout()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	_refresh_buttons(GameState.combat_state)


func is_combat_active() -> bool:
	return _is_active


func show_combat(combat_state: Dictionary) -> void:
	_is_active = true
	visible = true
	_update_layout()
	_refresh(combat_state)


func hide_combat() -> void:
	_is_active = false
	visible = false
	combat_ended_ui.emit()


func show_damage_number(world_pos: Vector2, amount: int, is_heal: bool = false) -> void:
	var label := Label.new()
	label.text = "+%d" % amount if is_heal else "-%d" % amount
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color(0.30, 0.80, 0.30) if is_heal else Color(0.95, 0.25, 0.25))
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 2)
	label.position = world_pos - Vector2(20, 30)
	label.z_index = 200
	add_child(label)
	var tween := create_tween()
	tween.tween_property(label, "position:y", label.position.y - 40, 1.0)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 1.0)
	tween.tween_callback(label.queue_free)


func _build_ui() -> void:
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.10, 0.05, 0.06, 0.94)
	bg.border_color = Color(0.80, 0.30, 0.24, 0.60)
	bg.set_border_width_all(1)
	bg.content_margin_left = 12
	bg.content_margin_right = 12
	bg.content_margin_top = 10
	bg.content_margin_bottom = 10
	add_theme_stylebox_override("panel", bg)

	var margin := MarginContainer.new()
	margin.name = "CombatMargin"
	margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(margin)

	var vbox := VBoxContainer.new()
	vbox.name = "CombatVBox"
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 8)
	margin.add_child(vbox)

	var header_row := HBoxContainer.new()
	header_row.name = "HeaderRow"
	vbox.add_child(header_row)

	_round_label = Label.new()
	_round_label.name = "RoundLabel"
	_round_label.add_theme_font_size_override("font_size", 15)
	header_row.add_child(_round_label)

	_active_label = Label.new()
	_active_label.name = "ActiveLabel"
	_active_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_active_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_active_label.add_theme_font_size_override("font_size", 15)
	header_row.add_child(_active_label)

	_summary_label = Label.new()
	_summary_label.name = "SummaryLabel"
	_summary_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary_label.add_theme_font_size_override("font_size", 13)
	vbox.add_child(_summary_label)

	_turn_order_bar = HBoxContainer.new()
	_turn_order_bar.name = "TurnOrderBar"
	_turn_order_bar.add_theme_constant_override("separation", 6)
	vbox.add_child(_turn_order_bar)

	var action_row := HBoxContainer.new()
	action_row.name = "QuickActions"
	action_row.add_theme_constant_override("separation", 8)
	vbox.add_child(action_row)

	_attack_button = _make_action_button("AttackButton", "Attack", "attack")
	action_row.add_child(_attack_button)
	_defend_button = _make_action_button("DefendButton", "Defend", "defend")
	action_row.add_child(_defend_button)
	_use_button = _make_action_button("UseButton", "Use", "use item")
	action_row.add_child(_use_button)
	_disengage_button = _make_action_button("DisengageButton", "Disengage", "disengage")
	action_row.add_child(_disengage_button)
	_flee_button = _make_action_button("FleeButton", "Flee", "flee")
	action_row.add_child(_flee_button)

	var scroll := ScrollContainer.new()
	scroll.name = "CombatantScroll"
	scroll.custom_minimum_size = Vector2(0, 112)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)

	_combatant_list = VBoxContainer.new()
	_combatant_list.name = "CombatantList"
	_combatant_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_combatant_list)


func _make_action_button(node_name: String, text: String, command: String) -> Button:
	var button := Button.new()
	button.name = node_name
	button.text = text
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0, 32)
	button.pressed.connect(func() -> void:
		command_requested.emit(command)
	)
	return button


func _refresh(combat_state: Dictionary) -> void:
	if combat_state.is_empty() or bool(combat_state.get("ended", false)):
		hide_combat()
		_clear_rows()
		return

	_round_label.text = "Round %d" % int(combat_state.get("round", 1))
	_active_label.text = "Turn: %s" % str(combat_state.get("active", "Unknown"))
	var combatants: Array = combat_state.get("combatants", [])
	var living_enemies := _living_enemies(combatants)
	var phase := str(combat_state.get("phase", "active_turn")).replace("_", " ").capitalize()
	_summary_label.text = "%s  |  %d hostiles  |  %d combatants" % [phase, living_enemies.size(), combatants.size()]
	_refresh_buttons(combat_state)

	_clear_rows()
	var turn_order = combat_state.get("turn_order", combatants)
	for child in _turn_order_bar.get_children():
		child.queue_free()
	for combatant in turn_order:
		if combatant is Dictionary:
			_turn_order_bar.add_child(_build_turn_chip(combatant, str(combat_state.get("active", ""))))
	for combatant in combatants:
		if combatant is Dictionary:
			_combatant_list.add_child(_build_row(combatant, str(combat_state.get("active", ""))))


func _refresh_buttons(combat_state: Dictionary) -> void:
	var is_player_turn = _is_player_turn(combat_state)
	var living_enemies := _living_enemies(combat_state.get("combatants", []))
	_attack_button.disabled = _is_waiting or living_enemies.is_empty() or not is_player_turn
	_defend_button.disabled = _is_waiting or not is_player_turn
	_use_button.disabled = _is_waiting or not is_player_turn
	_disengage_button.disabled = _is_waiting or not is_player_turn
	_flee_button.disabled = _is_waiting or not is_player_turn


func _build_turn_chip(combatant: Dictionary, active_name: String) -> Control:
	var slot := PanelContainer.new()
	slot.custom_minimum_size = Vector2(92, 28)
	var style := StyleBoxFlat.new()
	var is_current := str(combatant.get("name", "")) == active_name
	style.bg_color = Color(0.80, 0.32, 0.26, 0.45) if is_current else Color(0.20, 0.18, 0.22, 0.60)
	style.set_corner_radius_all(4)
	if is_current:
		style.border_color = Color(0.96, 0.86, 0.56)
		style.set_border_width_all(1)
	slot.add_theme_stylebox_override("panel", style)
	var label := Label.new()
	label.text = str(combatant.get("name", "???"))
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 11)
	slot.add_child(label)
	return slot


func _build_row(combatant: Dictionary, active_name: String) -> Control:
	var row := VBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var top := HBoxContainer.new()
	row.add_child(top)

	var name_label := Label.new()
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.text = str(combatant.get("name", "?"))
	if str(combatant.get("name", "")) == active_name:
		name_label.add_theme_color_override("font_color", Color(0.96, 0.86, 0.56))
	top.add_child(name_label)

	var detail := Label.new()
	detail.text = "HP %d/%d  AP %d" % [
		int(combatant.get("hp", 0)),
		int(combatant.get("max_hp", 1)),
		int(combatant.get("ap", 0)),
	]
	top.add_child(detail)

	var hp := ProgressBar.new()
	hp.max_value = maxi(int(combatant.get("max_hp", 1)), 1)
	hp.value = int(combatant.get("hp", 0))
	hp.show_percentage = false
	hp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(hp)

	return row


func _living_enemies(combatants: Array) -> Array:
	var enemies: Array = []
	for combatant in combatants:
		if not (combatant is Dictionary):
			continue
		if _is_player_combatant(combatant):
			continue
		if bool(combatant.get("dead", false)):
			continue
		enemies.append(combatant)
	return enemies


func _is_player_combatant(combatant: Dictionary) -> bool:
	return str(combatant.get("name", "")).strip_edges() == str(GameState.player.get("name", "")).strip_edges()


func _is_player_turn(combat_state: Dictionary) -> bool:
	return str(combat_state.get("active", "")).strip_edges() == str(GameState.player.get("name", "")).strip_edges()


func _clear_rows() -> void:
	for child in _combatant_list.get_children():
		child.queue_free()


func _on_combat_started() -> void:
	show_combat(GameState.combat_state)


func _on_combat_ended() -> void:
	hide_combat()


func _on_state_updated() -> void:
	if _is_active or GameState.is_in_combat():
		show_combat(GameState.combat_state)


func _update_layout() -> void:
	if _owner_surface == null or not is_instance_valid(_owner_surface):
		anchors_preset = Control.PRESET_TOP_WIDE
		offset_left = 12
		offset_top = 58
		offset_right = 380
		offset_bottom = 258
		return
	var rect := _owner_surface.get_global_rect()
	offset_left = rect.position.x + 12
	offset_top = rect.position.y + 12
	offset_right = rect.position.x + minf(rect.size.x * 0.42, 400.0)
	offset_bottom = rect.position.y + minf(rect.size.y * 0.34, 248.0)
