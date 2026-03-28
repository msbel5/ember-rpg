extends RefCounted


var initial_scene: String = ""
var command_file: String = ""
var result_file: String = ""
var status_file: String = ""
var artifact_root: String = ""
var cursor_position: Vector2i = Vector2i.ZERO
var last_seq: int = -1
var quit_requested: bool = false


func status_payload(extra: Dictionary = {}) -> Dictionary:
	var payload := {
		"ready": true,
		"scene": initial_scene,
		"command_file": command_file,
		"result_file": result_file,
		"status_file": status_file,
		"artifact_root": artifact_root,
	}
	for key in extra.keys():
		payload[key] = extra[key]
	return payload
