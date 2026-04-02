extends PanelContainer
class_name CreationWizard

const CreationCatalog = preload("res://scripts/ui/creation_catalog.gd")

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
var _advanced_open := false


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
	_sync_build_defaults()
	if _current_question().is_empty():
		_step = STEP_HISTORY if _step < STEP_HISTORY else _step
		_begin_history_reveal()
	else:
		_step = STEP_QUESTION
	_render()


func set_busy(busy: bool) -> void:
	_busy = busy
	_sync_footer()
	for child in _answer_buttons.get_children():
		if child is Button:
			child.disabled = busy


func current_step() -> int:
	return _step


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

	_sections["genre"] = _build_genre_section()
	_sections["question"] = _build_question_section()
	_sections["history"] = _build_history_section()
	_sections["roll"] = _build_roll_section()
	_sections["build"] = _build_build_section()
	_sections["dossier"] = _build_dossier_section()
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
	cancel_button.pressed.connect(func() -> void:
		canceled.emit()
	)
	footer.add_child(cancel_button)


func _build_genre_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "IdentitySection"
	section.add_theme_constant_override("separation", 14)
	var heading := Label.new()
	heading.name = "IdentityLabel"
	heading.text = "Choose your world, name your commander, and optionally pin a deterministic seed."
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	section.add_child(heading)
	_name_input = LineEdit.new()
	_name_input.name = "NameInput"
	_name_input.placeholder_text = "Commander name"
	section.add_child(_name_input)
	var cards := HBoxContainer.new()
	cards.name = "GenreCards"
	cards.add_theme_constant_override("separation", 18)
	section.add_child(cards)
	cards.add_child(_genre_card("FantasyCard", "Fantasy Ember", "Shape a realm of magic and steel", Color(0.78, 0.55, 0.25), "fantasy_ember"))
	cards.add_child(_genre_card("SciFiCard", "Sci-Fi Frontier", "Chart the frontier of a dying galaxy", Color(0.27, 0.76, 0.86), "scifi_frontier"))
	_advanced_toggle = Button.new()
	_advanced_toggle.name = "AdvancedToggle"
	_advanced_toggle.text = "Show Advanced Settings"
	_advanced_toggle.tooltip_text = "Reveal deterministic world seed and profile notes."
	_advanced_toggle.pressed.connect(func() -> void:
		_advanced_open = not _advanced_open
		_sync_advanced_section()
	)
	section.add_child(_advanced_toggle)
	_advanced_section = VBoxContainer.new()
	_advanced_section.name = "AdvancedSection"
	_advanced_section.visible = false
	_advanced_section.add_theme_constant_override("separation", 10)
	section.add_child(_advanced_section)
	_profile_hint = Label.new()
	_profile_hint.name = "ProfileHint"
	_profile_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_advanced_section.add_child(_profile_hint)
	_seed_input = LineEdit.new()
	_seed_input.name = "SeedInput"
	_seed_input.placeholder_text = "Optional world seed"
	_advanced_section.add_child(_seed_input)
	return section


func _build_question_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "QuestionSection"
	section.add_theme_constant_override("separation", 12)
	_question_progress = Label.new()
	_question_progress.name = "QuestionProgress"
	section.add_child(_question_progress)
	var atmosphere := Label.new()
	atmosphere.name = "AtmosphereLabel"
	atmosphere.text = "The world listens..."
	section.add_child(atmosphere)
	_question_prompt = RichTextLabel.new()
	_question_prompt.name = "QuestionPrompt"
	_question_prompt.bbcode_enabled = true
	_question_prompt.fit_content = true
	_question_prompt.scroll_active = false
	_question_prompt.custom_minimum_size = Vector2(0, 96)
	section.add_child(_question_prompt)
	_answer_buttons = VBoxContainer.new()
	_answer_buttons.name = "AnswerButtons"
	_answer_buttons.add_theme_constant_override("separation", 10)
	section.add_child(_answer_buttons)
	return section


func _build_history_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "HistorySection"
	var prompt := Label.new()
	prompt.text = "World history settles into place..."
	section.add_child(prompt)
	_history_text = RichTextLabel.new()
	_history_text.name = "HistoryText"
	_history_text.fit_content = false
	_history_text.scroll_active = true
	_history_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_history_text.custom_minimum_size = Vector2(0, 360)
	section.add_child(_history_text)
	_history_timer = Timer.new()
	_history_timer.wait_time = 0.033
	_history_timer.timeout.connect(_on_history_tick)
	section.add_child(_history_timer)
	return section


func _build_roll_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "RollSection"
	_roll_pool_label = Label.new()
	section.add_child(_roll_pool_label)
	_saved_roll_label = Label.new()
	section.add_child(_saved_roll_label)
	_silhouette = Control.new()
	_silhouette.name = "SilhouetteBoard"
	_silhouette.custom_minimum_size = Vector2(0, 220)
	section.add_child(_silhouette)
	_stat_rows = VBoxContainer.new()
	_stat_rows.name = "StatRows"
	section.add_child(_stat_rows)
	var button_row := HBoxContainer.new()
	button_row.add_theme_constant_override("separation", 10)
	section.add_child(button_row)
	for pair in [["RerollButton", "Reroll", func(): reroll_requested.emit()], ["SaveRollButton", "Lock Pool", func(): save_roll_requested.emit()], ["SwapRollButton", "Swap Pool", func(): swap_roll_requested.emit()]]:
		var button := Button.new()
		button.name = pair[0]
		button.text = pair[1]
		button.pressed.connect(pair[2])
		button_row.add_child(button)
	return section


func _build_build_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "BuildSection"
	_class_grid = GridContainer.new()
	_class_grid.name = "ClassGrid"
	_class_grid.columns = 3
	section.add_child(_class_grid)
	_alignment_grid = GridContainer.new()
	_alignment_grid.name = "AlignmentGrid"
	_alignment_grid.columns = 3
	section.add_child(_alignment_grid)
	_skill_budget_label = Label.new()
	section.add_child(_skill_budget_label)
	_skill_grid = GridContainer.new()
	_skill_grid.name = "SkillGrid"
	_skill_grid.columns = 4
	section.add_child(_skill_grid)
	return section


func _build_dossier_section() -> Control:
	var section := VBoxContainer.new()
	section.name = "DossierSection"
	_dossier_text = RichTextLabel.new()
	_dossier_text.name = "DossierText"
	_dossier_text.bbcode_enabled = true
	_dossier_text.fit_content = false
	_dossier_text.scroll_active = true
	_dossier_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	section.add_child(_dossier_text)
	return section


func _genre_card(node_name: String, title: String, subtitle: String, accent: Color, adapter_id: String) -> Button:
	var button := Button.new()
	button.name = node_name
	button.text = "%s\n%s" % [title, subtitle]
	button.custom_minimum_size = Vector2(400, 260)
	button.alignment = HORIZONTAL_ALIGNMENT_CENTER
	button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	button.add_theme_color_override("font_color", Color(0.95, 0.93, 0.88))
	button.add_theme_stylebox_override("normal", _card_style(Color(0.12, 0.10, 0.14), accent))
	button.add_theme_stylebox_override("hover", _card_style(Color(0.18, 0.14, 0.18), accent.lightened(0.2)))
	button.add_theme_stylebox_override("pressed", _card_style(Color(0.24, 0.16, 0.14), accent))
	button.tooltip_text = subtitle
	button.pressed.connect(func() -> void:
		_selected_adapter_id = adapter_id
		_render()
	)
	return button


func _render() -> void:
	for key in _sections.keys():
		var control: Control = _sections[key]
		control.visible = key == ["genre", "question", "history", "roll", "build", "dossier"][_step]
	_step_label.text = ["Step 0: Genre", "Step 1: Questions", "Step 2: History", "Step 3: Rolling", "Step 4: Build", "Step 5: Dossier"][_step]
	_sync_advanced_section()
	_render_question()
	_render_history()
	_render_roll()
	_render_build()
	_render_dossier()
	_render_preview()
	_sync_footer()
	_focus_current_step()
	call_deferred("_focus_current_step")


func _render_question() -> void:
	if _current_question().is_empty():
		return
	var questions: Array = _payload.get("questions", [])
	var index := _current_question_index() + 1
	_question_progress.text = "Question %d of %d" % [index, questions.size()]
	_question_prompt.text = "[b]%s[/b]" % str(_current_question().get("text", ""))
	_clear_children(_answer_buttons)
	var answer_index := 0
	for answer in _current_question().get("answers", []):
		var button := Button.new()
		button.name = "AnswerButton%d" % answer_index
		button.text = str(answer.get("text", "Answer"))
		button.custom_minimum_size = Vector2(0, 68)
		button.disabled = _busy
		button.pressed.connect(func() -> void:
			if not _busy:
				answer_requested.emit(str(_current_question().get("id", "")), str(answer.get("id", "")))
		)
		_answer_buttons.add_child(button)
		answer_index += 1


func _render_history() -> void:
	if _step != STEP_HISTORY:
		_history_timer.stop()
		return
	if _history_source.is_empty():
		_begin_history_reveal()


func _render_roll() -> void:
	_roll_pool_label.text = "Active Roll: %s" % CreationCatalog.roll_text(_payload.get("current_roll", []))
	_saved_roll_label.text = "Saved Roll: %s" % CreationCatalog.roll_text(_payload.get("saved_roll", []))
	_clear_children(_stat_rows)
	_clear_children(_silhouette)
	var positions = {"MND": Vector2(250, 18), "INS": Vector2(120, 62), "PRE": Vector2(380, 62), "END": Vector2(250, 108), "MIG": Vector2(250, 152), "AGI": Vector2(250, 196)}
	for ability in CreationCatalog.ability_order(_catalog):
		var label := Label.new()
		label.position = positions.get(str(ability), Vector2.ZERO)
		var value = int(_assigned_stats.get(ability, 10))
		label.text = "%s: %d (%+d)" % [ability, value, CreationCatalog.modifier(value)]
		_silhouette.add_child(label)
		_stat_rows.add_child(_stat_row(str(ability), value))


func _render_build() -> void:
	_rebuild_class_grid()
	_rebuild_alignment_grid()
	_rebuild_skill_grid()


func _render_dossier() -> void:
	var genesis: Dictionary = _payload.get("campaign_genesis", {})
	var stats: Array[String] = []
	for ability in CreationCatalog.ability_order(_catalog):
		stats.append("%s %d" % [ability, int(_assigned_stats.get(ability, 10))])
	_dossier_text.text = "[b]World Premise[/b]\n%s\n\n[b]Starting Pressure[/b]\n%s\n\n[b]History[/b]\n%s\n\n[b]Build[/b]\nClass: %s\nAlignment: %s\nSkills: %s\nStats: %s" % [
		str(genesis.get("world_premise", "A frontier waits.")),
		str(genesis.get("starting_pressure", "")),
		"\n".join(genesis.get("history_events", [])),
		_selected_class_id.capitalize(),
		_selected_alignment,
		", ".join(_selected_skills),
		" | ".join(stats),
	]


func _render_preview() -> void:
	var genesis: Dictionary = _payload.get("campaign_genesis", {})
	_preview_title.text = ["Genre", "Question", "History", "Rolled Pool", "Build", "Dossier"][_step]
	_preview_text.text = "[b]World Premise[/b]\n%s\n\n[b]Starting Pressure[/b]\n%s" % [str(genesis.get("world_premise", "Shape the world.")), str(genesis.get("starting_pressure", ""))]
	_preview_meta.text = "[b]Recommended[/b] %s / %s\n[b]Quest Seeds[/b] %s" % [str(_payload.get("recommended_class", "warrior")).capitalize(), str(_payload.get("recommended_alignment", "TN")), ", ".join(_payload.get("recommended_skills", []))]


func _sync_footer() -> void:
	_back_button.visible = _step in [STEP_HISTORY, STEP_ROLL, STEP_BUILD, STEP_DOSSIER]
	_next_button.visible = _step != STEP_DOSSIER
	_start_button.visible = _step == STEP_DOSSIER
	_back_button.disabled = _busy
	_next_button.disabled = _busy
	_start_button.disabled = _busy


func _on_next_pressed() -> void:
	if _busy:
		return
	match _step:
		STEP_GENRE:
			var player_name = _name_input.text.strip_edges()
			if player_name.is_empty():
				return
			start_creation_requested.emit(player_name, _selected_adapter_id, _selected_profile_id, _seed_value())
		STEP_HISTORY:
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
	_render()


func _emit_finalize() -> void:
	finalize_requested.emit({
		"player_name": _name_input.text.strip_edges(),
		"adapter_id": _selected_adapter_id,
		"profile_id": _selected_profile_id,
		"player_class": _selected_class_id,
		"alignment": _selected_alignment,
		"skill_proficiencies": _selected_skills,
		"assigned_stats": _assigned_stats.duplicate(true),
	})


func go_to_step(step: int) -> void:
	_step = clamp(step, STEP_GENRE, STEP_DOSSIER)
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
	if _step != STEP_QUESTION:
		return false
	if index < 0 or index >= _answer_buttons.get_child_count():
		return false
	var button = _answer_buttons.get_child(index)
	if button is Button and not button.disabled:
		button.emit_signal("pressed")
		return true
	return false


func _current_question() -> Dictionary:
	for question in _payload.get("questions", []):
		var question_id = str(question.get("id", ""))
		if not _answer_map().has(question_id):
			return question
	return {}


func _current_question_index() -> int:
	var index := 0
	for question in _payload.get("questions", []):
		if str(question.get("id", "")) == str(_current_question().get("id", "")):
			return index
		index += 1
	return 0


func _answer_map() -> Dictionary:
	var result := {}
	for entry in _payload.get("answers", []):
		result[str(entry.get("question_id", ""))] = str(entry.get("answer_id", ""))
	return result


func _begin_history_reveal() -> void:
	var events = _payload.get("campaign_genesis", {}).get("history_events", [])
	_history_source = "\n".join(events)
	_history_text.text = _history_source
	_history_text.visible_characters = 0
	if not _history_source.is_empty():
		_history_timer.start()
	_render()


func _on_history_tick() -> void:
	_history_text.visible_characters += 1
	if _history_text.visible_characters >= _history_source.length():
		_history_timer.stop()


func _sync_build_defaults() -> void:
	_selected_class_id = str(_payload.get("recommended_class", CreationCatalog.default_class_id(_catalog)))
	_selected_alignment = str(_payload.get("recommended_alignment", "TN"))
	_selected_skills = _string_array(_payload.get("recommended_skills", []))
	_assigned_stats = CreationCatalog.suggested_stats_for(_catalog, _selected_class_id, _payload.get("current_roll", []))


func _rebuild_class_grid() -> void:
	_clear_children(_class_grid)
	for entry in CreationCatalog.class_entries(_catalog):
		var button := Button.new()
		button.name = "Class_%s" % str(entry.get("id", "class"))
		button.text = "%s\n%s" % [str(entry.get("label", entry.get("id", ""))), str(entry.get("description", ""))]
		button.custom_minimum_size = Vector2(0, 92)
		button.pressed.connect(func() -> void:
			_selected_class_id = str(entry.get("id", ""))
			_selected_skills = _string_array(entry.get("default_skills", []))
			_assigned_stats = CreationCatalog.suggested_stats_for(_catalog, _selected_class_id, _payload.get("current_roll", []))
			_render()
		)
		_class_grid.add_child(button)


func _rebuild_alignment_grid() -> void:
	_clear_children(_alignment_grid)
	for code in ["LG", "NG", "CG", "LN", "TN", "CN", "LE", "NE", "CE"]:
		var button := Button.new()
		button.name = "Alignment_%s" % code
		button.text = code
		button.custom_minimum_size = Vector2(0, 54)
		button.pressed.connect(func() -> void:
			_selected_alignment = code
			_render()
		)
		_alignment_grid.add_child(button)


func _rebuild_skill_grid() -> void:
	_clear_children(_skill_grid)
	var class_entry = CreationCatalog.class_entry(_catalog, _selected_class_id)
	var skill_pool: Array = class_entry.get("skill_pool", [])
	var budget = int(class_entry.get("skill_pick_count", 2))
	_skill_budget_label.text = "Skills %d/%d selected" % [_selected_skills.size(), budget]
	for raw_skill in skill_pool:
		var skill = str(raw_skill)
		var button := Button.new()
		button.name = "Skill_%s" % skill
		button.text = CreationCatalog.humanize_id(skill)
		button.toggle_mode = true
		button.button_pressed = _selected_skills.has(skill)
		button.toggled.connect(func(pressed: bool) -> void:
			if pressed and not _selected_skills.has(skill) and _selected_skills.size() < budget:
				_selected_skills.append(skill)
			elif not pressed:
				_selected_skills.erase(skill)
			_render()
		)
		_skill_grid.add_child(button)


func _stat_row(ability: String, value: int) -> Control:
	var row := HBoxContainer.new()
	var minus := Button.new()
	minus.text = "-"
	minus.pressed.connect(func() -> void: _shift_stat_value(ability, -1))
	row.add_child(minus)
	var label := Label.new()
	label.text = "%s: %d (%+d)" % [ability, value, CreationCatalog.modifier(value)]
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	var plus := Button.new()
	plus.text = "+"
	plus.pressed.connect(func() -> void: _shift_stat_value(ability, 1))
	row.add_child(plus)
	return row


func _shift_stat_value(ability: String, direction: int) -> void:
	var current = int(_assigned_stats.get(ability, 10))
	var swap_ability := ""
	var swap_value: int = current
	for other in CreationCatalog.ability_order(_catalog):
		if other == ability:
			continue
		var candidate = int(_assigned_stats.get(other, 10))
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
	var raw = _seed_input.text.strip_edges()
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


func _card_style(bg: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = border
	style.set_border_width_all(2)
	style.set_corner_radius_all(14)
	style.content_margin_left = 16
	style.content_margin_top = 16
	style.content_margin_right = 16
	style.content_margin_bottom = 16
	return style


func _sync_advanced_section() -> void:
	if _advanced_section == null:
		return
	_advanced_section.visible = _advanced_open
	if _advanced_toggle != null:
		_advanced_toggle.text = "Hide Advanced Settings" if _advanced_open else "Show Advanced Settings"
	if _profile_hint != null:
		_profile_hint.text = "World profile: %s" % CreationCatalog.humanize_id(_selected_profile_id)


func _focus_current_step() -> void:
	match _step:
		STEP_GENRE:
			if _name_input != null:
				get_viewport().gui_release_focus()
				_name_input.grab_focus()
				_name_input.call_deferred("grab_focus")
		STEP_QUESTION:
			if _answer_buttons.get_child_count() > 0:
				var button = _answer_buttons.get_child(0)
				if button is Button:
					get_viewport().gui_release_focus()
					button.grab_focus()
					button.call_deferred("grab_focus")
		STEP_HISTORY, STEP_ROLL, STEP_BUILD:
			if _next_button != null and _next_button.visible:
				get_viewport().gui_release_focus()
				_next_button.grab_focus()
				_next_button.call_deferred("grab_focus")
		STEP_DOSSIER:
			if _start_button != null and _start_button.visible:
				get_viewport().gui_release_focus()
				_start_button.grab_focus()
				_start_button.call_deferred("grab_focus")


func _string_array(values) -> Array[String]:
	var result: Array[String] = []
	if values is Array:
		for value in values:
			result.append(str(value))
	return result


func _clear_children(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()
