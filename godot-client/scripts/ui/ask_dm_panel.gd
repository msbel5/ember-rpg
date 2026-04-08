extends PanelContainer
class_name AskDmPanelWidget

signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)
signal command_requested(command_text: String)

@onready var summary_label: Label = $AskMargin/AskVBox/SummaryLabel
@onready var prompt_input: LineEdit = $AskMargin/AskVBox/InputRow/PromptInput
@onready var submit_button: Button = $AskMargin/AskVBox/InputRow/SubmitButton
@onready var blockers_label: Label = $AskMargin/AskVBox/BlockersLabel
@onready var answer_text: RichTextLabel = $AskMargin/AskVBox/AnswerText
@onready var topic_title: Label = $AskMargin/AskVBox/TopicSection/TopicTitle
@onready var topic_list: VBoxContainer = $AskMargin/AskVBox/TopicSection/TopicList
@onready var command_title: Label = $AskMargin/AskVBox/CommandSection/CommandTitle
@onready var command_list: VBoxContainer = $AskMargin/AskVBox/CommandSection/CommandList

var _view: Dictionary = {}
var _waiting: bool = false


func _ready() -> void:
	prompt_input.placeholder_text = "Ask for a grounded reading of your next move..."
	submit_button.text = "Consult Fate"
	topic_title.text = "Related Threads"
	command_title.text = "Grounded Leads"
	submit_button.pressed.connect(_submit_query)
	prompt_input.text_submitted.connect(func(_text: String) -> void:
		_submit_query()
	)
	set_view({})


func set_waiting(waiting: bool) -> void:
	_waiting = waiting
	submit_button.disabled = waiting
	prompt_input.editable = not waiting


func set_view(view: Dictionary) -> void:
	_view = view.duplicate(true) if view is Dictionary else {}
	_render()


func set_prompt(prompt: String) -> void:
	prompt_input.text = prompt


func _render() -> void:
	summary_label.text = "Consult Fate using only the live `advisor_view`."
	blockers_label.text = ""
	answer_text.clear()
	for child in topic_list.get_children():
		child.queue_free()
	for child in command_list.get_children():
		child.queue_free()
	if _view.is_empty():
		answer_text.text = "No fate reading yet. Submit a grounded question."
		return
	var answer_lines = _view.get("answer_lines", [])
	answer_text.text = "\n".join(answer_lines) if answer_lines is Array and not answer_lines.is_empty() else "No grounded answer lines returned."
	var blockers = _view.get("blockers", [])
	if blockers is Array and not blockers.is_empty():
		blockers_label.text = "Blockers: %s" % ", ".join(blockers)
	for topic_id in _view.get("related_topic_ids", []):
		var chip := Label.new()
		chip.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		chip.text = str(topic_id)
		topic_list.add_child(chip)
	for suggested in _view.get("suggested_commands", []):
		var button := Button.new()
		button.text = str(suggested)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(func() -> void:
			command_requested.emit(str(suggested))
		)
		command_list.add_child(button)


func _submit_query() -> void:
	var query := prompt_input.text.strip_edges()
	if query.is_empty() or _waiting:
		return
	var history_text := "ask dm %s" % query
	if get_signal_connection_list("structured_action_requested").is_empty():
		command_requested.emit(history_text)
	else:
		structured_action_requested.emit("advisor", {"action_id": "ask_dm", "query": query}, history_text)
