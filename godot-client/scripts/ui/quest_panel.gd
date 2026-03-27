extends PanelContainer
class_name QuestPanelWidget

signal command_requested(command_text: String)

@onready var summary_label: Label = $QuestMargin/QuestVBox/SummaryLabel
@onready var active_list: VBoxContainer = $QuestMargin/QuestVBox/QuestScroll/QuestLists/ActiveList
@onready var offer_list: VBoxContainer = $QuestMargin/QuestVBox/QuestScroll/QuestLists/OfferList

var _is_waiting: bool = false


func _ready() -> void:
	GameState.state_updated.connect(_refresh)
	_refresh()


func set_waiting(waiting: bool) -> void:
	_is_waiting = waiting
	_refresh()


func _refresh() -> void:
	summary_label.text = "%d active, %d available" % [GameState.active_quests.size(), GameState.quest_offers.size()]
	_clear_rows(active_list)
	_clear_rows(offer_list)

	if GameState.active_quests.is_empty():
		active_list.add_child(_placeholder_label("No active quests. Talk to guards, merchants, and quest givers."))
	else:
		for quest in GameState.active_quests:
			if quest is Dictionary:
				active_list.add_child(_build_active_row(quest))

	if GameState.quest_offers.is_empty():
		offer_list.add_child(_placeholder_label("No available quest offers in view."))
	else:
		for offer in GameState.quest_offers:
			if offer is Dictionary:
				offer_list.add_child(_build_offer_row(offer))


func _build_active_row(quest: Dictionary) -> Control:
	var row = VBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var title = Label.new()
	title.text = str(quest.get("title", quest.get("quest_id", "Unknown Quest")))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(title)

	var meta = Label.new()
	var deadline = quest.get("deadline", null)
	var meta_parts = ["Status: %s" % str(quest.get("status", "active")).capitalize()]
	if deadline != null:
		meta_parts.append("Deadline: %s" % str(deadline))
	meta.text = "  ".join(meta_parts)
	meta.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(meta)

	var actions = HBoxContainer.new()
	var turn_in_button = Button.new()
	turn_in_button.text = "Turn In"
	turn_in_button.disabled = _is_waiting
	turn_in_button.pressed.connect(func() -> void:
		command_requested.emit("turn in quest %s" % str(quest.get("title", quest.get("quest_id", ""))))
	)
	actions.add_child(turn_in_button)
	row.add_child(actions)

	return row


func _build_offer_row(offer: Dictionary) -> Control:
	var row = VBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var title = Label.new()
	title.text = str(offer.get("title", offer.get("id", "Unknown Quest")))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(title)

	var description = Label.new()
	description.text = str(offer.get("description", ""))
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(description)

	var reward_label = Label.new()
	var reward_parts: Array[String] = []
	if offer.has("reward_gold"):
		reward_parts.append("%s gold" % str(offer.get("reward_gold", 0)))
	if offer.has("reward_xp"):
		reward_parts.append("%s XP" % str(offer.get("reward_xp", 0)))
	var requires_talk_first = _requires_in_person_acceptance(offer)
	var reward_text = "Rewards: %s" % (", ".join(reward_parts) if not reward_parts.is_empty() else "Unspecified")
	if requires_talk_first:
		reward_text += "\nTalk to the quest giver in person before accepting."
	reward_label.text = reward_text
	reward_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(reward_label)

	var actions = HBoxContainer.new()
	var accept_button = Button.new()
	accept_button.text = "Talk First" if requires_talk_first else "Accept"
	accept_button.disabled = _is_waiting or requires_talk_first
	if not requires_talk_first:
		accept_button.pressed.connect(func() -> void:
			command_requested.emit("accept quest %s" % str(offer.get("title", offer.get("id", ""))))
		)
	actions.add_child(accept_button)
	row.add_child(actions)

	return row


func _placeholder_label(text: String) -> Label:
	var label = Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.text = text
	return label


func _clear_rows(container: VBoxContainer) -> void:
	for child in container.get_children():
		child.queue_free()


func _requires_in_person_acceptance(offer: Dictionary) -> bool:
	return str(offer.get("kind", "")).to_lower() == "delivery" \
		and str(offer.get("giver_entity_id", "")).strip_edges().is_empty() \
		and str(offer.get("giver_name", "")).strip_edges().is_empty()
