extends PanelContainer
class_name NarrativePanelWidget

@onready var narrative_log: RichTextLabel = $NarrativeMargin/NarrativeVBox/NarrativeLog

var _typing_queue: Array[String] = []
var _is_typing: bool = false


func _ready() -> void:
	GameState.narrative_received.connect(_on_narrative)
	load_history(GameState.narrative_history)


func load_history(lines: Array[String]) -> void:
	narrative_log.clear()
	for line in lines:
		_append_block(line)


func append_system_text(text: String) -> void:
	_append_block(text)


func append_command(command_text: String) -> void:
	_append_block("[color=cyan]> %s[/color]" % command_text)


func show_thinking_indicator() -> void:
	_append_block("[color=gray][The DM is thinking...][/color]")


func get_plain_text() -> String:
	return narrative_log.get_parsed_text()


func _on_narrative(text: String) -> void:
	_typing_queue.append(text)
	if not _is_typing:
		_process_typing_queue()


func _process_typing_queue() -> void:
	_is_typing = true
	while not _typing_queue.is_empty():
		var text = _typing_queue.pop_front()
		await _type_text(text)
	_is_typing = false


func _type_text(text: String) -> void:
	var index = 0
	var chars_added = 0
	while index < text.length():
		if text[index] == "[":
			var end_index = text.find("]", index)
			if end_index != -1:
				narrative_log.append_text(text.substr(index, end_index - index + 1))
				index = end_index + 1
				continue
		narrative_log.append_text(text[index])
		index += 1
		chars_added += 1
		if chars_added % 3 == 0:
			await get_tree().process_frame
	narrative_log.append_text("\n\n")
	await get_tree().process_frame
	narrative_log.scroll_to_line(narrative_log.get_line_count())


func _append_block(text: String) -> void:
	narrative_log.append_text(text + "\n\n")
	narrative_log.scroll_to_line(narrative_log.get_line_count())
