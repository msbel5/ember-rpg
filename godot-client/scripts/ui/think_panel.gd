extends PanelContainer
class_name ThinkPanelWidget

signal command_requested(command_text: String)

@onready var summary_label: Label = $ThinkMargin/ThinkVBox/SummaryLabel
@onready var query_input: LineEdit = $ThinkMargin/ThinkVBox/InputRow/QueryInput
@onready var think_button: Button = $ThinkMargin/ThinkVBox/InputRow/ThinkButton
@onready var topic_label: Label = $ThinkMargin/ThinkVBox/TopicLabel
@onready var blockers_label: Label = $ThinkMargin/ThinkVBox/BlockersLabel
@onready var facts_text: RichTextLabel = $ThinkMargin/ThinkVBox/Columns/FactsPanel/FactsMargin/FactsText
@onready var rumors_text: RichTextLabel = $ThinkMargin/ThinkVBox/Columns/RumorsPanel/RumorsMargin/RumorsText
@onready var topics_list: VBoxContainer = $ThinkMargin/ThinkVBox/TopicsSection/TopicsList

var _view: Dictionary = {}


func _ready() -> void:
	think_button.pressed.connect(_submit_query)
	query_input.text_submitted.connect(func(_text: String) -> void:
		_submit_query()
	)
	set_view({})


func set_view(view: Dictionary) -> void:
	_view = view.duplicate(true) if view is Dictionary else {}
	_render()


func sync_from_game_state() -> void:
	var conversation: Dictionary = GameState.conversation_state if GameState.conversation_state is Dictionary else {}
	var selected_topic := str(conversation.get("ask_about_selected_topic_id", "")).strip_edges()
	if not selected_topic.is_empty() and query_input.text.strip_edges().is_empty():
		query_input.text = selected_topic
	_render()


func _render() -> void:
	summary_label.text = "Thread discovered knowledge without inventing hidden facts."
	topic_label.text = "No topic selected"
	blockers_label.text = ""
	facts_text.clear()
	rumors_text.clear()
	for child in topics_list.get_children():
		child.queue_free()
	if _view.is_empty():
		facts_text.text = "No `knowledge_view` response yet."
		rumors_text.text = "Awaiting grounded topic synthesis."
		return
	var topic = _view.get("topic", {})
	if topic is Dictionary and not topic.is_empty():
		topic_label.text = "%s (%s)" % [str(topic.get("label", topic.get("topic_id", "Topic"))), str(topic.get("category", "topic"))]
	var blockers = _view.get("blockers", [])
	if blockers is Array and not blockers.is_empty():
		blockers_label.text = "Blockers: %s" % ", ".join(blockers)
	var facts = _view.get("facts", [])
	facts_text.text = "\n".join(facts) if facts is Array and not facts.is_empty() else "No confirmed facts returned."
	var rumors = _view.get("rumors", [])
	rumors_text.text = "\n".join(rumors) if rumors is Array and not rumors.is_empty() else "No rumor lines returned."
	for entry in _view.get("topics", []):
		if not (entry is Dictionary):
			continue
		var button := Button.new()
		button.text = str(entry.get("label", entry.get("topic_id", "Topic")))
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(func() -> void:
			query_input.text = str(entry.get("topic_id", ""))
		)
		topics_list.add_child(button)
	var ask_about = _view.get("ask_about", {})
	if ask_about is Dictionary and not ask_about.is_empty():
		var ask_text := "\n\nAsk About\n%s" % str(ask_about.get("response_type", "")).capitalize()
		var ask_facts = ask_about.get("facts", [])
		if ask_facts is Array and not ask_facts.is_empty():
			ask_text += "\n" + "\n".join(ask_facts)
		var ask_rumors = ask_about.get("rumors", [])
		if ask_rumors is Array and not ask_rumors.is_empty():
			ask_text += "\n" + "\n".join(ask_rumors)
		rumors_text.text += ask_text


func _submit_query() -> void:
	var query := query_input.text.strip_edges()
	if query.is_empty():
		return
	command_requested.emit("think %s" % query)
