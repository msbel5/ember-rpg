extends PanelContainer
class_name TopicProbeModal

signal close_requested()
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


func set_topics(entries: Array, selected_topic_id: String = "") -> void:
	_topic_entries = entries.duplicate(true)
	_selected_topic_id = selected_topic_id.strip_edges()
	if _selected_topic_id.is_empty() and not _topic_entries.is_empty():
		_selected_topic_id = str((_topic_entries[0] as Dictionary).get("topic_id", "")).strip_edges()
	_refresh()


func show_modal() -> void:
	_refresh()
	visible = true
	grab_focus()


func hide_modal() -> void:
	visible = false
	close_requested.emit()


func _gui_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		hide_modal()
		get_viewport().set_input_as_handled()


func _refresh() -> void:
	title_label.text = "Ask About"
	summary_label.text = "%d discovered topic(s) available from the current speaker." % _topic_entries.size()
	for child in topic_list.get_children():
		child.queue_free()
	if _topic_entries.is_empty():
		var empty_label := Label.new()
		empty_label.text = "No deterministic ask-about topics are currently available."
		empty_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		topic_list.add_child(empty_label)
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
		row.text = str(entry.get("label", topic_id))
		row.alignment = HORIZONTAL_ALIGNMENT_LEFT
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.tooltip_text = str(entry.get("subtitle", ""))
		if topic_id == _selected_topic_id:
			row.text = "• %s" % row.text
		row.pressed.connect(_select_topic.bind(topic_id))
		topic_list.add_child(row)
	_select_topic(_selected_topic_id)


func _select_topic(topic_id: String) -> void:
	_selected_topic_id = topic_id.strip_edges()
	var selected_entry := _selected_entry()
	if selected_entry.is_empty():
		detail_text.text = "Select a discovered topic to ask about it."
		confirm_button.disabled = true
		return
	detail_text.text = "[b]%s[/b]\n%s\n\nStructured dialog ask_about is used when the host surface listens for it." % [
		str(selected_entry.get("label", _selected_topic_id)),
		str(selected_entry.get("subtitle", "Known topic")),
	]
	confirm_button.disabled = _selected_topic_id.is_empty()
	for child in topic_list.get_children():
		if child is Button:
			var button := child as Button
			var base_text := button.text.trim_prefix("• ")
			button.text = "• %s" % base_text if base_text == str(selected_entry.get("label", _selected_topic_id)) else base_text


func _selected_entry() -> Dictionary:
	for entry in _topic_entries:
		if entry is Dictionary and str(entry.get("topic_id", "")).strip_edges() == _selected_topic_id:
			return entry
	return {}


func _confirm_selection() -> void:
	if _selected_topic_id.is_empty():
		return
	topic_submitted.emit(_selected_topic_id)
	var history_text := "ask about %s" % str(_selected_entry().get("label", _selected_topic_id)).to_lower()
	if get_signal_connection_list("structured_action_requested").is_empty():
		command_requested.emit("ask about %s" % _selected_topic_id)
	else:
		structured_action_requested.emit("dialog", {"action_id": "ask_about", "topic_id": _selected_topic_id}, history_text)
	hide_modal()
