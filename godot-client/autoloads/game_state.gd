extends Node

# GameState Singleton — central state store
# Updated after every HTTP response from backend

# Session
var session_id: String = ""
var player: Dictionary = {}
var scene: String = "exploration"  # exploration | combat | dialogue | rest
var location: String = ""
var combat_state: Dictionary = {}
var narrative_history: Array[String] = []
var level_up_pending: Dictionary = {}
var map_data: Dictionary = {}
var entities: Dictionary = {}
var narrative_stream: Array = []
var player_map_pos: Vector2i = Vector2i(10, 7)  # Player position on tile map
var player_facing: int = 2  # 0=N,1=E,2=S,3=W — default facing south

# Signals
signal state_updated
signal combat_started
signal combat_ended
signal level_up_occurred(new_level: int)
signal narrative_received(text: String)
signal scene_changed(new_scene: String)
signal map_loaded(map_data: Dictionary)
signal entities_loaded(entities: Dictionary)
signal entity_revealed(entity_id: String)

func update_from_response(data: Dictionary) -> void:
	if data.has("session_id"):
		session_id = data["session_id"]

	if data.has("player"):
		player = data["player"]
		# Update player map position if backend provides it
		if player.has("position"):
			var pos = player["position"]
			player_map_pos = Vector2i(int(pos[0]), int(pos[1]))

	if data.has("location"):
		location = data["location"]

	# Narrative
	if data.has("narrative") and data["narrative"] != "":
		var text = _clean_narrative(data["narrative"])
		narrative_history.append(text)
		if narrative_history.size() > 50:
			narrative_history.pop_front()
		narrative_received.emit(text)

	# Scene change
	if data.has("scene") and data["scene"] != scene:
		var old_scene = scene
		scene = data["scene"]
		scene_changed.emit(scene)

		if scene == "combat" and old_scene != "combat":
			combat_started.emit()
		elif old_scene == "combat" and scene != "combat":
			combat_ended.emit()

	# Combat state
	if data.has("combat_state") and data["combat_state"] != null:
		combat_state = data["combat_state"]
		if combat_state.get("ended", false):
			combat_ended.emit()
	else:
		combat_state = {}

	# Level up
	if data.has("level_up") and data["level_up"] != null:
		level_up_pending = data["level_up"]
		level_up_occurred.emit(level_up_pending.get("new_level", 0))

	# Map data (from scene/enter)
	if data.has("map_data"):
		map_data = data["map_data"]
		map_loaded.emit(map_data)

	if data.has("entities"):
		entities = data["entities"]
		entities_loaded.emit(entities)

	if data.has("narrative_stream"):
		narrative_stream = data["narrative_stream"]
		for item in narrative_stream:
			if item.has("text") and item["text"] != "":
				var clean = _clean_narrative(item["text"])
				narrative_history.append(clean)
				narrative_received.emit(clean)
			# Emit reveal signal if present
			if item.has("reveal") and item["reveal"] != null:
				var reveal = item["reveal"]
				if reveal.has("id"):
					entity_revealed.emit(reveal["id"])

	state_updated.emit()

func reset() -> void:
	session_id = ""
	player = {}
	scene = "exploration"
	location = ""
	combat_state = {}
	narrative_history.clear()
	level_up_pending = {}
	map_data = {}
	entities = {}
	narrative_stream = []
	player_map_pos = Vector2i(10, 7)
	player_facing = 2

func is_in_combat() -> bool:
	return scene == "combat" and not combat_state.is_empty()

func get_player_hp_ratio() -> float:
	var hp = player.get("hp", 0)
	var max_hp = player.get("max_hp", 1)
	return float(hp) / float(max_hp)

func get_display_location() -> String:
	if location.is_empty():
		return "Unknown"
	return location.replace("_", " ").capitalize()

func _clean_narrative(text: String) -> String:
	# Detect and block raw LLM prompt leaks
	# Only block if MULTIPLE markers match (single match might be false positive)
	var lower = text.to_lower()
	var prompt_markers = [
		"generate merchant's response",
		"generate npc response",
		"generate response as they would",
		"in character with their personality",
		"respond as this character",
		"you are a dungeon master",
		"system prompt",
		"[instruction]",
	]
	var match_count = 0
	for marker in prompt_markers:
		if lower.contains(marker):
			match_count += 1
	if match_count >= 2:
		# Definite prompt leak — multiple markers
		print("[GameState] Blocked prompt leak (%d markers): %s" % [match_count, text.substr(0, 80)])
		return "..."
	if match_count == 1 and text.length() > 200:
		# Long text with one marker — likely prompt leak
		print("[GameState] Blocked long prompt leak: %s" % text.substr(0, 80))
		return "..."

	# Remove markdown headers and clean technical names
	var lines = text.split("\n")
	var cleaned: Array[String] = []
	for line in lines:
		var trimmed = line.strip_edges()
		if trimmed.begins_with("# "):
			continue
		if trimmed.begins_with("## "):
			continue
		if trimmed.is_empty():
			continue
		# Replace technical location names with display names
		trimmed = trimmed.replace("harbor_town", "Harbor Town")
		trimmed = trimmed.replace("forest_road", "Forest Road")
		trimmed = trimmed.replace("dark_dungeon", "Dark Dungeon")
		cleaned.append(trimmed)
	return "\n".join(cleaned)
