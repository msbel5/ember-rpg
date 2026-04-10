## Fallout-style dialog overlay — NPC text + player response buttons.
## Sits on top of the world viewport during conversations.
## Each player option is a full-width button (NOT a dropdown) showing
## skill check tags like "[CHA 14]" when requirements apply.
extends PanelContainer
class_name DialogOverlay

const TopicProbeModalScene = preload("res://scenes/components/topic_probe_modal.tscn")

signal command_requested(command_text: String)
signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)
signal ask_about_requested(topic_id: String)
signal transcript_requested(lines: Array)
signal trade_requested(store_id: String)
signal dialog_closed()

var _npc_name_label: Label
var _npc_text: RichTextLabel
var _options_container: VBoxContainer
var _action_row: HBoxContainer
var _ask_about_button: Button
var _transcript_button: Button
var _trade_button: Button
var _close_button: Button
var _topic_modal = null
var _transcript_modal: PopupPanel
var _transcript_text: RichTextLabel
var _is_active: bool = false
var _last_dialog_options: Array = []
var _dialog_metadata: Dictionary = {}


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

	_action_row = HBoxContainer.new()
	_action_row.name = "ActionRow"
	_action_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_action_row.add_theme_constant_override("separation", 8)
	vbox.add_child(_action_row)

	_ask_about_button = _make_side_button("AskAboutButton", "Ask About")
	_ask_about_button.pressed.connect(_on_ask_about_pressed)
	_action_row.add_child(_ask_about_button)

	_transcript_button = _make_side_button("TranscriptButton", "Transcript")
	_transcript_button.pressed.connect(_on_transcript_pressed)
	_action_row.add_child(_transcript_button)

	_trade_button = _make_side_button("TradeButton", "Trade")
	_trade_button.pressed.connect(_on_trade_pressed)
	_action_row.add_child(_trade_button)

	# Close / Goodbye button
	_close_button = Button.new()
	_close_button.name = "CloseButton"
	_close_button.text = "[Esc] Leave conversation"
	_close_button.add_theme_font_size_override("font_size", 14)
	_close_button.add_theme_color_override("font_color", Color(0.65, 0.62, 0.58))
	_close_button.pressed.connect(_on_close)
	vbox.add_child(_close_button)

	_topic_modal = TopicProbeModalScene.instantiate()
	_topic_modal.visible = false
	_topic_modal.close_requested.connect(_on_topic_modal_closed)
	_topic_modal.command_requested.connect(_emit_command)
	_topic_modal.topic_submitted.connect(_on_topic_submitted)
	_topic_modal.structured_action_requested.connect(_forward_structured_action)
	add_child(_topic_modal)

	_transcript_modal = PopupPanel.new()
	_transcript_modal.name = "TranscriptModal"
	_transcript_modal.visible = false
	_transcript_modal.size = Vector2i(620, 360)
	add_child(_transcript_modal)
	var transcript_margin := MarginContainer.new()
	transcript_margin.add_theme_constant_override("margin_left", 12)
	transcript_margin.add_theme_constant_override("margin_top", 12)
	transcript_margin.add_theme_constant_override("margin_right", 12)
	transcript_margin.add_theme_constant_override("margin_bottom", 12)
	_transcript_modal.add_child(transcript_margin)
	_transcript_text = RichTextLabel.new()
	_transcript_text.name = "TranscriptText"
	_transcript_text.bbcode_enabled = true
	_transcript_text.scroll_active = true
	_transcript_text.fit_content = false
	_transcript_text.custom_minimum_size = Vector2(596, 336)
	transcript_margin.add_child(_transcript_text)


func _unhandled_key_input(event: InputEvent) -> void:
	if not _is_active:
		return
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE:
			if _topic_modal != null and _topic_modal.visible:
				_topic_modal.hide_modal()
				get_viewport().set_input_as_handled()
				return
			if _transcript_modal != null and _transcript_modal.visible:
				_transcript_modal.hide()
				get_viewport().set_input_as_handled()
				return
			_on_close()
			get_viewport().set_input_as_handled()
		elif event.keycode >= KEY_1 and event.keycode <= KEY_9:
			var index: int = int(event.keycode) - int(KEY_1)
			_select_option(index)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_T:
			if _trade_button.visible and not _trade_button.disabled:
				_on_trade_pressed()
				get_viewport().set_input_as_handled()
		elif event.keycode == KEY_R:
			if _transcript_button.visible and not _transcript_button.disabled:
				_on_transcript_pressed()
				get_viewport().set_input_as_handled()
		elif event.keycode == KEY_A:
			if _ask_about_button.visible and not _ask_about_button.disabled:
				_on_ask_about_pressed()
				get_viewport().set_input_as_handled()


## Show dialog overlay with NPC text and player response options.
## options: Array of {text, command, skill_check?, enabled, disabled_reason}
func show_dialog(npc_name: String, npc_text: String, options: Array, metadata: Dictionary = {}) -> void:
	_npc_name_label.text = npc_name
	_npc_text.text = npc_text
	_dialog_metadata = metadata.duplicate(true)
	_last_dialog_options = options.duplicate(true)

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
	_refresh_side_actions()
	if _options_container.get_child_count() > 0:
		_options_container.get_child(0).grab_focus()


func hide_dialog() -> void:
	_is_active = false
	visible = false
	if _topic_modal != null:
		_topic_modal.hide_modal()
	if _transcript_modal != null:
		_transcript_modal.hide()
	dialog_closed.emit()


func is_dialog_active() -> bool:
	return _is_active


func _on_option_selected(command: String) -> void:
	if not command.is_empty():
		_emit_command(command)


func _on_close() -> void:
	var leave_command := _resolve_leave_command()
	if not leave_command.is_empty():
		_emit_command(leave_command)
		return
	hide_dialog()


func _select_option(index: int) -> void:
	if index < 0 or index >= _options_container.get_child_count():
		return
	var btn = _options_container.get_child(index)
	if btn is Button and not btn.disabled:
		var cmd := str(btn.get_meta("command", ""))
		if not cmd.is_empty():
			_emit_command(cmd)


func _make_side_button(button_name: String, button_text: String) -> Button:
	var button := Button.new()
	button.name = button_name
	button.text = button_text
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.add_theme_font_size_override("font_size", 14)
	return button


func _refresh_side_actions() -> void:
	var topic_entries := _topic_entries_from_state()
	var has_topics := not topic_entries.is_empty()
	_ask_about_button.visible = true
	_ask_about_button.disabled = not has_topics
	_ask_about_button.tooltip_text = "Ask about a discovered topic." if has_topics else "No discovered ask-about topics for this speaker."

	var transcript_lines := _conversation_transcript_lines()
	_transcript_button.visible = true
	_transcript_button.disabled = transcript_lines.is_empty()
	_transcript_button.tooltip_text = "Review the current conversation." if not transcript_lines.is_empty() else "No transcript lines recorded yet."

	var trade_context := _resolve_trade_context()
	_trade_button.visible = trade_context.get("enabled", false)
	_trade_button.disabled = not trade_context.get("enabled", false)
	_trade_button.tooltip_text = str(trade_context.get("tooltip", "Trade is unavailable."))

	if _topic_modal != null:
		_topic_modal.set_topics(topic_entries, _selected_topic_id_from_state())


func _topic_entries_from_state() -> Array:
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var topic_ids = conversation.get("ask_about_topic_ids", [])
	if not (topic_ids is Array):
		return []
	var selected_id := _selected_topic_id_from_state()
	var entries: Array = []
	for topic_id in topic_ids:
		var normalized_id := str(topic_id).strip_edges()
		if normalized_id.is_empty():
			continue
		entries.append({
			"topic_id": normalized_id,
			"label": _topic_label(normalized_id),
			"subtitle": _topic_category_label(normalized_id),
			"selected": normalized_id == selected_id,
		})
	return entries


func _selected_topic_id_from_state() -> String:
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var ask_about = conversation.get("ask_about", {})
	if ask_about is Dictionary:
		var topic = ask_about.get("topic", {})
		if topic is Dictionary:
			var nested_id := str(topic.get("topic_id", "")).strip_edges()
			if not nested_id.is_empty():
				return nested_id
	return str(conversation.get("ask_about_selected_topic_id", "")).strip_edges()


func _topic_label(topic_id: String) -> String:
	var tokens := topic_id.split(".")
	if tokens.size() >= 2:
		return _humanize_token(" ".join(tokens.slice(1, tokens.size())))
	return _humanize_token(topic_id)


func _topic_category_label(topic_id: String) -> String:
	var category := topic_id.split(".")[0] if topic_id.contains(".") else topic_id
	return _humanize_token(category)


func _humanize_token(value: String) -> String:
	var words: Array[String] = []
	for raw_word in value.replace(".", " ").replace("_", " ").split(" "):
		var word := str(raw_word).strip_edges()
		if word.is_empty():
			continue
		words.append(word.capitalize())
	return " ".join(words)


func _conversation_transcript_lines() -> Array:
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var transcript = conversation.get("transcript", [])
	var lines: Array = []
	if transcript is Array:
		for entry in transcript:
			if entry is Dictionary:
				var speaker := _normalized_line(entry.get("speaker", entry.get("role", "")))
				var text := _normalized_line(entry.get("text", entry.get("line", "")))
				if text.is_empty():
					continue
				lines.append("[b]%s[/b] %s" % [speaker if not speaker.is_empty() else "Line", text])
			else:
				var raw_text := _normalized_line(entry)
				if not raw_text.is_empty():
					lines.append(raw_text)
	if lines.is_empty():
		var npc_name := _normalized_line(_npc_name_label.text)
		var npc_text := _normalized_line(_npc_text.text)
		if not npc_name.is_empty() and not npc_text.is_empty():
			lines.append("[b]%s[/b] %s" % [npc_name, npc_text])
		for option in _last_dialog_options:
			if option is Dictionary:
				var option_text := _normalized_line(option.get("text", ""))
				if not option_text.is_empty():
					lines.append("[i]You:[/i] %s" % option_text)
	return lines


func _resolve_trade_context() -> Dictionary:
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var hinted_store_id := str(conversation.get("store_id", "")).strip_edges()
	if not hinted_store_id.is_empty():
		var hinted_store := GameState.store_by_id(hinted_store_id)
		if not hinted_store.is_empty():
			return _trade_context_from_store(hinted_store)
	var npc_id := str(conversation.get("npc_id", "")).strip_edges()
	var npc_name := str(conversation.get("npc_name", _npc_name_label.text)).strip_edges()
	for raw_store in GameState.stores:
		if not (raw_store is Dictionary):
			continue
		var store: Dictionary = raw_store
		if _store_matches_conversation(store, npc_id, npc_name):
			return _trade_context_from_store(store)
	return {
		"enabled": false,
		"tooltip": "Trade stays hidden until a verified live store route is exposed.",
	}


func _on_ask_about_pressed() -> void:
	if _topic_modal == null:
		return
	_topic_modal.set_topics(_topic_entries_from_state(), _selected_topic_id_from_state())
	_topic_modal.show_modal()


func _on_topic_modal_closed() -> void:
	if _options_container.get_child_count() > 0:
		_options_container.get_child(0).grab_focus()


func _on_topic_submitted(topic_id: String) -> void:
	ask_about_requested.emit(topic_id)


func _on_transcript_pressed() -> void:
	var lines := _conversation_transcript_lines()
	if lines.is_empty() or _transcript_modal == null or _transcript_text == null:
		return
	_transcript_text.clear()
	_transcript_text.text = "\n\n".join(lines)
	transcript_requested.emit(lines)
	_transcript_modal.popup_centered()


func _on_trade_pressed() -> void:
	var trade_context := _resolve_trade_context()
	if not trade_context.get("enabled", false):
		return
	var store_id := str(trade_context.get("store_id", "")).strip_edges()
	trade_requested.emit(store_id)
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var npc_name := str(conversation.get("npc_name", _npc_name_label.text)).strip_edges().to_lower()
	_emit_command("trade %s" % npc_name if not npc_name.is_empty() else "trade")


func _store_matches_conversation(store: Dictionary, npc_id: String, npc_name: String) -> bool:
	var store_npc_id := str(store.get("npc_id", "")).strip_edges()
	if not npc_id.is_empty() and not store_npc_id.is_empty() and store_npc_id == npc_id:
		return true
	var store_npc_name := str(store.get("npc_name", "")).strip_edges()
	if not npc_name.is_empty() and not store_npc_name.is_empty() and store_npc_name.to_lower() == npc_name.to_lower():
		return true
	return false


func _trade_context_from_store(store: Dictionary) -> Dictionary:
	var store_id := str(store.get("store_id", "")).strip_edges()
	var label := str(store.get("label", "Trader")).strip_edges()
	var services = store.get("services", [])
	var service_labels: Array[String] = []
	if services is Array:
		for service in services:
			if service is Dictionary:
				var service_label := str(service.get("label", "")).strip_edges()
				if not service_label.is_empty():
					service_labels.append(service_label)
	var tooltip := "Trade with %s." % label
	if not service_labels.is_empty():
		tooltip += " Services: %s." % ", ".join(service_labels.slice(0, 3))
	return {
		"enabled": not store_id.is_empty(),
		"store_id": store_id,
		"tooltip": tooltip,
	}


func _forward_structured_action(shortcut: String, args: Dictionary, history_text: String) -> void:
	structured_action_requested.emit(shortcut, args, history_text)


func _emit_command(command_text: String) -> void:
	command_requested.emit(command_text)


func _has_structured_connections() -> bool:
	return not get_signal_connection_list("structured_action_requested").is_empty()


func _normalized_line(value) -> String:
	if value == null:
		return ""
	var normalized := str(value).strip_edges()
	return "" if normalized == "<null>" else normalized


func _resolve_leave_command() -> String:
	for option in _last_dialog_options:
		if not (option is Dictionary):
			continue
		var command := str(option.get("command", "")).strip_edges()
		if command.is_empty():
			continue
		var transition_id := str(option.get("transition_id", "")).strip_edges().to_lower()
		var option_text := str(option.get("text", "")).strip_edges().to_lower()
		if transition_id.contains("leave") or transition_id.contains("goodbye"):
			return command
		if option_text.contains("maybe later") or option_text.contains("goodbye") or option_text.contains("leave"):
			return command
	return ""
