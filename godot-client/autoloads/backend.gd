extends Node

# Backend HTTP Client — all API calls to FastAPI server

const BACKEND_SETTING := "ember_rpg/backend_url"
const BACKEND_ENV := "EMBER_RPG_BACKEND_URL"
const DEFAULT_BACKEND_URL := "http://127.0.0.1:8741"

var base_url: String = ""

signal request_started
signal request_finished
signal request_error(message: String)
signal runtime_socket_connected(campaign_id: String)
signal runtime_socket_disconnected(campaign_id: String, reason: String)
signal runtime_message_received(message: Dictionary)

var _runtime_socket: WebSocketPeer
var _runtime_campaign_id: String = ""
var _runtime_connected: bool = false
var _runtime_url: String = ""

func _ready() -> void:
	base_url = _resolve_base_url()
	set_process(true)


func _exit_tree() -> void:
	test_cleanup()


func _process(_delta: float) -> void:
	_poll_runtime_socket()


func set_base_url(url: String) -> void:
	base_url = url.strip_edges().trim_suffix("/")


func get_base_url() -> String:
	return base_url


func ensure_runtime_socket(campaign_id: String, explicit_ws_url: String = "", explicit_ws_path: String = "") -> void:
	# Bridge path: no WebSocket needed, PythonBridge polls ticks directly
	if _use_bridge():
		var pb = get_node_or_null("/root/PythonBridge")
		pb.set_active_campaign(campaign_id)
		# Emit connected signal so game_session proceeds normally
		if not _runtime_connected:
			_runtime_connected = true
			_runtime_campaign_id = campaign_id
			runtime_socket_connected.emit(campaign_id)
		return

	var normalized_campaign := campaign_id.strip_edges()
	if normalized_campaign.is_empty():
		return
	var next_url := explicit_ws_url.strip_edges()
	if next_url.is_empty():
		var ws_path := explicit_ws_path.strip_edges()
		if ws_path.is_empty():
			ws_path = "/game/ws/campaigns/%s" % normalized_campaign
		next_url = _build_ws_url(ws_path)
	if next_url.is_empty():
		request_error.emit("Runtime socket URL is not configured.")
		return
	if _runtime_connected and normalized_campaign == _runtime_campaign_id and next_url == _runtime_url:
		return
	if _runtime_socket != null and normalized_campaign == _runtime_campaign_id and next_url == _runtime_url:
		return
	close_runtime_socket("reconnect")
	_runtime_socket = WebSocketPeer.new()
	var error := _runtime_socket.connect_to_url(next_url)
	if error != OK:
		_runtime_socket = null
		request_error.emit("Runtime socket failed: %s" % error_string(error))
		return
	_runtime_campaign_id = normalized_campaign
	_runtime_url = next_url
	_runtime_connected = false


func close_runtime_socket(reason: String = "closed") -> void:
	if _runtime_socket != null:
		_runtime_socket.close()
	_runtime_socket = null
	if _runtime_connected:
		runtime_socket_disconnected.emit(_runtime_campaign_id, reason)
	_runtime_connected = false
	_runtime_campaign_id = ""
	_runtime_url = ""


func test_cleanup() -> void:
	set_process(false)
	close_runtime_socket("test_cleanup")
	_cleanup_pending_http_requests()


func _cleanup_pending_http_requests() -> void:
	for child in get_children():
		if child is HTTPRequest:
			var request: HTTPRequest = child
			request.cancel_request()
			request.queue_free()


func runtime_submit_command(campaign_id: String, input_text: String, shortcut: String = "", args: Dictionary = {}) -> bool:
	# Bridge path: direct engine call, no WebSocket
	if _use_bridge():
		var pb = get_node_or_null("/root/PythonBridge")
		var cmd_args := {"campaign_id": campaign_id, "input": input_text, "args": args}
		if not shortcut.strip_edges().is_empty():
			cmd_args["shortcut"] = shortcut.strip_edges().to_lower()
		var result = pb.call_engine("run_command", cmd_args)
		# Emit the response as a runtime message so existing handlers process it
		runtime_message_received.emit({"type": "state", "payload": result})
		return true

	if not _runtime_socket_ready(campaign_id):
		return false
	var payload := {
		"type": "command",
		"input": input_text,
		"args": args,
	}
	if not shortcut.strip_edges().is_empty():
		payload["shortcut"] = shortcut.strip_edges().to_lower()
	return _send_runtime_payload(payload)


func set_runtime_mode(campaign_id: String, mode: String) -> bool:
	# Bridge path
	if _use_bridge():
		var pb = get_node_or_null("/root/PythonBridge")
		pb.call_engine("set_runtime_mode", {"campaign_id": campaign_id, "mode": mode})
		return true

	if not _runtime_socket_ready(campaign_id):
		return false
	var normalized_mode := mode.strip_edges().to_lower()
	if normalized_mode.is_empty():
		return false
	return _send_runtime_payload({
		"type": "runtime_mode",
		"mode": normalized_mode,
	})


func runtime_connected_for(campaign_id: String) -> bool:
	if _use_bridge():
		return true  # Bridge is always "connected"
	return _runtime_connected and campaign_id.strip_edges() == _runtime_campaign_id

# --- API Methods ---

func create_campaign(player_name: String, player_class: String, adapter_id: String, callback: Callable, profile_id: String = "standard", world_seed: int = -1) -> void:
	var body := {
		"player_name": player_name,
		"player_class": player_class,
		"adapter_id": adapter_id,
		"profile_id": profile_id,
	}
	if world_seed >= 0:
		body["seed"] = world_seed
	_post("/game/campaigns", JSON.stringify(body), callback)

func get_campaign_creation_catalog(callback: Callable) -> void:
	_http_get("/game/campaigns/creation/catalog", callback)

func start_campaign_creation(player_name: String, adapter_id: String, callback: Callable, profile_id: String = "standard", world_seed: int = -1, location: String = "") -> void:
	var body := {
		"player_name": player_name,
		"adapter_id": adapter_id,
		"profile_id": profile_id,
	}
	if world_seed >= 0:
		body["seed"] = world_seed
	if not location.is_empty():
		body["location"] = location
	_post("/game/campaigns/creation/start", JSON.stringify(body), callback)

func answer_campaign_creation(creation_id: String, question_id: String, answer_id: String, callback: Callable) -> void:
	var body := {
		"question_id": question_id,
		"answer_id": answer_id,
	}
	_post("/game/campaigns/creation/%s/answer" % creation_id, JSON.stringify(body), callback)

func reroll_campaign_creation(creation_id: String, callback: Callable) -> void:
	_post("/game/campaigns/creation/%s/reroll" % creation_id, "{}", callback)

func save_campaign_creation_roll(creation_id: String, callback: Callable) -> void:
	_post("/game/campaigns/creation/%s/save-roll" % creation_id, "{}", callback)

func swap_campaign_creation_roll(creation_id: String, callback: Callable) -> void:
	_post("/game/campaigns/creation/%s/swap-roll" % creation_id, "{}", callback)

func finalize_campaign_creation(creation_id: String, callback: Callable, payload: Dictionary = {}) -> void:
	_post("/game/campaigns/creation/%s/finalize" % creation_id, JSON.stringify(payload), callback)

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

func list_player_campaign_saves(player_id: String, callback: Callable) -> void:
	_http_get("/game/campaigns/saves/player/%s" % _resolve_player_id(player_id), callback)

func load_campaign(save_id: String, callback: Callable) -> void:
	_post("/game/campaigns/load/%s" % save_id, "{}", callback)

func delete_campaign_save(save_id: String, callback: Callable) -> void:
	_http_delete("/game/campaigns/saves/%s" % save_id, callback)

func delete_campaign(campaign_id: String, callback: Callable) -> void:
	_http_delete("/game/campaigns/%s" % campaign_id, callback)


func get_campaign_client_health(callback: Callable) -> void:
	_http_get("/game/health/campaign-client", callback)

# --- Internal HTTP ---

func _resolve_base_url() -> String:
	var env_url := OS.get_environment(BACKEND_ENV).strip_edges()
	if not env_url.is_empty():
		return env_url
	if ProjectSettings.has_setting(BACKEND_SETTING):
		var configured = str(ProjectSettings.get_setting(BACKEND_SETTING)).strip_edges()
		if not configured.is_empty():
			return configured
	return DEFAULT_BACKEND_URL

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


func _build_ws_url(path: String) -> String:
	var normalized_path := path.strip_edges()
	if normalized_path.is_empty():
		return ""
	var origin := base_url if not base_url.is_empty() else _resolve_base_url()
	if origin.begins_with("https://"):
		origin = "wss://%s" % origin.trim_prefix("https://")
	elif origin.begins_with("http://"):
		origin = "ws://%s" % origin.trim_prefix("http://")
	if not normalized_path.begins_with("/"):
		normalized_path = "/%s" % normalized_path
	return origin.trim_suffix("/") + normalized_path


func _runtime_socket_ready(campaign_id: String) -> bool:
	if _runtime_socket == null:
		return false
	if campaign_id.strip_edges() != _runtime_campaign_id:
		return false
	return _runtime_socket.get_ready_state() == WebSocketPeer.STATE_OPEN


func _send_runtime_payload(payload: Dictionary) -> bool:
	if _runtime_socket == null:
		return false
	var error := _runtime_socket.send_text(JSON.stringify(payload))
	if error != OK:
		request_error.emit("Runtime socket send failed: %s" % error_string(error))
		return false
	return true


func _poll_runtime_socket() -> void:
	if _runtime_socket == null:
		return
	_runtime_socket.poll()
	var state := _runtime_socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN and not _runtime_connected:
		_runtime_connected = true
		runtime_socket_connected.emit(_runtime_campaign_id)
	elif state == WebSocketPeer.STATE_CLOSED:
		var code := _runtime_socket.get_close_code()
		var reason := _runtime_socket.get_close_reason()
		close_runtime_socket("closed:%s:%s" % [code, reason])
		return
	while _runtime_socket.get_available_packet_count() > 0:
		var packet := _runtime_socket.get_packet()
		var parsed = JSON.parse_string(packet.get_string_from_utf8())
		if parsed is Dictionary:
			runtime_message_received.emit(parsed)
		else:
			request_error.emit("Runtime socket delivered invalid JSON.")

## Check if PythonBridge is available and connected.
func _use_bridge() -> bool:
	var pb = get_node_or_null("/root/PythonBridge")
	return pb != null and pb.backend_ready


## Route an HTTP-like call through PythonBridge (in-process, ~0.1ms).
## Falls back to real HTTP if bridge is not available.
func _bridge_call(path: String, body_dict: Dictionary, http_method: String, callback: Callable) -> void:
	var pb = get_node_or_null("/root/PythonBridge")
	if pb == null:
		return
	body_dict["_http_method"] = http_method
	var result = pb.call_engine(path, body_dict)
	if callback.is_valid():
		callback.call(result)
	request_finished.emit()


func _post(path: String, body: String, callback: Callable) -> void:
	# Bridge path: in-process call, no HTTP, ~0.1ms
	if _use_bridge():
		var body_dict = JSON.parse_string(body) if not body.is_empty() else {}
		if body_dict == null:
			body_dict = {}
		_bridge_call(path, body_dict, "POST", callback)
		return

	# HTTP fallback
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(path, http, callback))
	request_started.emit()

	var full_url = base_url + path
	print("[Backend] POST %s body_len=%d" % [full_url, body.length()])
	var headers = ["Content-Type: application/json"]
	var error = http.request(full_url, headers, HTTPClient.METHOD_POST, body)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_get(path: String, callback: Callable) -> void:
	# Bridge path
	if _use_bridge():
		_bridge_call(path, {}, "GET", callback)
		return

	# HTTP fallback
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(path, http, callback))
	request_started.emit()

	var error = http.request(base_url + path)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_delete(path: String, callback: Callable) -> void:
	# Bridge path
	if _use_bridge():
		_bridge_call(path, {}, "DELETE", callback)
		return

	# HTTP fallback
	if not _ensure_base_url(callback):
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(path, http, callback))
	request_started.emit()

	var error = http.request(base_url + path, [], HTTPClient.METHOD_DELETE)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, path: String, http: HTTPRequest, callback: Callable) -> void:
	http.queue_free()
	request_finished.emit()
	print("[Backend] Response: result=%d, code=%d, body_size=%d" % [result, response_code, body.size()])

	if result != HTTPRequest.RESULT_SUCCESS:
		request_error.emit("Connection failed — is the backend running?")
		if callback.is_valid():
			callback.call(null)
		return

	if response_code >= 400:
		var err_text = body.get_string_from_utf8()
		var err_msg = "HTTP %d" % response_code
		var err_data = JSON.parse_string(err_text)
		if err_data and err_data.has("detail"):
			err_msg = str(err_data["detail"])
		if response_code == 404:
			request_error.emit(_not_found_message_for(path))
		else:
			request_error.emit("Backend error: %s" % err_msg)
		print("[Backend] Error %d: %s" % [response_code, err_msg])
		if callback.is_valid():
			callback.call(null)
		return

	var text = body.get_string_from_utf8()
	var data = JSON.parse_string(text)
	if data == null:
		request_error.emit("Invalid response from backend")
		if callback.is_valid():
			callback.call(null)
		return

	if callback.is_valid():
		callback.call(data)


func _not_found_message_for(path: String) -> String:
	if path.begins_with("/game/campaigns/load/"):
		return "Save not found. Choose another save."
	if path.begins_with("/game/campaigns/saves/player/"):
		return "No campaign saves found for that player."
	if path.begins_with("/game/campaigns/saves/"):
		return "Campaign save not found."
	if path.begins_with("/game/campaigns/creation/"):
		return "Character creation expired. Start a new campaign."
	if path.begins_with("/game/campaigns/"):
		return "Campaign not found. Start a new campaign or load a different save."
	return "Requested content was not found."
