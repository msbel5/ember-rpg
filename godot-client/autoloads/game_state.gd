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

# Signals
signal state_updated
signal combat_started
signal combat_ended
signal level_up_occurred(new_level: int)
signal narrative_received(text: String)
signal scene_changed(new_scene: String)
signal map_loaded(map_data: Dictionary)
signal entities_loaded(entities: Dictionary)

func update_from_response(data: Dictionary) -> void:
	if data.has("session_id"):
		session_id = data["session_id"]

	if data.has("player"):
		player = data["player"]

	if data.has("location"):
		location = data["location"]

	# Narrative
	if data.has("narrative") and data["narrative"] != "":
		var text = data["narrative"]
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
				narrative_history.append(item["text"])
				narrative_received.emit(item["text"])

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

func is_in_combat() -> bool:
	return scene == "combat" and not combat_state.is_empty()

func get_player_hp_ratio() -> float:
	var hp = player.get("hp", 0)
	var max_hp = player.get("max_hp", 1)
	return float(hp) / float(max_hp)
