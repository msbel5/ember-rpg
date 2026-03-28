extends Node

# GameState Singleton — central state store
# Updated after every HTTP response from backend
const ResponseNormalizer = preload("res://scripts/net/response_normalizer.gd")
const RESUME_SEED_TEXT := "You step back into the campaign."

# Session / Campaign
var active_runtime: String = "session"
var session_id: String = ""
var campaign_id: String = ""
var adapter_id: String = "fantasy_ember"
var profile_id: String = "standard"
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
var last_save_slot: String = ""
var world_state: Dictionary = {}
var settlement_state: Dictionary = {}
var creation_state: Dictionary = {}
var character_sheet: Dictionary = {}
var recent_event_log: Array = []
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
signal settlement_updated(settlement: Dictionary)
signal creation_updated(state: Dictionary)
signal character_sheet_updated(sheet: Dictionary)

func update_from_response(data: Dictionary) -> void:
	if data.has("creation_id"):
		creation_state = data.duplicate(true)
		adapter_id = str(data.get("adapter_id", adapter_id))
		profile_id = str(data.get("profile_id", profile_id))
		if data.has("character_sheet") and data["character_sheet"] is Dictionary:
			character_sheet = data["character_sheet"]
			character_sheet_updated.emit(character_sheet)
		creation_updated.emit(creation_state)
		state_updated.emit()
		return

	if data.has("campaign") and data["campaign"] is Dictionary:
		active_runtime = "campaign"
		session_id = ""
		campaign_id = str(data.get("campaign_id", campaign_id))
		adapter_id = str(data.get("adapter_id", data["campaign"].get("world", {}).get("adapter_id", adapter_id)))
		profile_id = str(data.get("profile_id", data["campaign"].get("world", {}).get("profile_id", profile_id)))
		world_state = data["campaign"].get("world", {})
		settlement_state = data["campaign"].get("settlement", {})
		character_sheet = data["campaign"].get("character_sheet", {})
		if not character_sheet.is_empty():
			character_sheet_updated.emit(character_sheet)
		recent_event_log = data["campaign"].get("recent_event_log", [])
		var flattened_campaign = ResponseNormalizer.flatten_campaign_response(data, map_data)
		update_from_response(flattened_campaign)
		return

	if data.has("session_id"):
		active_runtime = "session"
		session_id = data["session_id"]
	if data.has("campaign_id"):
		campaign_id = str(data["campaign_id"])
	if data.has("adapter_id"):
		adapter_id = str(data["adapter_id"])
	if data.has("profile_id"):
		profile_id = str(data["profile_id"])
	if data.has("world_state") and data["world_state"] is Dictionary:
		world_state = data["world_state"]
	if data.has("settlement_state") and data["settlement_state"] is Dictionary:
		settlement_state = data["settlement_state"]
		settlement_updated.emit(settlement_state)
	if data.has("recent_event_log") and data["recent_event_log"] is Array:
		recent_event_log = data["recent_event_log"]
	if data.has("character_sheet") and data["character_sheet"] is Dictionary:
		character_sheet = data["character_sheet"]
		character_sheet_updated.emit(character_sheet)

	if data.has("player"):
		player = data["player"]
		player_map_pos = ResponseNormalizer.player_position_from(player, player_map_pos)
		if player.has("facing"):
			player_facing = ResponseNormalizer.facing_to_int(str(player["facing"]), player_facing)

	if data.has("location"):
		location = str(data["location"])
	if location.is_empty() and not settlement_state.is_empty():
		location = str(settlement_state.get("name", ""))

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
	if data.has("last_save_slot"):
		last_save_slot = str(data["last_save_slot"])

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
	active_runtime = "session"
	session_id = ""
	campaign_id = ""
	adapter_id = "fantasy_ember"
	profile_id = "standard"
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
	last_save_slot = ""
	world_state = {}
	settlement_state = {}
	creation_state = {}
	character_sheet = {}
	recent_event_log = []
	player_map_pos = Vector2i(10, 7)
	player_facing = 2

func is_in_combat() -> bool:
	return scene == "combat" and not combat_state.is_empty()

func has_active_campaign() -> bool:
	return active_runtime == "campaign" and not campaign_id.is_empty()

func get_player_hp_ratio() -> float:
	var hp = player.get("hp", 0)
	var max_hp = player.get("max_hp", 1)
	return float(hp) / float(max_hp)

func get_display_location() -> String:
	if location.is_empty():
		if not settlement_state.is_empty():
			var settlement_name = str(settlement_state.get("name", "")).strip_edges()
			if not settlement_name.is_empty():
				return settlement_name
		return "Unknown"
	return location.replace("_", " ").capitalize()


func seed_campaign_resume_narrative(backend_text: String = "") -> void:
	var cleaned_backend = _clean_narrative(backend_text.strip_edges())
	var message = RESUME_SEED_TEXT
	if not cleaned_backend.is_empty() and cleaned_backend != backend_text.strip_edges():
		message = cleaned_backend
	narrative_history.clear()
	narrative_history.append(message)

func _clean_narrative(text: String) -> String:
	var raw = text.strip_edges()
	if raw == "resume_campaign_ok.":
		return RESUME_SEED_TEXT

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

	# Strip bracketed debug metadata like [Region: terrain=..., climate=...]
	var stripped = text
	var bracket_start = stripped.find("[Region:")
	while bracket_start >= 0:
		var bracket_end = stripped.find("]", bracket_start)
		if bracket_end >= 0:
			stripped = stripped.substr(0, bracket_start).strip_edges() + " " + stripped.substr(bracket_end + 1).strip_edges()
		else:
			stripped = stripped.substr(0, bracket_start).strip_edges()
		bracket_start = stripped.find("[Region:")
	stripped = stripped.strip_edges()
	if stripped.is_empty():
		stripped = text.strip_edges()

	# Remove markdown headers and clean technical names
	var lines = stripped.split("\n")
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
		trimmed = trimmed.replace("upland_continent", "the uplands")
		trimmed = trimmed.replace("harbor_town", "Harbor Town")
		trimmed = trimmed.replace("forest_road", "Forest Road")
		trimmed = trimmed.replace("dark_dungeon", "Dark Dungeon")
		trimmed = trimmed.replace("temperate_band", "temperate region")
		cleaned.append(trimmed)
	return "\n".join(cleaned)

func _normalize_combat_payload(data: Dictionary) -> Dictionary:
	return ResponseNormalizer.normalize_combat(data)

func _normalize_map_payload(data: Dictionary) -> Dictionary:
	return ResponseNormalizer.normalize_map(data, map_data)

func _normalize_entities_payload(data: Dictionary) -> Dictionary:
	return ResponseNormalizer.normalize_entities(data)

func _group_entity_list(raw_entities: Array) -> Dictionary:
	return ResponseNormalizer.group_entity_list(raw_entities)

func _group_world_entities(raw_entities: Array) -> Dictionary:
	return ResponseNormalizer.group_world_entities(raw_entities)

func _guess_entity_template(entry: Dictionary) -> String:
	return ResponseNormalizer.guess_entity_template(entry)

func _context_actions_for(entry: Dictionary) -> Array:
	return ResponseNormalizer.context_actions_for(entry)

func _facing_to_int(facing: String) -> int:
	return ResponseNormalizer.facing_to_int(facing, player_facing)
