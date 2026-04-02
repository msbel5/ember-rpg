extends RefCounted
class_name CreationStepGenreQuestion



static func build_genre_section() -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "IdentitySection"
	section.add_theme_constant_override("separation", 14)
	var heading := Label.new()
	heading.name = "IdentityLabel"
	heading.text = "Name your commander and optionally pin a deterministic seed."
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	section.add_child(heading)

	var name_input := LineEdit.new()
	name_input.name = "NameInput"
	name_input.placeholder_text = "Commander name"
	section.add_child(name_input)

	var advanced_toggle := Button.new()
	advanced_toggle.name = "AdvancedToggle"
	advanced_toggle.text = "Show Advanced Settings"
	advanced_toggle.tooltip_text = "Reveal deterministic world seed and profile notes."
	section.add_child(advanced_toggle)

	var advanced_section := VBoxContainer.new()
	advanced_section.name = "AdvancedSection"
	advanced_section.visible = false
	advanced_section.add_theme_constant_override("separation", 10)
	section.add_child(advanced_section)

	var profile_hint := Label.new()
	profile_hint.name = "ProfileHint"
	profile_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	advanced_section.add_child(profile_hint)

	var seed_input := LineEdit.new()
	seed_input.name = "SeedInput"
	seed_input.placeholder_text = "Optional world seed"
	advanced_section.add_child(seed_input)

	return {
		"root": section,
		"name_input": name_input,
		"seed_input": seed_input,
		"advanced_section": advanced_section,
		"advanced_toggle": advanced_toggle,
		"profile_hint": profile_hint,
	}


static func build_question_section() -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "QuestionSection"
	section.add_theme_constant_override("separation", 12)

	var question_progress := Label.new()
	question_progress.name = "QuestionProgress"
	section.add_child(question_progress)

	var atmosphere := Label.new()
	atmosphere.name = "AtmosphereLabel"
	atmosphere.text = "The world listens..."
	section.add_child(atmosphere)

	var question_prompt := RichTextLabel.new()
	question_prompt.name = "QuestionPrompt"
	question_prompt.bbcode_enabled = true
	question_prompt.fit_content = true
	question_prompt.scroll_active = false
	question_prompt.custom_minimum_size = Vector2(0, 96)
	section.add_child(question_prompt)

	var answer_buttons := VBoxContainer.new()
	answer_buttons.name = "AnswerButtons"
	answer_buttons.add_theme_constant_override("separation", 10)
	section.add_child(answer_buttons)

	return {
		"root": section,
		"question_progress": question_progress,
		"question_prompt": question_prompt,
		"answer_buttons": answer_buttons,
	}


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
				owner.emit_answer(str(question.get("id", "")), str(answer.get("id", "")))
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
