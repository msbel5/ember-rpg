extends PanelContainer
class_name CharacterPanelWidget

const EntitySpriteCatalog = preload("res://scripts/world/entity_sprite_catalog.gd")

@onready var portrait_rect: TextureRect = $CharacterMargin/CharacterVBox/HeaderRow/PortraitFrame/Portrait
@onready var summary_label: Label = $CharacterMargin/CharacterVBox/HeaderRow/HeaderVBox/SummaryLabel
@onready var role_label: Label = $CharacterMargin/CharacterVBox/HeaderRow/HeaderVBox/RoleLabel
@onready var vitals_label: Label = $CharacterMargin/CharacterVBox/HeaderRow/HeaderVBox/VitalsLabel
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
		role_label.text = "Role unavailable"
		vitals_label.text = "No vitals available"
		portrait_rect.texture = null
		stats_text.clear()
		stats_text.text = "Character sheet data will appear here."
		return

	summary_label.text = str(sheet.get("name", "Adventurer"))
	role_label.text = "%s  |  %s" % [
		str(sheet.get("class_name", sheet.get("class", "Adventurer"))),
		str(sheet.get("alignment", "TN")),
	]
	vitals_label.text = _build_vitals_text()
	portrait_rect.texture = EntitySpriteCatalog.resolve_texture(_resolve_template_name(sheet))
	stats_text.clear()
	stats_text.text = _build_sheet_text(sheet)


func _build_sheet_text(sheet: Dictionary) -> String:
	var stat_chunks: Array[String] = []
	for stat in sheet.get("stats", []):
		if not (stat is Dictionary):
			continue
		var stat_id = str(stat.get("id", stat.get("ability", "")))
		stat_chunks.append("%s %d (%+d)" % [
			stat_id,
			int(stat.get("value", 10)),
			int(stat.get("modifier", 0)),
		])
	var lines: Array[String] = []
	if stat_chunks.is_empty():
		lines.append("[b]Stats[/b]  No live stat block.")
	else:
		lines.append("[b]Stats[/b]  %s" % "   ".join(stat_chunks.slice(0, 3)))
		if stat_chunks.size() > 3:
			lines.append("           %s" % "   ".join(stat_chunks.slice(3, min(stat_chunks.size(), 6))))

	var skill_chunks: Array[String] = []
	for skill in sheet.get("skills", []):
		if skill is Dictionary:
			skill_chunks.append("%s (%+d)" % [
				str(skill.get("label", skill.get("id", ""))),
				int(skill.get("bonus", 0)),
			])
		else:
			skill_chunks.append("%s" % str(skill))
	if skill_chunks.is_empty():
		lines.append("[b]Skills[/b]  None")
	else:
		var preview = skill_chunks.slice(0, min(skill_chunks.size(), 4))
		var skill_text = ", ".join(preview)
		if skill_chunks.size() > 4:
			skill_text += "  +%d more" % (skill_chunks.size() - 4)
		lines.append("[b]Skills[/b]  %s" % skill_text)
	return "\n".join(lines)


func _build_vitals_text() -> String:
	var hp = _int_value(GameState.player.get("hp", 0), 0)
	var max_hp = _int_value(GameState.player.get("max_hp", hp), hp)
	var ap = _int_value(GameState.player.get("action_points", GameState.player.get("ap", 0)), 0)
	var max_ap = _int_value(GameState.player.get("max_action_points", GameState.player.get("max_ap", ap)), ap)
	return "HP %d/%d  |  AP %d/%d" % [hp, maxi(max_hp, hp), ap, maxi(max_ap, ap)]


func _resolve_template_name(sheet: Dictionary) -> String:
	var template_name = str(sheet.get("class_name", sheet.get("class", GameState.player.get("player_class", "warrior")))).strip_edges().to_lower()
	if template_name.is_empty():
		return "warrior"
	return template_name


func _int_value(value, fallback: int) -> int:
	match typeof(value):
		TYPE_INT:
			return value
		TYPE_FLOAT:
			return int(value)
		TYPE_STRING:
			return int(value) if str(value).is_valid_int() else fallback
		_:
			return fallback


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
