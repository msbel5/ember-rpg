extends PanelContainer
class_name CreationWizard

const CreationCatalog = preload("res://scripts/ui/creation_catalog.gd")
const CreationWizardState = preload("res://scripts/ui/creation_wizard_state.gd")
const CreationStepGenreQuestion = preload("res://scripts/ui/creation_step_genre_question.gd")
const CreationStepHistoryRoll = preload("res://scripts/ui/creation_step_history_roll.gd")
const CreationStepBuildDossier = preload("res://scripts/ui/creation_step_build_dossier.gd")

const STEP_GENRE := 0
const STEP_QUESTION := 1
const STEP_HISTORY := 2
const STEP_ROLL := 3
const STEP_BUILD := 4
const STEP_DOSSIER := 5

signal canceled()
signal start_creation_requested(player_name: String, adapter_id: String, profile_id: String, seed: int)
signal answer_requested(question_id: String, answer_id: String)
signal reroll_requested()
signal save_roll_requested()
signal swap_roll_requested()
signal finalize_requested(payload: Dictionary)

var _catalog: Dictionary = {}
var _payload: Dictionary = {}
var _step: int = STEP_GENRE
var _selected_adapter_id := "fantasy_ember"
var _selected_profile_id := "standard"
var _selected_class_id := "warrior"
var _selected_alignment := "TN"
var _selected_skills: Array[String] = []
var _assigned_stats: Dictionary = {}
var _busy := false
var _advanced_open := false

var _name_input: LineEdit
var _seed_input: LineEdit
var _advanced_section: VBoxContainer
var _advanced_toggle: Button
var _profile_hint: Label
var _sections: Dictionary = {}
var _step_label: Label
var _preview_title: Label
var _preview_text: RichTextLabel
var _preview_meta: RichTextLabel
var _question_progress: Label
var _question_prompt: RichTextLabel
var _answer_buttons: VBoxContainer
var _history_text: RichTextLabel
var _history_timer: Timer
var _history_source := ""
var _roll_pool_label: Label
var _saved_roll_label: Label
var _stat_rows: VBoxContainer
var _silhouette: Control
var _class_grid: GridContainer
var _alignment_grid: GridContainer
var _skill_grid: GridContainer
var _skill_budget_label: Label
var _dossier_text: RichTextLabel
var _back_button: Button
var _next_button: Button
var _start_button: Button


func _ready() -> void:
	visible = false
	anchors_preset = Control.PRESET_FULL_RECT
	offset_left = 56.0
	offset_top = 42.0
	offset_right = -56.0
	offset_bottom = -42.0
	if get_child_count() == 0:
		_build_ui()
	_reset_state()


func open(player_name: String, adapter_id: String, profile_id: String) -> void:
	visible = true
	_selected_adapter_id = adapter_id if not adapter_id.is_empty() else "fantasy_ember"
	_selected_profile_id = profile_id if not profile_id.is_empty() else "standard"
	_name_input.text = player_name
	_seed_input.text = ""
	_payload = {}
	_step = STEP_GENRE
	_render()


func close() -> void:
	visible = false
	_reset_state()


func set_catalog(catalog: Dictionary) -> void:
	_catalog = catalog.duplicate(true)
	_selected_profile_id = CreationCatalog.default_profile_id(_catalog)
	if _payload.is_empty():
		_selected_class_id = CreationCatalog.default_class_id(_catalog)
	_render()


func apply_creation_state(payload: Dictionary) -> void:
	_payload = payload.duplicate(true)
	_catalog = CreationCatalog.catalog_from(_payload, _catalog)
	_selected_adapter_id = str(_payload.get("adapter_id", _selected_adapter_id))
	CreationWizardState.sync_build_defaults(self)
	_history_source = ""
	if _current_question().is_empty():
		_step = STEP_HISTORY if _step < STEP_HISTORY else _step
	else:
		_step = STEP_QUESTION
	_render()


func set_busy(busy: bool) -> void:
	_busy = busy
	CreationStepBuildDossier.sync_footer(self)
	for child in _answer_buttons.get_children():
		if child is Button:
			child.disabled = busy


func current_step() -> int:
	return _step


func go_to_step(step: int) -> void:
	_step = clamp(step, STEP_GENRE, STEP_DOSSIER)
	if _step == STEP_HISTORY:
		_history_source = ""
	_render()


func primary_action_for_key(keycode: Key) -> String:
	if not visible or _busy:
		return ""
	if keycode not in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
		return ""
	match _step:
		STEP_GENRE:
			return "next" if not _name_input.text.strip_edges().is_empty() else ""
		STEP_HISTORY, STEP_ROLL, STEP_BUILD:
			return "next"
		STEP_DOSSIER:
			return "start"
		_:
			return ""


func activate_answer_shortcut(index: int) -> bool:
	if _step != STEP_QUESTION or index < 0 or index >= _answer_buttons.get_child_count():
		return false
	var button = _answer_buttons.get_child(index)
	if button is Button and not button.disabled:
		button.emit_signal("pressed")
		return true
	return false


func _build_ui() -> void:
	var root := VBoxContainer.new()
	root.name = "VBox"
	root.anchors_preset = Control.PRESET_FULL_RECT
	root.offset_left = 18.0
	root.offset_top = 18.0
	root.offset_right = -18.0
	root.offset_bottom = -18.0
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_theme_constant_override("separation", 16)
	add_child(root)

	var header := Label.new()
	header.text = "Create Your Character"
	header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	header.add_theme_font_size_override("font_size", 34)
	root.add_child(header)

	_step_label = Label.new()
	_step_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_step_label.add_theme_font_size_override("font_size", 24)
	root.add_child(_step_label)

	var split := HSplitContainer.new()
	split.name = "CreationBody"
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.split_offset = 930
	root.add_child(split)

	var form := VBoxContainer.new()
	form.name = "FormPane"
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(form)

	var form_scroll := ScrollContainer.new()
	form_scroll.name = "FormScroll"
	form_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	form.add_child(form_scroll)

	var form_content := VBoxContainer.new()
	form_content.name = "FormContent"
	form_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form_content.add_theme_constant_override("separation", 14)
	form_scroll.add_child(form_content)

	var preview := PanelContainer.new()
	preview.name = "PreviewPane"
	preview.custom_minimum_size = Vector2(360, 0)
	split.add_child(preview)

	var preview_margin := MarginContainer.new()
	preview_margin.name = "PreviewMargin"
	preview_margin.anchors_preset = Control.PRESET_FULL_RECT
	preview_margin.add_theme_constant_override("margin_left", 14)
	preview_margin.add_theme_constant_override("margin_top", 14)
	preview_margin.add_theme_constant_override("margin_right", 14)
	preview_margin.add_theme_constant_override("margin_bottom", 14)
	preview.add_child(preview_margin)

	var preview_vbox := VBoxContainer.new()
	preview_vbox.name = "PreviewVBox"
	preview_vbox.add_theme_constant_override("separation", 10)
	preview_margin.add_child(preview_vbox)

	_preview_title = Label.new()
	_preview_title.name = "PreviewHeading"
	_preview_title.add_theme_font_size_override("font_size", 22)
	preview_vbox.add_child(_preview_title)

	_preview_text = RichTextLabel.new()
	_preview_text.name = "PreviewText"
	_preview_text.bbcode_enabled = true
	_preview_text.fit_content = false
	_preview_text.scroll_active = true
	_preview_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	preview_vbox.add_child(_preview_text)

	_preview_meta = RichTextLabel.new()
	_preview_meta.name = "PreviewMeta"
	_preview_meta.bbcode_enabled = true
	_preview_meta.fit_content = true
	_preview_meta.scroll_active = false
	preview_vbox.add_child(_preview_meta)

	_sections["genre"] = CreationStepGenreQuestion.build_genre_section(self)
	_sections["question"] = CreationStepGenreQuestion.build_question_section(self)
	_sections["history"] = CreationStepHistoryRoll.build_history_section(self)
	_sections["roll"] = CreationStepHistoryRoll.build_roll_section(self)
	_sections["build"] = CreationStepBuildDossier.build_build_section(self)
	_sections["dossier"] = CreationStepBuildDossier.build_dossier_section(self)
	for section in _sections.values():
		form_content.add_child(section)

	var footer := HBoxContainer.new()
	footer.name = "ButtonRow"
	footer.alignment = BoxContainer.ALIGNMENT_END
	footer.add_theme_constant_override("separation", 10)
	root.add_child(footer)

	_back_button = Button.new()
	_back_button.name = "BackButton"
	_back_button.text = "Previous"
	_back_button.pressed.connect(_on_back_pressed)
	footer.add_child(_back_button)

	_next_button = Button.new()
	_next_button.name = "NextButton"
	_next_button.text = "Next"
	_next_button.pressed.connect(_on_next_pressed)
	footer.add_child(_next_button)

	_start_button = Button.new()
	_start_button.name = "StartButton"
	_start_button.text = "Begin Your Story"
	_start_button.pressed.connect(_emit_finalize)
	footer.add_child(_start_button)

	var cancel_button := Button.new()
	cancel_button.name = "CancelButton"
	cancel_button.text = "Cancel"
	cancel_button.pressed.connect(func() -> void: canceled.emit())
	footer.add_child(cancel_button)


func _render() -> void:
	var section_order := ["genre", "question", "history", "roll", "build", "dossier"]
	for key in _sections.keys():
		var control: Control = _sections[key]
		control.visible = key == section_order[_step]
	_step_label.text = CreationWizardState.step_name(_step)
	CreationStepGenreQuestion.sync_advanced_section(self)
	CreationStepGenreQuestion.render_question(self)
	CreationStepHistoryRoll.render_history(self)
	CreationStepHistoryRoll.render_roll(self)
	CreationStepBuildDossier.render_build(self)
	CreationStepBuildDossier.render_dossier(self)
	CreationStepBuildDossier.render_preview(self)
	CreationStepBuildDossier.sync_footer(self)
	call_deferred("_focus_current_step")


func _on_next_pressed() -> void:
	if _busy:
		return
	match _step:
		STEP_GENRE:
			var player_name := _name_input.text.strip_edges()
			if player_name.is_empty():
				return
			start_creation_requested.emit(player_name, _selected_adapter_id, _selected_profile_id, _seed_value())
		STEP_HISTORY:
			if not CreationStepHistoryRoll.history_reveal_complete(self):
				CreationStepHistoryRoll.skip_history_reveal(self)
				return
			_step = STEP_ROLL
			_render()
		STEP_ROLL:
			_step = STEP_BUILD
			_render()
		STEP_BUILD:
			_step = STEP_DOSSIER
			_render()


func _on_back_pressed() -> void:
	if _busy:
		return
	_step = max(STEP_GENRE, _step - 1)
	if _step != STEP_HISTORY:
		_history_source = ""
	_render()


func _emit_finalize() -> void:
	finalize_requested.emit(
		{
			"player_name": _name_input.text.strip_edges(),
			"adapter_id": _selected_adapter_id,
			"profile_id": _selected_profile_id,
			"player_class": _selected_class_id,
			"alignment": _selected_alignment,
			"skill_proficiencies": _selected_skills,
			"assigned_stats": _assigned_stats.duplicate(true),
		}
	)


func _current_question() -> Dictionary:
	return CreationWizardState.current_question(_payload)


func _current_question_index() -> int:
	return CreationWizardState.current_question_index(_payload)


func _answer_map() -> Dictionary:
	return CreationWizardState.answer_map(_payload)


func _begin_history_reveal() -> void:
	CreationStepHistoryRoll.begin_history_reveal(self)


func _on_history_tick() -> void:
	CreationStepHistoryRoll.on_history_tick(self)


func _shift_stat_value(ability: String, direction: int) -> void:
	var current := int(_assigned_stats.get(ability, 10))
	var swap_ability := ""
	var swap_value: int = current
	for other in CreationCatalog.ability_order(_catalog):
		if other == ability:
			continue
		var candidate := int(_assigned_stats.get(other, 10))
		if direction > 0 and candidate > current and (swap_ability.is_empty() or candidate < swap_value):
			swap_ability = other
			swap_value = candidate
		if direction < 0 and candidate < current and (swap_ability.is_empty() or candidate > swap_value):
			swap_ability = other
			swap_value = candidate
	if swap_ability.is_empty():
		return
	_assigned_stats[ability] = swap_value
	_assigned_stats[swap_ability] = current
	_render()


func _seed_value() -> int:
	var raw := _seed_input.text.strip_edges()
	return int(raw) if raw.is_valid_int() else -1


func _reset_state() -> void:
	_payload = {}
	_history_source = ""
	_selected_adapter_id = "fantasy_ember"
	_selected_profile_id = CreationCatalog.default_profile_id(_catalog)
	_selected_class_id = CreationCatalog.default_class_id(_catalog)
	_selected_alignment = "TN"
	_selected_skills = []
	_assigned_stats = {}
	_step = STEP_GENRE
	_busy = false
	_advanced_open = false
	_render()


func _focus_current_step() -> void:
	if not visible or not is_inside_tree():
		return
	match _step:
		STEP_GENRE:
			_focus_control(_name_input)
		STEP_QUESTION:
			if _answer_buttons != null and _answer_buttons.get_child_count() > 0:
				_focus_control(_answer_buttons.get_child(0))
		STEP_HISTORY, STEP_ROLL, STEP_BUILD:
			if _next_button != null and _next_button.visible:
				_focus_control(_next_button)
		STEP_DOSSIER:
			if _start_button != null and _start_button.visible:
				_focus_control(_start_button)


func _focus_control(control) -> void:
	if not (control is Control):
		return
	if not control.is_inside_tree() or not control.visible:
		return
	get_viewport().gui_release_focus()
	control.grab_focus()


func _clear_children(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()
