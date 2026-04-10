extends Panel
class_name LoadBrowserWidget

signal save_load_requested(save_id: String)
signal browser_closed()

const IVORY := Color(0.93, 0.91, 0.87)
const MUTED := Color(0.70, 0.66, 0.61)
const GOLD := Color(0.82, 0.66, 0.38)

var _player_input: LineEdit
var _refresh_button: Button
var _close_button: Button
var _status_label: Label
var _save_list: VBoxContainer
var _detail_title: Label
var _detail_meta: RichTextLabel
var _selected_save_id := ""
var _selected_entry: Dictionary = {}
var _is_busy := false


func _ready() -> void:
	visible = false
	anchors_preset = Control.PRESET_FULL_RECT
	offset_left = 72.0
	offset_top = 52.0
	offset_right = -72.0
	offset_bottom = -52.0

	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.09, 0.08, 0.11, 0.97)
	bg.border_color = Color(0.44, 0.31, 0.18, 0.96)
	bg.set_corner_radius_all(18)
	bg.set_border_width_all(1)
	bg.shadow_color = Color(0.0, 0.0, 0.0, 0.4)
	bg.shadow_size = 8
	add_theme_stylebox_override("panel", bg)

	var shell := MarginContainer.new()
	shell.anchors_preset = Control.PRESET_FULL_RECT
	shell.add_theme_constant_override("margin_left", 22)
	shell.add_theme_constant_override("margin_top", 22)
	shell.add_theme_constant_override("margin_right", 22)
	shell.add_theme_constant_override("margin_bottom", 22)
	add_child(shell)

	var root := VBoxContainer.new()
	root.name = "VBox"
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_theme_constant_override("separation", 14)
	shell.add_child(root)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 16)
	root.add_child(header)

	var title_box := VBoxContainer.new()
	title_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_box.add_theme_constant_override("separation", 6)
	header.add_child(title_box)

	var header_label := Label.new()
	header_label.text = "Load Chronicle"
	header_label.add_theme_font_size_override("font_size", 30)
	header_label.add_theme_color_override("font_color", IVORY)
	title_box.add_child(header_label)

	_status_label = Label.new()
	_status_label.name = "StatusLabel"
	_status_label.text = "Choose a known survivor to reopen a chronicle."
	_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status_label.add_theme_color_override("font_color", MUTED)
	title_box.add_child(_status_label)

	_close_button = Button.new()
	_close_button.name = "BackButton"
	_close_button.text = "Back"
	_close_button.custom_minimum_size = Vector2(140, 46)
	_close_button.pressed.connect(close)
	header.add_child(_close_button)

	var player_row := HBoxContainer.new()
	player_row.name = "PlayerRow"
	player_row.add_theme_constant_override("separation", 10)
	root.add_child(player_row)

	var player_label := Label.new()
	player_label.text = "Ledger:"
	player_label.add_theme_color_override("font_color", GOLD)
	player_row.add_child(player_label)

	_player_input = LineEdit.new()
	_player_input.name = "PlayerInput"
	_player_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_player_input.placeholder_text = "Type a player or survivor name"
	_player_input.text_submitted.connect(func(_text: String) -> void:
		refresh()
	)
	player_row.add_child(_player_input)

	_refresh_button = Button.new()
	_refresh_button.name = "RefreshButton"
	_refresh_button.text = "Search"
	_refresh_button.custom_minimum_size = Vector2(132, 42)
	_refresh_button.pressed.connect(refresh)
	player_row.add_child(_refresh_button)

	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.split_offset = 560
	root.add_child(split)

	var list_panel := PanelContainer.new()
	list_panel.add_theme_stylebox_override("panel", _inner_panel_style())
	split.add_child(list_panel)

	var list_margin := MarginContainer.new()
	list_margin.add_theme_constant_override("margin_left", 14)
	list_margin.add_theme_constant_override("margin_top", 14)
	list_margin.add_theme_constant_override("margin_right", 14)
	list_margin.add_theme_constant_override("margin_bottom", 14)
	list_panel.add_child(list_margin)

	var list_vbox := VBoxContainer.new()
	list_vbox.add_theme_constant_override("separation", 10)
	list_margin.add_child(list_vbox)

	var list_title := Label.new()
	list_title.text = "Available saves"
	list_title.add_theme_font_size_override("font_size", 20)
	list_vbox.add_child(list_title)

	var scroll := ScrollContainer.new()
	scroll.name = "SaveScroll"
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	list_vbox.add_child(scroll)

	_save_list = VBoxContainer.new()
	_save_list.name = "SaveList"
	_save_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_save_list.add_theme_constant_override("separation", 8)
	scroll.add_child(_save_list)

	var detail_panel := PanelContainer.new()
	detail_panel.add_theme_stylebox_override("panel", _inner_panel_style())
	split.add_child(detail_panel)

	var detail_margin := MarginContainer.new()
	detail_margin.add_theme_constant_override("margin_left", 16)
	detail_margin.add_theme_constant_override("margin_top", 16)
	detail_margin.add_theme_constant_override("margin_right", 16)
	detail_margin.add_theme_constant_override("margin_bottom", 16)
	detail_panel.add_child(detail_margin)

	var detail_vbox := VBoxContainer.new()
	detail_vbox.add_theme_constant_override("separation", 12)
	detail_margin.add_child(detail_vbox)

	var detail_header := Label.new()
	detail_header.text = "Selected record"
	detail_header.add_theme_font_size_override("font_size", 20)
	detail_vbox.add_child(detail_header)

	_detail_title = Label.new()
	_detail_title.text = "No save selected"
	_detail_title.add_theme_font_size_override("font_size", 24)
	_detail_title.add_theme_color_override("font_color", IVORY)
	detail_vbox.add_child(_detail_title)

	_detail_meta = RichTextLabel.new()
	_detail_meta.bbcode_enabled = true
	_detail_meta.fit_content = true
	_detail_meta.scroll_active = false
	_detail_meta.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail_meta.text = "Search for a ledger and select a save to inspect it."
	detail_vbox.add_child(_detail_meta)

	var load_button := Button.new()
	load_button.name = "PrimaryLoadButton"
	load_button.text = "Load Selected Chronicle"
	load_button.custom_minimum_size = Vector2(0, 54)
	load_button.pressed.connect(func() -> void:
		_load_save(_selected_save_id)
	)
	detail_vbox.add_child(load_button)


func open(player_id: String = "") -> void:
	visible = true
	_player_input.text = player_id
	_selected_save_id = ""
	_selected_entry = {}
	_update_detail()
	_clear_rows()
	_status_label.text = "Choose a known survivor to reopen a chronicle."
	if not player_id.is_empty():
		refresh()
	_player_input.grab_focus()


func close() -> void:
	visible = false
	_selected_save_id = ""
	_selected_entry = {}
	_update_detail()
	_clear_rows()
	browser_closed.emit()


func refresh() -> void:
	var player_id := _player_input.text.strip_edges()
	if player_id.is_empty():
		_status_label.text = "Enter a player name to search the save ledger."
		_clear_rows()
		return
	_set_busy(true, "Scanning chronicle ledger for %s..." % player_id)
	Backend.list_player_campaign_saves(player_id, _on_saves_listed)


func populate_saves(entries: Array) -> void:
	_set_busy(false, "")
	_clear_rows()
	_selected_save_id = ""
	_selected_entry = {}
	if entries.is_empty():
		_status_label.text = "No campaign saves found."
		_update_detail()
		return
	var sorted := entries.duplicate()
	sorted.sort_custom(func(a, b): return str(a.get("timestamp", "")) > str(b.get("timestamp", "")))
	for index in range(sorted.size()):
		var entry: Dictionary = sorted[index]
		var row := _build_row(entry, index)
		_save_list.add_child(row)
		if index == 0:
			_selected_save_id = str(entry.get("save_id", entry.get("slot_name", "")))
			_selected_entry = entry.duplicate(true)
	_update_detail()
	_status_label.text = "Found %d chronicle save(s)." % sorted.size()


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


func _build_row(entry: Dictionary, index: int) -> Control:
	var row := Button.new()
	row.name = "SaveRow%d" % index
	row.alignment = HORIZONTAL_ALIGNMENT_LEFT
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.custom_minimum_size = Vector2(0, 72)
	row.toggle_mode = true
	row.text = _row_text(entry)
	row.tooltip_text = "Inspect %s" % str(entry.get("slot_name", entry.get("save_id", "chronicle")))
	var save_id := str(entry.get("save_id", entry.get("slot_name", "")))
	row.set_meta("save_id", save_id)
	row.button_pressed = save_id == _selected_save_id
	row.add_theme_stylebox_override("normal", _row_style(row.button_pressed))
	row.add_theme_stylebox_override("hover", _row_style(true))
	row.add_theme_stylebox_override("pressed", _row_style(true))
	row.pressed.connect(func() -> void:
		_selected_save_id = save_id
		_selected_entry = entry.duplicate(true)
		_refresh_row_selection()
		_update_detail()
	)
	return row


func _row_text(entry: Dictionary) -> String:
	var slot := str(entry.get("slot_name", entry.get("save_id", "Unnamed"))).strip_edges()
	var location := str(entry.get("location", "Unknown frontier")).strip_edges()
	var timestamp := str(entry.get("timestamp", "")).strip_edges()
	if timestamp.is_empty():
		return "%s\n%s" % [slot, location]
	return "%s\n%s  |  %s" % [slot, location, timestamp]


func _refresh_row_selection() -> void:
	for child in _save_list.get_children():
		if not (child is Button):
			continue
		child.button_pressed = str(child.get_meta("save_id", "")) == _selected_save_id
		child.add_theme_stylebox_override("normal", _row_style(child.button_pressed))


func _update_detail() -> void:
	if _selected_entry.is_empty():
		_detail_title.text = "No save selected"
		_detail_meta.text = "Search for a ledger and select a save to inspect it."
		return
	var slot := str(_selected_entry.get("slot_name", _selected_entry.get("save_id", "Unnamed"))).strip_edges()
	var location := str(_selected_entry.get("location", "Unknown frontier")).strip_edges()
	var save_id := str(_selected_entry.get("save_id", slot)).strip_edges()
	var timestamp := str(_selected_entry.get("timestamp", "Unrecorded")).strip_edges()
	_detail_title.text = slot
	_detail_meta.text = (
		"[b]Save ID[/b]  %s\n[b]Location[/b]  %s\n[b]Recorded[/b]  %s\n\n"
		+ "Loading returns directly to the active chronicle shell."
	) % [save_id, location, timestamp]


func _load_save(save_id: String) -> void:
	if _is_busy or save_id.is_empty():
		return
	_set_busy(true, "Loading %s..." % save_id)
	save_load_requested.emit(save_id)


func _clear_rows() -> void:
	for child in _save_list.get_children():
		_save_list.remove_child(child)
		child.queue_free()


func _set_busy(busy: bool, message: String) -> void:
	_is_busy = busy
	_refresh_button.disabled = busy
	_close_button.disabled = busy
	for child in _save_list.get_children():
		if child is Button:
			child.disabled = busy
	if not message.is_empty():
		_status_label.text = message


func _inner_panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.13, 0.11, 0.15, 0.98)
	style.set_corner_radius_all(14)
	style.set_border_width_all(1)
	style.border_color = Color(0.31, 0.25, 0.18, 0.95)
	return style


func _row_style(selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.20, 0.15, 0.10, 0.98) if selected else Color(0.15, 0.13, 0.17, 0.98)
	style.set_corner_radius_all(10)
	style.set_border_width_all(1)
	style.border_color = GOLD if selected else Color(0.24, 0.23, 0.28, 0.92)
	style.content_margin_left = 12
	style.content_margin_top = 12
	style.content_margin_right = 12
	style.content_margin_bottom = 12
	return style
