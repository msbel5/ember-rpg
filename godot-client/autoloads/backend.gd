extends Node

# Backend HTTP Client — all API calls to FastAPI server

const DEFAULT_URL = "http://localhost:8765"

var base_url: String = DEFAULT_URL

signal request_started
signal request_finished
signal request_error(message: String)

func _ready() -> void:
	if ProjectSettings.has_setting("ember_rpg/backend_url"):
		base_url = ProjectSettings.get_setting("ember_rpg/backend_url")

# --- API Methods ---

func create_session(player_name: String, player_class: String, callback: Callable) -> void:
	var body = JSON.stringify({"player_name": player_name, "player_class": player_class})
	_post("/game/session/new", body, callback)

func submit_action(session_id: String, input_text: String, callback: Callable) -> void:
	var body = JSON.stringify({"input": input_text})
	_post("/game/session/%s/action" % session_id, body, callback)

func get_session(session_id: String, callback: Callable) -> void:
	_http_get("/game/session/%s" % session_id, callback)

func delete_session(session_id: String, callback: Callable) -> void:
	_http_delete("/game/session/%s" % session_id, callback)

func get_map(session_id: String, callback: Callable) -> void:
	_http_get("/game/session/%s/map" % session_id, callback)

func save_game(session_id: String, callback: Callable) -> void:
	_post("/game/session/%s/save" % session_id, "{}", callback)

func load_game(save_id: String, callback: Callable) -> void:
	_post("/game/save/%s/load" % save_id, "{}", callback)

func list_saves(callback: Callable) -> void:
	_http_get("/game/saves", callback)

# --- Internal HTTP ---

func _post(path: String, body: String, callback: Callable) -> void:
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(http, callback))
	request_started.emit()

	var headers = ["Content-Type: application/json"]
	var error = http.request(base_url + path, headers, HTTPClient.METHOD_POST, body)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_get(path: String, callback: Callable) -> void:
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_request_completed.bind(http, callback))
	request_started.emit()

	var error = http.request(base_url + path)
	if error != OK:
		request_error.emit("HTTP request failed: %s" % error_string(error))
		http.queue_free()

func _http_delete(path: String, callback: Callable) -> void:
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

	if result != HTTPRequest.RESULT_SUCCESS:
		request_error.emit("Connection failed — is the backend running?")
		callback.call(null)
		return

	if response_code == 404:
		request_error.emit("Session not found. Start a new game?")
		callback.call(null)
		return

	if response_code >= 500:
		request_error.emit("Backend error (HTTP %d)" % response_code)
		callback.call(null)
		return

	var text = body.get_string_from_utf8()
	var data = JSON.parse_string(text)
	if data == null:
		request_error.emit("Invalid response from backend")
		callback.call(null)
		return

	callback.call(data)
