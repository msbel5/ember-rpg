extends PanelContainer
class_name CommandBarWidget

signal command_submitted(command_text: String)

@onready var history_label: Label = $CommandVBox/HistoryLabel
@onready var text_input: LineEdit = $CommandVBox/InputRow/TextInput
@onready var send_btn: Button = $CommandVBox/InputRow/SendButton

var _history: Array[String] = []


func _ready() -> void:
	text_input.text_submitted.connect(_on_text_submitted)
	send_btn.pressed.connect(_on_send_pressed)
	_refresh_history()


func focus_input() -> void:
	text_input.grab_focus()


func clear_input() -> void:
	text_input.text = ""


func has_input_focus() -> bool:
	return text_input.has_focus()


func set_waiting(waiting: bool) -> void:
	text_input.editable = not waiting
	send_btn.disabled = waiting


func submit_command(text: String) -> void:
	_emit_command(text)
	clear_input()


func _on_text_submitted(text: String) -> void:
	_emit_command(text)


func _on_send_pressed() -> void:
	_emit_command(text_input.text)


func _emit_command(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	_history.append(text)
	if _history.size() > 6:
		_history.pop_front()
	_refresh_history()
	command_submitted.emit(text)


func _refresh_history() -> void:
	if _history.is_empty():
		history_label.text = "Recent: none"
		return
	history_label.text = "Recent: %s" % " | ".join(_history.slice(maxi(_history.size() - 3, 0), _history.size()))
