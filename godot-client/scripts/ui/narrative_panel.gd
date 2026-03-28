extends PanelContainer
class_name NarrativePanelWidget

const TOKEN_REPLACEMENTS := {
	"resume_campaign_ok.": "You step back into the campaign.",
}
const MAX_VISIBLE_BLOCKS := 3

@onready var narrative_log: RichTextLabel = $NarrativeMargin/NarrativeVBox/NarrativeLog

var _typing_queue: Array[String] = []
var _is_typing: bool = false
var _display_blocks: Array[String] = []


func _ready() -> void:
	GameState.narrative_received.connect(_on_narrative)
	load_history(GameState.narrative_history)


func load_history(lines: Array[String]) -> void:
	narrative_log.clear()
	_display_blocks.clear()
	var start_index := maxi(lines.size() - MAX_VISIBLE_BLOCKS, 0)
	for index in range(start_index, lines.size()):
		_store_block(_normalize_display_text(str(lines[index])))
	_refresh_visible_blocks()


func append_system_text(text: String) -> void:
	_append_block(_normalize_display_text(text))


func append_command(command_text: String) -> void:
	_append_block("[color=cyan]> %s[/color]" % command_text)


func show_thinking_indicator() -> void:
	_append_block("[color=gray]The scene holds for a breath while the next beat settles.[/color]")


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
	_store_block(text)
	_refresh_visible_blocks()
	await get_tree().process_frame


func _append_block(text: String) -> void:
	_store_block(text)
	_refresh_visible_blocks()


func _normalize_display_text(text: String) -> String:
	var raw = text.strip_edges()
	if raw.is_empty():
		return text
	if TOKEN_REPLACEMENTS.has(raw):
		return str(TOKEN_REPLACEMENTS[raw])
	var embellished = _embellish_backend_line(raw)
	if embellished != raw:
		return embellished
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


func _embellish_backend_line(raw: String) -> String:
	if raw.contains("The DM is thinking"):
		return "The scene holds for a breath while the next beat settles."
	if raw.begins_with("You move "):
		var direction = raw.trim_prefix("You move ")
		var punctuation_index = direction.find(".")
		if punctuation_index >= 0:
			direction = direction.substr(0, punctuation_index)
		direction = direction.replace("(Position:", "").strip_edges()
		return "You head %s." % direction
	if raw.begins_with("You examine "):
		var subject = raw.trim_prefix("You examine ").trim_suffix(".").strip_edges()
		return "You study the %s." % subject
	if raw.begins_with("You attack "):
		var target = raw.trim_prefix("You attack ").trim_suffix(".").strip_edges()
		return "You lunge at %s." % target
	if raw.begins_with("You pick up "):
		var item = raw.trim_prefix("You pick up ").trim_suffix(".").strip_edges()
		return "You grab %s." % item
	if raw.begins_with("You talk to "):
		var speaker = raw.trim_prefix("You talk to ").trim_suffix(".").strip_edges()
		return "You turn to %s." % speaker
	if raw.begins_with("Established "):
		var subject = raw.trim_prefix("Established ").trim_suffix(".").strip_edges()
		return "The district secures %s." % subject
	if raw.begins_with("Built "):
		var subject_built = raw.trim_prefix("Built ").trim_suffix(".").strip_edges()
		return "Fresh work rises around %s." % subject_built
	return raw


func _store_block(text: String) -> void:
	_display_blocks.append(text)
	while _display_blocks.size() > MAX_VISIBLE_BLOCKS:
		_display_blocks.pop_front()


func _refresh_visible_blocks() -> void:
	narrative_log.clear()
	var latest_start_line := 0
	for index in range(_display_blocks.size()):
		if index == _display_blocks.size() - 1:
			latest_start_line = narrative_log.get_line_count()
		narrative_log.append_text(str(_display_blocks[index]) + "\n\n")
	call_deferred("_scroll_to_latest_block", latest_start_line)


func _scroll_to_latest_block(start_line: int) -> void:
	if not is_inside_tree() or not is_instance_valid(narrative_log):
		return
	narrative_log.scroll_to_line(maxi(start_line, 0))
