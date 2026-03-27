extends PanelContainer
class_name CharacterPanelWidget

@onready var summary_label: Label = $CharacterMargin/CharacterVBox/SummaryLabel
@onready var stats_text: RichTextLabel = $CharacterMargin/CharacterVBox/StatsText


func _ready() -> void:
	GameState.state_updated.connect(_refresh)
	GameState.character_sheet_updated.connect(_on_character_sheet_updated)
	_refresh()


func _on_character_sheet_updated(_sheet: Dictionary) -> void:
	_refresh()


func _refresh() -> void:
	var sheet = GameState.character_sheet
	if sheet.is_empty():
		sheet = _fallback_sheet()
	if sheet.is_empty():
		summary_label.text = "No active character"
		stats_text.clear()
		stats_text.text = "Character sheet data will appear here."
		return

	summary_label.text = "%s  |  %s  |  %s" % [
		str(sheet.get("name", "Adventurer")),
		str(sheet.get("class_name", sheet.get("class", "Adventurer"))),
		str(sheet.get("alignment", "TN")),
	]
	stats_text.clear()
	stats_text.text = _build_sheet_text(sheet)


func _build_sheet_text(sheet: Dictionary) -> String:
	var lines: Array[String] = ["[b]Stats[/b]"]
	for stat in sheet.get("stats", []):
		if not (stat is Dictionary):
			continue
		var stat_id = str(stat.get("id", stat.get("ability", "")))
		lines.append("%s %d (%+d)" % [
			stat_id,
			int(stat.get("value", 10)),
			int(stat.get("modifier", 0)),
		])
	lines.append("")
	lines.append("[b]Skills[/b]")
	var skills_written := false
	for skill in sheet.get("skills", []):
		if skill is Dictionary:
			lines.append("%s (%+d)" % [
				str(skill.get("label", skill.get("id", ""))),
				int(skill.get("bonus", 0)),
			])
		else:
			lines.append("%s" % str(skill))
		skills_written = true
	if not skills_written:
		lines.append("None")
	return "\n".join(lines)


func _fallback_sheet() -> Dictionary:
	if GameState.player.is_empty():
		return {}
	var stats: Array = []
	for ability in ["MIG", "AGI", "END", "MND", "INS", "PRE"]:
		var value = int(GameState.player.get("stats", {}).get(ability, 10))
		stats.append({
			"id": ability,
			"value": value,
			"modifier": int((value - 10) / 2),
		})
	return {
		"name": str(GameState.player.get("name", "Adventurer")),
		"class_name": str(GameState.player.get("player_class", "Adventurer")).capitalize(),
		"alignment": str(GameState.player.get("alignment", "TN")),
		"stats": stats,
		"skills": GameState.player.get("skill_proficiencies", []),
	}
