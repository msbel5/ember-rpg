extends Control

@onready var new_game_btn: Button = $VBoxContainer/NewGameButton
@onready var continue_btn: Button = $VBoxContainer/ContinueButton
@onready var quit_btn: Button = $VBoxContainer/QuitButton
@onready var creation_panel: Panel = $CharacterCreation
@onready var name_input: LineEdit = $CharacterCreation/VBox/NameInput
@onready var class_option: OptionButton = $CharacterCreation/VBox/ClassOption
@onready var start_btn: Button = $CharacterCreation/VBox/StartButton
@onready var back_btn: Button = $CharacterCreation/VBox/BackButton
@onready var status_label: Label = $StatusLabel

var current_creation_id: String = ""
var current_creation_player_name: String = ""
var recommended_alignment: String = "TN"

func _ready() -> void:
	creation_panel.visible = false
	status_label.text = ""
	continue_btn.disabled = true  # TODO: check for saved games
	class_option.disabled = true
	start_btn.text = "Prepare Character"

	new_game_btn.pressed.connect(_on_new_game)
	continue_btn.pressed.connect(_on_continue)
	quit_btn.pressed.connect(_on_quit)
	start_btn.pressed.connect(_on_start_adventure)
	back_btn.pressed.connect(_on_back)
	name_input.text_changed.connect(_on_name_changed)

	Backend.request_error.connect(_on_backend_error)

func _on_new_game() -> void:
	_reset_creation_state()
	creation_panel.visible = true
	name_input.grab_focus()

func _on_continue() -> void:
	# TODO: show save list
	pass

func _on_quit() -> void:
	get_tree().quit()

func _on_back() -> void:
	_reset_creation_state()
	creation_panel.visible = false

func _on_start_adventure() -> void:
	var player_name = name_input.text.strip_edges()
	if player_name.is_empty():
		status_label.text = "Enter a character name!"
		return

	start_btn.disabled = true
	if current_creation_id.is_empty():
		status_label.text = "Preparing your character..."
		Backend.start_creation(player_name, _on_creation_started)
		return

	status_label.text = "Creating your adventure..."
	var player_class = _selected_class_id()
	Backend.finalize_creation(current_creation_id, player_class, recommended_alignment, _on_session_created)

func _on_creation_started(data) -> void:
	start_btn.disabled = false
	if data == null:
		status_label.text = "Failed to prepare character options!"
		return
	current_creation_id = str(data.get("creation_id", ""))
	current_creation_player_name = name_input.text.strip_edges()
	recommended_alignment = str(data.get("recommended_alignment", "TN"))
	_populate_class_options(data)
	class_option.disabled = false
	start_btn.text = "Start Adventure"
	status_label.text = "Class options loaded from backend. Review and continue."

func _on_session_created(data) -> void:
	start_btn.disabled = false
	if data == null:
		status_label.text = "Failed to connect to backend!"
		return

	GameState.update_from_response(data)
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")

func _on_backend_error(message: String) -> void:
	start_btn.disabled = false
	status_label.text = message

func _on_name_changed(_new_text: String) -> void:
	if not current_creation_id.is_empty():
		_reset_creation_state(false)
		status_label.text = "Name changed. Character options will refresh on submit."

func _reset_creation_state(clear_name: bool = false) -> void:
	current_creation_id = ""
	current_creation_player_name = ""
	recommended_alignment = "TN"
	class_option.clear()
	class_option.disabled = true
	start_btn.disabled = false
	start_btn.text = "Prepare Character"
	if clear_name:
		name_input.text = ""

func _populate_class_options(data: Dictionary) -> void:
	class_option.clear()
	var class_weights: Dictionary = data.get("class_weights", {})
	var class_ids := class_weights.keys()
	class_ids.sort()
	if class_ids.is_empty():
		class_ids = [str(data.get("recommended_class", "warrior"))]
	for class_id in class_ids:
		var selected_class_id := str(class_id)
		class_option.add_item(selected_class_id.capitalize())
		var index := class_option.item_count - 1
		class_option.set_item_metadata(index, selected_class_id)
		if selected_class_id == str(data.get("recommended_class", "")):
			class_option.select(index)

func _selected_class_id() -> String:
	if class_option.item_count == 0:
		return "warrior"
	var index := class_option.selected
	var meta = class_option.get_item_metadata(index)
	if meta == null:
		return class_option.get_item_text(index).to_lower()
	return str(meta)
