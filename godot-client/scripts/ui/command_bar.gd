extends PanelContainer
class_name CommandBarWidget

signal command_submitted(command_text: String)
signal quick_save_requested
signal saves_requested

@onready var history_label: Label = $CommandVBox/HistoryLabel
@onready var text_input: LineEdit = $CommandVBox/InputRow/TextInput
@onready var send_btn: Button = $CommandVBox/InputRow/SendButton
@onready var quick_save_btn: Button = $CommandVBox/InputRow/QuickSaveButton
@onready var saves_btn: Button = $CommandVBox/InputRow/SavesButton

var _history: Array[String] = []


func _ready() -> void:
	text_input.text_submitted.connect(_on_text_submitted)
	send_btn.pressed.connect(_on_send_pressed)
	quick_save_btn.pressed.connect(func() -> void:
		quick_save_requested.emit()
	)
	saves_btn.pressed.connect(func() -> void:
		saves_requested.emit()
	)
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
	quick_save_btn.disabled = waiting
	saves_btn.disabled = waiting


func submit_command(text: String) -> void:
	_emit_command(text)
	clear_input()


func remember_command(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	if not _history.is_empty() and _history[_history.size() - 1] == text:
		return
	_history.append(text)
	if _history.size() > 6:
		_history.pop_front()
	_refresh_history()


func _on_text_submitted(text: String) -> void:
	_emit_command(text)


func _on_send_pressed() -> void:
	_emit_command(text_input.text)


func _emit_command(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	remember_command(text)
	command_submitted.emit(text)


func _refresh_history() -> void:
	if _history.is_empty():
		history_label.text = "Recent: none"
		return
	history_label.text = "Recent: %s" % " | ".join(_history.slice(maxi(_history.size() - 3, 0), _history.size()))
