extends Node

const BACKEND_ENV := "EMBER_RPG_BACKEND_URL"
const PYTHON_ENV := "EMBER_RPG_PYTHON"
const BACKEND_SETTING := "ember_rpg/backend_url"
const DEFAULT_BACKEND_URL := "http://127.0.0.1:8741"
const PREFERRED_PORTS := [8741, 8765]
const DEV_SERVER_PATH := "res://../frp-backend/dev_server.py"
const REPO_VENV_PYTHON := "res://../.venv/Scripts/python.exe"

signal status_changed(message: String)
signal bootstrap_finished(success: bool)

var backend_ready: bool = false
var last_error: String = ""
var resolved_url: String = ""
var health_payload: Dictionary = {}

var _bootstrap_started: bool = false
var _managed_backend_pid: int = -1


func _exit_tree() -> void:
	test_cleanup()


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


func test_cleanup() -> void:
	reset_state()
	_cleanup_pending_http_requests()


func _cleanup_pending_http_requests() -> void:
	for child in get_children():
		if child is HTTPRequest:
			var request: HTTPRequest = child
			request.cancel_request()
			request.queue_free()


func _run_bootstrap() -> void:
	status_changed.emit("Connecting to campaign backend...")
	var candidates = _candidate_urls()
	for candidate in candidates:
		var payload = await _probe_backend(candidate)
		_record_health_failure(payload)
		if _health_is_ready(payload):
			_commit_backend(candidate, payload)
			return
	if OS.is_debug_build() and not _has_explicit_backend_override():
		status_changed.emit("Launching repo-managed campaign backend...")
		var managed = await _launch_managed_backend(true)
		if _health_is_ready(managed.get("payload", {})):
			_commit_backend(str(managed.get("url", "")), managed.get("payload", {}))
			return
	# Backend not found — try launching in debug builds
	if OS.is_debug_build():
		status_changed.emit("Launching campaign backend...")
		var pid = _spawn_backend_process(8741)
		if pid > 0:
			_managed_backend_pid = pid
	# Retry loop with shorter waits
	for attempt in range(5):
		status_changed.emit("Waiting for backend... (attempt %d/5)" % [attempt + 1])
		await get_tree().create_timer(1.0).timeout
		for candidate in candidates:
			var payload = await _probe_backend(candidate)
			_record_health_failure(payload)
			if _health_is_ready(payload):
				_commit_backend(candidate, payload)
				return
	# Final attempt: try launching managed backend on alternate port
	if OS.is_debug_build():
		var launched = await _launch_managed_backend()
		_record_health_failure(launched.get("payload", {}))
		if _health_is_ready(launched.get("payload", {})):
			_commit_backend(str(launched.get("url", "")), launched.get("payload", {}))
			return
	backend_ready = false
	if last_error.is_empty():
		last_error = "Campaign backend is unavailable. Start the backend or fix the configured URL."
	status_changed.emit(last_error)
	bootstrap_finished.emit(false)


func _commit_backend(url: String, payload: Dictionary) -> void:
	print("[BackendRuntime] _commit_backend called, url=%s" % url)
	backend_ready = true
	last_error = ""
	resolved_url = url
	health_payload = payload.duplicate(true)
	Backend.set_base_url(url)
	status_changed.emit("Connected to campaign backend at %s." % url)
	print("[BackendRuntime] Emitting bootstrap_finished(true)")
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


func _has_explicit_backend_override() -> bool:
	var env_url = OS.get_environment(BACKEND_ENV).strip_edges()
	if not env_url.is_empty():
		return true
	if ProjectSettings.has_setting(BACKEND_SETTING):
		var configured = str(ProjectSettings.get_setting(BACKEND_SETTING)).strip_edges()
		if not configured.is_empty():
			return true
	return false


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
		and bool(payload.get("campaign_save_load", false)) \
		and bool(payload.get("websocket_transport", false))


func _record_health_failure(payload: Dictionary) -> void:
	if payload.is_empty():
		return
	if not bool(payload.get("websocket_transport", false)):
		last_error = "Campaign backend is missing WebSocket runtime support. Install backend requirements and relaunch."


func _launch_managed_backend(prefer_spawn: bool = false) -> Dictionary:
	status_changed.emit("Launching a managed campaign backend...")
	if not prefer_spawn:
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
	var backend_script = ProjectSettings.globalize_path(DEV_SERVER_PATH)
	if not FileAccess.file_exists(backend_script):
		last_error = "Backend dev server script is missing: %s" % backend_script
		status_changed.emit(last_error)
		return -1
	var launch = _resolve_python_launch()
	var python = str(launch.get("binary", "")).strip_edges()
	if python.is_empty():
		last_error = "No usable Python runtime was found for the campaign backend."
		status_changed.emit(last_error)
		return -1
	var args: PackedStringArray = launch.get("args", PackedStringArray())
	args.append_array(PackedStringArray([backend_script, "--host", "127.0.0.1", "--port", str(port)]))
	var pid = OS.create_process(python, args, false)
	if pid <= 0:
		last_error = "Failed to launch the campaign backend with %s." % python
		status_changed.emit(last_error)
	return pid


func _resolve_python_launch() -> Dictionary:
	var env_python = OS.get_environment(PYTHON_ENV).strip_edges()
	if not env_python.is_empty():
		return {"binary": env_python, "args": PackedStringArray()}
	var repo_python = ProjectSettings.globalize_path(REPO_VENV_PYTHON)
	if FileAccess.file_exists(repo_python):
		return {"binary": repo_python, "args": PackedStringArray()}
	if OS.get_name() == "Windows":
		return {"binary": "py", "args": PackedStringArray(["-3"])}
	return {"binary": "python", "args": PackedStringArray()}


func _wait_for_backend(base_url: String, timeout_seconds: float) -> Dictionary:
	var deadline = Time.get_ticks_msec() + int(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		var payload = await _probe_backend(base_url)
		if _health_is_ready(payload):
			return payload
		await get_tree().create_timer(0.35).timeout
	return {}
