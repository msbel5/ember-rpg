extends Node
## Python Bridge — raw TCP socket IPC replacing HTTP/WebSocket.
##
## Starts the Python backend as a subprocess with a raw TCP server on port 9741.
## Godot connects via StreamPeerTCP and sends/receives newline-delimited JSON.
##
## Protocol:
##   Send: {"id": 1, "method": "health", "args": {}}\n
##   Recv: {"id": 1, "result": {...}}\n
##
## Latency: ~0.1-0.5ms per call (vs 5-50ms for HTTP).
##
## Usage:
##   var result = PythonBridge.call_engine("health", {})
##   var state = PythonBridge.call_engine("get_campaign", {"campaign_id": cid})

signal bridge_ready
signal bridge_error(message: String)

const BRIDGE_PORT := 9741
const CONNECT_TIMEOUT_MS := 10000
const READ_TIMEOUT_MS := 5000

var _pid: int = -1
var _tcp: StreamPeerTCP
var _connected: bool = false
var _request_id: int = 0
var _recv_buffer: String = ""

# Tick timers — Godot controls tick pacing (pull-based, not push)
var _visual_tick_timer: float = 0.0
var _world_tick_timer: float = 0.0
const VISUAL_TICK_INTERVAL := 0.1   # 10fps ambient NPC polling
const WORLD_TICK_INTERVAL := 15.0   # world simulation advance

var active_campaign_id: String = ""
var backend_ready: bool = false


func _ready() -> void:
	_start_bridge()


func _exit_tree() -> void:
	_stop_bridge()


func _process(delta: float) -> void:
	# Poll TCP socket
	if _tcp != null:
		_tcp.poll()

	if not _connected or active_campaign_id.is_empty():
		return

	# Visual tick — ambient NPC movement (replaces WebSocket visual_delta push)
	_visual_tick_timer += delta
	if _visual_tick_timer >= VISUAL_TICK_INTERVAL:
		_visual_tick_timer = 0.0
		_poll_visual_tick()

	# World tick — advance simulation (replaces server-side tick loop push)
	_world_tick_timer += delta
	if _world_tick_timer >= WORLD_TICK_INTERVAL:
		_world_tick_timer = 0.0
		_poll_world_tick()


## Synchronous engine call. Returns result dictionary.
## Blocks for ~0.1-0.5ms (TCP loopback + Python processing).
func call_engine(method: String, args: Dictionary = {}) -> Dictionary:
	if not _connected:
		return {"error": "bridge not connected"}

	_request_id += 1
	var request := {
		"id": _request_id,
		"method": method,
		"args": args,
	}

	# Send request
	var request_json := JSON.stringify(request) + "\n"
	var send_err := _tcp.put_data(request_json.to_utf8_buffer())
	if send_err != OK:
		push_warning("[PythonBridge] send failed: %s" % error_string(send_err))
		return {"error": "send failed"}

	# Read response (blocking with timeout)
	var deadline := Time.get_ticks_msec() + READ_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		_tcp.poll()
		var avail := _tcp.get_available_bytes()
		if avail > 0:
			var recv_result := _tcp.get_data(avail)
			if recv_result[0] == OK:
				_recv_buffer += recv_result[1].get_string_from_utf8()

		# Check for complete line
		var nl := _recv_buffer.find("\n")
		if nl >= 0:
			var line := _recv_buffer.substr(0, nl).strip_edges()
			_recv_buffer = _recv_buffer.substr(nl + 1)
			if line.is_empty():
				continue
			var parsed = JSON.parse_string(line)
			if parsed is Dictionary:
				if parsed.has("result"):
					return parsed["result"] if parsed["result"] is Dictionary else {"value": parsed["result"]}
				return parsed
			return {"error": "invalid response"}

		# Small sleep to avoid busy-wait
		OS.delay_msec(0)

	return {"error": "timeout"}


## Set the active campaign for tick polling.
func set_active_campaign(campaign_id: String) -> void:
	active_campaign_id = campaign_id
	_world_tick_timer = 0.0
	_visual_tick_timer = 0.0


# --- Bridge lifecycle -------------------------------------------------------

func _start_bridge() -> void:
	var repo_root := ProjectSettings.globalize_path("res://").get_base_dir()
	var backend_dir := repo_root.path_join("frp-backend")
	var python_exe := repo_root.path_join(".venv/Scripts/python.exe")
	var bridge_script := backend_dir.path_join("bridge.py")

	if not FileAccess.file_exists(python_exe):
		python_exe = repo_root.path_join(".venv/bin/python")
	if not FileAccess.file_exists(python_exe):
		push_warning("[PythonBridge] no .venv python found, trying system python")
		python_exe = "python"

	if not FileAccess.file_exists(bridge_script):
		push_error("[PythonBridge] bridge.py not found: %s" % bridge_script)
		bridge_error.emit("bridge.py not found")
		return

	# Start Python bridge subprocess
	print("[PythonBridge] starting: %s" % bridge_script)
	_pid = OS.create_process(python_exe, [bridge_script], false)
	if _pid <= 0:
		push_error("[PythonBridge] failed to start subprocess")
		bridge_error.emit("subprocess failed")
		return
	print("[PythonBridge] subprocess pid=%d" % _pid)

	# Wait for the bridge to start listening, then connect
	_connect_with_retry()


func _connect_with_retry() -> void:
	var deadline := Time.get_ticks_msec() + CONNECT_TIMEOUT_MS
	_tcp = StreamPeerTCP.new()

	while Time.get_ticks_msec() < deadline:
		var err := _tcp.connect_to_host("127.0.0.1", BRIDGE_PORT)
		if err == OK:
			# Wait for connection to establish
			var conn_deadline := Time.get_ticks_msec() + 3000
			while Time.get_ticks_msec() < conn_deadline:
				_tcp.poll()
				var status := _tcp.get_status()
				if status == StreamPeerTCP.STATUS_CONNECTED:
					_connected = true
					backend_ready = true
					print("[PythonBridge] connected to bridge on port %d" % BRIDGE_PORT)
					bridge_ready.emit()

					# Verify with health check
					var health := call_engine("health")
					print("[PythonBridge] health: %s" % str(health).substr(0, 200))
					return
				elif status == StreamPeerTCP.STATUS_ERROR:
					break
				OS.delay_msec(50)

		OS.delay_msec(200)
		_tcp = StreamPeerTCP.new()  # retry with fresh socket

	push_error("[PythonBridge] could not connect after %dms" % CONNECT_TIMEOUT_MS)
	bridge_error.emit("connection timeout")


func _stop_bridge() -> void:
	if _tcp != null:
		_tcp.disconnect_from_host()
		_tcp = null
	_connected = false
	backend_ready = false
	if _pid > 0:
		OS.kill(_pid)
		_pid = -1


# --- Tick polling -----------------------------------------------------------

func _poll_visual_tick() -> void:
	var result := call_engine("visual_tick", {"campaign_id": active_campaign_id})
	var actors = result.get("actors", [])
	if actors is Array and not actors.is_empty():
		var payload := {"type": "visual_delta", "actors": actors}
		var gs = get_node_or_null("/root/GameState")
		if gs != null:
			gs.apply_visual_delta(payload)


func _poll_world_tick() -> void:
	var result := call_engine("tick", {"campaign_id": active_campaign_id})
	if result.has("error"):
		return
	var gs = get_node_or_null("/root/GameState")
	if gs != null:
		gs.update_from_response(result)
