extends PanelContainer
class_name CombatOverlay

signal command_requested(command_text: String)
signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)
signal combat_ended_ui()

var _round_label: Label
var _active_label: Label
var _summary_label: Label
var _turn_order_bar: HBoxContainer
var _action_row: HBoxContainer
var _combatant_list: VBoxContainer
var _owner_surface: Control
var _is_active: bool = false
var _is_waiting: bool = false
var _action_buttons: Dictionary = {}


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
	_refresh(GameState.combat_state)


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

	_action_row = HBoxContainer.new()
	_action_row.name = "QuickActions"
	_action_row.add_theme_constant_override("separation", 8)
	vbox.add_child(_action_row)

	for action_def in [
		{"id": "attack", "node_name": "AttackButton", "label": "Attack"},
		{"id": "defend", "node_name": "DefendButton", "label": "Defend"},
		{"id": "end_turn", "node_name": "EndTurnButton", "label": "End Turn"},
		{"id": "flee", "node_name": "FleeButton", "label": "Flee"},
	]:
		var button := Button.new()
		button.name = str(action_def["node_name"])
		button.text = str(action_def["label"])
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size = Vector2(0, 32)
		button.visible = false
		button.pressed.connect(_on_action_button_pressed.bind(button))
		_action_row.add_child(button)
		_action_buttons[str(action_def["id"])] = button

	var scroll := ScrollContainer.new()
	scroll.name = "CombatantScroll"
	scroll.custom_minimum_size = Vector2(0, 112)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)

	_combatant_list = VBoxContainer.new()
	_combatant_list.name = "CombatantList"
	_combatant_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_combatant_list)


func _refresh(combat_state: Dictionary) -> void:
	if combat_state.is_empty() or bool(combat_state.get("ended", false)):
		hide_combat()
		_clear_rows()
		_clear_turn_order()
		_refresh_action_buttons({})
		return

	var combatants: Array = combat_state.get("combatants", [])
	_round_label.text = "Round %d" % int(combat_state.get("round", 1))
	_active_label.text = "Turn: %s" % _resolve_turn_actor_name(combat_state)
	var phase := str(combat_state.get("phase", "active_turn")).replace("_", " ").capitalize()
	var living_enemies := _living_enemies(combatants)
	var visible_actions := _supported_visible_actions(combat_state)
	var action_summary := ", ".join(visible_actions.map(func(action_id: String) -> String:
		return action_id.replace("_", " ").capitalize()
	))
	if action_summary.is_empty():
		action_summary = "No direct shell actions"
	_summary_label.text = "%s  |  %d hostiles  |  %s" % [phase, living_enemies.size(), action_summary]
	_refresh_action_buttons(combat_state)

	_clear_turn_order()
	var active_actor_id := _current_turn_actor_id(combat_state)
	var turn_order = combat_state.get("turn_order", combatants)
	for combatant in turn_order:
		if combatant is Dictionary:
			_turn_order_bar.add_child(_build_turn_chip(combatant, active_actor_id))

	_clear_rows()
	for combatant in combatants:
		if combatant is Dictionary:
			_combatant_list.add_child(_build_row(combatant, active_actor_id))


func _refresh_action_buttons(combat_state: Dictionary) -> void:
	var supported := _supported_visible_actions(combat_state)
	var player_turn := _is_player_turn(combat_state)
	var attack_target := _first_attack_target(combat_state)
	for action_id in _action_buttons.keys():
		var button: Button = _action_buttons[action_id]
		button.visible = false
		button.disabled = true
		button.set_meta("shortcut", "")
		button.set_meta("args", {})
		button.set_meta("history_text", "")
		button.tooltip_text = ""

	if supported.has("attack") and not attack_target.is_empty():
		var attack_button: Button = _action_buttons["attack"]
		var attack_target_name := _target_display_name(attack_target)
		attack_button.visible = true
		attack_button.disabled = _is_waiting or not player_turn
		attack_button.tooltip_text = "Attack %s" % attack_target_name
		attack_button.set_meta("shortcut", "combat")
		attack_button.set_meta("args", {
			"action_id": "attack",
			"target_id": str(attack_target.get("actor_id", "")),
		})
		attack_button.set_meta("history_text", "attack %s" % attack_target_name.to_lower())

	for simple_action in ["defend", "end_turn", "flee"]:
		if not supported.has(simple_action):
			continue
		var button: Button = _action_buttons[simple_action]
		button.visible = true
		button.disabled = _is_waiting or not player_turn
		button.tooltip_text = button.text
		button.set_meta("shortcut", "combat")
		button.set_meta("args", {"action_id": simple_action})
		button.set_meta("history_text", simple_action)


func _supported_visible_actions(combat_state: Dictionary) -> Array[String]:
	var visible_actions: Array[String] = []
	var raw_actions = combat_state.get("available_actions", [])
	if not (raw_actions is Array):
		return visible_actions
	for raw_action in raw_actions:
		var action_id := str(raw_action).strip_edges().to_lower()
		if action_id in ["attack", "defend", "flee", "end_turn"] and not visible_actions.has(action_id):
			visible_actions.append(action_id)
	return visible_actions


func _build_turn_chip(combatant: Dictionary, active_actor_id: String) -> Control:
	var slot := PanelContainer.new()
	slot.custom_minimum_size = Vector2(92, 28)
	var style := StyleBoxFlat.new()
	var is_current := str(combatant.get("actor_id", "")).strip_edges() == active_actor_id
	style.bg_color = Color(0.80, 0.32, 0.26, 0.45) if is_current else Color(0.20, 0.18, 0.22, 0.60)
	style.set_corner_radius_all(4)
	if is_current:
		style.border_color = Color(0.96, 0.86, 0.56)
		style.set_border_width_all(1)
	slot.add_theme_stylebox_override("panel", style)
	var label := Label.new()
	label.text = _combatant_name(combatant)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 11)
	slot.add_child(label)
	return slot


func _build_row(combatant: Dictionary, active_actor_id: String) -> Control:
	var row := VBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var top := HBoxContainer.new()
	row.add_child(top)

	var name_label := Label.new()
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.text = _combatant_name(combatant)
	if str(combatant.get("actor_id", "")).strip_edges() == active_actor_id:
		name_label.add_theme_color_override("font_color", Color(0.96, 0.86, 0.56))
	top.add_child(name_label)

	var detail := Label.new()
	detail.text = _combatant_turn_summary(combatant)
	top.add_child(detail)

	var hp := ProgressBar.new()
	hp.max_value = maxi(int(combatant.get("max_hp", 1)), 1)
	hp.value = int(combatant.get("hp", 0))
	hp.show_percentage = false
	hp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(hp)

	return row


func _combatant_name(combatant: Dictionary) -> String:
	return str(combatant.get("name", combatant.get("actor_id", "?")))


func _living_enemies(combatants: Array) -> Array:
	var enemies: Array = []
	for combatant in combatants:
		if not (combatant is Dictionary):
			continue
		if bool(combatant.get("is_player", false)):
			continue
		if not _combatant_is_alive(combatant):
			continue
		enemies.append(combatant)
	return enemies


func _combatant_is_alive(combatant: Dictionary) -> bool:
	if combatant.has("alive"):
		return bool(combatant.get("alive", true))
	return not bool(combatant.get("dead", false))


func _player_actor_id() -> String:
	var actor_id := str(GameState.player.get("actor_id", "")).strip_edges()
	if actor_id.is_empty():
		return "player"
	return actor_id


func _current_turn_actor_id(combat_state: Dictionary) -> String:
	return str(combat_state.get("turn_actor_id", "")).strip_edges()


func _resolve_turn_actor_name(combat_state: Dictionary) -> String:
	var turn_actor_id := _current_turn_actor_id(combat_state)
	for combatant in combat_state.get("combatants", []):
		if combatant is Dictionary and str(combatant.get("actor_id", "")).strip_edges() == turn_actor_id:
			return _combatant_name(combatant)
	return str(combat_state.get("active", turn_actor_id if not turn_actor_id.is_empty() else "Unknown"))


func _is_player_turn(combat_state: Dictionary) -> bool:
	var turn_actor_id := _current_turn_actor_id(combat_state)
	if not turn_actor_id.is_empty():
		return turn_actor_id == _player_actor_id()
	var player_name := str(GameState.player.get("name", "")).strip_edges()
	return not player_name.is_empty() and _resolve_turn_actor_name(combat_state) == player_name


func _first_attack_target(combat_state: Dictionary) -> Dictionary:
	var targets = combat_state.get("targets", [])
	if targets is Array:
		for target in targets:
			if target is Dictionary and str(target.get("actor_id", "")).strip_edges() != _player_actor_id():
				return target
	for combatant in combat_state.get("combatants", []):
		if combatant is Dictionary and not bool(combatant.get("is_player", false)) and _combatant_is_alive(combatant):
			return combatant
	return {}


func _target_display_name(target: Dictionary) -> String:
	return str(target.get("name", target.get("actor_id", "target"))).strip_edges()


func _combatant_turn_summary(combatant: Dictionary) -> String:
	var turn_resources: Dictionary = combatant.get("turn_resources", {})
	if turn_resources.is_empty():
		return "HP %d/%d" % [int(combatant.get("hp", 0)), int(combatant.get("max_hp", 1))]
	var action_text = "Act ready" if bool(turn_resources.get("action_available", false)) else "Act spent"
	return "HP %d/%d  |  %s  |  Move %d/%d" % [
		int(combatant.get("hp", 0)),
		int(combatant.get("max_hp", 1)),
		action_text,
		int(turn_resources.get("movement_remaining", 0)),
		int(turn_resources.get("speed", 0)),
	]


func _clear_rows() -> void:
	for child in _combatant_list.get_children():
		child.queue_free()


func _clear_turn_order() -> void:
	for child in _turn_order_bar.get_children():
		child.queue_free()


func _on_action_button_pressed(button: Button) -> void:
	var shortcut := str(button.get_meta("shortcut", "")).strip_edges()
	var history_text := str(button.get_meta("history_text", "")).strip_edges()
	var args = button.get_meta("args", {})
	if shortcut.is_empty() or not (args is Dictionary):
		return
	structured_action_requested.emit(shortcut, args, history_text)


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
