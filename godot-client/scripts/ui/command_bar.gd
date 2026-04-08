extends PanelContainer
class_name CommandBarWidget

signal command_submitted(command_text: String)
signal quick_save_requested
signal saves_requested

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

var _history: Array[String] = []
var _action_buttons: Dictionary = {}
var _command_entry_context: String = "hidden"
var _is_waiting: bool = false
const COMMAND_CONTEXT_HIDDEN := "hidden"
const COMMAND_CONTEXT_DIALOG := "dialog"
const VERB_ORDER := ["talk", "attack", "examine", "use", "rest"]
const VERB_LABELS := {
	"talk": "Talk",
	"attack": "Attack",
	"examine": "Examine",
	"use": "Use",
	"rest": "Rest",
}


func _ready() -> void:
	text_input.text_submitted.connect(_on_text_submitted)
	send_btn.pressed.connect(_on_send_pressed)
	quick_save_btn.pressed.connect(func() -> void:
		quick_save_requested.emit()
	)
	saves_btn.pressed.connect(func() -> void:
		saves_requested.emit()
	)
	_action_buttons = {
		"talk": focus_action_one,
		"attack": focus_action_two,
		"examine": focus_action_three,
		"use": focus_action_four,
		"rest": focus_action_five,
	}
	for verb in _action_buttons.keys():
		var button: Button = _action_buttons[verb]
		button.pressed.connect(_on_focus_action_pressed.bind(button))
	text_input.placeholder_text = "Type a command or choose a verb..."
	send_btn.text = "Act"
	quick_save_btn.text = "Save"
	saves_btn.text = "Loads"
	set_focus_summary("")
	set_focus_actions([])
	set_command_entry_context(COMMAND_CONTEXT_HIDDEN)
	_refresh_history()


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
