## Save browser panel — lists campaign saves for a player and loads them.
## Extracted from title_screen.gd for SOLID compliance.
extends Panel
class_name LoadBrowserWidget

signal save_load_requested(save_id: String)
signal browser_closed()

var _player_input: LineEdit
var _refresh_button: Button
var _close_button: Button
var _status_label: Label
var _save_list: VBoxContainer
var _is_busy: bool = false


func _ready() -> void:
	visible = false
	anchors_preset = Control.PRESET_FULL_RECT
	offset_left = 88.0
	offset_top = 72.0
	offset_right = -88.0
	offset_bottom = -72.0

	var vbox := VBoxContainer.new()
	vbox.name = "BrowserVBox"
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 12)
	add_child(vbox)

	var header := Label.new()
	header.text = "Continue Campaign"
	header.add_theme_font_size_override("font_size", 22)
	header.add_theme_color_override("font_color", Color(0.80, 0.66, 0.26))
	header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(header)

	var player_row := HBoxContainer.new()
	player_row.add_theme_constant_override("separation", 8)
	vbox.add_child(player_row)

	var player_label := Label.new()
	player_label.text = "Player:"
	player_row.add_child(player_label)

	_player_input = LineEdit.new()
	_player_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_player_input.placeholder_text = "Enter player name"
	_player_input.text_submitted.connect(func(_t: String): refresh())
	player_row.add_child(_player_input)

	_refresh_button = Button.new()
	_refresh_button.text = "Refresh"
	_refresh_button.pressed.connect(refresh)
	player_row.add_child(_refresh_button)

	_status_label = Label.new()
	_status_label.text = "Choose a save slot to continue."
	_status_label.add_theme_font_size_override("font_size", 14)
	_status_label.add_theme_color_override("font_color", Color(0.65, 0.62, 0.58))
	vbox.add_child(_status_label)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)

	_save_list = VBoxContainer.new()
	_save_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_save_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_save_list)

	var btn_row := HBoxContainer.new()
	btn_row.alignment = BoxContainer.ALIGNMENT_END
	vbox.add_child(btn_row)

	_close_button = Button.new()
	_close_button.text = "Back"
	_close_button.pressed.connect(close)
	btn_row.add_child(_close_button)


func open(player_id: String = "") -> void:
	visible = true
	_player_input.text = player_id
	_status_label.text = "Choose a save slot to continue." if not player_id.is_empty() else "Enter a player name."
	_clear_rows()
	if not player_id.is_empty():
		refresh()
	_player_input.grab_focus()


func close() -> void:
	visible = false
	_clear_rows()
	browser_closed.emit()


func refresh() -> void:
	var player_id := _player_input.text.strip_edges()
	if player_id.is_empty():
		_status_label.text = "Enter a player name to browse saves."
		_clear_rows()
		return
	_set_busy(true, "Loading saves for %s..." % player_id)
	Backend.list_saves(_on_saves_listed, player_id)


func populate_saves(entries: Array) -> void:
	_set_busy(false, "")
	_clear_rows()
	if entries.is_empty():
		_status_label.text = "No campaign saves found."
		return
	var sorted := entries.duplicate()
	sorted.sort_custom(func(a, b): return str(a.get("timestamp", "")) > str(b.get("timestamp", "")))
	for entry in sorted:
		_save_list.add_child(_build_row(entry))
	_status_label.text = "Found %d save(s)." % sorted.size()


func _on_saves_listed(data) -> void:
	if data == null:
		_set_busy(false, "Failed to load saves.")
		return
	var entries: Array = []
	if data is Array:
		entries = data
	elif data is Dictionary:
		entries = data.get("saves", [])
	populate_saves(entries)


func _build_row(entry: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var slot := str(entry.get("slot_name", entry.get("save_id", "Unnamed")))
	var loc := str(entry.get("location", "Unknown"))
	var title_lbl := Label.new()
	title_lbl.text = "%s — %s" % [slot, loc]
	title_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_child(title_lbl)

	var meta_lbl := Label.new()
	meta_lbl.text = "Saved %s" % str(entry.get("timestamp", ""))
	meta_lbl.modulate = Color(0.75, 0.75, 0.78)
	info.add_child(meta_lbl)

	row.add_child(info)

	var save_id := str(entry.get("save_id", slot))
	var load_btn := Button.new()
	load_btn.text = "Load"
	load_btn.disabled = _is_busy
	load_btn.pressed.connect(func(): _load_save(save_id))
	row.add_child(load_btn)
	return row


func _load_save(save_id: String) -> void:
	if _is_busy or save_id.is_empty():
		return
	_set_busy(true, "Loading %s..." % save_id)
	save_load_requested.emit(save_id)


func _clear_rows() -> void:
	for child in _save_list.get_children():
		child.queue_free()


func _set_busy(busy: bool, message: String) -> void:
	_is_busy = busy
	_refresh_button.disabled = busy
	_close_button.disabled = busy
	for child in _save_list.get_children():
		if child is HBoxContainer:
			for gc in child.get_children():
				if gc is Button:
					gc.disabled = busy
	if not message.is_empty():
		_status_label.text = message
