extends PanelContainer
class_name TopicProbeModal

const DialogOverlayState = preload("res://scripts/ui/dialog_overlay_state.gd")

signal close_requested()
signal topic_selected_changed(topic_id: String)
signal topic_submitted(topic_id: String)
signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)
signal command_requested(command_text: String)

@onready var title_label: Label = $ModalMargin/ModalVBox/HeaderRow/TitleLabel
@onready var summary_label: Label = $ModalMargin/ModalVBox/SummaryLabel
@onready var topic_list: VBoxContainer = $ModalMargin/ModalVBox/BodyRow/TopicScroll/TopicList
@onready var detail_text: RichTextLabel = $ModalMargin/ModalVBox/BodyRow/DetailPanel/DetailMargin/DetailText
@onready var confirm_button: Button = $ModalMargin/ModalVBox/FooterRow/ConfirmButton
@onready var close_button: Button = $ModalMargin/ModalVBox/FooterRow/CloseButton

var _topic_entries: Array = []
var _selected_topic_id: String = ""


func _ready() -> void:
	name = "TopicProbeModal"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	anchors_preset = Control.PRESET_CENTER
	custom_minimum_size = Vector2(640, 360)
	confirm_button.pressed.connect(_confirm_selection)
	close_button.pressed.connect(hide_modal)
	var game_state = get_node_or_null("/root/GameState")
	if game_state != null and game_state.has_signal("dialog_state_changed"):
		game_state.dialog_state_changed.connect(_on_dialog_state_changed)


func set_topics(entries: Array, selected_topic_id: String = "") -> void:
	_topic_entries.clear()
	for raw_entry in entries:
		var entry: Dictionary = DialogOverlayState.normalize_topic_entry(raw_entry)
		if entry.is_empty():
			continue
		_topic_entries.append(entry)
	_selected_topic_id = _resolve_initial_selection(selected_topic_id)
	_refresh()


func open_for_current_dialog(selected_topic_id: String = "") -> void:
	set_topics(DialogOverlayState.topic_entries_from_state(), selected_topic_id)
	show_modal()


func show_modal() -> void:
	_refresh()
	visible = true
	if not confirm_button.disabled:
		confirm_button.grab_focus()
	grab_focus()


func hide_modal() -> void:
	if not visible:
		return
	visible = false
	close_requested.emit()


func _gui_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_ESCAPE:
				hide_modal()
				get_viewport().set_input_as_handled()
			KEY_UP:
				_move_selection(-1)
				get_viewport().set_input_as_handled()
			KEY_DOWN:
				_move_selection(1)
				get_viewport().set_input_as_handled()
			KEY_HOME:
				_jump_selection(true)
				get_viewport().set_input_as_handled()
			KEY_END:
				_jump_selection(false)
				get_viewport().set_input_as_handled()
			KEY_PAGEUP:
				_move_selection(-10)
				get_viewport().set_input_as_handled()
			KEY_PAGEDOWN:
				_move_selection(10)
				get_viewport().set_input_as_handled()
			KEY_ENTER, KEY_KP_ENTER:
				_confirm_selection()
				get_viewport().set_input_as_handled()


func _refresh() -> void:
	title_label.text = "Ask About"
	var available_count := _available_topic_ids().size()
	summary_label.text = "%d discovered topic(s) available from the current speaker." % available_count
	for child in topic_list.get_children():
		child.queue_free()
	if _topic_entries.is_empty():
		var empty_button := Button.new()
		empty_button.text = "No deterministic ask-about topics are currently available."
		empty_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		empty_button.disabled = true
		empty_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		topic_list.add_child(empty_button)
		detail_text.text = "Pick a live dialogue target first."
		confirm_button.disabled = true
		return
	for entry in _topic_entries:
		if not (entry is Dictionary):
			continue
		var topic_id := str(entry.get("topic_id", "")).strip_edges()
		if topic_id.is_empty():
			continue
		var row := Button.new()
		var label := str(entry.get("label", topic_id)).strip_edges()
		var subtitle := str(entry.get("subtitle", "Known topic")).strip_edges()
		var category := str(entry.get("category", "topic")).strip_edges()
		var gating := str(entry.get("gating", "")).strip_edges()
		row.text = "%s\n[%s] %s" % [label, category.to_upper(), subtitle]
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.tooltip_text = gating if not gating.is_empty() else subtitle
		row.disabled = not gating.is_empty()
		row.set_meta("topic_id", topic_id)
		row.pressed.connect(_select_topic.bind(topic_id))
		topic_list.add_child(row)
	if _selected_topic_id.is_empty():
		_selected_topic_id = _resolve_initial_selection("")
	_select_topic(_selected_topic_id)


func _select_topic(topic_id: String) -> void:
	_selected_topic_id = topic_id.strip_edges()
	var selected_entry := _selected_entry()
	if selected_entry.is_empty():
		detail_text.text = "Select a discovered topic to ask about it."
		confirm_button.disabled = true
		return
	var gating := str(selected_entry.get("gating", "")).strip_edges()
	detail_text.text = "[b]%s[/b]\n%s\n\nStructured dialog ask_about is used when the host surface listens for it." % [
		str(selected_entry.get("label", _selected_topic_id)),
		str(selected_entry.get("subtitle", "Known topic")),
	]
	if not gating.is_empty():
		detail_text.text += "\n\n[i]Unavailable:[/i] %s" % gating
	confirm_button.disabled = _selected_topic_id.is_empty() or not gating.is_empty()
	topic_selected_changed.emit(_selected_topic_id)
	for child in topic_list.get_children():
		if child is Button:
			var button := child as Button
			var row_topic_id := str(button.get_meta("topic_id", "")).strip_edges()
			button.button_pressed = row_topic_id == _selected_topic_id and not button.disabled
			button.set_meta("selected", button.button_pressed)
			if row_topic_id == _selected_topic_id:
				button.grab_focus()


func _selected_entry() -> Dictionary:
	for entry in _topic_entries:
		if entry is Dictionary and str(entry.get("topic_id", "")).strip_edges() == _selected_topic_id:
			return entry
	return {}


func _confirm_selection() -> void:
	if _selected_topic_id.is_empty():
		return
	var selected_entry := _selected_entry()
	if not str(selected_entry.get("gating", "")).strip_edges().is_empty():
		return
	topic_submitted.emit(_selected_topic_id)
	var history_text := "ask about %s" % str(selected_entry.get("label", _selected_topic_id)).to_lower()
	if get_signal_connection_list("structured_action_requested").is_empty():
		command_requested.emit("ask about %s" % _selected_topic_id)
	else:
		structured_action_requested.emit("dialog", {"action_id": "ask_about", "topic_id": _selected_topic_id}, history_text)
	hide_modal()


func _resolve_initial_selection(preferred_topic_id: String) -> String:
	var preferred := preferred_topic_id.strip_edges()
	if not preferred.is_empty() and _entry_for_topic_id(preferred).get("gating", "") == "":
		return preferred
	var available := _available_topic_ids()
	if not available.is_empty():
		return str(available[0])
	if not _topic_entries.is_empty():
		return str((_topic_entries[0] as Dictionary).get("topic_id", "")).strip_edges()
	return ""


func _available_topic_ids() -> Array:
	var ids: Array = []
	for raw_entry in _topic_entries:
		if not (raw_entry is Dictionary):
			continue
		var entry: Dictionary = raw_entry
		if not str(entry.get("gating", "")).strip_edges().is_empty():
			continue
		var topic_id := str(entry.get("topic_id", "")).strip_edges()
		if not topic_id.is_empty():
			ids.append(topic_id)
	return ids


func _entry_for_topic_id(topic_id: String) -> Dictionary:
	for raw_entry in _topic_entries:
		if raw_entry is Dictionary and str(raw_entry.get("topic_id", "")).strip_edges() == topic_id:
			return raw_entry
	return {}


func _move_selection(delta: int) -> void:
	var available := _available_topic_ids()
	if available.is_empty():
		return
	var current_index := available.find(_selected_topic_id)
	if current_index == -1:
		current_index = 0
	else:
		current_index = clampi(current_index + delta, 0, available.size() - 1)
	_select_topic(str(available[current_index]))


func _jump_selection(to_first: bool) -> void:
	var available := _available_topic_ids()
	if available.is_empty():
		return
	_select_topic(str(available[0] if to_first else available[available.size() - 1]))


func _on_dialog_state_changed(_dialog_payload: Dictionary) -> void:
	if not visible:
		return
	var game_state = get_node_or_null("/root/GameState")
	if game_state == null or not game_state.has_method("has_active_dialog"):
		hide_modal()
		return
	if not bool(game_state.has_active_dialog()):
		hide_modal()
		return
	var topic_entries: Array = DialogOverlayState.topic_entries_from_state()
	if topic_entries.is_empty():
		hide_modal()
		return
	set_topics(topic_entries, _selected_topic_id)
