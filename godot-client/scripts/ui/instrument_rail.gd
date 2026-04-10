extends PanelContainer
class_name InstrumentRailWidget

signal command_submitted(command_text: String)
signal quick_save_requested
signal saves_requested
signal panel_requested(panel_id: String)

@onready var _monitor_title: Label = $RailMargin/RailVBox/IntelRow/MonitorFrame/MonitorMargin/MonitorVBox/MonitorTitle
@onready var _monitor_log: RichTextLabel = $RailMargin/RailVBox/IntelRow/MonitorFrame/MonitorMargin/MonitorVBox/MonitorLog
@onready var focus_label: Label = $RailMargin/RailVBox/FocusLabel
@onready var focus_action_one: Button = $RailMargin/RailVBox/FocusActionsRow/FocusActionOne
@onready var focus_action_two: Button = $RailMargin/RailVBox/FocusActionsRow/FocusActionTwo
@onready var focus_action_three: Button = $RailMargin/RailVBox/FocusActionsRow/FocusActionThree
@onready var focus_action_four: Button = $RailMargin/RailVBox/FocusActionsRow/FocusActionFour
@onready var focus_action_five: Button = $RailMargin/RailVBox/FocusActionsRow/FocusActionFive
@onready var quick_save_btn: Button = $RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/SaveRow/QuickSaveButton
@onready var saves_btn: Button = $RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/SaveRow/SavesButton
@onready var _mode_label: Label = $RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/ModeLabel
@onready var _state_label: Label = $RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/StateLabel
@onready var _hero_button: Button = $RailMargin/RailVBox/ShellGrid/HeroButton
@onready var _items_button: Button = $RailMargin/RailVBox/ShellGrid/ItemsButton
@onready var _map_button: Button = $RailMargin/RailVBox/ShellGrid/MapButton
@onready var _quests_button: Button = $RailMargin/RailVBox/ShellGrid/QuestsButton
@onready var _town_button: Button = $RailMargin/RailVBox/ShellGrid/TownButton
@onready var _menu_button: Button = $RailMargin/RailVBox/ShellGrid/MenuButton

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

var _history: Array[String] = []
var _action_buttons: Dictionary = {}
var _panel_buttons: Dictionary = {}
var _panel_group: ButtonGroup = ButtonGroup.new()
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
	if get_node_or_null("/root/GameState") != null:
		GameState.state_updated.connect(_refresh_monitor)
	set_focus_summary("")
	set_focus_actions([])
	set_panel_actions({}, "")
	_refresh_monitor()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	quick_save_btn.disabled = waiting
	saves_btn.disabled = waiting
	for button in _action_buttons.values():
		button.disabled = waiting or str(button.get_meta("command", "")).strip_edges().is_empty()
	if waiting:
		for panel_button in _panel_buttons.values():
			panel_button.disabled = true


func set_focus_summary(summary: String) -> void:
	var next_summary = summary.strip_edges()
	if next_summary.is_empty():
		next_summary = "Select a person, threat, or landmark, then right-click to move or act."
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
	var normalized = text.strip_edges()
	if normalized.is_empty():
		return
	command_submitted.emit(normalized)


func remember_command(text: String) -> void:
	var normalized = text.strip_edges()
	if normalized.is_empty():
		return
	if not _history.is_empty() and _history[_history.size() - 1] == normalized:
		return
	_history.append(normalized)
	if _history.size() > 4:
		_history.pop_front()
	_refresh_monitor()


func _refresh_monitor() -> void:
	if get_node_or_null("/root/GameState") == null:
		_monitor_title.text = "Field Notes"
		_monitor_log.text = "Awaiting a live campaign feed."
		_mode_label.text = "Mode: offline"
		_state_label.text = "No live world state."
		return
	var shell_mode := str(GameState.current_shell_mode()).replace("_", " ").capitalize()
	_mode_label.text = "Mode: %s" % shell_mode
	var monitor_lines: Array[String] = []
	for line in GameState.narrative_history.slice(maxi(GameState.narrative_history.size() - 2, 0), GameState.narrative_history.size()):
		var normalized := str(line).strip_edges()
		if normalized.is_empty():
			continue
		monitor_lines.append(normalized)
	if monitor_lines.is_empty() and not _history.is_empty():
		monitor_lines.append("Last action: %s" % _history[_history.size() - 1])
	_monitor_title.text = "Field Notes"
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
	button.disabled = command.is_empty() or _is_waiting
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
