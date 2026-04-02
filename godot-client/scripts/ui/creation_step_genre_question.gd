extends RefCounted
class_name CreationStepGenreQuestion



static func build_genre_section(owner) -> Control:
	var section := VBoxContainer.new()
	section.name = "IdentitySection"
	section.add_theme_constant_override("separation", 14)
	var heading := Label.new()
	heading.name = "IdentityLabel"
	heading.text = "Choose your world, name your commander, and optionally pin a deterministic seed."
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	section.add_child(heading)

	owner._name_input = LineEdit.new()
	owner._name_input.name = "NameInput"
	owner._name_input.placeholder_text = "Commander name"
	section.add_child(owner._name_input)

	var cards := HBoxContainer.new()
	cards.name = "GenreCards"
	cards.add_theme_constant_override("separation", 18)
	section.add_child(cards)
	cards.add_child(_genre_card(owner, "FantasyCard", "Fantasy Ember", "Shape a realm of magic and steel", Color(0.78, 0.55, 0.25), "fantasy_ember"))
	cards.add_child(_genre_card(owner, "SciFiCard", "Sci-Fi Frontier", "Chart the frontier of a dying galaxy", Color(0.27, 0.76, 0.86), "scifi_frontier"))

	owner._advanced_toggle = Button.new()
	owner._advanced_toggle.name = "AdvancedToggle"
	owner._advanced_toggle.text = "Show Advanced Settings"
	owner._advanced_toggle.tooltip_text = "Reveal deterministic world seed and profile notes."
	owner._advanced_toggle.pressed.connect(func() -> void:
		owner._advanced_open = not owner._advanced_open
		sync_advanced_section(owner)
	)
	section.add_child(owner._advanced_toggle)

	owner._advanced_section = VBoxContainer.new()
	owner._advanced_section.name = "AdvancedSection"
	owner._advanced_section.visible = false
	owner._advanced_section.add_theme_constant_override("separation", 10)
	section.add_child(owner._advanced_section)

	owner._profile_hint = Label.new()
	owner._profile_hint.name = "ProfileHint"
	owner._profile_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	owner._advanced_section.add_child(owner._profile_hint)

	owner._seed_input = LineEdit.new()
	owner._seed_input.name = "SeedInput"
	owner._seed_input.placeholder_text = "Optional world seed"
	owner._advanced_section.add_child(owner._seed_input)
	return section


static func build_question_section(owner) -> Control:
	var section := VBoxContainer.new()
	section.name = "QuestionSection"
	section.add_theme_constant_override("separation", 12)

	owner._question_progress = Label.new()
	owner._question_progress.name = "QuestionProgress"
	section.add_child(owner._question_progress)

	var atmosphere := Label.new()
	atmosphere.name = "AtmosphereLabel"
	atmosphere.text = "The world listens..."
	section.add_child(atmosphere)

	owner._question_prompt = RichTextLabel.new()
	owner._question_prompt.name = "QuestionPrompt"
	owner._question_prompt.bbcode_enabled = true
	owner._question_prompt.fit_content = true
	owner._question_prompt.scroll_active = false
	owner._question_prompt.custom_minimum_size = Vector2(0, 96)
	section.add_child(owner._question_prompt)

	owner._answer_buttons = VBoxContainer.new()
	owner._answer_buttons.name = "AnswerButtons"
	owner._answer_buttons.add_theme_constant_override("separation", 10)
	section.add_child(owner._answer_buttons)
	return section


static func render_question(owner) -> void:
	var question: Dictionary = owner._current_question()
	if question.is_empty():
		return
	var questions: Array = owner._payload.get("questions", [])
	var index: int = int(owner._current_question_index()) + 1
	owner._question_progress.text = "Question %d of %d" % [index, questions.size()]
	owner._question_prompt.text = "[b]%s[/b]" % str(question.get("text", ""))
	owner._clear_children(owner._answer_buttons)

	var answer_index := 0
	for answer in question.get("answers", []):
		var button := Button.new()
		button.name = "AnswerButton%d" % answer_index
		button.text = str(answer.get("text", "Answer"))
		button.custom_minimum_size = Vector2(0, 68)
		button.disabled = owner._busy
		button.tooltip_text = str(answer.get("description", button.text))
		button.pressed.connect(func() -> void:
			if not owner._busy:
				owner.answer_requested.emit(str(question.get("id", "")), str(answer.get("id", "")))
		)
		owner._answer_buttons.add_child(button)
		answer_index += 1


static func sync_advanced_section(owner) -> void:
	if owner._advanced_section == null:
		return
	owner._advanced_section.visible = owner._advanced_open
	if owner._advanced_toggle != null:
		owner._advanced_toggle.text = "Hide Advanced Settings" if owner._advanced_open else "Show Advanced Settings"
	if owner._profile_hint != null:
		owner._profile_hint.text = "World profile: %s" % CreationCatalog.humanize_id(owner._selected_profile_id)


static func _genre_card(owner, node_name: String, title: String, subtitle: String, accent: Color, adapter_id: String) -> Button:
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
		owner._selected_adapter_id = adapter_id
		owner._render()
	)
	return button


static func _card_style(bg: Color, border: Color) -> StyleBoxFlat:
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
