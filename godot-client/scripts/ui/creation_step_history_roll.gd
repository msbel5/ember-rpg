extends RefCounted
class_name CreationStepHistoryRoll



static func build_history_section(owner) -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "HistorySection"
	var prompt := Label.new()
	prompt.text = "World history settles into place..."
	section.add_child(prompt)

	var history_text := RichTextLabel.new()
	history_text.name = "HistoryText"
	history_text.bbcode_enabled = true
	history_text.fit_content = false
	history_text.scroll_active = true
	history_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	history_text.custom_minimum_size = Vector2(0, 360)
	section.add_child(history_text)

	var history_timer := Timer.new()
	history_timer.wait_time = 0.033
	history_timer.timeout.connect(owner._on_history_tick)
	section.add_child(history_timer)

	return {
		"root": section,
		"history_text": history_text,
		"history_timer": history_timer,
	}


static func build_roll_section(owner) -> Dictionary:
	var section := VBoxContainer.new()
	section.name = "RollSection"

	var roll_pool_label := Label.new()
	section.add_child(roll_pool_label)

	var saved_roll_label := Label.new()
	section.add_child(saved_roll_label)

	var silhouette := Control.new()
	silhouette.name = "SilhouetteBoard"
	silhouette.custom_minimum_size = Vector2(0, 220)
	section.add_child(silhouette)

	var stat_rows := VBoxContainer.new()
	stat_rows.name = "StatRows"
	section.add_child(stat_rows)

	var button_row := HBoxContainer.new()
	button_row.add_theme_constant_override("separation", 10)
	section.add_child(button_row)

	for pair in [
		["RerollButton", "Reroll", func() -> void: owner.emit_reroll()],
		["SaveRollButton", "Lock Pool", func() -> void: owner.emit_save_roll()],
		["SwapRollButton", "Swap Pool", func() -> void: owner.emit_swap_roll()],
	]:
		var button := Button.new()
		button.name = pair[0]
		button.text = pair[1]
		button.pressed.connect(pair[2])
		button_row.add_child(button)

	return {
		"root": section,
		"roll_pool_label": roll_pool_label,
		"saved_roll_label": saved_roll_label,
		"stat_rows": stat_rows,
		"silhouette": silhouette,
	}


static func render_history(owner) -> void:
	if owner._step != owner.STEP_HISTORY:
		if owner._history_timer != null:
			owner._history_timer.stop()
		return
	if owner._history_source.is_empty():
		begin_history_reveal(owner)


static func begin_history_reveal(owner) -> void:
	owner._history_timeline_data = CreationWizardState.history_timeline(owner._payload)
	owner._history_visible_events = 0
	owner._history_source = CreationWizardState.history_source(owner._payload)
	owner._history_text.text = ""
	if not owner._history_timeline_data.is_empty():
		owner._history_timer.start()
	else:
		owner._history_text.text = owner._history_source


static func skip_history_reveal(owner) -> void:
	if owner._history_timer != null:
		owner._history_timer.stop()
	if owner._history_text != null:
		owner._history_visible_events = owner._history_timeline_data.size()
		owner._history_text.text = _formatted_timeline(owner._history_timeline_data)


static func history_reveal_complete(owner) -> bool:
	return owner._history_timeline_data.is_empty() or owner._history_visible_events >= owner._history_timeline_data.size()


static func on_history_tick(owner) -> void:
	owner._history_visible_events += 1
	owner._history_text.text = _formatted_timeline(owner._history_timeline_data.slice(0, owner._history_visible_events))
	owner._history_text.scroll_to_line(owner._history_text.get_line_count())
	if owner._history_visible_events >= owner._history_timeline_data.size():
		owner._history_timer.stop()


static func render_roll(owner) -> void:
	var raw_roll = owner._payload.get("current_roll", [])
	var current_roll: Array = raw_roll if raw_roll is Array else []
	var raw_saved = owner._payload.get("saved_roll", null)
	var saved_roll: Array = raw_saved if raw_saved is Array else []
	var total := 0
	for value in current_roll:
		total += int(value)
	owner._roll_pool_label.text = "Current Pool  %d total  |  %d high  |  %d low" % [
		total,
		int(current_roll.max()) if not current_roll.is_empty() else 0,
		int(current_roll.min()) if not current_roll.is_empty() else 0,
	]
	owner._saved_roll_label.text = "Locked Pool  %s" % (
		"ready to swap" if not saved_roll.is_empty() else "not locked yet"
	)
	owner._clear_children(owner._stat_rows)
	owner._clear_children(owner._silhouette)

	var positions := {
		"MND": Vector2(250, 18),
		"INS": Vector2(120, 62),
		"PRE": Vector2(380, 62),
		"END": Vector2(250, 108),
		"MIG": Vector2(250, 152),
		"AGI": Vector2(250, 196),
	}
	for ability in CreationCatalog.ability_order(owner._catalog):
		var label := Label.new()
		label.position = positions.get(str(ability), Vector2.ZERO)
		var value := int(owner._assigned_stats.get(ability, 10))
		label.text = "%s: %d (%+d)" % [ability, value, CreationCatalog.modifier(value)]
		label.add_theme_font_size_override("font_size", 19)
		owner._silhouette.add_child(label)
		owner._stat_rows.add_child(_stat_row(owner, str(ability), value))


static func _stat_row(owner, ability: String, value: int) -> Control:
	var row := HBoxContainer.new()
	var minus := Button.new()
	minus.text = "-"
	minus.pressed.connect(func() -> void: owner._shift_stat_value(ability, -1))
	row.add_child(minus)

	var label := Label.new()
	label.text = "%s: %d (%+d)" % [ability, value, CreationCatalog.modifier(value)]
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.add_theme_font_size_override("font_size", 16)
	row.add_child(label)

	var plus := Button.new()
	plus.text = "+"
	plus.pressed.connect(func() -> void: owner._shift_stat_value(ability, 1))
	row.add_child(plus)
	return row


static func _formatted_timeline(entries: Array) -> String:
	var sections: Array[String] = []
	for entry in entries:
		if not (entry is Dictionary):
			continue
		var year := int(entry.get("year", 0))
		var headline := str(entry.get("headline", "")).strip_edges()
		var summary := str(entry.get("summary", "")).strip_edges()
		var tags: Array = entry.get("tags", [])
		var tag_line := ""
		if tags is Array and not tags.is_empty():
			tag_line = "\n[color=#bfa56a]%s[/color]" % "  |  ".join(tags.slice(0, 4))
		sections.append("[b]Year %d - %s[/b]\n%s%s" % [year, headline, summary, tag_line])
	return "\n\n".join(sections)
