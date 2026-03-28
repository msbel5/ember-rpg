extends Control


@onready var input_field: LineEdit = $Margin/VBox/InputField
@onready var status_label: Label = $Margin/VBox/StatusLabel

var last_key_down: String = ""
var last_key_up: String = ""
var key_down_count: int = 0
var key_up_count: int = 0
var mouse_move_count: int = 0
var mouse_down_count: int = 0
var mouse_up_count: int = 0
var last_mouse_position: Vector2 = Vector2.ZERO


func _ready() -> void:
	input_field.grab_focus()
	status_label.text = "Probe ready"


func _input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_name = OS.get_keycode_string(event.keycode).to_lower()
		if event.pressed:
			last_key_down = key_name
			key_down_count += 1
		else:
			last_key_up = key_name
			key_up_count += 1
	elif event is InputEventMouseMotion:
		mouse_move_count += 1
		last_mouse_position = event.position
	elif event is InputEventMouseButton:
		last_mouse_position = event.position
		if event.pressed:
			mouse_down_count += 1
		else:
			mouse_up_count += 1
