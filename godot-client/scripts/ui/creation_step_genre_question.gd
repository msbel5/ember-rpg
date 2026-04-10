extends RefCounted
class_name CreationStepGenreQuestion

const OPENING_ARCHETYPES := {
	"ash_scout": {
		"title": "Ash Scout",
		"subtitle": "Ranger line · travel-first · balanced oath",
		"body": "Tracks roads, reads danger, and survives with little support.",
	},
	"relic_hunter": {
		"title": "Relic Hunter",
		"subtitle": "Rogue line · salvage · flexible morality",
		"body": "Finds hidden routes, pries secrets loose, and profits from old ruins.",
	},
	"court_emissary": {
		"title": "Court Emissary",
		"subtitle": "Bard line · diplomacy · rumor authority",
		"body": "Talks through danger, wins leverage, and reads faction pressure early.",
	},
	"ember_adept": {
		"title": "Ember Adept",
		"subtitle": "Mage line · arcana · risk-heavy openings",
		"body": "Trades raw resilience for powerful ritual options and lore leverage.",
	},
}


static func build_genre_section() -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "IdentitySection"
	section.add_theme_constant_override("separation", 16)

	var intro_panel := PanelContainer.new()
	intro_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.14, 0.11, 0.10, 0.98)))
	section.add_child(intro_panel)

	var intro_margin := MarginContainer.new()
	intro_margin.add_theme_constant_override("margin_left", 14)
	intro_margin.add_theme_constant_override("margin_top", 14)
	intro_margin.add_theme_constant_override("margin_right", 14)
	intro_margin.add_theme_constant_override("margin_bottom", 14)
	intro_panel.add_child(intro_margin)

	var intro_vbox := VBoxContainer.new()
	intro_vbox.add_theme_constant_override("separation", 8)
	intro_margin.add_child(intro_vbox)

	var heading := Label.new()
	heading.name = "IdentityLabel"
	heading.text = "Who walks into the ashlands first?"
	heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	heading.add_theme_font_size_override("font_size", 24)
	intro_vbox.add_child(heading)

	var intro_copy := Label.new()
	intro_copy.text = "Name your survivor, then choose an opening discipline. You can still refine class, oath, and skills later."
	intro_copy.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	intro_copy.add_theme_color_override("font_color", Color(0.72, 0.68, 0.62))
	intro_vbox.add_child(intro_copy)

	var name_panel := PanelContainer.new()
	name_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.12, 0.10, 0.13, 0.98)))
	section.add_child(name_panel)

	var name_margin := MarginContainer.new()
	name_margin.add_theme_constant_override("margin_left", 14)
	name_margin.add_theme_constant_override("margin_top", 14)
	name_margin.add_theme_constant_override("margin_right", 14)
	name_margin.add_theme_constant_override("margin_bottom", 14)
	name_panel.add_child(name_margin)

	var name_vbox := VBoxContainer.new()
	name_vbox.add_theme_constant_override("separation", 10)
	name_margin.add_child(name_vbox)

	var name_label := Label.new()
	name_label.text = "Chronicle name"
	name_label.add_theme_color_override("font_color", Color(0.80, 0.66, 0.39))
	name_vbox.add_child(name_label)

	var name_input := LineEdit.new()
	name_input.name = "NameInput"
	name_input.placeholder_text = "Enter the name carried into the first scene"
	name_input.custom_minimum_size = Vector2(0, 52)
	name_input.add_theme_font_size_override("font_size", 24)
	name_vbox.add_child(name_input)

	var preset_panel := PanelContainer.new()
	preset_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.12, 0.10, 0.13, 0.98)))
	section.add_child(preset_panel)

	var preset_margin := MarginContainer.new()
	preset_margin.add_theme_constant_override("margin_left", 14)
	preset_margin.add_theme_constant_override("margin_top", 14)
	preset_margin.add_theme_constant_override("margin_right", 14)
	preset_margin.add_theme_constant_override("margin_bottom", 14)
	preset_panel.add_child(preset_margin)

	var preset_vbox := VBoxContainer.new()
	preset_vbox.add_theme_constant_override("separation", 12)
	preset_margin.add_child(preset_vbox)

	var preset_label := Label.new()
	preset_label.text = "Opening discipline"
	preset_label.add_theme_font_size_override("font_size", 20)
	preset_vbox.add_child(preset_label)

	var preset_grid := GridContainer.new()
	preset_grid.name = "GenreCards"
	preset_grid.columns = 2
	preset_grid.add_theme_constant_override("h_separation", 10)
	preset_grid.add_theme_constant_override("v_separation", 10)
	preset_vbox.add_child(preset_grid)

	var preset_buttons := {}
	for preset_id in OPENING_ARCHETYPES.keys():
		var info: Dictionary = OPENING_ARCHETYPES[preset_id]
		var card := Button.new()
		card.name = "%sCard" % str(preset_id).capitalize().replace("_", "")
		card.alignment = HORIZONTAL_ALIGNMENT_LEFT
		card.custom_minimum_size = Vector2(0, 144)
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var body_preview := str(info.get("body", "")).strip_edges()
		if body_preview.length() > 74:
			body_preview = body_preview.substr(0, 71) + "..."
		card.text = "%s\n%s\n%s" % [info.get("title", preset_id), info.get("subtitle", ""), body_preview]
		card.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		card.focus_mode = Control.FOCUS_ALL
		preset_grid.add_child(card)
		preset_buttons[preset_id] = card

	var advanced_toggle := Button.new()
	advanced_toggle.name = "AdvancedToggle"
	advanced_toggle.text = "Show Chronicle Seed"
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
	seed_input.placeholder_text = "Optional deterministic world seed"
	advanced_section.add_child(seed_input)

	return {
		"root": section,
		"name_input": name_input,
		"seed_input": seed_input,
		"advanced_section": advanced_section,
		"advanced_toggle": advanced_toggle,
		"profile_hint": profile_hint,
		"genre_cards": preset_buttons,
	}


static func build_question_section() -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "QuestionSection"
	section.add_theme_constant_override("separation", 14)

	var question_progress := Label.new()
	question_progress.name = "QuestionProgress"
	question_progress.add_theme_color_override("font_color", Color(0.80, 0.66, 0.39))
	section.add_child(question_progress)

	var question_panel := PanelContainer.new()
	question_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.14, 0.11, 0.10, 0.98)))
	section.add_child(question_panel)

	var question_margin := MarginContainer.new()
	question_margin.add_theme_constant_override("margin_left", 16)
	question_margin.add_theme_constant_override("margin_top", 16)
	question_margin.add_theme_constant_override("margin_right", 16)
	question_margin.add_theme_constant_override("margin_bottom", 16)
	question_panel.add_child(question_margin)

	var question_vbox := VBoxContainer.new()
	question_vbox.add_theme_constant_override("separation", 10)
	question_margin.add_child(question_vbox)

	var atmosphere := Label.new()
	atmosphere.name = "AtmosphereLabel"
	atmosphere.text = "The world asks its price."
	atmosphere.add_theme_color_override("font_color", Color(0.72, 0.68, 0.62))
	question_vbox.add_child(atmosphere)

	var question_prompt := RichTextLabel.new()
	question_prompt.name = "QuestionPrompt"
	question_prompt.bbcode_enabled = true
	question_prompt.fit_content = true
	question_prompt.scroll_active = false
	question_prompt.custom_minimum_size = Vector2(0, 92)
	question_vbox.add_child(question_prompt)

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
		var answer_text := str(answer.get("text", "Answer"))
		var answer_desc := str(answer.get("description", "")).strip_edges()
		var answer_preview := answer_desc
		if answer_preview.length() > 96:
			answer_preview = answer_preview.substr(0, 93) + "..."
		button.text = answer_text if answer_preview.is_empty() else "%s\n%s" % [answer_text, answer_preview]
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.custom_minimum_size = Vector2(0, 96)
		button.disabled = owner._busy
		button.tooltip_text = answer_desc if not answer_desc.is_empty() else answer_text
		button.add_theme_stylebox_override("normal", _choice_style())
		button.add_theme_stylebox_override("hover", _choice_style(true))
		button.add_theme_stylebox_override("pressed", _choice_style(true))
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
		owner._advanced_toggle.text = "Hide Chronicle Seed" if owner._advanced_open else "Show Chronicle Seed"
	if owner._profile_hint != null:
		owner._profile_hint.text = "World profile: %s" % CreationCatalog.humanize_id(owner._selected_profile_id)


static func render_genre_cards(owner) -> void:
	for preset_id in owner._genre_card_buttons.keys():
		var button: Button = owner._genre_card_buttons[preset_id]
		var selected := str(preset_id) == str(owner._selected_archetype_id)
		button.add_theme_stylebox_override("normal", _preset_style(selected))
		button.add_theme_stylebox_override("hover", _preset_style(true))
		button.add_theme_stylebox_override("pressed", _preset_style(true))


static func _panel_style(bg: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.set_corner_radius_all(14)
	style.set_border_width_all(1)
	style.border_color = Color(0.33, 0.25, 0.18, 0.95)
	return style


static func _preset_style(selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.22, 0.15, 0.10, 0.98) if selected else Color(0.12, 0.10, 0.13, 0.98)
	style.set_corner_radius_all(12)
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.66, 0.39) if selected else Color(0.28, 0.24, 0.20, 0.94)
	style.content_margin_left = 12
	style.content_margin_top = 12
	style.content_margin_right = 12
	style.content_margin_bottom = 12
	return style


static func _choice_style(hovered: bool = false) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.18, 0.13, 0.10, 0.98) if hovered else Color(0.12, 0.10, 0.13, 0.98)
	style.set_corner_radius_all(12)
	style.set_border_width_all(1)
	style.border_color = Color(0.80, 0.66, 0.39) if hovered else Color(0.28, 0.24, 0.20, 0.94)
	style.content_margin_left = 12
	style.content_margin_top = 12
	style.content_margin_right = 12
	style.content_margin_bottom = 12
	return style
