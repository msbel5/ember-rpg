extends Control

const PROFILE_PATH := "user://client_profile.cfg"
const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")

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
@onready var creation_panel: Panel = $CharacterCreation
@onready var status_label: Label = $StatusLabel

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


func _ready() -> void:
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
	_reset_wizard_state()
	continue_btn.disabled = false


func _on_new_game() -> void:
	status_label.text = ""
	load_browser.visible = false
	creation_panel.visible = true
	creation_payload = {}
	wizard_step = STEP_IDENTITY
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
	var question = _current_question()
	if question.is_empty():
		wizard_step = STEP_ROLL
		_refresh_creation_view()
		return
	if answer_option.item_count == 0:
		status_label.text = "Select an answer."
		return
	var answer_id = str(answer_option.get_item_metadata(answer_option.selected))
	_set_busy(true, "Recording answer...")
	Backend.answer_campaign_creation(str(creation_payload.get("creation_id", "")), str(question.get("id", "")), answer_id, _on_question_answered)


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
	GameState.last_save_slot = requested_save_id
	_store_last_player_id(str(GameState.player.get("name", _last_player_id())))
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
		STEP_QUESTIONNAIRE:
			step_label.text = "Step 2: Questionnaire"
		STEP_ROLL:
			step_label.text = "Step 3: Dice"
		STEP_BUILD:
			step_label.text = "Step 4: Build"
		STEP_SUMMARY:
			step_label.text = "Step 5: Summary"

	if wizard_step == STEP_QUESTIONNAIRE:
		_update_question_view()
	elif wizard_step == STEP_ROLL:
		_update_roll_view()
	elif wizard_step == STEP_BUILD:
		_update_build_view()
	elif wizard_step == STEP_SUMMARY:
		_update_summary_preview()


func _on_toggle_advanced() -> void:
	advanced_section.visible = not advanced_section.visible
	_update_advanced_toggle_text()


func _update_advanced_toggle_text() -> void:
	advanced_toggle_button.text = "Hide Advanced Settings" if advanced_section.visible else "Show Advanced Settings"


func _open_load_browser() -> void:
	creation_panel.visible = false
	load_browser.visible = true
	status_label.text = ""
	load_player_input.text = _last_player_id()
	load_status_label.text = "Choose a save slot to continue."
	_clear_load_rows()
	_update_advanced_toggle_text()
	_refresh_load_browser()
	load_player_input.grab_focus()


func _close_load_browser() -> void:
	load_browser.visible = false
	load_status_label.text = "Choose a save slot to continue."
	_clear_load_rows()
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
	for entry in sorted_entries:
		if entry is Dictionary:
			load_save_list.add_child(_build_save_row(entry))
	load_status_label.text = "Found %d save(s)." % sorted_entries.size()


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
	var save_id = str(entry.get("save_id", slot_name))
	load_button.text = "Load"
	load_button.tooltip_text = "Load %s" % slot_name
	load_button.pressed.connect(func() -> void:
		_load_save_from_browser(save_id)
	)
	row.add_child(load_button)
	return row


func _load_save_from_browser(save_id: String) -> void:
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
	if not message.is_empty():
		load_status_label.text = message


func _update_question_view() -> void:
	var questions: Array = creation_payload.get("questions", [])
	var answers: Array = creation_payload.get("answers", [])
	var question = _current_question()
	if question.is_empty():
		question_progress_label.text = "Questionnaire complete"
		question_prompt.text = "All questions answered."
		answer_option.clear()
		return
	question_progress_label.text = "Question %d/%d" % [answers.size() + 1, questions.size()]
	question_prompt.text = str(question.get("text", question.get("id", "Question")))
	answer_option.clear()
	for entry in question.get("answers", []):
		answer_option.add_item(str(entry.get("text", "Answer")))
		answer_option.set_item_metadata(answer_option.item_count - 1, str(entry.get("id", "")))
	answer_option.select(0)


func _update_roll_view() -> void:
	current_roll_label.text = "Current Roll: %s" % _roll_text(creation_payload.get("current_roll", []))
	var saved_roll = creation_payload.get("saved_roll", null)
	saved_roll_label.text = "Saved Roll: %s" % (_roll_text(saved_roll) if saved_roll != null else "-")


func _update_build_view() -> void:
	if _draft_build_state.is_empty():
		_apply_creation_defaults(false)
	else:
		_restore_build_state()
	_update_summary_preview()


func _update_summary_preview() -> void:
	var recommended_class = str(creation_payload.get("recommended_class", _selected_class_id()))
	var recommended_alignment = str(creation_payload.get("recommended_alignment", alignment_input.text.strip_edges()))
	var recommended_skills = ", ".join(creation_payload.get("recommended_skills", []))
	var selected_stats = _selected_stats()
	var stat_lines: Array[String] = []
	for ability in ABILITY_ORDER:
		stat_lines.append("%s %d (%+d)" % [ability, int(selected_stats.get(ability, 10)), _modifier(int(selected_stats.get(ability, 10)))])
	summary_text.text = "[b]recommended[/b]\nClass: %s\nAlignment: %s\nSkills: %s\n\n[b]final build[/b]\nClass: %s\nAlignment: %s\nSkills: %s\nStats: %s" % [
		recommended_class.capitalize(),
		recommended_alignment,
		recommended_skills,
		_selected_class_id().capitalize(),
		alignment_input.text.strip_edges(),
		", ".join(_selected_skills()),
		" | ".join(stat_lines),
	]


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
	_suppress_build_tracking = false


func _apply_recommended_stats() -> void:
	var assigned = _suggested_stats_for(_selected_class_id())
	_suppress_build_tracking = true
	for ability in ABILITY_ORDER:
		_stat_input_for(ability).text = str(assigned.get(ability, 10))
	_suppress_build_tracking = false


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
	continue_btn.disabled = false
	load_status_label.text = "Choose a save slot to continue."
	_clear_load_rows()
	_update_advanced_toggle_text()
	_refresh_creation_view()


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
			return $CharacterCreation/VBox/BuildSection/StatsGrid/MIGInput
		"AGI":
			return $CharacterCreation/VBox/BuildSection/StatsGrid/AGIInput
		"END":
			return $CharacterCreation/VBox/BuildSection/StatsGrid/ENDInput
		"MND":
			return $CharacterCreation/VBox/BuildSection/StatsGrid/MNDInput
		"INS":
			return $CharacterCreation/VBox/BuildSection/StatsGrid/INSInput
		"PRE":
			return $CharacterCreation/VBox/BuildSection/StatsGrid/PREInput
	return $CharacterCreation/VBox/BuildSection/StatsGrid/MIGInput


func _modifier(value: int) -> int:
	return int((value - 10) / 2)


func _roll_text(values) -> String:
	if values == null:
		return "-"
	if not (values is Array):
		return "-"
	var parts: Array[String] = []
	for entry in values:
		parts.append(str(entry))
	return ", ".join(parts)


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
	if event.keycode != KEY_F12:
		return
	var screenshot_path = ScreenshotCapture.capture_viewport(get_viewport(), "phase2/title", "title_screen")
	if screenshot_path.is_empty():
		status_label.text = "Viewport capture failed."
	else:
		status_label.text = "Viewport capture saved: %s" % screenshot_path
	get_viewport().set_input_as_handled()
