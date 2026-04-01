extends Node

const BACKEND_ENV := "EMBER_RPG_BACKEND_URL"
const BACKEND_SETTING := "ember_rpg/backend_url"
const DEFAULT_BACKEND_URL := "http://127.0.0.1:8741"
const PREFERRED_PORTS := [8741, 8765]
const DEV_SERVER_PATH := "res://../frp-backend/dev_server.py"

signal status_changed(message: String)
signal bootstrap_finished(success: bool)

var backend_ready: bool = false
var last_error: String = ""
var resolved_url: String = ""
var health_payload: Dictionary = {}

var _bootstrap_started: bool = false
var _managed_backend_pid: int = -1


func ensure_bootstrap() -> void:
	if _bootstrap_started:
		return
	_bootstrap_started = true
	call_deferred("_run_bootstrap")


func reset_state() -> void:
	backend_ready = false
	last_error = ""
	resolved_url = ""
	health_payload = {}
	_bootstrap_started = false


func _run_bootstrap() -> void:
	status_changed.emit("Starting campaign backend...")
	# In debug builds, launch backend process immediately while also probing
	if OS.is_debug_build():
		_spawn_backend_process(8741)
	status_changed.emit("Connecting to campaign backend...")
	# Probe all candidates (the one we just launched will be ready soon)
	var candidates = _candidate_urls()
	for attempt in range(3):
		for candidate in candidates:
			var payload = await _probe_backend(candidate)
			if _health_is_ready(payload):
				_commit_backend(candidate, payload)
				return
		# Wait briefly between retries for backend to finish starting
		status_changed.emit("Waiting for backend to start... (attempt %d/3)" % [attempt + 1])
		await get_tree().create_timer(1.5).timeout
	# Final attempt: try launching managed backend on alternate port
	if OS.is_debug_build():
		var launched = await _launch_managed_backend()
		if _health_is_ready(launched.get("payload", {})):
			_commit_backend(str(launched.get("url", "")), launched.get("payload", {}))
			return
	backend_ready = false
	last_error = "Campaign backend is unavailable. Start the backend or fix the configured URL."
	status_changed.emit(last_error)
	bootstrap_finished.emit(false)


func _commit_backend(url: String, payload: Dictionary) -> void:
	backend_ready = true
	last_error = ""
	resolved_url = url
	health_payload = payload.duplicate(true)
	Backend.set_base_url(url)
	status_changed.emit("Connected to campaign backend at %s." % url)
	bootstrap_finished.emit(true)


func _candidate_urls() -> Array[String]:
	var urls: Array[String] = []
	var env_url = OS.get_environment(BACKEND_ENV).strip_edges()
	if not env_url.is_empty():
		urls.append(env_url.trim_suffix("/"))
	var configured = ""
	if ProjectSettings.has_setting(BACKEND_SETTING):
		configured = str(ProjectSettings.get_setting(BACKEND_SETTING)).strip_edges()
	if not configured.is_empty() and not urls.has(configured.trim_suffix("/")):
		urls.append(configured.trim_suffix("/"))
	for port in PREFERRED_PORTS:
		var candidate = "http://127.0.0.1:%d" % port
		if not urls.has(candidate):
			urls.append(candidate)
	if urls.is_empty():
		urls.append(DEFAULT_BACKEND_URL)
	return urls


func _probe_backend(base_url: String) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)
	var request_url = "%s/game/health/campaign-client" % base_url.trim_suffix("/")
	var request_error = http.request(request_url)
	if request_error != OK:
		http.queue_free()
		return {}
	var result = await http.request_completed
	http.queue_free()
	var response_code = int(result[1])
	if response_code >= 400:
		return {}
	var body: PackedByteArray = result[3]
	var payload = JSON.parse_string(body.get_string_from_utf8())
	return payload if payload is Dictionary else {}


func _health_is_ready(payload: Dictionary) -> bool:
	return bool(payload.get("ok", false)) \
		and bool(payload.get("campaign_creation", false)) \
		and bool(payload.get("campaign_runtime", false)) \
		and bool(payload.get("campaign_save_load", false))


func _launch_managed_backend() -> Dictionary:
	status_changed.emit("Launching a managed campaign backend...")
	for port in PREFERRED_PORTS:
		var candidate = "http://127.0.0.1:%d" % port
		var payload = await _probe_backend(candidate)
		if _health_is_ready(payload):
			return {"url": candidate, "payload": payload}
	for port in range(8765, 8775):
		var pid = _spawn_backend_process(port)
		if pid <= 0:
			continue
		_managed_backend_pid = pid
		var candidate = "http://127.0.0.1:%d" % port
		var payload = await _wait_for_backend(candidate, 12.0)
		if _health_is_ready(payload):
			return {"url": candidate, "payload": payload}
	return {}


func _spawn_backend_process(port: int) -> int:
	var python = OS.get_environment("EMBER_RPG_PYTHON").strip_edges()
	if python.is_empty():
		python = "python"
	var backend_script = ProjectSettings.globalize_path(DEV_SERVER_PATH)
	if not FileAccess.file_exists(backend_script):
		last_error = "Backend dev server script is missing: %s" % backend_script
		return -1
	var args = PackedStringArray([backend_script, "--host", "127.0.0.1", "--port", str(port)])
	return OS.create_process(python, args, false)


func _wait_for_backend(base_url: String, timeout_seconds: float) -> Dictionary:
	var deadline = Time.get_ticks_msec() + int(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		var payload = await _probe_backend(base_url)
		if _health_is_ready(payload):
			return payload
		await get_tree().create_timer(0.35).timeout
	return {}
