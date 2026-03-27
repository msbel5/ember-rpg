extends Node

# Backend HTTP Client — all API calls to FastAPI server

const BACKEND_SETTING := "ember_rpg/backend_url"
const BACKEND_ENV := "EMBER_RPG_BACKEND_URL"

var base_url: String = ""

signal request_started
signal request_finished
signal request_error(message: String)

func _ready() -> void:
	base_url = _resolve_base_url()

# --- API Methods ---

func create_session(player_name: String, player_class: String, callback: Callable) -> void:
	var body = JSON.stringify({"player_name": player_name, "player_class": player_class})
	_post("/game/session/new", body, callback)

func start_creation(player_name: String, callback: Callable, location: String = "") -> void:
	var body = JSON.stringify({
		"player_name": player_name,
		"location": location if not location.is_empty() else null
	})
	_post("/game/session/creation/start", body, callback)

func finalize_creation(creation_id: String, player_class: String, alignment: String, callback: Callable, location: String = "") -> void:
	var body = JSON.stringify({
		"player_class": player_class,
		"alignment": alignment,
		"location": location if not location.is_empty() else null
	})
	_post("/game/session/creation/%s/finalize" % creation_id, body, callback)

func submit_action(session_id: String, input_text: String, callback: Callable) -> void:
	var body = JSON.stringify({"input": input_text})
	_post("/game/session/%s/action" % session_id, body, callback)

func get_session(session_id: String, callback: Callable) -> void:
	_http_get("/game/session/%s" % session_id, callback)

func delete_session(session_id: String, callback: Callable) -> void:
	_http_delete("/game/session/%s" % session_id, callback)

func get_map(session_id: String, callback: Callable) -> void:
	_http_get("/game/session/%s/map" % session_id, callback)

func get_inventory(session_id: String, callback: Callable) -> void:
	_http_get("/game/session/%s/inventory" % session_id, callback)

func enter_scene(session_id: String, location: String, callback: Callable, location_type: String = "") -> void:
	var p = _get_player_state()
	var player_name = p.get("name", "Adventurer")
	var player_level = int(p.get("level", 1))
	var body = JSON.stringify({
		"session_id": session_id,
		"location": location,
		"location_type": location_type if not location_type.is_empty() else _infer_location_type(location),
		"player_name": player_name,
		"player_level": player_level
	})
	_post("/game/scene/enter", body, callback)

func save_game(session_id: String, callback: Callable, slot_name: String = "", player_id: String = "") -> void:
	var body = {
		"player_id": _resolve_player_id(player_id),
	}
	if not slot_name.is_empty():
		body["slot_name"] = slot_name
	_post("/game/session/%s/save" % session_id, JSON.stringify(body), callback)

func load_game(save_id: String, callback: Callable) -> void:
	_post("/game/session/load/%s" % save_id, "{}", callback)

func list_saves(callback: Callable, player_id: String = "") -> void:
	_http_get("/game/saves/%s" % _resolve_player_id(player_id), callback)

func delete_save(save_id: String, callback: Callable) -> void:
	_http_delete("/game/saves/%s" % save_id, callback)

func create_campaign(player_name: String, player_class: String, adapter_id: String, callback: Callable, profile_id: String = "standard", seed: int = -1) -> void:
	var body := {
		"player_name": player_name,
		"player_class": player_class,
		"adapter_id": adapter_id,
		"profile_id": profile_id,
	}
	if seed >= 0:
		body["seed"] = seed
	_post("/game/campaigns", JSON.stringify(body), callback)

func get_campaign(campaign_id: String, callback: Callable) -> void:
	_http_get("/game/campaigns/%s" % campaign_id, callback)

func submit_campaign_command(campaign_id: String, input_text: String, callback: Callable, shortcut: String = "", args: Dictionary = {}) -> void:
	var body := {
		"input": input_text,
		"args": args,
	}
	if not shortcut.is_empty():
		body["shortcut"] = shortcut
	_post("/game/campaigns/%s/commands" % campaign_id, JSON.stringify(body), callback)

func get_campaign_region(campaign_id: String, callback: Callable) -> void:
	_http_get("/game/campaigns/%s/region/current" % campaign_id, callback)

func get_campaign_settlement(campaign_id: String, callback: Callable) -> void:
	_http_get("/game/campaigns/%s/settlement/current" % campaign_id, callback)

func save_campaign(campaign_id: String, callback: Callable, slot_name: String = "", player_id: String = "") -> void:
	var body := {}
	var resolved_player_id := _resolve_player_id(player_id)
	if not resolved_player_id.is_empty():
		body["player_id"] = resolved_player_id
	if not slot_name.is_empty():
		body["slot_name"] = slot_name
	_post("/game/campaigns/%s/save" % campaign_id, JSON.stringify(body), callback)

func list_campaign_saves(campaign_id: String, callback: Callable) -> void:
	_http_get("/game/campaigns/%s/saves" % campaign_id, callback)

func load_campaign(save_id: String, callback: Callable) -> void:
	_post("/game/campaigns/load/%s" % save_id, "{}", callback)

func delete_campaign(campaign_id: String, callback: Callable) -> void:
	_http_delete("/game/campaigns/%s" % campaign_id, callback)

# --- Internal HTTP ---

func _resolve_base_url() -> String:
	var env_url := OS.get_environment(BACKEND_ENV).strip_edges()
	if not env_url.is_empty():
		return env_url
	if ProjectSettings.has_setting(BACKEND_SETTING):
		return str(ProjectSettings.get_setting(BACKEND_SETTING)).strip_edges()
	return ""

func _ensure_base_url(callback: Callable) -> bool:
	if not base_url.is_empty():
		return true
	request_error.emit("Backend URL is not configured. Set %s or %s." % [BACKEND_ENV, BACKEND_SETTING])
	callback.call(null)
	return false

func _get_game_state() -> Node:
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		return loop.root.get_node_or_null("GameState")
	return null

func _get_player_state() -> Dictionary:
	var game_state = _get_game_state()
	if game_state == null:
		return {}
	return game_state.player

func _resolve_player_id(explicit_player_id: String = "") -> String:
	var cleaned = explicit_player_id.strip_edges()
	if not cleaned.is_empty():
		return cleaned
	var player_name = str(_get_player_state().get("name", "")).strip_edges()
	if not player_name.is_empty():
		return player_name
	return "player"

func _infer_location_type(location: String) -> String:
	var loc = location.to_lower()
	if loc.contains("forest") or loc.contains("road") or loc.contains("wild"):
		return "wilderness"
	if loc.contains("cave"):
		return "cave"
	if loc.contains("dungeon"):
		return "dungeon"
	if loc.contains("tavern") or loc.contains("inn"):
		return "tavern"
	return "town"

func _post(path: String, body: String, callback: Callable) -> void:
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(http, callback))
	request_started.emit()

	var full_url = base_url + path
	print("[Backend] POST %s body_len=%d" % [full_url, body.length()])
	var headers = ["Content-Type: application/json"]
	var error = http.request(full_url, headers, HTTPClient.METHOD_POST, body)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_get(path: String, callback: Callable) -> void:
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(http, callback))
	request_started.emit()

	var error = http.request(base_url + path)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_delete(path: String, callback: Callable) -> void:
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(http, callback))
	request_started.emit()

	var error = http.request(base_url + path, [], HTTPClient.METHOD_DELETE)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest, callback: Callable) -> void:
	http.queue_free()
	request_finished.emit()
	print("[Backend] Response: result=%d, code=%d, body_size=%d" % [result, response_code, body.size()])

	if result != HTTPRequest.RESULT_SUCCESS:
		request_error.emit("Connection failed — is the backend running?")
		callback.call(null)
		return

	if response_code >= 400:
		var err_text = body.get_string_from_utf8()
		var err_msg = "HTTP %d" % response_code
		var err_data = JSON.parse_string(err_text)
		if err_data and err_data.has("detail"):
			err_msg = str(err_data["detail"])
		if response_code == 404:
			request_error.emit("Session not found. Start a new game?")
		else:
			request_error.emit("Backend error: %s" % err_msg)
		print("[Backend] Error %d: %s" % [response_code, err_msg])
		callback.call(null)
		return

	var text = body.get_string_from_utf8()
	var data = JSON.parse_string(text)
	if data == null:
		request_error.emit("Invalid response from backend")
		callback.call(null)
		return

	callback.call(data)
