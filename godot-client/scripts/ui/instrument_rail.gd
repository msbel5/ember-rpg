extends PanelContainer
class_name InstrumentRailWidget

signal command_submitted(command_text: String)
signal quick_save_requested
signal saves_requested
signal panel_requested(panel_id: String)

@onready var _monitor_title: Label = $MonitorFrame/MonitorMargin/MonitorVBox/MonitorTitle
@onready var _monitor_log: RichTextLabel = $MonitorFrame/MonitorMargin/MonitorVBox/MonitorLog
@onready var history_label: Label = $CommandVBox/HistoryLabel
@onready var focus_label: Label = $CommandVBox/FocusLabel
@onready var focus_action_one: Button = $CommandVBox/FocusActionsRow/FocusActionOne
@onready var focus_action_two: Button = $CommandVBox/FocusActionsRow/FocusActionTwo
@onready var focus_action_three: Button = $CommandVBox/FocusActionsRow/FocusActionThree
@onready var focus_action_four: Button = $CommandVBox/FocusActionsRow/FocusActionFour
@onready var focus_action_five: Button = $CommandVBox/FocusActionsRow/FocusActionFive
@onready var prompt_label: Label = $CommandVBox/InputRow/PromptLabel
@onready var text_input: LineEdit = $CommandVBox/InputRow/TextInput
@onready var send_btn: Button = $CommandVBox/InputRow/SendButton
@onready var quick_save_btn: Button = $CommandVBox/InputRow/QuickSaveButton
@onready var saves_btn: Button = $CommandVBox/InputRow/SavesButton
@onready var _mode_label: Label = $ShellFrame/ShellMargin/ShellVBox/ModeLabel
@onready var _state_label: Label = $ShellFrame/ShellMargin/ShellVBox/StateLabel
@onready var _hero_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowOne/HeroButton
@onready var _items_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowOne/ItemsButton
@onready var _map_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowOne/MapButton
@onready var _quests_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowTwo/QuestsButton
@onready var _town_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowTwo/TownButton
@onready var _menu_button: Button = $ShellFrame/ShellMargin/ShellVBox/PanelRowTwo/MenuButton

const VERB_ORDER := ["talk", "attack", "examine", "use", "rest"]
const VERB_LABELS := {
	"talk": "Talk",
	"attack": "Attack",
	"examine": "Examine",
	"use": "Use",
	"rest": "Rest",
}
const PANEL_LABELS := {
	"hero": "Hero",
	"items": "Items",
	"map": "Map",
	"quests": "Quests",
	"town": "Town",
	"pause": "Menu",
}
const COMMAND_CONTEXT_HIDDEN := "hidden"
const COMMAND_CONTEXT_DIALOG := "dialog"

var _history: Array[String] = []
var _action_buttons: Dictionary = {}
var _panel_buttons: Dictionary = {}
var _panel_group: ButtonGroup = ButtonGroup.new()
var _command_entry_context: String = COMMAND_CONTEXT_HIDDEN
var _is_waiting: bool = false


func _ready() -> void:
	_action_buttons = {
		"talk": focus_action_one,
		"attack": focus_action_two,
		"examine": focus_action_three,
		"use": focus_action_four,
		"rest": focus_action_five,
	}
	_panel_buttons = {
		"hero": _hero_button,
		"items": _items_button,
		"map": _map_button,
		"quests": _quests_button,
		"town": _town_button,
		"pause": _menu_button,
	}
	text_input.text_submitted.connect(_on_text_submitted)
	send_btn.pressed.connect(_on_send_pressed)
	quick_save_btn.pressed.connect(func() -> void:
		quick_save_requested.emit()
	)
	saves_btn.pressed.connect(func() -> void:
		saves_requested.emit()
	)
	for verb in _action_buttons.keys():
		var button: Button = _action_buttons[verb]
		button.pressed.connect(_on_focus_action_pressed.bind(button))
	for panel_id in _panel_buttons.keys():
		var panel_button: Button = _panel_buttons[panel_id]
		panel_button.toggle_mode = true
		panel_button.button_group = _panel_group
		panel_button.pressed.connect(_on_panel_button_pressed.bind(panel_id))
	text_input.placeholder_text = "What do you do?"
	send_btn.text = "Act"
	quick_save_btn.text = "Save"
	saves_btn.text = "Loads"
	if get_node_or_null("/root/GameState") != null:
		GameState.state_updated.connect(_refresh_monitor)
	set_focus_summary("")
	set_focus_actions([])
	set_panel_actions({}, "")
	set_command_entry_context(COMMAND_CONTEXT_HIDDEN)
	_refresh_history()
	_refresh_monitor()


func focus_input() -> void:
	if command_entry_visible():
		text_input.grab_focus()


func clear_input() -> void:
	text_input.text = ""


func has_input_focus() -> bool:
	return text_input.has_focus()


func command_entry_visible() -> bool:
	return text_input.visible and send_btn.visible


func set_command_entry_context(context: String) -> void:
	var normalized := context.strip_edges().to_lower()
	if normalized != COMMAND_CONTEXT_DIALOG:
		normalized = COMMAND_CONTEXT_HIDDEN
	_command_entry_context = normalized
	var entry_visible := _command_entry_context == COMMAND_CONTEXT_DIALOG
	history_label.visible = entry_visible
	prompt_label.visible = entry_visible
	text_input.visible = entry_visible
	send_btn.visible = entry_visible
	text_input.placeholder_text = "Ask about a known topic or speak plainly..." if entry_visible else "Point-and-click to act"
	send_btn.text = "Speak" if entry_visible else "Act"
	if not entry_visible:
		text_input.release_focus()
		text_input.text = ""
	text_input.editable = not _is_waiting and entry_visible
	send_btn.disabled = _is_waiting or not entry_visible
	_refresh_history()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	text_input.editable = not waiting and command_entry_visible()
	send_btn.disabled = waiting or not command_entry_visible()
	quick_save_btn.disabled = waiting
	saves_btn.disabled = waiting
	for button in _action_buttons.values():
		button.disabled = waiting or str(button.get_meta("command", "")).strip_edges().is_empty()
	if waiting:
		for panel_button in _panel_buttons.values():
			panel_button.disabled = true
	if waiting:
		if history_label.visible:
			history_label.text = "Prompts locked while the world catches up..."
	else:
		_refresh_history()


func set_focus_summary(summary: String) -> void:
	var next_summary = summary.strip_edges()
	if next_summary.is_empty():
		next_summary = "Focus: choose a person, threat, or landmark to reveal the next useful verb."
	focus_label.text = next_summary


func set_focus_actions(actions: Array) -> void:
	var by_verb: Dictionary = {}
	for action in actions:
		if not (action is Dictionary):
			continue
		var verb := _resolve_verb(action)
		if verb.is_empty() or by_verb.has(verb):
			continue
		by_verb[verb] = action
	if not by_verb.has("examine"):
		by_verb["examine"] = {"verb": "examine", "label": "Examine area", "command": "look around"}
	if not by_verb.has("rest"):
		by_verb["rest"] = {"verb": "rest", "label": "Rest and recover", "command": "rest"}
	for verb in VERB_ORDER:
		_apply_focus_action_button(_action_buttons[verb], by_verb.get(verb, {}), verb)


func set_panel_actions(panel_states: Dictionary, active_panel_id: String = "") -> void:
	for panel_id in _panel_buttons.keys():
		var button: Button = _panel_buttons[panel_id]
		var raw_state = panel_states.get(panel_id, {})
		var visible := false
		var enabled := false
		var tooltip := ""
		if raw_state is Dictionary:
			visible = bool(raw_state.get("visible", false))
			enabled = bool(raw_state.get("enabled", false))
			tooltip = str(raw_state.get("tooltip", "")).strip_edges()
		elif raw_state is bool:
			visible = raw_state
			enabled = raw_state
		button.visible = visible
		button.disabled = not enabled
		button.text = PANEL_LABELS.get(panel_id, button.text)
		button.tooltip_text = tooltip
		button.button_pressed = visible and not active_panel_id.is_empty() and panel_id == active_panel_id


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
	if not command_entry_visible():
		return
	_emit_command(text)


func _on_send_pressed() -> void:
	if not command_entry_visible():
		return
	_emit_command(text_input.text)


func _emit_command(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	remember_command(text)
	command_submitted.emit(text)


func _refresh_history() -> void:
	var prefix := "Recent Prompts" if _command_entry_context == COMMAND_CONTEXT_DIALOG else "Recent Orders"
	if _history.is_empty():
		history_label.text = "%s: none yet" % prefix
		return
	history_label.text = "%s: %s" % [prefix, " | ".join(_history.slice(maxi(_history.size() - 3, 0), _history.size()))]


func _refresh_monitor() -> void:
	if get_node_or_null("/root/GameState") == null:
		_monitor_title.text = "Field Monitor"
		_monitor_log.text = "Awaiting a live campaign feed."
		_mode_label.text = "Mode: offline"
		_state_label.text = "No live world state."
		return
	var shell_mode := str(GameState.current_shell_mode()).replace("_", " ").capitalize()
	_mode_label.text = "Mode: %s" % shell_mode
	var monitor_lines: Array[String] = []
	for line in GameState.narrative_history.slice(maxi(GameState.narrative_history.size() - 3, 0), GameState.narrative_history.size()):
		var normalized := str(line).strip_edges()
		if normalized.is_empty():
			continue
		monitor_lines.append(normalized)
	_monitor_title.text = "Field Monitor"
	_monitor_log.text = "\n\n".join(monitor_lines) if not monitor_lines.is_empty() else "No recent field notes."
	_state_label.text = _build_state_summary()


func _build_state_summary() -> String:
	var summary_chunks: Array[String] = []
	if GameState.has_active_travel():
		var destination_name := str(GameState.travel_state.get("destination_name", GameState.travel_state.get("destination_region_id", "Unknown"))).strip_edges()
		summary_chunks.append("Travel: %s (%sh left)" % [destination_name, int(GameState.travel_state.get("travel_hours_remaining", 0))])
	elif not GameState.location.is_empty():
		summary_chunks.append("Site: %s" % GameState.get_display_location())
	if not GameState.crime_state.is_empty() and bool(GameState.crime_state.get("wanted", false)):
		summary_chunks.append("Wanted · bounty %d" % int(GameState.crime_state.get("active_bounty", 0)))
	elif GameState.scene == "combat":
		summary_chunks.append("Combat pressure rising")
	if summary_chunks.is_empty():
		summary_chunks.append("No urgent field pressure.")
	return "\n".join(summary_chunks)


func _apply_focus_action_button(button: Button, action: Dictionary, verb: String) -> void:
	var label = str(action.get("label", VERB_LABELS.get(verb, ""))).strip_edges()
	var command = str(action.get("command", "")).strip_edges()
	button.text = str(VERB_LABELS.get(verb, label))
	button.visible = not command.is_empty()
	button.disabled = command.is_empty()
	button.set_meta("command", command)
	button.tooltip_text = label if not label.is_empty() else ""


func _on_focus_action_pressed(button: Button) -> void:
	var command = str(button.get_meta("command", "")).strip_edges()
	if command.is_empty():
		return
	command_submitted.emit(command)


func _on_panel_button_pressed(panel_id: String) -> void:
	if panel_id.is_empty():
		return
	var button: Button = _panel_buttons.get(panel_id)
	if button == null or not button.visible or button.disabled:
		return
	panel_requested.emit(panel_id)


func _resolve_verb(action: Dictionary) -> String:
	var explicit = str(action.get("verb", "")).strip_edges().to_lower()
	if not explicit.is_empty():
		return explicit
	var command = str(action.get("command", "")).strip_edges().to_lower()
	if command.begins_with("talk "):
		return "talk"
	if command.begins_with("attack "):
		return "attack"
	if command == "rest":
		return "rest"
	if command.begins_with("examine ") or command == "look around" or command == "search area":
		return "examine"
	if command.begins_with("pick up ") or command.begins_with("use ") or command.begins_with("trade ") or command.begins_with("open "):
		return "use"
	var label = str(action.get("label", "")).strip_edges().to_lower()
	for verb in VERB_ORDER:
		if label.begins_with(verb):
			return verb
	return ""
