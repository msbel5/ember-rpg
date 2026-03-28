extends PanelContainer
class_name NarrativePanelWidget

const TOKEN_REPLACEMENTS := {
	"resume_campaign_ok.": "You steady yourself and step back into the campaign.",
}

@onready var narrative_log: RichTextLabel = $NarrativeMargin/NarrativeVBox/NarrativeLog

var _typing_queue: Array[String] = []
var _is_typing: bool = false


func _ready() -> void:
	GameState.narrative_received.connect(_on_narrative)
	load_history(GameState.narrative_history)


func load_history(lines: Array[String]) -> void:
	narrative_log.clear()
	for line in lines:
		_append_block(_normalize_display_text(line))


func append_system_text(text: String) -> void:
	_append_block(_normalize_display_text(text))


func append_command(command_text: String) -> void:
	_append_block("[color=cyan]> %s[/color]" % command_text)


func show_thinking_indicator() -> void:
	_append_block("[color=gray][The DM is thinking...][/color]")


func get_plain_text() -> String:
	return narrative_log.get_parsed_text()


func _on_narrative(text: String) -> void:
	_typing_queue.append(_normalize_display_text(text))
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
	_scroll_to_latest_paragraph()


func _append_block(text: String) -> void:
	narrative_log.append_text(text + "\n\n")
	_scroll_to_latest_paragraph()


func _normalize_display_text(text: String) -> String:
	var raw = text.strip_edges()
	if raw.is_empty():
		return text
	if TOKEN_REPLACEMENTS.has(raw):
		return str(TOKEN_REPLACEMENTS[raw])
	if raw.contains("_") and not raw.contains(" "):
		var punctuation := ""
		if raw.ends_with(".") or raw.ends_with("!") or raw.ends_with("?"):
			punctuation = raw.right(1)
			raw = raw.left(raw.length() - 1)
		var parts = raw.split("_", false)
		for index in range(parts.size()):
			var part = str(parts[index])
			if part == "ok":
				parts[index] = "ready"
			elif not part.is_empty():
				parts[index] = part.capitalize()
		return " ".join(parts) + punctuation
	return text


func _scroll_to_latest_paragraph() -> void:
	var paragraph_index = maxi(narrative_log.get_paragraph_count() - 2, 0)
	narrative_log.scroll_to_paragraph(paragraph_index)
