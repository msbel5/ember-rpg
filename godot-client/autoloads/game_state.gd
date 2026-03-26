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
var world_entities: Array = []
var inventory_items: Array = []
var ground_items: Array = []
var active_quests: Array = []
var quest_offers: Array = []
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
signal inventory_updated(items: Array)

func update_from_response(data: Dictionary) -> void:
	if data.has("session_id"):
		session_id = data["session_id"]

	if data.has("player"):
		player = data["player"]
		if player.has("position") and player["position"] is Array and player["position"].size() >= 2:
			var pos = player["position"]
			player_map_pos = Vector2i(int(pos[0]), int(pos[1]))
		if player.has("facing"):
			player_facing = _facing_to_int(str(player["facing"]))

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

	var normalized_combat = _normalize_combat_payload(data)
	if normalized_combat != null:
		combat_state = normalized_combat
		if combat_state.get("ended", false):
			combat_ended.emit()
	elif data.has("combat_state") or data.has("combat"):
		combat_state = {}

	# Level up
	if data.has("level_up") and data["level_up"] != null:
		level_up_pending = data["level_up"]
		level_up_occurred.emit(level_up_pending.get("new_level", 0))

	var normalized_map = _normalize_map_payload(data)
	if not normalized_map.is_empty():
		map_data = normalized_map
		map_loaded.emit(map_data)

	if data.has("world_entities") and data["world_entities"] is Array:
		world_entities = data["world_entities"]
	var normalized_entities = _normalize_entities_payload(data)
	if not normalized_entities.is_empty():
		entities = normalized_entities
		entities_loaded.emit(entities)

	if data.has("ground_items") and data["ground_items"] is Array:
		ground_items = data["ground_items"]

	if data.has("active_quests") and data["active_quests"] is Array:
		active_quests = data["active_quests"]
	if data.has("quest_offers") and data["quest_offers"] is Array:
		quest_offers = data["quest_offers"]

	if data.has("items") and data["items"] is Array:
		inventory_items = data["items"]
		player["inventory"] = data["items"]
		if data.has("gold"):
			player["gold"] = int(data["gold"])
		inventory_updated.emit(inventory_items)
	elif player.has("inventory") and player["inventory"] is Array:
		inventory_items = player["inventory"]
		inventory_updated.emit(inventory_items)

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
	world_entities = []
	inventory_items = []
	ground_items = []
	active_quests = []
	quest_offers = []
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

func _normalize_combat_payload(data: Dictionary) -> Dictionary:
	if data.has("combat_state") and data["combat_state"] is Dictionary:
		return data["combat_state"]
	if data.has("combat") and data["combat"] is Dictionary:
		return data["combat"]
	return {}

func _normalize_map_payload(data: Dictionary) -> Dictionary:
	if data.has("map_data") and data["map_data"] is Dictionary:
		return data["map_data"]
	if data.has("map") and data["map"] is Dictionary:
		var normalized = map_data.duplicate(true) if not map_data.is_empty() else {}
		normalized.merge(data["map"], true)
		return normalized
	return {}

func _normalize_entities_payload(data: Dictionary) -> Dictionary:
	if data.has("entities"):
		if data["entities"] is Dictionary:
			return data["entities"]
		if data["entities"] is Array:
			return _group_entity_list(data["entities"])
	if data.has("world_entities") and data["world_entities"] is Array:
		return _group_world_entities(data["world_entities"])
	return {}

func _group_entity_list(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": _guess_entity_template(entry),
			"position": entry.get("position", [0, 0]),
			"role": entry.get("role", ""),
			"context_actions": _context_actions_for(entry),
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped

func _group_world_entities(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("entity_type", "npc")).to_lower()
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": _guess_entity_template(entry),
			"position": entry.get("position", [0, 0]),
			"context_actions": _context_actions_for(entry),
			"is_hostile": str(entry.get("disposition", "")).to_lower() == "hostile",
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type == "creature" or normalized["is_hostile"]:
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped

func _guess_entity_template(entry: Dictionary) -> String:
	var explicit_template = str(entry.get("template", "")).strip_edges().to_lower()
	if not explicit_template.is_empty():
		return explicit_template
	var role = str(entry.get("role", entry.get("job", ""))).to_lower()
	if not role.is_empty():
		return role.replace(" ", "_")
	var name_hint = str(entry.get("name", "")).to_lower()
	for candidate in ["merchant", "guard", "blacksmith", "priest", "beggar", "goblin", "skeleton", "orc", "wolf", "rat", "spider"]:
		if name_hint.contains(candidate):
			return candidate
	var entity_type = str(entry.get("type", entry.get("entity_type", "warrior"))).to_lower()
	if entity_type == "item":
		return "chest"
	return "warrior"

func _context_actions_for(entry: Dictionary) -> Array:
	if entry.has("context_actions") and entry["context_actions"] is Array:
		return entry["context_actions"]
	var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
	if entity_type == "item":
		return ["examine", "pick up"]
	if entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
		return ["attack", "examine"]
	var role = str(entry.get("role", entry.get("job", ""))).to_lower()
	if ["merchant", "innkeeper", "blacksmith"].has(role):
		return ["talk", "trade", "examine"]
	return ["talk", "examine"]

func _facing_to_int(facing: String) -> int:
	match facing.to_lower():
		"north":
			return 0
		"east":
			return 1
		"south":
			return 2
		"west":
			return 3
	return player_facing
