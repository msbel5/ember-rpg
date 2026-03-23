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

func _ready() -> void:
	creation_panel.visible = false
	status_label.text = ""
	continue_btn.disabled = true  # TODO: check for saved games

	new_game_btn.pressed.connect(_on_new_game)
	continue_btn.pressed.connect(_on_continue)
	quit_btn.pressed.connect(_on_quit)
	start_btn.pressed.connect(_on_start_adventure)
	back_btn.pressed.connect(_on_back)

	# Populate class options
	class_option.clear()
	class_option.add_item("Warrior")
	class_option.add_item("Rogue")
	class_option.add_item("Mage")
	class_option.add_item("Priest")

	Backend.request_error.connect(_on_backend_error)

func _on_new_game() -> void:
	creation_panel.visible = true
	name_input.grab_focus()

func _on_continue() -> void:
	# TODO: show save list
	pass

func _on_quit() -> void:
	get_tree().quit()

func _on_back() -> void:
	creation_panel.visible = false

func _on_start_adventure() -> void:
	var player_name = name_input.text.strip_edges()
	if player_name.is_empty():
		status_label.text = "Enter a character name!"
		return

	var player_class = class_option.get_item_text(class_option.selected).to_lower()
	status_label.text = "Creating your adventure..."
	start_btn.disabled = true

	Backend.create_session(player_name, player_class, _on_session_created)

func _on_session_created(data) -> void:
	start_btn.disabled = false
	if data == null:
		status_label.text = "Failed to connect to backend!"
		return

	GameState.update_from_response(data)
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")

func _on_backend_error(message: String) -> void:
	status_label.text = message
