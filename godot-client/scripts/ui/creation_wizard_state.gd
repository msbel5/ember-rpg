extends RefCounted
class_name CreationWizardState



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


static func history_timeline(payload: Dictionary) -> Array:
	var genesis: Dictionary = payload.get("campaign_genesis", {})
	var timeline = genesis.get("history_timeline", [])
	if timeline is Array and not timeline.is_empty():
		return timeline
	var fallback: Array = []
	var fallback_sequence := 1
	for raw_event in genesis.get("history_events", []):
		var event_text := str(raw_event).strip_edges()
		if event_text.is_empty():
			continue
		var year := 0
		var era_label := ""
		var summary := event_text
		var headline := "Recorded Event"
		var colon_index := event_text.find(":")
		if colon_index > 0:
			era_label = event_text.substr(0, colon_index).strip_edges()
			summary = event_text.substr(colon_index + 1).strip_edges()
		if event_text.begins_with("Year "):
			if colon_index > 5:
				year = int(event_text.substr(5, colon_index - 5))
			if era_label == "Year %d" % year:
				era_label = "Recorded Era"
		fallback.append({
			"sequence": fallback_sequence,
			"era_label": era_label,
			"year": year,
			"headline": headline,
			"summary": summary,
			"tags": [],
			"importance": 2,
		})
		fallback_sequence += 1
	return fallback


static func history_source(payload: Dictionary) -> String:
	var lines: Array[String] = []
	for entry in history_timeline(payload):
		if not (entry is Dictionary):
			continue
		var headline := str(entry.get("headline", "")).strip_edges()
		var summary := _ensure_sentence(str(entry.get("summary", "")).strip_edges())
		var era_label := str(entry.get("era_label", "")).strip_edges()
		if not era_label.is_empty() and not headline.is_empty():
			lines.append("[b]%s - %s[/b]\n%s" % [era_label, headline, summary])
		elif not era_label.is_empty():
			lines.append("[b]%s[/b]\n%s" % [era_label, summary])
		elif not headline.is_empty():
			lines.append("[b]%s[/b]\n%s" % [headline, summary])
		elif not summary.is_empty():
			lines.append(summary)
	if lines.is_empty():
		var genesis: Dictionary = payload.get("campaign_genesis", {})
		var premise := _ensure_sentence(str(genesis.get("world_premise", "A frontier waits to be named.")).strip_edges())
		var pressure := _ensure_sentence(
			str(genesis.get("starting_pressure", "The first campfire burns under a suspicious dark.")).strip_edges()
		)
		lines.append("[b]Founding Decades - First Omen[/b]\n%s" % premise)
		lines.append("[b]Opening Generation - Frontier Pressure[/b]\n%s" % pressure)
	return "\n\n".join(lines)


static func sync_build_defaults(owner) -> void:
	if not bool(owner._class_locked_by_player):
		owner._selected_class_id = str(owner._payload.get("recommended_class", CreationCatalog.default_class_id(owner._catalog)))
	if not bool(owner._alignment_locked_by_player):
		owner._selected_alignment = str(owner._payload.get("recommended_alignment", "TN"))
	if not bool(owner._skills_locked_by_player):
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
		"Name Your Hero",
		"World Questions",
		"World History",
		"Stat Roll",
		"Class & Skills",
		"Review & Begin",
	][step]


static func preview_heading(step: int) -> String:
	return ["Identity", "Question", "History", "Rolled Pool", "Build", "Dossier"][step]


static func _ensure_sentence(text: String) -> String:
	var trimmed := text.strip_edges()
	if trimmed.is_empty():
		return "The frontier waits."
	if trimmed.ends_with(".") or trimmed.ends_with("!") or trimmed.ends_with("?"):
		return trimmed
	return "%s." % trimmed
