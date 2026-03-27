extends Control

const PROFILE_PATH := "user://client_profile.cfg"
const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")

const CLASS_OPTIONS := [
	{"label": "Warrior", "id": "warrior"},
	{"label": "Rogue", "id": "rogue"},
	{"label": "Mage", "id": "mage"},
	{"label": "Priest", "id": "priest"},
]

const ADAPTER_OPTIONS := [
	{"label": "Fantasy Ember", "id": "fantasy_ember"},
	{"label": "Sci-Fi Frontier", "id": "scifi_frontier"},
]

@onready var new_game_btn: Button = $VBoxContainer/NewGameButton
@onready var continue_btn: Button = $VBoxContainer/ContinueButton
@onready var quit_btn: Button = $VBoxContainer/QuitButton
@onready var creation_panel: Panel = $CharacterCreation
@onready var name_input: LineEdit = $CharacterCreation/VBox/NameInput
@onready var class_option: OptionButton = $CharacterCreation/VBox/ClassOption
@onready var adapter_option: OptionButton = $CharacterCreation/VBox/AdapterOption
@onready var start_btn: Button = $CharacterCreation/VBox/StartButton
@onready var back_btn: Button = $CharacterCreation/VBox/BackButton
@onready var status_label: Label = $StatusLabel


func _ready() -> void:
	creation_panel.visible = false
	status_label.text = ""
	new_game_btn.pressed.connect(_on_new_game)
	continue_btn.pressed.connect(_on_continue)
	quit_btn.pressed.connect(_on_quit)
	start_btn.pressed.connect(_on_start_campaign)
	back_btn.pressed.connect(_on_back)
	Backend.request_error.connect(_on_backend_error)
	_populate_class_options()
	_populate_adapter_options()
	continue_btn.disabled = _last_campaign_save_id().is_empty()


func _on_new_game() -> void:
	status_label.text = ""
	creation_panel.visible = true
	start_btn.disabled = false
	start_btn.text = "Start Campaign"
	name_input.grab_focus()


func _on_continue() -> void:
	var save_id = _last_campaign_save_id()
	if save_id.is_empty():
		status_label.text = "No previous campaign save found."
		continue_btn.disabled = true
		return
	continue_btn.disabled = true
	status_label.text = "Loading %s..." % save_id
	Backend.load_campaign(save_id, _on_campaign_loaded.bind(save_id))


func _on_quit() -> void:
	get_tree().quit()


func _on_back() -> void:
	creation_panel.visible = false
	status_label.text = ""


func _on_start_campaign() -> void:
	var player_name = name_input.text.strip_edges()
	if player_name.is_empty():
		status_label.text = "Enter a character name."
		return
	start_btn.disabled = true
	status_label.text = "Creating campaign..."
	GameState.reset()
	Backend.create_campaign(player_name, _selected_class_id(), _selected_adapter_id(), _on_campaign_created)


func _on_campaign_created(data) -> void:
	start_btn.disabled = false
	if data == null:
		status_label.text = "Failed to create a campaign."
		return
	GameState.reset()
	GameState.update_from_response(data)
	_store_last_player_id(str(GameState.player.get("name", name_input.text.strip_edges())))
	_store_last_adapter_id(str(GameState.adapter_id))
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _on_campaign_loaded(data, requested_save_id: String) -> void:
	continue_btn.disabled = false
	if data == null:
		status_label.text = "Failed to load %s." % requested_save_id
		return
	GameState.reset()
	GameState.update_from_response(data)
	GameState.last_save_slot = requested_save_id
	_store_last_player_id(str(GameState.player.get("name", _last_player_id())))
	_store_last_adapter_id(str(GameState.adapter_id))
	_store_last_campaign_save_id(requested_save_id)
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _on_backend_error(message: String) -> void:
	start_btn.disabled = false
	continue_btn.disabled = _last_campaign_save_id().is_empty()
	status_label.text = message


func _populate_class_options() -> void:
	class_option.clear()
	for entry in CLASS_OPTIONS:
		class_option.add_item(str(entry["label"]))
		class_option.set_item_metadata(class_option.item_count - 1, str(entry["id"]))
	class_option.select(0)


func _populate_adapter_options() -> void:
	adapter_option.clear()
	var preferred = _last_adapter_id()
	var selected_index := 0
	for index in range(ADAPTER_OPTIONS.size()):
		var entry = ADAPTER_OPTIONS[index]
		adapter_option.add_item(str(entry["label"]))
		adapter_option.set_item_metadata(index, str(entry["id"]))
		if preferred == str(entry["id"]):
			selected_index = index
	adapter_option.select(selected_index)


func _selected_class_id() -> String:
	if class_option.item_count == 0:
		return "warrior"
	return str(class_option.get_item_metadata(class_option.selected))


func _selected_adapter_id() -> String:
	if adapter_option.item_count == 0:
		return "fantasy_ember"
	return str(adapter_option.get_item_metadata(adapter_option.selected))


func _store_last_player_id(player_id: String) -> void:
	_store_profile_value("last_player_id", player_id.strip_edges())


func _last_player_id() -> String:
	return str(_profile_value("last_player_id", "")).strip_edges()


func _store_last_adapter_id(value: String) -> void:
	_store_profile_value("last_adapter_id", value.strip_edges())


func _last_adapter_id() -> String:
	return str(_profile_value("last_adapter_id", "fantasy_ember")).strip_edges()


func _store_last_campaign_save_id(save_id: String) -> void:
	_store_profile_value("last_campaign_save_id", save_id.strip_edges())
	continue_btn.disabled = save_id.strip_edges().is_empty()


func _last_campaign_save_id() -> String:
	return str(_profile_value("last_campaign_save_id", "")).strip_edges()


func _store_profile_value(key: String, value) -> void:
	if str(value).strip_edges().is_empty():
		return
	var profile = ConfigFile.new()
	profile.load(PROFILE_PATH)
	profile.set_value("profile", key, value)
	profile.save(PROFILE_PATH)


func _profile_value(key: String, fallback):
	var profile = ConfigFile.new()
	if profile.load(PROFILE_PATH) != OK:
		return fallback
	return profile.get_value("profile", key, fallback)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return
	if event.keycode != KEY_F12:
		return
	var screenshot_path = ScreenshotCapture.capture_viewport(get_viewport(), "phase2/title", "title_screen")
	if screenshot_path.is_empty():
		status_label.text = "Viewport capture failed."
	else:
		status_label.text = "Viewport capture saved: %s" % screenshot_path
	get_viewport().set_input_as_handled()
