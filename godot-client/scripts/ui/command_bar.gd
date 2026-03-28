extends PanelContainer
class_name CommandBarWidget

const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")

signal command_submitted(command_text: String)
signal quick_save_requested
signal saves_requested

@onready var history_label: Label = $CommandVBox/HistoryLabel
@onready var focus_label: Label = $CommandVBox/FocusLabel
@onready var focus_action_one: Button = $CommandVBox/FocusActionsRow/FocusActionOne
@onready var focus_action_two: Button = $CommandVBox/FocusActionsRow/FocusActionTwo
@onready var roster_row: HBoxContainer = $CommandVBox/RosterRow
@onready var roster_one: Button = $CommandVBox/RosterRow/RosterOne
@onready var roster_two: Button = $CommandVBox/RosterRow/RosterTwo
@onready var roster_three: Button = $CommandVBox/RosterRow/RosterThree
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
	focus_action_one.pressed.connect(_on_focus_action_pressed.bind(focus_action_one))
	focus_action_two.pressed.connect(_on_focus_action_pressed.bind(focus_action_two))
	roster_one.pressed.connect(_on_focus_action_pressed.bind(roster_one))
	roster_two.pressed.connect(_on_focus_action_pressed.bind(roster_two))
	roster_three.pressed.connect(_on_focus_action_pressed.bind(roster_three))
	text_input.placeholder_text = "Move, talk, trade, defend, save..."
	send_btn.text = "Act"
	quick_save_btn.text = "Save"
	saves_btn.text = "Loads"
	set_focus_summary("")
	set_focus_actions([])
	set_scene_roster([])
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
	focus_action_one.disabled = waiting or str(focus_action_one.get_meta("command", "")).strip_edges().is_empty()
	focus_action_two.disabled = waiting or str(focus_action_two.get_meta("command", "")).strip_edges().is_empty()
	for button in [roster_one, roster_two, roster_three]:
		button.disabled = waiting or str(button.get_meta("command", "")).strip_edges().is_empty()
	if waiting:
		history_label.text = "Orders locked while the world catches up..."
	else:
		_refresh_history()


func set_focus_summary(summary: String) -> void:
	var next_summary = summary.strip_edges()
	if next_summary.is_empty():
		next_summary = "Focus: click a prop, person, or threat for the clearest next action."
	focus_label.text = next_summary


func set_focus_actions(actions: Array) -> void:
	var next_actions = actions.duplicate(true)
	if next_actions.is_empty():
		next_actions = [
			{"label": "Look Around", "command": "look around"},
			{"label": "Inventory", "command": "inventory"},
		]
	_apply_focus_action_button(focus_action_one, next_actions[0] if next_actions.size() > 0 else {})
	_apply_focus_action_button(focus_action_two, next_actions[1] if next_actions.size() > 1 else {})


func set_scene_roster(entries: Array) -> void:
	var next_entries = entries.duplicate(true)
	_apply_roster_button(roster_one, next_entries[0] if next_entries.size() > 0 else {})
	_apply_roster_button(roster_two, next_entries[1] if next_entries.size() > 1 else {})
	_apply_roster_button(roster_three, next_entries[2] if next_entries.size() > 2 else {})
	roster_row.visible = roster_one.visible or roster_two.visible or roster_three.visible


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
		history_label.text = "Recent Orders: none yet"
		return
	history_label.text = "Recent Orders: %s" % " | ".join(_history.slice(maxi(_history.size() - 3, 0), _history.size()))


func _apply_focus_action_button(button: Button, action: Dictionary) -> void:
	var label = str(action.get("label", "")).strip_edges()
	var command = str(action.get("command", "")).strip_edges()
	button.text = label
	button.visible = not label.is_empty()
	button.disabled = command.is_empty()
	button.set_meta("command", command)


func _apply_roster_button(button: Button, entry: Dictionary) -> void:
	var label = str(entry.get("label", "")).strip_edges()
	var command = str(entry.get("command", "")).strip_edges()
	var template_name = str(entry.get("template", "")).strip_edges().to_lower()
	button.text = label
	button.visible = not label.is_empty()
	button.disabled = command.is_empty()
	button.set_meta("command", command)
	button.icon = EntitySpriteCatalog.resolve_texture(template_name) if not template_name.is_empty() else null


func _on_focus_action_pressed(button: Button) -> void:
	var command = str(button.get_meta("command", "")).strip_edges()
	if command.is_empty():
		return
	command_submitted.emit(command)
