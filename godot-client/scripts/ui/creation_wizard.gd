extends PanelContainer
class_name CreationWizard


const STEP_GENRE := 0
const STEP_QUESTION := 1
const STEP_HISTORY := 2
const STEP_ROLL := 3
const STEP_BUILD := 4
const STEP_DOSSIER := 5

const STEP_KEYS := ["genre", "question", "history", "roll", "build", "dossier"]
const STEP_SUBTITLES := {
	STEP_GENRE: "Name the survivor and choose a starting discipline.",
	STEP_QUESTION: "Answer the world's first questions and set your moral pull.",
	STEP_HISTORY: "Watch the continent cohere into a living chronicle.",
	STEP_ROLL: "Assign the rolled pool into a body that can survive the ashlands.",
	STEP_BUILD: "Choose class, oath, and field proficiencies.",
	STEP_DOSSIER: "Review the finished dossier before the first day begins.",
}
const OPENING_PRESETS := {
	"ash_scout": {
		"label": "Ash Scout",
		"class_id": "ranger",
		"alignment": "TN",
		"skills": ["survival", "perception"],
	},
	"relic_hunter": {
		"label": "Relic Hunter",
		"class_id": "rogue",
		"alignment": "CN",
		"skills": ["investigation", "sleight_of_hand"],
	},
	"court_emissary": {
		"label": "Court Emissary",
		"class_id": "bard",
		"alignment": "NG",
		"skills": ["persuasion", "history"],
	},
	"ember_adept": {
		"label": "Ember Adept",
		"class_id": "mage",
		"alignment": "CG",
		"skills": ["arcana", "history"],
	},
}

signal canceled()
signal start_creation_requested(player_name: String, adapter_id: String, profile_id: String, world_seed: int)
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
var _selected_archetype_id := "ash_scout"
var _selected_class_id := "warrior"
var _selected_alignment := "TN"
var _selected_skills: Array[String] = []
var _assigned_stats: Dictionary = {}
var _busy := false
var _advanced_open := false
var _class_locked_by_player := false
var _alignment_locked_by_player := false
var _skills_locked_by_player := false

@onready var _root_vbox: VBoxContainer = $VBox
@onready var _chapter_row: HBoxContainer = $VBox/HeaderPanel/HeaderMargin/HeaderVBox/ChapterRail
@onready var _form_content: VBoxContainer = $VBox/CreationBody/FormPane/FormScroll/FormContent
@onready var _header_panel: PanelContainer = $VBox/HeaderPanel
@onready var _form_pane: PanelContainer = $VBox/CreationBody/FormPane
@onready var _cancel_button: Button = $VBox/ButtonRow/CancelButton
var _name_input: LineEdit
var _seed_input: LineEdit
var _advanced_section: VBoxContainer
var _advanced_toggle: Button
var _profile_hint: Label
var _genre_card_buttons: Dictionary = {}
var _sections: Dictionary = {}
@onready var _step_label: Label = $VBox/HeaderPanel/HeaderMargin/HeaderVBox/StepLabel
@onready var _step_subtitle: Label = $VBox/HeaderPanel/HeaderMargin/HeaderVBox/StepSubtitle
@onready var _preview_title: Label = $VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewHeading
@onready var _preview_text: RichTextLabel = $VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewText
@onready var _preview_meta: RichTextLabel = $VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewMeta
@onready var _preview_footer: RichTextLabel = $VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox/PreviewFooter
var _question_progress: Label
var _question_prompt: RichTextLabel
var _answer_buttons: VBoxContainer
var _history_text: RichTextLabel
var _history_timer: Timer
var _history_source := ""
var _history_timeline_data: Array = []
var _history_visible_events := 0
var _roll_pool_label: Label
var _saved_roll_label: Label
var _stat_rows: VBoxContainer
var _silhouette: Control
var _class_grid: GridContainer
var _alignment_grid: GridContainer
var _skill_grid: GridContainer
var _skill_budget_label: Label
var _dossier_text: RichTextLabel
var _dossier_identity: RichTextLabel
var _dossier_world: RichTextLabel
var _dossier_history: RichTextLabel
var _dossier_stats_grid: GridContainer
@onready var _preview_pane: PanelContainer = $VBox/CreationBody/PreviewPane
var _chapter_buttons: Array[Button] = []
@onready var _back_button: Button = $VBox/ButtonRow/BackButton
@onready var _next_button: Button = $VBox/ButtonRow/NextButton
@onready var _start_button: Button = $VBox/ButtonRow/StartButton


func _ready() -> void:
	visible = false
	anchors_preset = Control.PRESET_FULL_RECT
	offset_left = 34.0
	offset_top = 28.0
	offset_right = -34.0
	offset_bottom = -28.0
	_apply_shell_styling()
	_build_dynamic_sections()
	_wire_footer_actions()
	_reset_state()


func open(player_name: String, adapter_id: String, profile_id: String) -> void:
	visible = true
	_selected_adapter_id = adapter_id if not adapter_id.is_empty() else "fantasy_ember"
	_selected_profile_id = profile_id if not profile_id.is_empty() else "standard"
	_name_input.text = player_name
	_seed_input.text = ""
	_payload = {}
	_step = STEP_GENRE
	_class_locked_by_player = false
	_alignment_locked_by_player = false
	_skills_locked_by_player = false
	_apply_opening_preset(_selected_archetype_id, false)
	_render()


func close() -> void:
	visible = false
	_reset_state()


func set_catalog(catalog: Dictionary) -> void:
	_catalog = catalog.duplicate(true)
	_selected_profile_id = CreationCatalog.default_profile_id(_catalog)
	if _payload.is_empty():
		_apply_opening_preset(_selected_archetype_id, false)
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
	for button in _chapter_buttons:
		button.disabled = busy


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
		button.pressed.emit()
		return true
	return false


func _apply_shell_styling() -> void:
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = Color(0.08, 0.07, 0.10, 0.97)
	panel_style.border_color = Color(0.46, 0.32, 0.18, 0.94)
	panel_style.set_border_width_all(1)
	panel_style.set_corner_radius_all(18)
	panel_style.shadow_color = Color(0.0, 0.0, 0.0, 0.4)
	panel_style.shadow_size = 10
	add_theme_stylebox_override("panel", panel_style)
	if _root_vbox != null:
		_root_vbox.add_theme_constant_override("separation", 16)
	if _header_panel != null:
		_header_panel.add_theme_stylebox_override("panel", _card_style(Color(0.12, 0.10, 0.14, 0.98), 16))
	var header_margin: MarginContainer = $VBox/HeaderPanel/HeaderMargin
	if header_margin != null:
		header_margin.add_theme_constant_override("margin_left", 18)
		header_margin.add_theme_constant_override("margin_top", 16)
		header_margin.add_theme_constant_override("margin_right", 18)
		header_margin.add_theme_constant_override("margin_bottom", 16)
	var header_vbox: VBoxContainer = $VBox/HeaderPanel/HeaderMargin/HeaderVBox
	if header_vbox != null:
		header_vbox.add_theme_constant_override("separation", 10)
	var eyebrow: Label = $VBox/HeaderPanel/HeaderMargin/HeaderVBox/EyebrowLabel
	if eyebrow != null:
		eyebrow.add_theme_font_size_override("font_size", 14)
		eyebrow.add_theme_color_override("font_color", Color(0.80, 0.66, 0.39))
	var title: Label = $VBox/HeaderPanel/HeaderMargin/HeaderVBox/TitleLabel
	if title != null:
		title.add_theme_font_size_override("font_size", 34)
	if _step_label != null:
		_step_label.add_theme_font_size_override("font_size", 24)
	if _step_subtitle != null:
		_step_subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_step_subtitle.add_theme_color_override("font_color", Color(0.72, 0.68, 0.61))
	if _chapter_row != null:
		_chapter_row.add_theme_constant_override("separation", 8)
	var body: HSplitContainer = $VBox/CreationBody
	if body != null:
		body.split_offset = 420
	if _preview_pane != null:
		_preview_pane.add_theme_stylebox_override("panel", _card_style(Color(0.12, 0.09, 0.10, 0.98), 18))
	_preview_pane.custom_minimum_size = Vector2(360, 0)
	var preview_margin: MarginContainer = $VBox/CreationBody/PreviewPane/PreviewMargin
	if preview_margin != null:
		preview_margin.add_theme_constant_override("margin_left", 18)
		preview_margin.add_theme_constant_override("margin_top", 18)
		preview_margin.add_theme_constant_override("margin_right", 18)
		preview_margin.add_theme_constant_override("margin_bottom", 18)
	var preview_vbox: VBoxContainer = $VBox/CreationBody/PreviewPane/PreviewMargin/PreviewVBox
	if preview_vbox != null:
		preview_vbox.add_theme_constant_override("separation", 12)
	if _form_pane != null:
		_form_pane.add_theme_stylebox_override("panel", _card_style(Color(0.11, 0.10, 0.13, 0.98), 18))
	var form_scroll: ScrollContainer = $VBox/CreationBody/FormPane/FormScroll
	if form_scroll != null:
		form_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		form_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	if _form_content != null:
		_form_content.add_theme_constant_override("separation", 16)
	var footer: HBoxContainer = $VBox/ButtonRow
	if footer != null:
		footer.alignment = BoxContainer.ALIGNMENT_END
		footer.add_theme_constant_override("separation", 10)
	if _back_button != null:
		_back_button.custom_minimum_size = Vector2(140, 46)
	if _next_button != null:
		_next_button.custom_minimum_size = Vector2(180, 46)
	if _start_button != null:
		_start_button.custom_minimum_size = Vector2(200, 46)
	if _cancel_button != null:
		_cancel_button.custom_minimum_size = Vector2(160, 46)


func _build_dynamic_sections() -> void:
	if _form_content == null or not _sections.is_empty():
		return
	for step_index in range(STEP_KEYS.size()):
		var chapter_button := Button.new()
		chapter_button.name = "ChapterChip%d" % step_index
		chapter_button.text = "%d. %s" % [step_index + 1, CreationWizardState.step_name(step_index)]
		chapter_button.custom_minimum_size = Vector2(0, 40)
		chapter_button.focus_mode = Control.FOCUS_NONE
		chapter_button.pressed.connect(_on_chapter_pressed.bind(step_index))
		_chapter_row.add_child(chapter_button)
		_chapter_buttons.append(chapter_button)

	var genre_refs := CreationStepGenreQuestion.build_genre_section()
	_name_input = genre_refs.name_input
	_seed_input = genre_refs.seed_input
	_advanced_section = genre_refs.advanced_section
	_advanced_toggle = genre_refs.advanced_toggle
	_profile_hint = genre_refs.profile_hint
	_genre_card_buttons = genre_refs.genre_cards
	_advanced_toggle.pressed.connect(func() -> void:
		_advanced_open = not _advanced_open
		CreationStepGenreQuestion.sync_advanced_section(self)
	)
	for preset_id in _genre_card_buttons.keys():
		var card_button: Button = _genre_card_buttons[preset_id]
		card_button.pressed.connect(_on_genre_card_pressed.bind(String(preset_id)))
	_sections["genre"] = genre_refs.root

	var question_refs := CreationStepGenreQuestion.build_question_section()
	_question_progress = question_refs.question_progress
	_question_prompt = question_refs.question_prompt
	_answer_buttons = question_refs.answer_buttons
	_sections["question"] = question_refs.root

	var history_refs := CreationStepHistoryRoll.build_history_section(self)
	_history_text = history_refs.history_text
	_history_timer = history_refs.history_timer
	_sections["history"] = history_refs.root

	var roll_refs := CreationStepHistoryRoll.build_roll_section(self)
	_roll_pool_label = roll_refs.roll_pool_label
	_saved_roll_label = roll_refs.saved_roll_label
	_stat_rows = roll_refs.stat_rows
	_silhouette = roll_refs.silhouette
	_sections["roll"] = roll_refs.root

	var build_refs := CreationStepBuildDossier.build_build_section()
	_class_grid = build_refs.class_grid
	_alignment_grid = build_refs.alignment_grid
	_skill_grid = build_refs.skill_grid
	_skill_budget_label = build_refs.skill_budget_label
	_sections["build"] = build_refs.root

	var dossier_refs := CreationStepBuildDossier.build_dossier_section()
	_dossier_text = dossier_refs.dossier_text
	_dossier_identity = dossier_refs.dossier_identity
	_dossier_world = dossier_refs.dossier_world
	_dossier_history = dossier_refs.dossier_history
	_dossier_stats_grid = dossier_refs.dossier_stats_grid
	_sections["dossier"] = dossier_refs.root

	for section in _sections.values():
		_form_content.add_child(section)


func _wire_footer_actions() -> void:
	if _back_button != null and not _back_button.pressed.is_connected(_on_back_pressed):
		_back_button.pressed.connect(_on_back_pressed)
	if _next_button != null and not _next_button.pressed.is_connected(_on_next_pressed):
		_next_button.pressed.connect(_on_next_pressed)
	if _start_button != null and not _start_button.pressed.is_connected(_emit_finalize):
		_start_button.pressed.connect(_emit_finalize)
	if _cancel_button != null and not _cancel_button.pressed.is_connected(_emit_cancel):
		_cancel_button.pressed.connect(_emit_cancel)


func _emit_cancel() -> void:
	canceled.emit()


func _render() -> void:
	for key in _sections.keys():
		var control: Control = _sections[key]
		control.visible = key == STEP_KEYS[_step]
	_step_label.text = CreationWizardState.step_name(_step)
	_step_subtitle.text = STEP_SUBTITLES.get(_step, "")
	_sync_chapter_rail()
	CreationStepGenreQuestion.sync_advanced_section(self)
	CreationStepGenreQuestion.render_genre_cards(self)
	CreationStepGenreQuestion.render_question(self)
	CreationStepHistoryRoll.render_history(self)
	CreationStepHistoryRoll.render_roll(self)
	CreationStepBuildDossier.render_build(self)
	CreationStepBuildDossier.render_dossier(self)
	if _preview_pane.visible:
		CreationStepBuildDossier.render_preview(self)
	_render_preview_footer()
	CreationStepBuildDossier.sync_footer(self)
	call_deferred("_focus_current_step")


func _sync_chapter_rail() -> void:
	for index in range(_chapter_buttons.size()):
		var button := _chapter_buttons[index]
		button.disabled = _busy or index > _step
		button.add_theme_stylebox_override("normal", _chapter_style(index == _step, index < _step))
		button.add_theme_stylebox_override("hover", _chapter_style(true, index < _step))
		button.add_theme_stylebox_override("pressed", _chapter_style(true, index < _step))


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


func _on_chapter_pressed(target_step: int) -> void:
	if target_step <= _step and not _busy:
		go_to_step(target_step)


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


func _render_preview_footer() -> void:
	var archetype: Dictionary = OPENING_PRESETS.get(_selected_archetype_id, {})
	var class_label := str(archetype.get("label", CreationCatalog.humanize_id(_selected_class_id)))
	var skill_line := ", ".join(_selected_skills) if not _selected_skills.is_empty() else "No field proficiencies locked yet."
	_preview_footer.text = (
		"[b]Opening discipline[/b] %s\n[b]Chosen class[/b] %s\n[b]Alignment[/b] %s\n[b]Field proficiencies[/b] %s"
	) % [class_label, CreationCatalog.humanize_id(_selected_class_id), _selected_alignment, skill_line]


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


func _on_genre_card_pressed(preset_id: String) -> void:
	_apply_opening_preset(preset_id, true)
	_render()


func _apply_opening_preset(preset_id: String, user_initiated: bool) -> void:
	var normalized := preset_id.strip_edges()
	if not OPENING_PRESETS.has(normalized):
		return
	_selected_archetype_id = normalized
	var preset: Dictionary = OPENING_PRESETS[normalized]
	_selected_class_id = str(preset.get("class_id", _selected_class_id))
	_selected_alignment = str(preset.get("alignment", _selected_alignment))
	_selected_skills = CreationWizardState.string_array(preset.get("skills", []))
	if user_initiated:
		_class_locked_by_player = true
		_alignment_locked_by_player = true
		_skills_locked_by_player = true
	if not _payload.is_empty():
		_assigned_stats = CreationCatalog.suggested_stats_for(
			_catalog,
			_selected_class_id,
			_payload.get("current_roll", []),
		)


func _reset_state() -> void:
	_payload = {}
	_history_source = ""
	_history_timeline_data = []
	_history_visible_events = 0
	_selected_adapter_id = "fantasy_ember"
	_selected_profile_id = CreationCatalog.default_profile_id(_catalog)
	_selected_archetype_id = "ash_scout"
	_selected_class_id = CreationCatalog.default_class_id(_catalog)
	_selected_alignment = "TN"
	_selected_skills = []
	_assigned_stats = {}
	_step = STEP_GENRE
	_busy = false
	_advanced_open = false
	_class_locked_by_player = false
	_alignment_locked_by_player = false
	_skills_locked_by_player = false
	_apply_opening_preset(_selected_archetype_id, false)
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


func emit_answer(question_id: String, answer_id: String) -> void:
	answer_requested.emit(question_id, answer_id)


func emit_reroll() -> void:
	reroll_requested.emit()


func emit_save_roll() -> void:
	save_roll_requested.emit()


func emit_swap_roll() -> void:
	swap_roll_requested.emit()


func _clear_children(node: Node) -> void:
	for child in node.get_children():
		node.remove_child(child)
		child.queue_free()


func _card_style(bg: Color, radius: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.border_color = Color(0.42, 0.31, 0.18, 0.94)
	style.set_border_width_all(1)
	style.set_corner_radius_all(radius)
	return style


func _chapter_style(active: bool, completed: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.28, 0.18, 0.10, 0.98) if active else (Color(0.18, 0.14, 0.12, 0.98) if completed else Color(0.11, 0.10, 0.13, 0.98))
	style.border_color = Color(0.82, 0.66, 0.38, 1.0) if active else Color(0.30, 0.26, 0.20, 0.96)
	style.set_border_width_all(1)
	style.set_corner_radius_all(10)
	style.content_margin_left = 12
	style.content_margin_top = 8
	style.content_margin_right = 12
	style.content_margin_bottom = 8
	return style
