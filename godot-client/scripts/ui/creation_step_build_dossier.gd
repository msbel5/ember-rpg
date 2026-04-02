extends RefCounted
class_name CreationStepBuildDossier

const CreationCatalog = preload("res://scripts/ui/creation_catalog.gd")
const CreationWizardState = preload("res://scripts/ui/creation_wizard_state.gd")


static func build_build_section(owner) -> Control:
	var section := VBoxContainer.new()
	section.name = "BuildSection"

	owner._class_grid = GridContainer.new()
	owner._class_grid.name = "ClassGrid"
	owner._class_grid.columns = 3
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
	var section := VBoxContainer.new()
	section.name = "DossierSection"
	owner._dossier_text = RichTextLabel.new()
	owner._dossier_text.name = "DossierText"
	owner._dossier_text.bbcode_enabled = true
	owner._dossier_text.fit_content = false
	owner._dossier_text.scroll_active = true
	owner._dossier_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	section.add_child(owner._dossier_text)
	return section


static func render_build(owner) -> void:
	_rebuild_class_grid(owner)
	_rebuild_alignment_grid(owner)
	_rebuild_skill_grid(owner)


static func render_dossier(owner) -> void:
	var genesis: Dictionary = owner._payload.get("campaign_genesis", {})
	var stats: Array[String] = []
	for ability in CreationCatalog.ability_order(owner._catalog):
		stats.append("%s %d" % [ability, int(owner._assigned_stats.get(ability, 10))])

	var history_text := CreationWizardState.history_source(owner._payload)
	owner._dossier_text.text = (
		"[b]World Premise[/b]\n%s\n\n[b]Starting Pressure[/b]\n%s\n\n[b]History[/b]\n%s\n\n[b]Build[/b]\nClass: %s\nAlignment: %s\nSkills: %s\nStats: %s"
		% [
			str(genesis.get("world_premise", "A frontier waits.")),
			str(genesis.get("starting_pressure", "")),
			history_text,
			owner._selected_class_id.capitalize(),
			owner._selected_alignment,
			", ".join(owner._selected_skills),
			" | ".join(stats),
		]
	)


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
		button.custom_minimum_size = Vector2(0, 92)
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
