## Fallout-style dialog overlay — NPC text + player response buttons.
## Sits on top of the world viewport during conversations.
## Each player option is a full-width button (NOT a dropdown) showing
## skill check tags like "[CHA 14]" when requirements apply.
extends PanelContainer
class_name DialogOverlay

signal command_requested(command_text: String)
signal dialog_closed()

var _npc_name_label: Label
var _npc_text: RichTextLabel
var _options_container: VBoxContainer
var _close_button: Button
var _is_active: bool = false


func _ready() -> void:
	name = "DialogOverlay"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP

	# Semi-transparent dark panel covering bottom 40% of parent
	anchors_preset = Control.PRESET_BOTTOM_WIDE
	anchor_top = 0.55
	anchor_bottom = 1.0
	offset_top = 0
	offset_bottom = -8
	offset_left = 8
	offset_right = -8

	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.06, 0.05, 0.08, 0.94)
	bg.border_color = Color(0.80, 0.66, 0.39, 0.6)
	bg.border_width_top = 2
	bg.corner_radius_top_left = 8
	bg.corner_radius_top_right = 8
	bg.content_margin_left = 16
	bg.content_margin_right = 16
	bg.content_margin_top = 12
	bg.content_margin_bottom = 12
	add_theme_stylebox_override("panel", bg)

	var vbox := VBoxContainer.new()
	vbox.name = "DialogVBox"
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 8)
	add_child(vbox)

	# NPC name
	_npc_name_label = Label.new()
	_npc_name_label.name = "NpcNameLabel"
	_npc_name_label.add_theme_font_size_override("font_size", 18)
	_npc_name_label.add_theme_color_override("font_color", Color(0.80, 0.66, 0.26))
	vbox.add_child(_npc_name_label)

	# NPC text
	_npc_text = RichTextLabel.new()
	_npc_text.name = "NpcText"
	_npc_text.bbcode_enabled = true
	_npc_text.fit_content = true
	_npc_text.custom_minimum_size = Vector2(0, 60)
	_npc_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_npc_text.add_theme_font_size_override("normal_font_size", 16)
	_npc_text.add_theme_color_override("default_color", Color(0.92, 0.90, 0.85))
	vbox.add_child(_npc_text)

	# Separator
	var sep := HSeparator.new()
	sep.add_theme_constant_override("separation", 4)
	vbox.add_child(sep)

	# Player options
	var scroll := ScrollContainer.new()
	scroll.name = "OptionsScroll"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)

	_options_container = VBoxContainer.new()
	_options_container.name = "OptionsContainer"
	_options_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_options_container.add_theme_constant_override("separation", 4)
	scroll.add_child(_options_container)

	# Close / Goodbye button
	_close_button = Button.new()
	_close_button.name = "CloseButton"
	_close_button.text = "[Esc] Leave conversation"
	_close_button.add_theme_font_size_override("font_size", 14)
	_close_button.add_theme_color_override("font_color", Color(0.65, 0.62, 0.58))
	_close_button.pressed.connect(_on_close)
	vbox.add_child(_close_button)


func _unhandled_key_input(event: InputEvent) -> void:
	if not _is_active:
		return
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			_on_close()
			get_viewport().set_input_as_handled()
		elif event.keycode >= KEY_1 and event.keycode <= KEY_9:
			var index: int = int(event.keycode) - int(KEY_1)
			_select_option(index)
			get_viewport().set_input_as_handled()


## Show dialog overlay with NPC text and player response options.
## options: Array of {text, command, skill_check?, enabled, disabled_reason}
func show_dialog(npc_name: String, npc_text: String, options: Array) -> void:
	_npc_name_label.text = npc_name
	_npc_text.text = npc_text

	# Clear old options
	for child in _options_container.get_children():
		child.queue_free()

	# Build option buttons
	for i in range(options.size()):
		var opt: Dictionary = options[i] if options[i] is Dictionary else {}
		var btn := Button.new()
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT

		var skill_check = opt.get("skill_check", {})
		var check_tag := str(opt.get("check", "")).strip_edges()
		if skill_check is Dictionary and check_tag.is_empty():
			check_tag = str(skill_check.get("label", "")).strip_edges()
		var option_text := str(opt.get("text", "..."))
		var available := bool(opt.get("enabled", opt.get("available", true)))
		var command := str(opt.get("command", ""))
		var disabled_reason := str(opt.get("disabled_reason", "")).strip_edges()
		btn.name = "OptionButton%d" % i

		if not check_tag.is_empty():
			btn.text = "%d. [%s] %s" % [i + 1, check_tag, option_text]
		else:
			btn.text = "%d. %s" % [i + 1, option_text]

		btn.add_theme_font_size_override("font_size", 15)
		if available:
			btn.add_theme_color_override("font_color", Color(0.88, 0.86, 0.80))
			btn.pressed.connect(_on_option_selected.bind(command))
		else:
			btn.add_theme_color_override("font_color", Color(0.45, 0.43, 0.40))
			btn.disabled = true
			btn.tooltip_text = disabled_reason if not disabled_reason.is_empty() else "Requirement not met: %s" % check_tag

		btn.set_meta("command", command)
		_options_container.add_child(btn)

	_is_active = true
	visible = true
	if _options_container.get_child_count() > 0:
		_options_container.get_child(0).grab_focus()


func hide_dialog() -> void:
	_is_active = false
	visible = false
	dialog_closed.emit()


func is_dialog_active() -> bool:
	return _is_active


func _on_option_selected(command: String) -> void:
	if not command.is_empty():
		command_requested.emit(command)


func _on_close() -> void:
	hide_dialog()


func _select_option(index: int) -> void:
	if index < 0 or index >= _options_container.get_child_count():
		return
	var btn = _options_container.get_child(index)
	if btn is Button and not btn.disabled:
		var cmd := str(btn.get_meta("command", ""))
		if not cmd.is_empty():
			command_requested.emit(cmd)
