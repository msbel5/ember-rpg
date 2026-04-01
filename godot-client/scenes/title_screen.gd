extends Control

const PROFILE_PATH := "user://client_profile.cfg"
const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")
const EmberTheme = preload("res://scripts/ui/ember_theme.gd")

const STEP_IDENTITY := 0
const STEP_QUESTIONNAIRE := 1
const STEP_ROLL := 2
const STEP_BUILD := 3
const STEP_SUMMARY := 4

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

const ABILITY_ORDER := ["MIG", "AGI", "END", "MND", "INS", "PRE"]
const CLASS_PRIORITIES := {
	"warrior": ["MIG", "END", "AGI", "PRE", "INS", "MND"],
	"rogue": ["AGI", "INS", "PRE", "END", "MIG", "MND"],
	"mage": ["MND", "INS", "AGI", "PRE", "END", "MIG"],
	"priest": ["INS", "MND", "PRE", "END", "AGI", "MIG"],
}

@onready var new_game_btn: Button = $VBoxContainer/NewGameButton
@onready var continue_btn: Button = $VBoxContainer/ContinueButton
@onready var quit_btn: Button = $VBoxContainer/QuitButton
@onready var main_menu: VBoxContainer = $VBoxContainer
@onready var title_label: Label = $TitleLabel
@onready var subtitle_label: Label = $SubtitleLabel
@onready var creation_panel: Panel = $CharacterCreation
@onready var status_label: Label = $StatusLabel
@onready var creation_vbox: VBoxContainer = $CharacterCreation/VBox

@onready var step_label: Label = $CharacterCreation/VBox/StepLabel
@onready var identity_section: VBoxContainer = $CharacterCreation/VBox/IdentitySection
@onready var questionnaire_section: VBoxContainer = $CharacterCreation/VBox/QuestionnaireSection
@onready var roll_section: VBoxContainer = $CharacterCreation/VBox/RollSection
@onready var build_section: VBoxContainer = $CharacterCreation/VBox/BuildSection
@onready var summary_section: VBoxContainer = $CharacterCreation/VBox/SummarySection

@onready var name_input: LineEdit = $CharacterCreation/VBox/IdentitySection/NameInput
@onready var adapter_option: OptionButton = $CharacterCreation/VBox/IdentitySection/AdapterOption
@onready var advanced_toggle_button: Button = $CharacterCreation/VBox/IdentitySection/AdvancedToggleButton
@onready var advanced_section: VBoxContainer = $CharacterCreation/VBox/IdentitySection/AdvancedSection
@onready var profile_input: LineEdit = $CharacterCreation/VBox/IdentitySection/AdvancedSection/ProfileInput
@onready var seed_input: LineEdit = $CharacterCreation/VBox/IdentitySection/AdvancedSection/SeedInput

@onready var question_progress_label: Label = $CharacterCreation/VBox/QuestionnaireSection/QuestionProgressLabel
@onready var question_prompt: RichTextLabel = $CharacterCreation/VBox/QuestionnaireSection/QuestionPrompt
@onready var answer_option: OptionButton = $CharacterCreation/VBox/QuestionnaireSection/AnswerOption

@onready var current_roll_label: Label = $CharacterCreation/VBox/RollSection/CurrentRollLabel
@onready var saved_roll_label: Label = $CharacterCreation/VBox/RollSection/SavedRollLabel
@onready var reroll_button: Button = $CharacterCreation/VBox/RollSection/RollButtonRow/RerollButton
@onready var save_roll_button: Button = $CharacterCreation/VBox/RollSection/RollButtonRow/SaveRollButton
@onready var swap_roll_button: Button = $CharacterCreation/VBox/RollSection/RollButtonRow/SwapRollButton

@onready var class_option: OptionButton = $CharacterCreation/VBox/BuildSection/ClassOption
@onready var alignment_input: LineEdit = $CharacterCreation/VBox/BuildSection/AlignmentInput
@onready var skills_input: LineEdit = $CharacterCreation/VBox/BuildSection/SkillsInput
@onready var auto_assign_button: Button = $CharacterCreation/VBox/BuildSection/AutoAssignButton
@onready var stats_grid: GridContainer = $CharacterCreation/VBox/BuildSection/StatsGrid
@onready var mig_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/MIGInput
@onready var agi_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/AGIInput
@onready var end_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/ENDInput
@onready var mnd_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/MNDInput
@onready var ins_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/INSInput
@onready var pre_input: LineEdit = $CharacterCreation/VBox/BuildSection/StatsGrid/PREInput
@onready var summary_text: RichTextLabel = $CharacterCreation/VBox/SummarySection/SummaryText

@onready var back_step_button: Button = $CharacterCreation/VBox/ButtonRow/BackStepButton
@onready var next_button: Button = $CharacterCreation/VBox/ButtonRow/NextButton
@onready var start_button: Button = $CharacterCreation/VBox/ButtonRow/StartButton
@onready var cancel_button: Button = $CharacterCreation/VBox/ButtonRow/BackButton
@onready var load_browser: Panel = $LoadBrowser
@onready var load_player_input: LineEdit = $LoadBrowser/VBox/PlayerRow/PlayerInput
@onready var load_refresh_button: Button = $LoadBrowser/VBox/PlayerRow/RefreshButton
@onready var load_status_label: Label = $LoadBrowser/VBox/StatusLabel
@onready var load_save_list: VBoxContainer = $LoadBrowser/VBox/SaveScroll/SaveList
@onready var load_close_button: Button = $LoadBrowser/VBox/ButtonRow/CloseButton

var wizard_step: int = STEP_IDENTITY
var creation_payload: Dictionary = {}
var is_busy: bool = false
var load_browser_busy: bool = false
var _build_touched: bool = false
var _suppress_build_tracking: bool = false
var _draft_build_state: Dictionary = {}
var _questionnaire_choices: Dictionary = {}
var _questionnaire_selectors: Dictionary = {}
var _pending_questionnaire_answers: Array = []
var _question_scroll: ScrollContainer
var _question_list: VBoxContainer
var _creation_body: HSplitContainer
var _creation_form_scroll: ScrollContainer
var _creation_form_content: VBoxContainer
var _creation_preview_panel: PanelContainer
var _creation_preview_title: Label
var _creation_preview_text: RichTextLabel
var _creation_preview_meta: RichTextLabel
var _allocation_panel: VBoxContainer
var _allocation_state_label: Label
var _allocation_pool_label: Label
var _allocation_hint: RichTextLabel
var _allocation_value_labels: Dictionary = {}
var _allocation_minus_buttons: Dictionary = {}
var _allocation_plus_buttons: Dictionary = {}


func _ready() -> void:
	EmberTheme.apply_title_screen(self)
	creation_panel.visible = false
	load_browser.visible = false
	status_label.text = ""
	new_game_btn.pressed.connect(_on_new_game)
	continue_btn.pressed.connect(_on_continue)
	quit_btn.pressed.connect(_on_quit)
	next_button.pressed.connect(_on_next_pressed)
	back_step_button.pressed.connect(_on_previous_step)
	cancel_button.pressed.connect(_on_cancel_pressed)
	start_button.pressed.connect(_on_finalize_pressed)
	reroll_button.pressed.connect(_on_reroll_pressed)
	save_roll_button.pressed.connect(_on_save_roll_pressed)
	swap_roll_button.pressed.connect(_on_swap_roll_pressed)
	auto_assign_button.pressed.connect(_on_auto_assign_pressed)
	advanced_toggle_button.pressed.connect(_on_toggle_advanced)
	load_refresh_button.pressed.connect(_refresh_load_browser)
	load_close_button.pressed.connect(_close_load_browser)
	load_player_input.text_submitted.connect(func(_text: String) -> void:
		_refresh_load_browser()
	)
	Backend.request_error.connect(_on_backend_error)

	_populate_adapter_options()
	_populate_class_options()
	_wire_build_tracking()
	_install_creation_shell()
	_install_questionnaire_canvas()
	_install_allocation_board()
	_configure_build_inputs()
	_reset_wizard_state()
	continue_btn.disabled = false


func _on_new_game() -> void:
	status_label.text = ""
	load_browser.visible = false
	creation_panel.visible = true
	creation_payload = {}
	wizard_step = STEP_IDENTITY
	_refresh_shell_visibility()
	_refresh_creation_view()
	name_input.grab_focus()


func _on_continue() -> void:
	_open_load_browser()


func _on_quit() -> void:
	get_tree().quit()


func _on_cancel_pressed() -> void:
	_reset_wizard_state()


func _on_previous_step() -> void:
	if is_busy:
		return
	match wizard_step:
		STEP_BUILD:
			wizard_step = STEP_ROLL
		STEP_SUMMARY:
			wizard_step = STEP_BUILD
		_:
			return
	_refresh_creation_view()


func _on_next_pressed() -> void:
	if is_busy:
		return
	match wizard_step:
		STEP_IDENTITY:
			_begin_creation_flow()
		STEP_QUESTIONNAIRE:
			_submit_question_answer()
		STEP_ROLL:
			wizard_step = STEP_BUILD
			_refresh_creation_view()
		STEP_BUILD:
			_capture_build_state()
			_update_summary_preview()
			wizard_step = STEP_SUMMARY
			_refresh_creation_view()


func _on_finalize_pressed() -> void:
	if is_busy:
		return
	if creation_payload.is_empty():
		status_label.text = "Start character creation first."
		return
	var payload := {
		"player_name": name_input.text.strip_edges(),
		"adapter_id": _selected_adapter_id(),
		"profile_id": _selected_profile_id(),
		"player_class": _selected_class_id(),
		"alignment": alignment_input.text.strip_edges(),
		"skill_proficiencies": _selected_skills(),
		"assigned_stats": _selected_stats(),
		"selected_facets": _selected_creation_facets(),
		"creation_answers": creation_payload.get("answers", []),
		"creation_profile": {
			"campaign_genesis": creation_payload.get("campaign_genesis", {}),
			"world_seed_hints": creation_payload.get("world_seed_hints", {}),
			"questionnaire": _questionnaire_choices.duplicate(true),
		},
	}
	var seed_value = _selected_seed()
	if seed_value >= 0:
		payload["seed"] = seed_value
	_set_busy(true, "Finalizing campaign...")
	Backend.finalize_campaign_creation(str(creation_payload.get("creation_id", "")), _on_campaign_created, payload)


func _begin_creation_flow() -> void:
	var player_name = name_input.text.strip_edges()
	if player_name.is_empty():
		status_label.text = "Enter a character name."
		return
	GameState.reset()
	_set_busy(true, "Starting creation...")
	Backend.start_campaign_creation(
		player_name,
		_selected_adapter_id(),
		_on_creation_started,
		_selected_profile_id(),
		_selected_seed(),
		"",
	)


func _on_creation_started(data) -> void:
	_set_busy(false, "")
	if data == null:
		status_label.text = "Failed to start character creation."
		return
	_apply_creation_state(data)
	if _current_question().is_empty():
		wizard_step = STEP_ROLL
	else:
		wizard_step = STEP_QUESTIONNAIRE
	_refresh_creation_view()


func _submit_question_answer() -> void:
	var queue: Array = []
	var answered_map = _answered_question_map()
	for question_id in _question_ids_in_display_order():
		var answer_id = str(_questionnaire_choices.get(question_id, "")).strip_edges()
		if answer_id.is_empty():
			status_label.text = "Answer every questionnaire item before moving on."
			return
		if str(answered_map.get(question_id, "")) != answer_id:
			queue.append({
				"question_id": question_id,
				"answer_id": answer_id,
			})
	_pending_questionnaire_answers = queue
	if _pending_questionnaire_answers.is_empty():
		wizard_step = STEP_ROLL
		_refresh_creation_view()
		return
	_set_busy(true, "Locking questionnaire into the campaign frame...")
	_submit_next_questionnaire_answer()


func _on_question_answered(data) -> void:
	_set_busy(false, "")
	if data == null:
		status_label.text = "Failed to record answer."
		return
	_apply_creation_state(data)
	if _current_question().is_empty():
		wizard_step = STEP_ROLL
	else:
		wizard_step = STEP_QUESTIONNAIRE
	_refresh_creation_view()


func _submit_next_questionnaire_answer() -> void:
	if _pending_questionnaire_answers.is_empty():
		_set_busy(false, "")
		wizard_step = STEP_ROLL
		_refresh_creation_view()
		return
	var entry = _pending_questionnaire_answers[0]
	_pending_questionnaire_answers.remove_at(0)
	Backend.answer_campaign_creation(
		str(creation_payload.get("creation_id", "")),
		str(entry.get("question_id", "")),
		str(entry.get("answer_id", "")),
		_on_questionnaire_batch_answered.bind(str(entry.get("question_id", "")), str(entry.get("answer_id", ""))),
	)


func _on_questionnaire_batch_answered(data, _question_id: String, _answer_id: String) -> void:
	if data == null:
		_pending_questionnaire_answers.clear()
		_set_busy(false, "")
		status_label.text = "Failed to record the questionnaire."
		return
	_apply_creation_state(data)
	_submit_next_questionnaire_answer()


func _on_reroll_pressed() -> void:
	if is_busy or creation_payload.is_empty():
		return
	_set_busy(true, "Rolling stats...")
	Backend.reroll_campaign_creation(str(creation_payload.get("creation_id", "")), _on_roll_updated)


func _on_save_roll_pressed() -> void:
	if is_busy or creation_payload.is_empty():
		return
	_set_busy(true, "Saving roll...")
	Backend.save_campaign_creation_roll(str(creation_payload.get("creation_id", "")), _on_roll_updated)


func _on_swap_roll_pressed() -> void:
	if is_busy or creation_payload.is_empty():
		return
	_set_busy(true, "Swapping rolls...")
	Backend.swap_campaign_creation_roll(str(creation_payload.get("creation_id", "")), _on_roll_updated)


func _on_roll_updated(data) -> void:
	_set_busy(false, "")
	if data == null:
		status_label.text = "Failed to update rolls."
		return
	_apply_creation_state(data)
	_refresh_creation_view()


func _apply_creation_state(data: Dictionary) -> void:
	creation_payload = data.duplicate(true)
	GameState.update_from_response(creation_payload)
	_sync_questionnaire_choices_from_payload(true)
	_build_touched = false
	_draft_build_state = {}
	_apply_creation_defaults(true)


func _go_to_step(step: int) -> void:
	if wizard_step == STEP_BUILD and step == STEP_SUMMARY:
		_capture_build_state()
	wizard_step = clampi(step, STEP_IDENTITY, STEP_SUMMARY)
	_refresh_creation_view()


func _on_auto_assign_pressed() -> void:
	_apply_recommended_stats()
	_build_touched = true
	_update_summary_preview()


func _on_campaign_created(data) -> void:
	_set_busy(false, "")
	if data == null:
		status_label.text = "Failed to create a campaign."
		return
	GameState.reset()
	GameState.update_from_response(data)
	_store_last_player_id(str(GameState.player.get("name", name_input.text.strip_edges())))
	_store_last_adapter_id(str(GameState.adapter_id))
	creation_payload = {}
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _on_campaign_loaded(data, requested_save_id: String) -> void:
	_set_load_browser_busy(false, "")
	if data == null:
		if load_browser.visible:
			load_status_label.text = "Failed to load %s." % requested_save_id
		else:
			status_label.text = "Failed to load %s." % requested_save_id
		return
	GameState.reset()
	GameState.update_from_response(data)
	GameState.seed_campaign_resume_narrative(str(data.get("narrative", "")))
	GameState.last_save_slot = requested_save_id
	var resumed_player_id = str(GameState.player.get("name", _last_player_id()))
	_store_last_player_id(resumed_player_id)
	_store_last_resume_player_id(resumed_player_id)
	_store_last_adapter_id(str(GameState.adapter_id))
	_store_last_campaign_save_id(requested_save_id)
	get_tree().change_scene_to_file("res://scenes/game_session.tscn")


func _on_backend_error(message: String) -> void:
	_set_busy(false, "")
	_set_load_browser_busy(false, "")
	continue_btn.disabled = false
	if load_browser.visible:
		load_status_label.text = message
	else:
		status_label.text = message


func _set_busy(busy: bool, message: String) -> void:
	is_busy = busy
	next_button.disabled = busy
	start_button.disabled = busy
	back_step_button.disabled = busy
	reroll_button.disabled = busy
	save_roll_button.disabled = busy
	swap_roll_button.disabled = busy
	auto_assign_button.disabled = busy
	if not message.is_empty():
		status_label.text = message
	elif not busy:
		status_label.text = ""


func _refresh_creation_view() -> void:
	identity_section.visible = wizard_step == STEP_IDENTITY
	questionnaire_section.visible = wizard_step == STEP_QUESTIONNAIRE
	roll_section.visible = wizard_step == STEP_ROLL
	build_section.visible = wizard_step == STEP_BUILD
	summary_section.visible = wizard_step == STEP_SUMMARY
	next_button.visible = wizard_step != STEP_SUMMARY
	start_button.visible = wizard_step == STEP_SUMMARY
	back_step_button.visible = wizard_step in [STEP_BUILD, STEP_SUMMARY]

	match wizard_step:
		STEP_IDENTITY:
			step_label.text = "Step 1: Identity"
			_set_creation_preview(
				"Commander Intake",
				"[b]Identity Frame[/b]\nChoose the commander name, adapter, and optional deterministic world seed before the world frame locks in.",
				"[b]Identity Rule[/b]\nName is required. Profile and seed are optional overrides, not hidden blockers."
			)
		STEP_QUESTIONNAIRE:
			step_label.text = "Step 2: World and Commander Questions"
		STEP_ROLL:
			step_label.text = "Step 3: Rolled Pool"
		STEP_BUILD:
			step_label.text = "Step 4: Allocation and Build"
		STEP_SUMMARY:
			step_label.text = "Step 5: Dossier"

	if wizard_step == STEP_QUESTIONNAIRE:
		_update_question_view()
	elif wizard_step == STEP_ROLL:
		_update_roll_view()
	elif wizard_step == STEP_BUILD:
		_update_build_view()
	elif wizard_step == STEP_SUMMARY:
		_update_summary_preview()
	call_deferred("_focus_primary_creation_control")


func _on_toggle_advanced() -> void:
	advanced_section.visible = not advanced_section.visible
	_update_advanced_toggle_text()


func _update_advanced_toggle_text() -> void:
	advanced_toggle_button.text = "Hide Advanced Settings" if advanced_section.visible else "Show Advanced Settings"


func _open_load_browser() -> void:
	creation_panel.visible = false
	load_browser.visible = true
	status_label.text = ""
	_refresh_shell_visibility()
	load_player_input.text = _preferred_resume_player_id()
	load_status_label.text = "Choose a save slot to continue." if not load_player_input.text.is_empty() else "Enter a player name to browse saves."
	_clear_load_rows()
	_update_advanced_toggle_text()
	if not load_player_input.text.is_empty():
		_refresh_load_browser()
	load_player_input.grab_focus()


func _close_load_browser() -> void:
	load_browser.visible = false
	load_status_label.text = "Choose a save slot to continue."
	_clear_load_rows()
	_refresh_shell_visibility()
	new_game_btn.grab_focus()


func _refresh_load_browser() -> void:
	var player_id = load_player_input.text.strip_edges()
	if player_id.is_empty():
		load_status_label.text = "Enter a player name to browse saves."
		_clear_load_rows()
		return
	_set_load_browser_busy(true, "Loading saves for %s..." % player_id)
	Backend.list_saves(_on_saves_listed, player_id)


func _on_saves_listed(data) -> void:
	_set_load_browser_busy(false, "")
	_clear_load_rows()
	if data == null:
		return
	var entries: Array = []
	if data is Array:
		entries = data
	elif data is Dictionary and data.get("saves", []) is Array:
		entries = data.get("saves", [])
	if entries.is_empty():
		load_status_label.text = "No saves found for this player."
		return
	var sorted_entries := entries.duplicate()
	sorted_entries.sort_custom(func(left, right) -> bool:
		return str(left.get("timestamp", "")) > str(right.get("timestamp", ""))
	)
	var campaign_entries: Array = []
	var hidden_incompatible_count := 0
	for entry in sorted_entries:
		if entry is Dictionary:
			if _is_campaign_compatible_save(entry):
				campaign_entries.append(entry)
			else:
				hidden_incompatible_count += 1

	if campaign_entries.is_empty():
		if hidden_incompatible_count > 0:
			load_status_label.text = "Only legacy or incompatible saves are available for this player."
		else:
			load_status_label.text = "No campaign saves found for this player."
		return

	for entry in campaign_entries:
		load_save_list.add_child(_build_save_row(entry))
	_sync_load_browser_row_buttons()
	if hidden_incompatible_count > 0:
		load_status_label.text = "Found %d campaign save(s). Hidden %d legacy save(s)." % [campaign_entries.size(), hidden_incompatible_count]
	else:
		load_status_label.text = "Found %d campaign save(s)." % campaign_entries.size()


func _build_save_row(entry: Dictionary) -> Control:
	var row = HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var info = VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var slot_name = str(entry.get("slot_name", entry.get("save_id", "Unnamed Save")))
	var location = str(entry.get("location", "Unknown Location"))
	var title = Label.new()
	title.text = "%s — %s" % [slot_name, location]
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_child(title)

	var meta = Label.new()
	meta.text = "Saved %s" % str(entry.get("timestamp", "Unknown time"))
	meta.modulate = Color(0.75, 0.75, 0.78)
	meta.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.add_child(meta)

	row.add_child(info)

	var load_button = Button.new()
	load_button.name = "LoadButton"
	var save_id = str(entry.get("save_id", slot_name))
	load_button.text = "Load"
	load_button.tooltip_text = "Load %s" % slot_name
	load_button.disabled = load_browser_busy
	load_button.pressed.connect(func() -> void:
		_load_save_from_browser(save_id)
	)
	row.add_child(load_button)
	return row


func _load_save_from_browser(save_id: String) -> void:
	if load_browser_busy:
		return
	if save_id.is_empty():
		load_status_label.text = "This save is missing a save_id."
		return
	_set_load_browser_busy(true, "Loading %s..." % save_id)
	Backend.load_campaign(save_id, _on_campaign_loaded.bind(save_id))


func _clear_load_rows() -> void:
	for child in load_save_list.get_children():
		child.queue_free()


func _set_load_browser_busy(busy: bool, message: String) -> void:
	load_browser_busy = busy
	continue_btn.disabled = busy
	load_refresh_button.disabled = busy
	load_close_button.disabled = busy
	_sync_load_browser_row_buttons()
	if not message.is_empty():
		load_status_label.text = message


func _sync_load_browser_row_buttons() -> void:
	for child in load_save_list.get_children():
		if child is HBoxContainer:
			for grandchild in child.get_children():
				if grandchild is Button:
					grandchild.disabled = load_browser_busy


func _is_campaign_compatible_save(entry: Dictionary) -> bool:
	if entry.has("campaign_compatible"):
		return bool(entry.get("campaign_compatible", true))
	return false


func _install_creation_shell() -> void:
	creation_panel.anchors_preset = Control.PRESET_FULL_RECT
	creation_panel.anchor_left = 0.0
	creation_panel.anchor_top = 0.0
	creation_panel.anchor_right = 1.0
	creation_panel.anchor_bottom = 1.0
	creation_panel.offset_left = 48.0
	creation_panel.offset_top = 40.0
	creation_panel.offset_right = -48.0
	creation_panel.offset_bottom = -40.0
	load_browser.anchors_preset = Control.PRESET_FULL_RECT
	load_browser.anchor_left = 0.0
	load_browser.anchor_top = 0.0
	load_browser.anchor_right = 1.0
	load_browser.anchor_bottom = 1.0
	load_browser.offset_left = 88.0
	load_browser.offset_top = 72.0
	load_browser.offset_right = -88.0
	load_browser.offset_bottom = -72.0
	creation_vbox.add_theme_constant_override("separation", 18)
	if creation_vbox.get_node_or_null("CreationBody") != null:
		return
	var button_row := $CharacterCreation/VBox/ButtonRow
	button_row.alignment = BoxContainer.ALIGNMENT_END
	_creation_body = HSplitContainer.new()
	_creation_body.name = "CreationBody"
	_creation_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_creation_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_creation_body.split_offset = 720
	creation_vbox.add_child(_creation_body)
	creation_vbox.move_child(_creation_body, creation_vbox.get_children().find(button_row))

	var form_pane = VBoxContainer.new()
	form_pane.name = "FormPane"
	form_pane.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form_pane.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_creation_body.add_child(form_pane)

	_creation_form_scroll = ScrollContainer.new()
	_creation_form_scroll.name = "FormScroll"
	_creation_form_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_creation_form_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_creation_form_scroll.custom_minimum_size = Vector2(0, 520)
	form_pane.add_child(_creation_form_scroll)

	_creation_form_content = VBoxContainer.new()
	_creation_form_content.name = "FormContent"
	_creation_form_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_creation_form_content.add_theme_constant_override("separation", 16)
	_creation_form_scroll.add_child(_creation_form_content)

	for section in [identity_section, questionnaire_section, roll_section, build_section, summary_section]:
		var parent = section.get_parent()
		if parent != null:
			parent.remove_child(section)
		_creation_form_content.add_child(section)
		section.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	_creation_preview_panel = PanelContainer.new()
	_creation_preview_panel.name = "PreviewPane"
	_creation_preview_panel.custom_minimum_size = Vector2(360, 0)
	_creation_preview_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_creation_preview_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_creation_body.add_child(_creation_preview_panel)

	var preview_margin = MarginContainer.new()
	preview_margin.name = "PreviewMargin"
	preview_margin.add_theme_constant_override("margin_left", 14)
	preview_margin.add_theme_constant_override("margin_top", 12)
	preview_margin.add_theme_constant_override("margin_right", 14)
	preview_margin.add_theme_constant_override("margin_bottom", 12)
	_creation_preview_panel.add_child(preview_margin)

	var preview_vbox = VBoxContainer.new()
	preview_vbox.name = "PreviewVBox"
	preview_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview_vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	preview_vbox.add_theme_constant_override("separation", 10)
	preview_margin.add_child(preview_vbox)

	_creation_preview_title = Label.new()
	_creation_preview_title.name = "PreviewHeading"
	_creation_preview_title.text = "Campaign Genesis"
	_creation_preview_title.add_theme_font_size_override("font_size", 22)
	preview_vbox.add_child(_creation_preview_title)

	_creation_preview_text = RichTextLabel.new()
	_creation_preview_text.name = "PreviewText"
	_creation_preview_text.bbcode_enabled = true
	_creation_preview_text.fit_content = false
	_creation_preview_text.scroll_active = true
	_creation_preview_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_creation_preview_text.custom_minimum_size = Vector2(0, 320)
	preview_vbox.add_child(_creation_preview_text)

	_creation_preview_meta = RichTextLabel.new()
	_creation_preview_meta.name = "PreviewMeta"
	_creation_preview_meta.bbcode_enabled = true
	_creation_preview_meta.fit_content = true
	_creation_preview_meta.scroll_active = false
	_creation_preview_meta.custom_minimum_size = Vector2(0, 120)
	preview_vbox.add_child(_creation_preview_meta)


func _install_questionnaire_canvas() -> void:
	answer_option.visible = false
	question_prompt.visible = false
	question_prompt.custom_minimum_size = Vector2(0, 132)
	question_prompt.bbcode_enabled = true
	question_prompt.fit_content = false
	question_prompt.scroll_active = true
	_question_scroll = ScrollContainer.new()
	_question_scroll.name = "QuestionScroll"
	_question_scroll.custom_minimum_size = Vector2(0, 360)
	_question_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_question_list = VBoxContainer.new()
	_question_list.name = "QuestionList"
	_question_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_question_list.add_theme_constant_override("separation", 12)
	_question_scroll.add_child(_question_list)
	questionnaire_section.add_child(_question_scroll)
	questionnaire_section.move_child(_question_scroll, questionnaire_section.get_child_count() - 1)


func _install_allocation_board() -> void:
	_allocation_panel = VBoxContainer.new()
	_allocation_panel.name = "AllocationPanel"
	_allocation_panel.add_theme_constant_override("separation", 8)
	_allocation_state_label = Label.new()
	_allocation_state_label.name = "AllocationStateLabel"
	_allocation_panel.add_child(_allocation_state_label)
	_allocation_pool_label = Label.new()
	_allocation_pool_label.name = "AllocationPoolLabel"
	_allocation_pool_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_allocation_panel.add_child(_allocation_pool_label)
	_allocation_hint = RichTextLabel.new()
	_allocation_hint.name = "AllocationHint"
	_allocation_hint.custom_minimum_size = Vector2(0, 80)
	_allocation_hint.bbcode_enabled = true
	_allocation_hint.fit_content = true
	_allocation_hint.scroll_active = false
	_allocation_panel.add_child(_allocation_hint)
	for ability in ABILITY_ORDER:
		var row = HBoxContainer.new()
		row.name = "%sRow" % ability
		row.add_theme_constant_override("separation", 8)
		var ability_label = Label.new()
		ability_label.text = ability
		ability_label.custom_minimum_size = Vector2(52, 0)
		row.add_child(ability_label)
		var minus_button = Button.new()
		minus_button.text = "-"
		minus_button.custom_minimum_size = Vector2(36, 36)
		minus_button.pressed.connect(_on_shift_stat_pressed.bind(ability, -1))
		row.add_child(minus_button)
		var value_label = Label.new()
		value_label.text = "10 (+0)"
		value_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(value_label)
		var plus_button = Button.new()
		plus_button.text = "+"
		plus_button.custom_minimum_size = Vector2(36, 36)
		plus_button.pressed.connect(_on_shift_stat_pressed.bind(ability, 1))
		row.add_child(plus_button)
		_allocation_value_labels[ability] = value_label
		_allocation_minus_buttons[ability] = minus_button
		_allocation_plus_buttons[ability] = plus_button
		_allocation_panel.add_child(row)
	build_section.add_child(_allocation_panel)
	build_section.move_child(_allocation_panel, build_section.get_children().find(auto_assign_button) + 1)


func _configure_build_inputs() -> void:
	auto_assign_button.text = "Reset To Recommended Assignment"
	class_option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	alignment_input.placeholder_text = "LG, TN, CG..."
	skills_input.placeholder_text = "athletics, perception"
	for ability in ABILITY_ORDER:
		var field = _stat_input_for(ability)
		field.editable = false
		field.visible = false
	stats_grid.visible = false


func _question_groups_for_view() -> Array:
	var groups = creation_payload.get("question_groups", [])
	if groups is Array and not groups.is_empty():
		return groups
	if creation_payload.get("questions", []) is Array:
		return [{
			"id": "questionnaire",
			"title": "Questionnaire",
			"subtitle": "Answer every question before continuing.",
			"questions": creation_payload.get("questions", []),
		}]
	return []


func _question_ids_in_display_order() -> Array[String]:
	var ordered: Array[String] = []
	for group in _question_groups_for_view():
		if not (group is Dictionary):
			continue
		for question in group.get("questions", []):
			if question is Dictionary:
				ordered.append(str(question.get("id", "")))
	return ordered


func _answered_question_map() -> Dictionary:
	var answered := {}
	for entry in creation_payload.get("answers", []):
		if entry is Dictionary:
			answered[str(entry.get("question_id", ""))] = str(entry.get("answer_id", ""))
	return answered


func _sync_questionnaire_choices_from_payload(preserve_existing: bool) -> void:
	var merged: Dictionary = {}
	if preserve_existing:
		merged = _questionnaire_choices.duplicate(true)
	for entry in creation_payload.get("answers", []):
		if entry is Dictionary:
			merged[str(entry.get("question_id", ""))] = str(entry.get("answer_id", ""))
	_questionnaire_choices = merged


func _render_questionnaire_cards() -> void:
	if _question_list == null:
		return
	for child in _question_list.get_children():
		child.queue_free()
	_questionnaire_selectors.clear()
	for group in _question_groups_for_view():
		if not (group is Dictionary):
			continue
		var card = PanelContainer.new()
		var margin = MarginContainer.new()
		margin.add_theme_constant_override("margin_left", 12)
		margin.add_theme_constant_override("margin_top", 10)
		margin.add_theme_constant_override("margin_right", 12)
		margin.add_theme_constant_override("margin_bottom", 10)
		card.add_child(margin)
		var group_box = VBoxContainer.new()
		group_box.add_theme_constant_override("separation", 8)
		margin.add_child(group_box)
		var title = Label.new()
		title.text = str(group.get("title", "Question Group"))
		group_box.add_child(title)
		var subtitle = Label.new()
		subtitle.text = str(group.get("subtitle", ""))
		subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		group_box.add_child(subtitle)
		for question in group.get("questions", []):
			if not (question is Dictionary):
				continue
			var question_box = VBoxContainer.new()
			question_box.add_theme_constant_override("separation", 4)
			var prompt = RichTextLabel.new()
			prompt.bbcode_enabled = true
			prompt.fit_content = true
			prompt.scroll_active = false
			prompt.custom_minimum_size = Vector2(0, 42)
			prompt.text = "[b]%s[/b]" % str(question.get("text", "Question"))
			question_box.add_child(prompt)
			var selector = OptionButton.new()
			selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			selector.add_item("Choose an answer...")
			selector.set_item_metadata(0, "")
			var selected_answer_id = str(_questionnaire_choices.get(str(question.get("id", "")), str(question.get("selected_answer_id", ""))))
			for answer in question.get("answers", []):
				selector.add_item(str(answer.get("text", "Answer")))
				selector.set_item_metadata(selector.item_count - 1, str(answer.get("id", "")))
			var selected_index := 0
			for idx in range(selector.item_count):
				if str(selector.get_item_metadata(idx)) == selected_answer_id:
					selected_index = idx
					break
			selector.select(selected_index)
			selector.item_selected.connect(_on_questionnaire_answer_selected.bind(str(question.get("id", "")), selector))
			question_box.add_child(selector)
			group_box.add_child(question_box)
			_questionnaire_selectors[str(question.get("id", ""))] = selector
		_question_list.add_child(card)


func _on_questionnaire_answer_selected(index: int, question_id: String, selector: OptionButton) -> void:
	var answer_id = str(selector.get_item_metadata(index)).strip_edges()
	if answer_id.is_empty():
		_questionnaire_choices.erase(question_id)
	else:
		_questionnaire_choices[question_id] = answer_id
	_update_questionnaire_preview()


func _selected_questionnaire_answers() -> Array:
	var selected: Array = []
	for group in _question_groups_for_view():
		if not (group is Dictionary):
			continue
		for question in group.get("questions", []):
			if not (question is Dictionary):
				continue
			var answer_id = str(_questionnaire_choices.get(str(question.get("id", "")), "")).strip_edges()
			if answer_id.is_empty():
				continue
			for answer in question.get("answers", []):
				if answer is Dictionary and str(answer.get("id", "")) == answer_id:
					selected.append(answer)
					break
	return selected


func _merge_int_weights(target: Dictionary, updates: Dictionary) -> void:
	for key in updates.keys():
		target[str(key)] = int(target.get(str(key), 0)) + int(updates.get(key, 0))


func _top_weight_label(weights: Dictionary, labels: Dictionary, fallback: String) -> String:
	var best_key := ""
	var best_value := -9999
	for key in weights.keys():
		var value = int(weights.get(key, 0))
		if value > best_value or (value == best_value and str(key) < best_key):
			best_key = str(key)
			best_value = value
	if best_key.is_empty():
		return fallback
	return str(labels.get(best_key, best_key.replace("_", " ")))


func _unique_strings(values: Array, limit: int) -> Array[String]:
	var result: Array[String] = []
	for value in values:
		var text = str(value).strip_edges()
		if text.is_empty() or result.has(text):
			continue
		result.append(text)
		if result.size() >= limit:
			break
	return result


func _update_questionnaire_preview() -> void:
	var preview_title := "Live Genesis Preview"
	var selected = _selected_questionnaire_answers()
	if selected.is_empty():
		var empty_preview = "[b]Live Genesis Preview[/b]\nChoose answers to shape the world, colony pressure, and opening quest themes."
		question_prompt.text = empty_preview
		_set_creation_preview(preview_title, empty_preview, "[b]Questionnaire Rule[/b]\nEvery visible question must be answered before the rolled pool unlocks.")
		return
	var adapter_bias := {}
	var settlement_bias := {}
	var faction_bias := {}
	var world_tags: Array = []
	var tone_tags: Array = []
	var quest_themes: Array = []
	for answer in selected:
		if answer is Dictionary:
			_merge_int_weights(adapter_bias, answer.get("adapter_weights", {}))
			_merge_int_weights(settlement_bias, answer.get("settlement_bias", {}))
			_merge_int_weights(faction_bias, answer.get("faction_bias", {}))
			world_tags.append_array(answer.get("world_tags", []))
			tone_tags.append_array(answer.get("tone_tags", []))
			quest_themes.append_array(answer.get("quest_themes", []))
	var adapter_name = _top_weight_label(adapter_bias, {
		"fantasy_ember": "Fantasy Ember",
		"scifi_frontier": "Sci-Fi Frontier",
	}, "Fantasy Ember")
	var settlement_name = _top_weight_label(settlement_bias, {
		"fortified_hamlet": "fortified hamlet",
		"border_keep": "border keep",
		"scholar_enclave": "scholar enclave",
		"relay_station": "relay station",
		"harbor_settlement": "harbor settlement",
		"mining_camp": "mining camp",
		"orbital_colony": "orbital colony",
		"pilgrim_town": "pilgrim town",
	}, "frontier settlement")
	var faction_name = _top_weight_label(faction_bias, {
		"guard_captains": "guard captains",
		"clergy": "clergy",
		"guilds": "guilds",
		"free_traders": "free traders",
		"nobility": "nobility",
		"research_conclave": "research conclave",
		"colonial_office": "colonial office",
		"smugglers": "smugglers",
	}, "local power brokers")
	var world_bits = _unique_strings(world_tags, 3)
	var tone_bits = _unique_strings(tone_tags, 3)
	var quest_bits = _unique_strings(quest_themes, 4)
	var preview_text = "[b]Live Genesis Preview[/b]\nWorld: %s shaped by %s.\nColony: %s under pressure from %s.\nTone: %s.\nQuest seeds: %s." % [
		adapter_name,
		", ".join(world_bits) if not world_bits.is_empty() else "frontier stress",
		settlement_name,
		faction_name,
		", ".join(tone_bits) if not tone_bits.is_empty() else "uncertain pressure",
		", ".join(quest_bits) if not quest_bits.is_empty() else "no quest themes locked yet",
	]
	question_prompt.text = preview_text
	_set_creation_preview(preview_title, preview_text, "[b]Questionnaire Rule[/b]\nVisible answers directly bias adapter tone, settlement pressure, faction pull, and quest seed themes.")


func _selected_creation_facets() -> Dictionary:
	return {
		"questionnaire": _questionnaire_choices.duplicate(true),
		"campaign_genesis": creation_payload.get("campaign_genesis", {}).duplicate(true),
		"world_seed_hints": creation_payload.get("world_seed_hints", {}).duplicate(true),
	}


func _on_shift_stat_pressed(ability: String, direction: int) -> void:
	_shift_stat_value(ability, direction)


func _shift_stat_value(ability: String, direction: int) -> void:
	var stats = _selected_stats()
	var current_value = int(stats.get(ability, 10))
	var swap_ability := ""
	var swap_value: int = current_value
	for other in ABILITY_ORDER:
		if other == ability:
			continue
		var candidate = int(stats.get(other, 10))
		if direction > 0:
			if candidate <= current_value:
				continue
			if swap_ability.is_empty() or candidate < swap_value:
				swap_ability = other
				swap_value = candidate
		else:
			if candidate >= current_value:
				continue
			if swap_ability.is_empty() or candidate > swap_value:
				swap_ability = other
				swap_value = candidate
	if swap_ability.is_empty():
		return
	_suppress_build_tracking = true
	_stat_input_for(ability).text = str(swap_value)
	_stat_input_for(swap_ability).text = str(current_value)
	_suppress_build_tracking = false
	_build_touched = true
	_refresh_allocation_board()
	_update_summary_preview()


func _refresh_allocation_board() -> void:
	if _allocation_panel == null:
		return
	_allocation_state_label.text = "Locked pool: exact rolled array. Use +/- to swap values between abilities."
	_allocation_pool_label.text = "Rolled Pool  %s" % _roll_text(creation_payload.get("current_roll", []))
	_allocation_hint.text = "[b]Build Rule[/b]\nThe six assigned stats must remain a permutation of the active rolled pool. Raw number entry is disabled on purpose."
	var stats = _selected_stats()
	for ability in ABILITY_ORDER:
		var value = int(stats.get(ability, 10))
		if _allocation_value_labels.has(ability):
			var label: Label = _allocation_value_labels[ability]
			label.text = "%d  (%+d)" % [value, _modifier(value)]
		if _allocation_minus_buttons.has(ability):
			var minus_button: Button = _allocation_minus_buttons[ability]
			minus_button.disabled = not _has_swap_candidate(ability, -1, stats)
		if _allocation_plus_buttons.has(ability):
			var plus_button: Button = _allocation_plus_buttons[ability]
			plus_button.disabled = not _has_swap_candidate(ability, 1, stats)


func _has_swap_candidate(ability: String, direction: int, stats: Dictionary) -> bool:
	var current_value = int(stats.get(ability, 10))
	for other in ABILITY_ORDER:
		if other == ability:
			continue
		var candidate = int(stats.get(other, 10))
		if direction > 0 and candidate > current_value:
			return true
		if direction < 0 and candidate < current_value:
			return true
	return false


func _update_question_view() -> void:
	var total_questions = _question_ids_in_display_order().size()
	var answered_count = _answered_question_map().size()
	question_progress_label.text = "Answer every visible question. %d / %d locked into the current creation state." % [answered_count, total_questions]
	_render_questionnaire_cards()
	_update_questionnaire_preview()


func _update_roll_view() -> void:
	current_roll_label.text = "Active Rolled Pool: %s" % _roll_text(creation_payload.get("current_roll", []))
	var saved_roll = creation_payload.get("saved_roll", null)
	saved_roll_label.text = "Saved Pool: %s" % (_roll_text(saved_roll) if saved_roll != null else "No saved pool yet")
	save_roll_button.text = "Lock This Pool"
	swap_roll_button.text = "Swap Active / Saved"
	reroll_button.text = "Roll Fresh Pool"
	_set_creation_preview(
		"Rolled Pool Authority",
		"[b]Active Pool[/b]\n%s\n\n[b]Saved Pool[/b]\n%s" % [
			_roll_text(creation_payload.get("current_roll", [])),
			_roll_text(saved_roll) if saved_roll != null else "No saved pool yet",
		],
		"[b]Roll Rule[/b]\nLock a pool before swapping. The build step can only permute the active pool; it can never mint new values."
	)


func _update_build_view() -> void:
	if _draft_build_state.is_empty():
		_apply_creation_defaults(false)
	else:
		_restore_build_state()
	_refresh_allocation_board()
	_update_summary_preview()


func _update_summary_preview() -> void:
	var genesis = creation_payload.get("campaign_genesis", {})
	var recommended_class = str(creation_payload.get("recommended_class", _selected_class_id()))
	var recommended_alignment = str(creation_payload.get("recommended_alignment", alignment_input.text.strip_edges()))
	var recommended_skills = ", ".join(creation_payload.get("recommended_skills", []))
	var selected_stats = _selected_stats()
	var stat_lines: Array[String] = []
	for ability in ABILITY_ORDER:
		stat_lines.append("%s %d (%+d)" % [ability, int(selected_stats.get(ability, 10)), _modifier(int(selected_stats.get(ability, 10)))])
	var quest_themes = genesis.get("quest_seed_themes", [])
	summary_text.text = "[b]World Premise[/b]\n%s\n\n[b]Commander Profile[/b]\n%s\n\n[b]Colony Pressure[/b]\n%s\n\n[b]Quest Seeds[/b]\n%s\n\n[b]Recommended Frame[/b]\nClass: %s\nAlignment: %s\nSkills: %s\n\n[b]Final Build[/b]\nClass: %s\nAlignment: %s\nSkills: %s\nStats: %s" % [
		str(genesis.get("world_premise", "A frontier colony waits for the first hard decision.")),
		str(genesis.get("commander_profile", "The commander has not yet been fully framed.")),
		str(genesis.get("starting_pressure", "Choose answers that define the colony's first pressure.")),
		", ".join(quest_themes) if quest_themes is Array and not quest_themes.is_empty() else "No quest themes locked yet.",
		recommended_class.capitalize(),
		recommended_alignment,
		recommended_skills,
		_selected_class_id().capitalize(),
		alignment_input.text.strip_edges(),
		", ".join(_selected_skills()),
		" | ".join(stat_lines),
	]
	if wizard_step == STEP_SUMMARY:
		_set_creation_preview(
			"Launch Dossier",
			"[b]Start Check[/b]\nReview the dossier on the left before committing.\n\n[b]Current Class[/b] %s\n[b]Alignment[/b] %s\n[b]Skills[/b] %s" % [
				_selected_class_id().capitalize(),
				alignment_input.text.strip_edges(),
				", ".join(_selected_skills()),
			],
			"[b]Launch Rule[/b]\nUse Previous to revise build decisions. Start Campaign should never be the first time the player sees world premise or starting pressure."
		)
	elif wizard_step == STEP_BUILD:
		_set_creation_preview(
			"Allocation Board",
			"[b]Current Build[/b]\nClass: %s\nAlignment: %s\nSkills: %s\nStats: %s" % [
				_selected_class_id().capitalize(),
				alignment_input.text.strip_edges(),
				", ".join(_selected_skills()),
				" | ".join(stat_lines),
			],
			"[b]Build Rule[/b]\nThe six assigned stats must remain a permutation of the active rolled pool. Use +/- to swap positions; raw number entry stays locked."
		)


func _apply_creation_defaults(force: bool = false) -> void:
	if creation_payload.is_empty():
		return
	if _build_touched and not force:
		return
	_suppress_build_tracking = true
	_select_class_by_id(str(creation_payload.get("recommended_class", "warrior")))
	alignment_input.text = str(creation_payload.get("recommended_alignment", "TN"))
	skills_input.text = ", ".join(creation_payload.get("recommended_skills", []))
	_apply_recommended_stats()
	_refresh_allocation_board()
	_suppress_build_tracking = false


func _apply_recommended_stats() -> void:
	var assigned = _suggested_stats_for(_selected_class_id())
	_suppress_build_tracking = true
	for ability in ABILITY_ORDER:
		_stat_input_for(ability).text = str(assigned.get(ability, 10))
	_suppress_build_tracking = false
	_refresh_allocation_board()


func _suggested_stats_for(class_id: String) -> Dictionary:
	var rolled: Array = []
	for value in creation_payload.get("current_roll", []):
		rolled.append(int(value))
	rolled.sort()
	rolled.reverse()
	var priorities: Array = CLASS_PRIORITIES.get(class_id, CLASS_PRIORITIES["warrior"])
	var assigned := {}
	for index in range(ABILITY_ORDER.size()):
		var ability = str(priorities[index] if index < priorities.size() else ABILITY_ORDER[index])
		var value = int(rolled[index] if index < rolled.size() else 10)
		assigned[ability] = value
	for ability in ABILITY_ORDER:
		if not assigned.has(ability):
			assigned[ability] = 10
	return assigned


func _current_question() -> Dictionary:
	var questions: Array = creation_payload.get("questions", [])
	var answered_ids := {}
	for entry in creation_payload.get("answers", []):
		if entry is Dictionary:
			answered_ids[str(entry.get("question_id", ""))] = true
	for question in questions:
		if question is Dictionary and not answered_ids.has(str(question.get("id", ""))):
			return question
	return {}


func _selected_stats() -> Dictionary:
	var stats := {}
	for ability in ABILITY_ORDER:
		var raw_value = _stat_input_for(ability).text.strip_edges()
		stats[ability] = int(raw_value) if raw_value.is_valid_int() else 10
	return stats


func _selected_skills() -> Array[String]:
	var parsed: Array[String] = []
	for chunk in skills_input.text.split(","):
		var skill = chunk.strip_edges().to_lower()
		if not skill.is_empty():
			parsed.append(skill)
	return parsed


func _selected_adapter_id() -> String:
	if adapter_option.item_count == 0:
		return "fantasy_ember"
	return str(adapter_option.get_item_metadata(adapter_option.selected))


func _selected_class_id() -> String:
	if class_option.item_count == 0:
		return "warrior"
	return str(class_option.get_item_metadata(class_option.selected))


func _selected_profile_id() -> String:
	var value = profile_input.text.strip_edges()
	return value if not value.is_empty() else "standard"


func _selected_seed() -> int:
	var value = seed_input.text.strip_edges()
	if value.is_valid_int():
		return int(value)
	return -1


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


func _populate_class_options() -> void:
	class_option.clear()
	for entry in CLASS_OPTIONS:
		class_option.add_item(str(entry["label"]))
		class_option.set_item_metadata(class_option.item_count - 1, str(entry["id"]))
	class_option.select(0)


func _select_class_by_id(class_id: String) -> void:
	for index in range(class_option.item_count):
		if str(class_option.get_item_metadata(index)) == class_id:
			class_option.select(index)
			return


func _reset_wizard_state() -> void:
	creation_panel.visible = false
	load_browser.visible = false
	creation_payload = {}
	wizard_step = STEP_IDENTITY
	_build_touched = false
	_draft_build_state = {}
	_questionnaire_choices.clear()
	_questionnaire_selectors.clear()
	_pending_questionnaire_answers.clear()
	_suppress_build_tracking = true
	name_input.text = _last_player_id()
	profile_input.text = "standard"
	seed_input.text = ""
	advanced_section.visible = false
	alignment_input.text = ""
	skills_input.text = ""
	for ability in ABILITY_ORDER:
		_stat_input_for(ability).text = "10"
	_suppress_build_tracking = false
	status_label.text = ""
	question_progress_label.text = "Answer every question to shape the campaign frame."
	question_prompt.text = "[b]Live Genesis Preview[/b]\nChoose answers to shape the world, colony pressure, and opening quest themes."
	continue_btn.disabled = false
	load_status_label.text = "Choose a save slot to continue."
	_clear_load_rows()
	_update_advanced_toggle_text()
	_refresh_allocation_board()
	_set_creation_preview(
		"Campaign Genesis",
		"[b]Creation Surface[/b]\nName the commander, set optional world seed controls, then answer the grouped questions that shape the deterministic campaign frame.",
		"[b]Flow[/b]\nIdentity -> Questionnaire -> Rolled Pool -> Allocation -> Dossier"
	)
	_refresh_shell_visibility()
	_refresh_creation_view()
	if not creation_panel.visible and not load_browser.visible:
		new_game_btn.grab_focus()


func _wire_build_tracking() -> void:
	class_option.item_selected.connect(_on_build_field_changed)
	alignment_input.text_changed.connect(_on_build_field_changed)
	skills_input.text_changed.connect(_on_build_field_changed)
	for ability in ABILITY_ORDER:
		_stat_input_for(ability).text_changed.connect(_on_build_field_changed)


func _on_build_field_changed(_value = null) -> void:
	if _suppress_build_tracking:
		return
	_build_touched = true


func _capture_build_state() -> void:
	_draft_build_state = {
		"class_id": _selected_class_id(),
		"alignment": alignment_input.text,
		"skills": skills_input.text,
		"stats": _selected_stats(),
	}


func _restore_build_state() -> void:
	if _draft_build_state.is_empty():
		return
	_suppress_build_tracking = true
	_select_class_by_id(str(_draft_build_state.get("class_id", _selected_class_id())))
	alignment_input.text = str(_draft_build_state.get("alignment", ""))
	skills_input.text = str(_draft_build_state.get("skills", ""))
	var stats = _draft_build_state.get("stats", {})
	if stats is Dictionary:
		for ability in ABILITY_ORDER:
			_stat_input_for(ability).text = str(stats.get(ability, 10))
	_suppress_build_tracking = false


func _stat_input_for(ability: String) -> LineEdit:
	match ability:
		"MIG":
			return mig_input
		"AGI":
			return agi_input
		"END":
			return end_input
		"MND":
			return mnd_input
		"INS":
			return ins_input
		"PRE":
			return pre_input
	return mig_input


func _modifier(value: int) -> int:
	return int((value - 10) / 2)


func _roll_text(values) -> String:
	if values == null:
		return "-"
	if not (values is Array):
		return "-"
	var parts: Array[String] = []
	for entry in values:
		parts.append(str(int(entry)))
	return ", ".join(parts)


func _store_last_player_id(player_id: String) -> void:
	_store_profile_value("last_player_id", player_id.strip_edges())


func _last_player_id() -> String:
	return str(_profile_value("last_player_id", "")).strip_edges()


func _store_last_resume_player_id(player_id: String) -> void:
	_store_profile_value("last_resume_player_id", player_id.strip_edges())


func _last_resume_player_id() -> String:
	return str(_profile_value("last_resume_player_id", "")).strip_edges()


func _preferred_resume_player_id() -> String:
	return _last_resume_player_id()


func _store_last_adapter_id(value: String) -> void:
	_store_profile_value("last_adapter_id", value.strip_edges())


func _last_adapter_id() -> String:
	return str(_profile_value("last_adapter_id", "fantasy_ember")).strip_edges()


func _store_last_campaign_save_id(save_id: String) -> void:
	_store_profile_value("last_campaign_save_id", save_id.strip_edges())
	continue_btn.disabled = false


func _last_campaign_save_id() -> String:
	return str(_profile_value("last_campaign_save_id", "")).strip_edges()


func _store_profile_value(key: String, value) -> void:
	var profile = ConfigFile.new()
	profile.load(PROFILE_PATH)
	if str(value).strip_edges().is_empty():
		if profile.has_section_key("profile", key):
			profile.erase_section_key("profile", key)
	else:
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
	var wizard_action = _primary_wizard_action_for_key(event.keycode)
	if _trigger_wizard_action(wizard_action):
		get_viewport().set_input_as_handled()
		return
	if event.keycode != KEY_F12:
		return
	var screenshot_path = ScreenshotCapture.capture_viewport(get_viewport(), "phase2/title", "title_screen")
	if screenshot_path.is_empty():
		status_label.text = "Viewport capture failed."
	else:
		status_label.text = "Viewport capture saved: %s" % screenshot_path
	get_viewport().set_input_as_handled()


func _refresh_shell_visibility() -> void:
	var show_menu_shell = not creation_panel.visible and not load_browser.visible
	main_menu.visible = show_menu_shell
	title_label.visible = show_menu_shell
	subtitle_label.visible = show_menu_shell
	var hero_panel = get_node_or_null("HeroPanel")
	if hero_panel != null:
		hero_panel.visible = show_menu_shell


func _set_creation_preview(title: String, body: String, meta: String) -> void:
	if _creation_preview_title != null:
		_creation_preview_title.text = title
	if _creation_preview_text != null:
		_creation_preview_text.text = body
	if _creation_preview_meta != null:
		_creation_preview_meta.text = meta


func _focus_primary_creation_control() -> void:
	match wizard_step:
		STEP_IDENTITY:
			name_input.grab_focus()
		STEP_QUESTIONNAIRE:
			if not _questionnaire_selectors.is_empty():
				var first_key = _questionnaire_selectors.keys()[0]
				var selector: OptionButton = _questionnaire_selectors[first_key]
				selector.grab_focus()
			else:
				next_button.grab_focus()
		STEP_ROLL:
			reroll_button.grab_focus()
		STEP_BUILD:
			class_option.grab_focus()
		STEP_SUMMARY:
			start_button.grab_focus()


func _primary_wizard_action_for_key(keycode: int) -> String:
	if load_browser.visible or not creation_panel.visible or is_busy:
		return ""
	if keycode not in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		return ""
	if wizard_step == STEP_SUMMARY and start_button.visible and not start_button.disabled:
		return "start"
	if wizard_step in [STEP_IDENTITY, STEP_QUESTIONNAIRE, STEP_ROLL, STEP_BUILD] and next_button.visible and not next_button.disabled:
		return "next"
	return ""


func _trigger_wizard_action(action: String) -> bool:
	match action:
		"next":
			_on_next_pressed()
			return true
		"start":
			_on_finalize_pressed()
			return true
	return false
