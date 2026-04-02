extends RefCounted
class_name CreationStepBuildDossier


const ALIGNMENT_INFO := {
	"LG": {"name": "Lawful Good", "desc": "Honourable and dutiful. Upholds law and protects the innocent."},
	"NG": {"name": "Neutral Good", "desc": "Kind-hearted pragmatist. Does what is right without dogma."},
	"CG": {"name": "Chaotic Good", "desc": "Free-spirited rebel. Fights tyranny and champions the downtrodden."},
	"LN": {"name": "Lawful Neutral", "desc": "Order above all. Follows the code regardless of moral outcome."},
	"TN": {"name": "True Neutral", "desc": "Balanced observer. Acts on circumstance, not ideology."},
	"CN": {"name": "Chaotic Neutral", "desc": "Unpredictable free agent. Values personal freedom above all else."},
	"LE": {"name": "Lawful Evil", "desc": "Calculated tyrant. Uses structure and hierarchy to dominate."},
	"NE": {"name": "Neutral Evil", "desc": "Pure self-interest. No loyalty except to personal gain."},
	"CE": {"name": "Chaotic Evil", "desc": "Destructive anarchist. Revels in chaos and cruelty."},
}

const GOLD := Color(0.78, 0.55, 0.25)


static func build_build_section() -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "BuildSection"
	section.add_theme_constant_override("separation", 12)

	var class_grid := GridContainer.new()
	class_grid.name = "ClassGrid"
	class_grid.columns = 2
	section.add_child(class_grid)

	var alignment_grid := GridContainer.new()
	alignment_grid.name = "AlignmentGrid"
	alignment_grid.columns = 3
	section.add_child(alignment_grid)

	var skill_budget_label := Label.new()
	section.add_child(skill_budget_label)

	var skill_grid := GridContainer.new()
	skill_grid.name = "SkillGrid"
	skill_grid.columns = 5
	section.add_child(skill_grid)

	return {
		"root": section,
		"class_grid": class_grid,
		"alignment_grid": alignment_grid,
		"skill_grid": skill_grid,
		"skill_budget_label": skill_budget_label,
	}


static func build_dossier_section() -> Dictionary:
	var section := HBoxContainer.new()
	section.name = "DossierSection"
	section.add_theme_constant_override("separation", 14)

	var left := VBoxContainer.new()
	left.name = "DossierPrimary"
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 10)
	section.add_child(left)

	var identity_panel := PanelContainer.new()
	identity_panel.custom_minimum_size = Vector2(0, 140)
	left.add_child(identity_panel)
	var identity_margin := MarginContainer.new()
	identity_margin.add_theme_constant_override("margin_left", 12)
	identity_margin.add_theme_constant_override("margin_top", 12)
	identity_margin.add_theme_constant_override("margin_right", 12)
	identity_margin.add_theme_constant_override("margin_bottom", 12)
	identity_panel.add_child(identity_margin)
	var dossier_identity := RichTextLabel.new()
	dossier_identity.name = "DossierIdentity"
	dossier_identity.bbcode_enabled = true
	dossier_identity.fit_content = true
	dossier_identity.scroll_active = false
	identity_margin.add_child(dossier_identity)

	var stats_panel := PanelContainer.new()
	stats_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(stats_panel)
	var stats_margin := MarginContainer.new()
	stats_margin.add_theme_constant_override("margin_left", 12)
	stats_margin.add_theme_constant_override("margin_top", 12)
	stats_margin.add_theme_constant_override("margin_right", 12)
	stats_margin.add_theme_constant_override("margin_bottom", 12)
	stats_panel.add_child(stats_margin)
	var dossier_stats_grid := GridContainer.new()
	dossier_stats_grid.name = "DossierStatsGrid"
	dossier_stats_grid.columns = 2
	dossier_stats_grid.add_theme_constant_override("h_separation", 14)
	dossier_stats_grid.add_theme_constant_override("v_separation", 8)
	stats_margin.add_child(dossier_stats_grid)

	var right := VBoxContainer.new()
	right.name = "DossierSecondary"
	right.custom_minimum_size = Vector2(360, 0)
	right.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 10)
	section.add_child(right)

	var dossier_world := RichTextLabel.new()
	dossier_world.name = "DossierWorld"
	dossier_world.bbcode_enabled = true
	dossier_world.fit_content = true
	dossier_world.scroll_active = false
	right.add_child(_framed_block(dossier_world))

	var dossier_history := RichTextLabel.new()
	dossier_history.name = "DossierHistory"
	dossier_history.bbcode_enabled = true
	dossier_history.fit_content = false
	dossier_history.scroll_active = true
	dossier_history.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(_framed_block(dossier_history))

	return {
		"root": section,
		"dossier_identity": dossier_identity,
		"dossier_world": dossier_world,
		"dossier_history": dossier_history,
		"dossier_stats_grid": dossier_stats_grid,
	}


static func render_build(owner) -> void:
	_rebuild_class_grid(owner)
	_rebuild_alignment_grid(owner)
	_rebuild_skill_grid(owner)


static func render_dossier(owner) -> void:
	var genesis: Dictionary = owner._payload.get("campaign_genesis", {})
	var stat_cards: Array[String] = []
	for ability in CreationCatalog.ability_order(owner._catalog):
		var value := int(owner._assigned_stats.get(ability, 10))
		stat_cards.append("%s %d (%+d)" % [ability, value, CreationCatalog.modifier(value)])

	var alignment_label: String = str(owner._selected_alignment)
	if ALIGNMENT_INFO.has(alignment_label):
		alignment_label = "%s (%s)" % [ALIGNMENT_INFO[owner._selected_alignment].name, owner._selected_alignment]

	owner._dossier_identity.text = (
		"[b]%s[/b]\nClass: %s\nAlignment: %s\nSkills: %s"
		% [
			owner._name_input.text.strip_edges(),
			owner._selected_class_id.capitalize(),
			alignment_label,
			", ".join(owner._selected_skills),
		]
	)

	owner._clear_children(owner._dossier_stats_grid)
	for stat_line in stat_cards:
		var label := Label.new()
		label.text = stat_line
		label.add_theme_font_size_override("font_size", 15)
		owner._dossier_stats_grid.add_child(label)

	# Dossier right panel shows Quest Seeds (no duplicate of preview sidebar)
	var quest_seeds: Array = genesis.get("quest_seed_themes", [])
	if not quest_seeds.is_empty():
		owner._dossier_world.text = "[b]Quest Seeds[/b]\n%s" % ", ".join(quest_seeds)
	else:
		owner._dossier_world.text = ""

	var timeline_entries: Array = CreationWizardState.history_timeline(owner._payload)
	var history_sections: Array[String] = []
	for entry in timeline_entries.slice(0, min(8, timeline_entries.size())):
		if not (entry is Dictionary):
			continue
		history_sections.append(
			"[b]Year %d - %s[/b]\n%s"
			% [int(entry.get("year", 0)), str(entry.get("headline", "")), str(entry.get("summary", ""))]
		)
	owner._dossier_history.text = "[b]Chronicle Highlights[/b]\n\n%s" % "\n\n".join(history_sections)


static func render_preview(owner) -> void:
	var genesis: Dictionary = owner._payload.get("campaign_genesis", {})
	owner._preview_title.text = CreationWizardState.preview_heading(owner._step)
	owner._preview_text.text = "[b]World Premise[/b]\n%s\n\n[b]Starting Pressure[/b]\n%s" % [
		str(genesis.get("world_premise", "Shape the world.")),
		str(genesis.get("starting_pressure", "")),
	]
	owner._preview_meta.text = "[b]Recommended[/b] %s / %s\n[b]Quest Seeds[/b] %s" % [
		str(owner._payload.get("recommended_class", "warrior")).capitalize(),
		str(owner._payload.get("recommended_alignment", "TN")),
		", ".join(owner._payload.get("recommended_skills", [])),
	]


static func sync_footer(owner) -> void:
	owner._back_button.visible = owner._step in [owner.STEP_HISTORY, owner.STEP_ROLL, owner.STEP_BUILD, owner.STEP_DOSSIER]
	owner._next_button.visible = owner._step != owner.STEP_DOSSIER
	owner._start_button.visible = owner._step == owner.STEP_DOSSIER
	owner._back_button.disabled = owner._busy
	owner._next_button.disabled = owner._busy
	owner._start_button.disabled = owner._busy


static func _rebuild_class_grid(owner) -> void:
	owner._clear_children(owner._class_grid)
	for entry in CreationCatalog.class_entries(owner._catalog):
		var class_id := str(entry.get("id", "class"))
		var is_selected: bool = class_id == str(owner._selected_class_id)
		var button := Button.new()
		button.name = "Class_%s" % class_id
		var class_label: String = str(entry.get("label", entry.get("id", "")))
		var class_desc: String = str(entry.get("description", ""))
		if class_desc.length() > 50:
			class_desc = class_desc.substr(0, 47) + "..."
		button.text = "%s\n%s" % [class_label, class_desc]
		button.custom_minimum_size = Vector2(200, 80)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		if is_selected:
			button.add_theme_stylebox_override("normal", _selection_style(true))
			button.add_theme_stylebox_override("hover", _selection_style(true))
			button.add_theme_stylebox_override("pressed", _selection_style(true))
			button.add_theme_stylebox_override("focus", _selection_style(true))
		button.pressed.connect(func() -> void:
			owner._selected_class_id = class_id
			owner._selected_skills = CreationWizardState.string_array(entry.get("default_skills", []))
			owner._assigned_stats = CreationCatalog.suggested_stats_for(
				owner._catalog,
				owner._selected_class_id,
				owner._payload.get("current_roll", []),
			)
			owner._render()
		)
		owner._class_grid.add_child(button)


static func _rebuild_alignment_grid(owner) -> void:
	owner._clear_children(owner._alignment_grid)
	for code in ["LG", "NG", "CG", "LN", "TN", "CN", "LE", "NE", "CE"]:
		var is_selected: bool = code == str(owner._selected_alignment)
		var info: Dictionary = ALIGNMENT_INFO.get(code, {})
		var button := Button.new()
		button.name = "Alignment_%s" % code
		button.text = "%s\n%s" % [code, info.get("name", code)]
		button.custom_minimum_size = Vector2(0, 64)
		button.tooltip_text = info.get("desc", "")
		if is_selected:
			button.add_theme_stylebox_override("normal", _selection_style(true))
			button.add_theme_stylebox_override("hover", _selection_style(true))
			button.add_theme_stylebox_override("pressed", _selection_style(true))
			button.add_theme_stylebox_override("focus", _selection_style(true))
		button.pressed.connect(func() -> void:
			owner._selected_alignment = code
			owner._render()
		)
		owner._alignment_grid.add_child(button)


static func _rebuild_skill_grid(owner) -> void:
	owner._clear_children(owner._skill_grid)
	var class_entry = CreationCatalog.class_entry(owner._catalog, owner._selected_class_id)
	var skill_pool: Array = class_entry.get("skill_pool", [])
	var budget := int(class_entry.get("skill_pick_count", 2))
	owner._skill_budget_label.text = "Skills %d/%d selected" % [owner._selected_skills.size(), budget]

	for raw_skill in skill_pool:
		var skill := str(raw_skill)
		var button := Button.new()
		button.name = "Skill_%s" % skill
		button.text = CreationCatalog.humanize_id(skill)
		button.toggle_mode = true
		button.button_pressed = owner._selected_skills.has(skill)
		if button.button_pressed:
			button.add_theme_stylebox_override("normal", _selection_style(true))
			button.add_theme_stylebox_override("hover", _selection_style(true))
			button.add_theme_stylebox_override("pressed", _selection_style(true))
			button.add_theme_stylebox_override("focus", _selection_style(true))
		button.toggled.connect(func(pressed: bool) -> void:
			if pressed and not owner._selected_skills.has(skill) and owner._selected_skills.size() < budget:
				owner._selected_skills.append(skill)
			elif not pressed:
				owner._selected_skills.erase(skill)
			owner._render()
		)
		owner._skill_grid.add_child(button)


static func _selection_style(selected: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	if selected:
		style.bg_color = Color(0.16, 0.12, 0.10)
		style.border_color = GOLD
		style.set_border_width_all(3)
	else:
		style.bg_color = Color(0.12, 0.10, 0.14)
		style.border_color = Color(0.3, 0.28, 0.32)
		style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	style.content_margin_left = 12
	style.content_margin_top = 8
	style.content_margin_right = 12
	style.content_margin_bottom = 8
	return style


static func _framed_block(content: Control) -> Control:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	panel.add_child(margin)
	margin.add_child(content)
	return panel
