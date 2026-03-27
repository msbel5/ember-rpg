extends Control
class_name SaveLoadPanelWidget

signal save_requested(slot_name: String)
signal load_requested(save_id: String)
signal delete_requested(save_id: String)
signal refresh_requested
signal closed

@onready var status_label: Label = $ModalFrame/ModalMargin/ModalVBox/StatusLabel
@onready var slot_input: LineEdit = $ModalFrame/ModalMargin/ModalVBox/SaveRow/SlotInput
@onready var save_button: Button = $ModalFrame/ModalMargin/ModalVBox/SaveRow/SaveButton
@onready var refresh_button: Button = $ModalFrame/ModalMargin/ModalVBox/Toolbar/RefreshButton
@onready var close_button: Button = $ModalFrame/ModalMargin/ModalVBox/Toolbar/CloseButton
@onready var save_list: VBoxContainer = $ModalFrame/ModalMargin/ModalVBox/SaveScroll/SaveList

var _save_summaries: Array = []
var _is_busy: bool = false


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	save_button.pressed.connect(_on_save_pressed)
	refresh_button.pressed.connect(func() -> void:
		refresh_requested.emit()
	)
	close_button.pressed.connect(close_panel)


func open_panel(status_text: String = "Loading saves...") -> void:
	visible = true
	set_status(status_text)
	slot_input.grab_focus()


func close_panel() -> void:
	visible = false
	closed.emit()


func set_busy(busy: bool) -> void:
	_is_busy = busy
	save_button.disabled = busy
	refresh_button.disabled = busy
	slot_input.editable = not busy
	for row in save_list.get_children():
		if row is HBoxContainer:
			for child in row.get_children():
				if child is Button:
					child.disabled = busy


func set_status(text: String) -> void:
	status_label.text = text


func set_default_slot(slot_name: String) -> void:
	slot_input.placeholder_text = slot_name
	if slot_input.text.strip_edges().is_empty():
		slot_input.text = slot_name


func set_save_summaries(summaries: Array) -> void:
	_save_summaries = summaries.duplicate(true)
	_save_summaries.sort_custom(func(a, b): return str(a.get("timestamp", "")) > str(b.get("timestamp", "")))
	_rebuild_save_rows()


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		close_panel()
		get_viewport().set_input_as_handled()


func _on_save_pressed() -> void:
	if _is_busy:
		return
	save_requested.emit(slot_input.text.strip_edges())


func _rebuild_save_rows() -> void:
	for child in save_list.get_children():
		child.queue_free()

	if _save_summaries.is_empty():
		var empty_label = Label.new()
		empty_label.text = "No save slots found for this adventurer."
		empty_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		save_list.add_child(empty_label)
		return

	for summary in _save_summaries:
		if not (summary is Dictionary):
			continue
		save_list.add_child(_build_row(summary))


func _build_row(summary: Dictionary) -> Control:
	var row = HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var details = Label.new()
	details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.text = "%s\n%s  %s" % [
		str(summary.get("slot_name", summary.get("save_id", "Unknown Slot"))),
		str(summary.get("location", "Unknown")),
		str(summary.get("timestamp", "")),
	]
	row.add_child(details)

	var load_button = Button.new()
	load_button.text = "Load"
	load_button.disabled = _is_busy
	load_button.pressed.connect(func() -> void:
		load_requested.emit(str(summary.get("save_id", "")))
	)
	row.add_child(load_button)

	var delete_button = Button.new()
	delete_button.text = "Delete"
	delete_button.disabled = _is_busy
	delete_button.pressed.connect(func() -> void:
		delete_requested.emit(str(summary.get("save_id", "")))
	)
	row.add_child(delete_button)

	return row
