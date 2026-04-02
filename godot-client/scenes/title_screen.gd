extends Control

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")
# EmberTheme, ProfileStorage, CreationWizard available via class_name

const PROFILE_PATH := ProfileStorage.PROFILE_PATH
const STEP_GENRE := CreationWizard.STEP_GENRE
const STEP_QUESTIONNAIRE := CreationWizard.STEP_QUESTION
const STEP_HISTORY_REVEAL := CreationWizard.STEP_HISTORY
const STEP_ROLL := CreationWizard.STEP_ROLL
const STEP_BUILD := CreationWizard.STEP_BUILD
const STEP_SUMMARY := CreationWizard.STEP_DOSSIER

@onready var title_menu: Control = $TitleMenu
@onready var status_label: Label = $StatusLabel
@onready var backend_panel: PanelContainer = $BackendDiagnostics
@onready var backend_message_label: RichTextLabel = $BackendDiagnostics/Margin/VBox/MessageLabel
@onready var backend_retry_button: Button = $BackendDiagnostics/Margin/VBox/RetryButton
@onready var creation_wizard: PanelContainer = $CharacterCreation
@onready var load_browser: Panel = $LoadBrowser

var _backend_ready := false
var _catalog_loading := false
var _catalog: Dictionary = {}
var _pending_open_creation := false


func _ready() -> void:
	EmberTheme.apply_title_screen(self)
	title_menu.new_game_requested.connect(_on_new_game)
	title_menu.continue_requested.connect(_on_continue)
	title_menu.quit_requested.connect(func() -> void: get_tree().quit())
	creation_wizard.canceled.connect(_close_creation)
	creation_wizard.start_creation_requested.connect(_start_creation_flow)
	creation_wizard.answer_requested.connect(_answer_creation_question)
	creation_wizard.reroll_requested.connect(_reroll_creation)
	creation_wizard.save_roll_requested.connect(_save_creation_roll)
	creation_wizard.swap_roll_requested.connect(_swap_creation_roll)
	creation_wizard.finalize_requested.connect(_finalize_creation)
	load_browser.save_load_requested.connect(_load_campaign)
	load_browser.browser_closed.connect(_close_load_browser)
	backend_retry_button.pressed.connect(_retry_backend_bootstrap)
	Backend.request_error.connect(_on_backend_error)
	if _requires_backend_bootstrap():
		_bind_backend_runtime()
		BackendRuntime.ensure_bootstrap()
	else:
		_backend_ready = true
		_request_creation_catalog()
	_refresh_menu_state()
	title_menu.focus_default()


func _on_new_game() -> void:
	if not _backend_ready:
		status_label.text = "Campaign backend is still starting."
		backend_panel.visible = true
		return
	if _catalog.is_empty():
		_pending_open_creation = true
		status_label.text = "Loading creation catalog..."
		_request_creation_catalog()
		return
	_open_creation()


func _on_continue() -> void:
	if not _backend_ready:
		status_label.text = "Campaign backend is not ready yet."
		return
	var player_id := ProfileStorage.preferred_resume_player_id()
	load_browser.open(player_id)
	title_menu.visible = false
	creation_wizard.visible = false
	status_label.text = "Continue from a canonical campaign save."


func _open_creation() -> void:
	_pending_open_creation = false
	load_browser.visible = false
	title_menu.visible = false
	creation_wizard.set_catalog(_catalog)
	creation_wizard.open(ProfileStorage.last_player_id(), ProfileStorage.last_adapter_id(), "standard")
	status_label.text = ""


func _close_creation() -> void:
	creation_wizard.close()
	title_menu.visible = true
	_refresh_menu_state()
	title_menu.focus_default()


func _close_load_browser() -> void:
	load_browser.visible = false
	load_browser._clear_rows()
	title_menu.visible = true
	_refresh_menu_state()
	title_menu.focus_default()


func _start_creation_flow(player_name: String, adapter_id: String, profile_id: String, seed: int) -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Starting creation..."
	Backend.start_campaign_creation(player_name, adapter_id, _on_creation_started, profile_id, seed, "")


func _on_creation_started(data) -> void:
	creation_wizard.set_busy(false)
	if data == null:
		status_label.text = "Failed to start character creation."
		return
	GameState.update_from_response(data)
	creation_wizard.apply_creation_state(data)
	status_label.text = ""


func _answer_creation_question(question_id: String, answer_id: String) -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Locking answer into the campaign frame..."
	Backend.answer_campaign_creation(str(GameState.creation_state.get("creation_id", "")), question_id, answer_id, _on_creation_updated)


func _reroll_creation() -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Rolling a fresh pool..."
	Backend.reroll_campaign_creation(str(GameState.creation_state.get("creation_id", "")), _on_creation_updated)


func _save_creation_roll() -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Locking the current pool..."
	Backend.save_campaign_creation_roll(str(GameState.creation_state.get("creation_id", "")), _on_creation_updated)


func _swap_creation_roll() -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Swapping active and saved pools..."
	Backend.swap_campaign_creation_roll(str(GameState.creation_state.get("creation_id", "")), _on_creation_updated)


func _on_creation_updated(data) -> void:
	creation_wizard.set_busy(false)
	if data == null:
		status_label.text = "Creation update failed."
		return
	GameState.update_from_response(data)
	creation_wizard.apply_creation_state(data)
	status_label.text = ""


func _finalize_creation(payload: Dictionary) -> void:
	creation_wizard.set_busy(true)
	status_label.text = "Finalizing campaign..."
	Backend.finalize_campaign_creation(str(GameState.creation_state.get("creation_id", "")), _on_campaign_created, payload)


func _on_campaign_created(data) -> void:
	creation_wizard.set_busy(false)
	if data == null:
		status_label.text = "Failed to create the campaign."
		return
	GameState.reset()
	GameState.update_from_response(data)
	ProfileStorage.store_last_player_id(str(GameState.player.get("name", "")))
	ProfileStorage.store_last_resume_player_id(str(GameState.player.get("name", "")))
	ProfileStorage.store_last_adapter_id(str(GameState.adapter_id))
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _load_campaign(save_id: String) -> void:
	status_label.text = "Loading %s..." % save_id
	Backend.load_campaign(save_id, _on_campaign_loaded.bind(save_id))


func _on_campaign_loaded(data, save_id: String) -> void:
	if data == null:
		status_label.text = "Failed to load %s." % save_id
		return
	GameState.reset()
	GameState.update_from_response(data)
	GameState.seed_campaign_resume_narrative(str(data.get("narrative", "")))
	GameState.last_save_slot = save_id
	ProfileStorage.store_last_player_id(str(GameState.player.get("name", "")))
	ProfileStorage.store_last_resume_player_id(str(GameState.player.get("name", "")))
	ProfileStorage.store_last_adapter_id(str(GameState.adapter_id))
	ProfileStorage.store_last_campaign_save_id(save_id)
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _request_creation_catalog() -> void:
	if _catalog_loading:
		return
	_catalog_loading = true
	status_label.text = "Loading creation catalog..."
	Backend.get_campaign_creation_catalog(_on_creation_catalog_loaded)


func _on_creation_catalog_loaded(data) -> void:
	_catalog_loading = false
	if data == null:
		status_label.text = "Failed to load the creation catalog."
		_refresh_menu_state()
		return
	_catalog = data.duplicate(true)
	creation_wizard.set_catalog(_catalog)
	status_label.text = ""
	_refresh_menu_state()
	if _pending_open_creation:
		_open_creation()


func _on_backend_error(message: String) -> void:
	status_label.text = message
	if _requires_backend_bootstrap():
		backend_panel.visible = true
		backend_message_label.text = "[b]Backend error[/b]\n%s" % message


func _bind_backend_runtime() -> void:
	if not BackendRuntime.status_changed.is_connected(_on_backend_runtime_status):
		BackendRuntime.status_changed.connect(_on_backend_runtime_status)
	if not BackendRuntime.bootstrap_finished.is_connected(_on_backend_runtime_finished):
		BackendRuntime.bootstrap_finished.connect(_on_backend_runtime_finished)


func _retry_backend_bootstrap() -> void:
	backend_retry_button.disabled = true
	BackendRuntime.reset_state()
	_bind_backend_runtime()
	BackendRuntime.ensure_bootstrap()


func _on_backend_runtime_status(message: String) -> void:
	backend_panel.visible = true
	backend_message_label.text = "[b]Campaign backend required[/b]\n%s" % message
	status_label.text = message
	backend_retry_button.disabled = false


func _on_backend_runtime_finished(success: bool) -> void:
	backend_retry_button.disabled = false
	_backend_ready = success
	if success:
		backend_panel.visible = false
		_request_creation_catalog()
	else:
		backend_panel.visible = true
	_refresh_menu_state()


func _refresh_menu_state() -> void:
	title_menu.set_continue_enabled(_backend_ready and not ProfileStorage.preferred_resume_player_id().is_empty())
	if not _backend_ready and _requires_backend_bootstrap():
		backend_panel.visible = true
	elif status_label.text == "Loading creation catalog..." and not _catalog_loading:
		status_label.text = ""
	if title_menu.visible and not creation_wizard.visible and not load_browser.visible:
		title_menu.focus_default()


func _set_busy(busy: bool, message: String) -> void:
	creation_wizard.set_busy(busy)
	status_label.text = message if busy else ""


func _apply_creation_state(payload: Dictionary) -> void:
	GameState.update_from_response(payload)
	creation_wizard.apply_creation_state(payload)


func _go_to_step(step: int) -> void:
	creation_wizard.go_to_step(step)


func _primary_wizard_action_for_key(keycode: Key) -> String:
	return creation_wizard.primary_action_for_key(keycode)


func _store_last_player_id(player_id: String) -> void:
	ProfileStorage.store_last_player_id(player_id)


func _store_last_resume_player_id(player_id: String) -> void:
	ProfileStorage.store_last_resume_player_id(player_id)


func _clear_load_rows() -> void:
	load_browser._clear_rows()


func _on_saves_listed(data) -> void:
	load_browser._on_saves_listed(data)


func _set_load_browser_busy(busy: bool, message: String) -> void:
	load_browser._set_busy(busy, message)


func _requires_backend_bootstrap() -> bool:
	return DisplayServer.get_name() != "headless"


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_F12:
			var screenshot_path = ScreenshotCapture.capture_viewport(get_viewport(), "phase2/title", "title_screen")
			status_label.text = "Viewport capture saved: %s" % screenshot_path if not screenshot_path.is_empty() else "Viewport capture failed."
			get_viewport().set_input_as_handled()
		KEY_ESCAPE:
			if load_browser.visible:
				_close_load_browser()
			elif creation_wizard.visible:
				_close_creation()
			get_viewport().set_input_as_handled()
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			if creation_wizard.visible and creation_wizard.activate_answer_shortcut(int(event.keycode - KEY_1)):
				get_viewport().set_input_as_handled()
		KEY_ENTER, KEY_KP_ENTER, KEY_SPACE:
			if not creation_wizard.visible:
				return
			match _primary_wizard_action_for_key(event.keycode):
				"next":
					creation_wizard._on_next_pressed()
					get_viewport().set_input_as_handled()
				"start":
					creation_wizard._emit_finalize()
					get_viewport().set_input_as_handled()
