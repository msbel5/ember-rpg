extends RefCounted
class_name CreationStepBuildDossier

const CreationCatalog = preload("res://scripts/ui/creation_catalog.gd")
const CreationWizardState = preload("res://scripts/ui/creation_wizard_state.gd")


static func build_build_section(owner) -> Control:
	var section := VBoxContainer.new()
	section.name = "BuildSection"
	section.add_theme_constant_override("separation", 12)

	owner._class_grid = GridContainer.new()
	owner._class_grid.name = "ClassGrid"
	owner._class_grid.columns = 2
	section.add_child(owner._class_grid)

	owner._alignment_grid = GridContainer.new()
	owner._alignment_grid.name = "AlignmentGrid"
	owner._alignment_grid.columns = 3
	section.add_child(owner._alignment_grid)

	owner._skill_budget_label = Label.new()
	section.add_child(owner._skill_budget_label)

	owner._skill_grid = GridContainer.new()
	owner._skill_grid.name = "SkillGrid"
	owner._skill_grid.columns = 4
	section.add_child(owner._skill_grid)
	return section


static func build_dossier_section(owner) -> Control:
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
	owner._dossier_identity = RichTextLabel.new()
	owner._dossier_identity.name = "DossierIdentity"
	owner._dossier_identity.bbcode_enabled = true
	owner._dossier_identity.fit_content = true
	owner._dossier_identity.scroll_active = false
	identity_margin.add_child(owner._dossier_identity)

	var stats_panel := PanelContainer.new()
	stats_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(stats_panel)
	var stats_margin := MarginContainer.new()
	stats_margin.add_theme_constant_override("margin_left", 12)
	stats_margin.add_theme_constant_override("margin_top", 12)
	stats_margin.add_theme_constant_override("margin_right", 12)
	stats_margin.add_theme_constant_override("margin_bottom", 12)
	stats_panel.add_child(stats_margin)
	owner._dossier_stats_grid = GridContainer.new()
	owner._dossier_stats_grid.name = "DossierStatsGrid"
	owner._dossier_stats_grid.columns = 2
	owner._dossier_stats_grid.add_theme_constant_override("h_separation", 14)
	owner._dossier_stats_grid.add_theme_constant_override("v_separation", 8)
	stats_margin.add_child(owner._dossier_stats_grid)

	var right := VBoxContainer.new()
	right.name = "DossierSecondary"
	right.custom_minimum_size = Vector2(360, 0)
	right.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 10)
	section.add_child(right)

	owner._dossier_world = RichTextLabel.new()
	owner._dossier_world.name = "DossierWorld"
	owner._dossier_world.bbcode_enabled = true
	owner._dossier_world.fit_content = true
	owner._dossier_world.scroll_active = false
	right.add_child(_framed_block(owner._dossier_world))

	owner._dossier_history = RichTextLabel.new()
	owner._dossier_history.name = "DossierHistory"
	owner._dossier_history.bbcode_enabled = true
	owner._dossier_history.fit_content = false
	owner._dossier_history.scroll_active = true
	owner._dossier_history.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(_framed_block(owner._dossier_history))
	return section


static func render_build(owner) -> void:
	_rebuild_class_grid(owner)
	_rebuild_alignment_grid(owner)
	_rebuild_skill_grid(owner)


static func render_dossier(owner) -> void:
	var genesis: Dictionary = owner._payload.get("campaign_genesis", {})
	var stat_cards: Array[String] = []
	for ability in CreationCatalog.ability_order(owner._catalog):
		var value := int(owner._assigned_stats.get(ability, 10))
		stat_cards.append("[b]%s[/b] %d (%+d)" % [ability, value, CreationCatalog.modifier(value)])

	owner._dossier_identity.text = (
		"[b]%s[/b]\nClass: %s\nAlignment: %s\nSkills: %s"
		% [
			owner._name_input.text.strip_edges(),
			owner._selected_class_id.capitalize(),
			owner._selected_alignment,
			", ".join(owner._selected_skills),
		]
	)

	owner._clear_children(owner._dossier_stats_grid)
	for stat_line in stat_cards:
		var label := Label.new()
		label.text = stat_line.replace("[b]", "").replace("[/b]", "")
		label.add_theme_font_size_override("font_size", 15)
		owner._dossier_stats_grid.add_child(label)

	owner._dossier_world.text = (
		"[b]World Premise[/b]\n%s\n\n[b]Starting Pressure[/b]\n%s\n\n[b]Quest Seeds[/b]\n%s"
		% [
			str(genesis.get("world_premise", "A frontier waits.")),
			str(genesis.get("starting_pressure", "")),
			", ".join(genesis.get("quest_seed_themes", [])),
		]
	)

	var timeline_entries: Array = CreationWizardState.history_timeline(owner._payload)
	var history_sections: Array[String] = []
	for entry in timeline_entries.slice(0, min(5, timeline_entries.size())):
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
		var button := Button.new()
		button.name = "Class_%s" % str(entry.get("id", "class"))
		button.text = "%s\n%s" % [str(entry.get("label", entry.get("id", ""))), str(entry.get("description", ""))]
		button.custom_minimum_size = Vector2(0, 110)
		button.pressed.connect(func() -> void:
			owner._selected_class_id = str(entry.get("id", ""))
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
		var button := Button.new()
		button.name = "Alignment_%s" % code
		button.text = code
		button.custom_minimum_size = Vector2(0, 54)
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
		button.toggled.connect(func(pressed: bool) -> void:
			if pressed and not owner._selected_skills.has(skill) and owner._selected_skills.size() < budget:
				owner._selected_skills.append(skill)
			elif not pressed:
				owner._selected_skills.erase(skill)
			owner._render()
		)
		owner._skill_grid.add_child(button)


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
