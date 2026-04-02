extends RefCounted
class_name CreationWizardState

const CreationCatalog = preload("res://scripts/ui/creation_catalog.gd")


static func current_question(payload: Dictionary) -> Dictionary:
	for question in payload.get("questions", []):
		var question_id := str(question.get("id", ""))
		if not answer_map(payload).has(question_id):
			return question
	return {}


static func current_question_index(payload: Dictionary) -> int:
	var active_question := current_question(payload)
	var index := 0
	for question in payload.get("questions", []):
		if str(question.get("id", "")) == str(active_question.get("id", "")):
			return index
		index += 1
	return 0


static func answer_map(payload: Dictionary) -> Dictionary:
	var result := {}
	for entry in payload.get("answers", []):
		result[str(entry.get("question_id", ""))] = str(entry.get("answer_id", ""))
	return result


static func history_source(payload: Dictionary) -> String:
	var genesis: Dictionary = payload.get("campaign_genesis", {})
	var lines: Array[String] = []
	for raw_event in genesis.get("history_events", []):
		var event_text := str(raw_event).strip_edges()
		if not event_text.is_empty():
			lines.append(event_text)
	if lines.is_empty():
		var premise := _ensure_sentence(str(genesis.get("world_premise", "A frontier waits to be named.")).strip_edges())
		var pressure := _ensure_sentence(
			str(genesis.get("starting_pressure", "The first campfire burns under a suspicious dark.")).strip_edges()
		)
		lines.append("Year 1: %s" % premise)
		lines.append("Year 19: %s" % pressure)
	return "\n".join(lines)


static func sync_build_defaults(owner) -> void:
	owner._selected_class_id = str(owner._payload.get("recommended_class", CreationCatalog.default_class_id(owner._catalog)))
	owner._selected_alignment = str(owner._payload.get("recommended_alignment", "TN"))
	owner._selected_skills = string_array(owner._payload.get("recommended_skills", []))
	owner._assigned_stats = CreationCatalog.suggested_stats_for(
		owner._catalog,
		owner._selected_class_id,
		owner._payload.get("current_roll", []),
	)


static func string_array(values) -> Array[String]:
	var result: Array[String] = []
	if values is Array:
		for value in values:
			result.append(str(value))
	return result


static func step_name(step: int) -> String:
	return [
		"Step 0: Genre",
		"Step 1: Questions",
		"Step 2: History",
		"Step 3: Rolling",
		"Step 4: Build",
		"Step 5: Dossier",
	][step]


static func preview_heading(step: int) -> String:
	return ["Genre", "Question", "History", "Rolled Pool", "Build", "Dossier"][step]


static func _ensure_sentence(text: String) -> String:
	var trimmed := text.strip_edges()
	if trimmed.is_empty():
		return "The frontier waits."
	if trimmed.ends_with(".") or trimmed.ends_with("!") or trimmed.ends_with("?"):
		return trimmed
	return "%s." % trimmed
