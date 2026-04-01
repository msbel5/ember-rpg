## Combat mode overlay — turn order bar + action buttons + floating damage.
## Appears over the world viewport when combat starts.
## Replaces the exploration action bar with combat-specific actions.
extends PanelContainer
class_name CombatOverlay

signal command_requested(command_text: String)
signal combat_ended_ui()

var _turn_order_bar: HBoxContainer
var _action_bar: HBoxContainer
var _combat_log: RichTextLabel
var _end_combat_label: Label
var _is_active: bool = false


func _ready() -> void:
	name = "CombatOverlay"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP

	# Top of world viewport
	anchors_preset = Control.PRESET_TOP_WIDE
	anchor_bottom = 0.0
	offset_bottom = 140

	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.08, 0.04, 0.04, 0.88)
	bg.border_color = Color(0.72, 0.22, 0.22, 0.6)
	bg.border_width_bottom = 2
	bg.content_margin_left = 12
	bg.content_margin_right = 12
	bg.content_margin_top = 8
	bg.content_margin_bottom = 8
	add_theme_stylebox_override("panel", bg)

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 6)
	add_child(vbox)

	# Turn order header
	var header := Label.new()
	header.text = "COMBAT"
	header.add_theme_font_size_override("font_size", 14)
	header.add_theme_color_override("font_color", Color(0.72, 0.22, 0.22))
	header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(header)

	# Turn order bar — portraits/icons of combatants
	_turn_order_bar = HBoxContainer.new()
	_turn_order_bar.add_theme_constant_override("separation", 4)
	_turn_order_bar.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_child(_turn_order_bar)

	# Action buttons
	_action_bar = HBoxContainer.new()
	_action_bar.add_theme_constant_override("separation", 8)
	_action_bar.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_child(_action_bar)

	_add_action_button("Attack (A)", "attack", KEY_A)
	_add_action_button("Spell (S)", "cast spell", KEY_S)
	_add_action_button("Item (I)", "use item", KEY_I)
	_add_action_button("Defend (D)", "defend", KEY_D)
	_add_action_button("Flee (F)", "flee", KEY_F)

	# End-of-combat label
	_end_combat_label = Label.new()
	_end_combat_label.text = ""
	_end_combat_label.add_theme_font_size_override("font_size", 12)
	_end_combat_label.add_theme_color_override("font_color", Color(0.65, 0.62, 0.58))
	_end_combat_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(_end_combat_label)

	if get_node_or_null("/root/GameState") != null:
		GameState.combat_started.connect(_on_combat_started)
		GameState.combat_ended.connect(_on_combat_ended)


func _unhandled_key_input(event: InputEvent) -> void:
	if not _is_active or not (event is InputEventKey) or not event.pressed:
		return
	match event.keycode:
		KEY_A: command_requested.emit("attack")
		KEY_S: command_requested.emit("cast spell")
		KEY_I: command_requested.emit("use item")
		KEY_D: command_requested.emit("defend")
		KEY_F: command_requested.emit("flee")
		_: return
	get_viewport().set_input_as_handled()


func show_combat(combat_state: Dictionary) -> void:
	_is_active = true
	visible = true
	_update_turn_order(combat_state)
	_end_combat_label.text = ""


func hide_combat() -> void:
	_is_active = false
	visible = false
	combat_ended_ui.emit()


func is_combat_active() -> bool:
	return _is_active


func show_damage_number(world_pos: Vector2, amount: int, is_heal: bool = false) -> void:
	# Floating damage text — added to the world viewport's overlay
	var label := Label.new()
	label.text = "+%d" % amount if is_heal else "-%d" % amount
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color(0.30, 0.80, 0.30) if is_heal else Color(0.95, 0.25, 0.25))
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	label.add_theme_constant_override("outline_size", 2)
	label.position = world_pos - Vector2(20, 30)
	label.z_index = 200
	add_child(label)
	var tween := create_tween()
	tween.tween_property(label, "position:y", label.position.y - 40, 1.0)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 1.0)
	tween.tween_callback(label.queue_free)


func _update_turn_order(combat_state: Dictionary) -> void:
	for child in _turn_order_bar.get_children():
		child.queue_free()
	var participants: Array = combat_state.get("turn_order", combat_state.get("participants", []))
	for p in participants:
		if not (p is Dictionary):
			continue
		var slot := PanelContainer.new()
		slot.custom_minimum_size = Vector2(80, 28)
		var slot_bg := StyleBoxFlat.new()
		var is_current := bool(p.get("is_current", false))
		slot_bg.bg_color = Color(0.72, 0.22, 0.22, 0.5) if is_current else Color(0.20, 0.18, 0.22, 0.5)
		slot_bg.corner_radius_top_left = 4
		slot_bg.corner_radius_top_right = 4
		slot_bg.corner_radius_bottom_left = 4
		slot_bg.corner_radius_bottom_right = 4
		if is_current:
			slot_bg.border_color = Color(0.95, 0.80, 0.30)
			slot_bg.border_width_bottom = 2
		slot.add_theme_stylebox_override("panel", slot_bg)
		var lbl := Label.new()
		lbl.text = str(p.get("name", "???"))
		lbl.add_theme_font_size_override("font_size", 11)
		lbl.add_theme_color_override("font_color", Color(0.90, 0.88, 0.82) if not is_current else Color(1.0, 0.95, 0.75))
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		slot.add_child(lbl)
		_turn_order_bar.add_child(slot)


func _add_action_button(text: String, command: String, _hotkey: int) -> void:
	var btn := Button.new()
	btn.text = text
	btn.custom_minimum_size = Vector2(100, 30)
	btn.add_theme_font_size_override("font_size", 13)
	btn.pressed.connect(func(): command_requested.emit(command))
	_action_bar.add_child(btn)


func _on_combat_started() -> void:
	show_combat(GameState.combat_state)


func _on_combat_ended() -> void:
	_end_combat_label.text = "Combat ended."
	await get_tree().create_timer(1.5).timeout
	hide_combat()
