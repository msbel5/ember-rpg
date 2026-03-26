extends "res://autoloads/backend.gd"

var last_request: Dictionary = {}


func _ensure_base_url(_callback: Callable) -> bool:
	return true


func _post(path: String, body: String, _callback: Callable) -> void:
	last_request = {
		"method": "POST",
		"path": path,
		"body": body,
	}


func _http_get(path: String, _callback: Callable) -> void:
	last_request = {
		"method": "GET",
		"path": path,
	}


func _http_delete(path: String, _callback: Callable) -> void:
	last_request = {
		"method": "DELETE",
		"path": path,
	}
