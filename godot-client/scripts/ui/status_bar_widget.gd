## Compact top strip for the gameplay shell.
## This is the single authoritative status surface used by game_session.
extends PanelContainer
class_name StatusBarWidget

var _player_info: Label
var _time_label: Label
var _gold_label: Label
var _hp_bar: ProgressBar
var _hp_label: Label
var _location_label: Label


func _ready() -> void:
	name = "StatusBar"
	custom_minimum_size = Vector2(0, 42)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.08, 0.07, 0.10, 0.94)
	bg.border_color = Color(0.80, 0.66, 0.39, 0.38)
	bg.border_width_bottom = 1
	bg.content_margin_left = 12
	bg.content_margin_right = 12
	bg.content_margin_top = 4
	bg.content_margin_bottom = 4
	add_theme_stylebox_override("panel", bg)

	var status_row := HBoxContainer.new()
	status_row.name = "StatusRow"
	status_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status_row.add_theme_constant_override("separation", 10)
	add_child(status_row)

	_player_info = _make_label("Hero", Color(0.96, 0.92, 0.86), 15)
	_player_info.name = "PlayerInfo"
	_player_info.custom_minimum_size = Vector2(240, 0)
	status_row.add_child(_player_info)

	status_row.add_child(_make_separator())

	_time_label = _make_label("Day 1, 12:00", Color(0.76, 0.73, 0.68), 13)
	_time_label.name = "TimeLabel"
	status_row.add_child(_time_label)

	status_row.add_child(_make_separator())

	_gold_label = _make_label("Gold: 0", Color(0.86, 0.72, 0.28), 13)
	_gold_label.name = "GoldLabel"
	status_row.add_child(_gold_label)

	status_row.add_child(_make_separator())

	_hp_bar = ProgressBar.new()
	_hp_bar.name = "HPBar"
	_hp_bar.custom_minimum_size = Vector2(120, 14)
	_hp_bar.max_value = 100
	_hp_bar.value = 100
	_hp_bar.show_percentage = false
	_apply_bar_style(_hp_bar)
	status_row.add_child(_hp_bar)

	_hp_label = _make_label("HP 0/0", Color(0.94, 0.58, 0.54), 13)
	_hp_label.name = "HPLabel"
	status_row.add_child(_hp_label)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status_row.add_child(spacer)

	_location_label = _make_label("Unknown", Color(0.90, 0.88, 0.82), 13)
	_location_label.name = "LocationLabel"
	_location_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_location_label.clip_text = true
	_location_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status_row.add_child(_location_label)

	if get_node_or_null("/root/GameState") != null:
		GameState.state_updated.connect(_refresh)
		GameState.settlement_updated.connect(_on_settlement_updated)
		GameState.map_loaded.connect(_on_map_loaded)
		GameState.scene_changed.connect(_on_scene_changed)
	_refresh()


func _refresh(_payload = null) -> void:
	var player = GameState.player
	if player.is_empty():
		_player_info.text = "No active hero"
		_time_label.text = ""
		_gold_label.text = "Gold: 0"
		_location_label.text = "No live survey"
		_set_hp(0, 1)
		return

	var player_name = str(player.get("name", "Unknown"))
	var class_label = str(player.get("player_class", "adventurer")).capitalize()
	var level = int(player.get("level", 1))
	_player_info.text = "%s Lv.%d %s" % [player_name, level, class_label]

	var world_clock := {}
	if GameState.world_state is Dictionary:
		world_clock = GameState.world_state.get("clock", {})
	var player_clock = player.get("game_time", {})
	var clock = world_clock if world_clock is Dictionary and not world_clock.is_empty() else player_clock
	if clock is Dictionary and not clock.is_empty():
		var day := int(clock.get("day", clock.get("current_day", 1)))
		var hour := int(clock.get("hour", clock.get("current_hour", 12)))
		var weather := str(clock.get("weather", clock.get("weather_label", ""))).strip_edges()
		_time_label.text = "Day %d, %02d:00%s" % [day, hour, (" | %s" % weather) if not weather.is_empty() else ""]
	else:
		_time_label.text = ""

	var gold := int(player.get("gold", 0))
	_gold_label.text = "Gold: %d" % gold

	var hp := int(player.get("hp", player.get("current_hp", 0)))
	var max_hp := int(player.get("max_hp", player.get("maximum_hp", hp)))
	_set_hp(hp, max_hp)

	var display_location = GameState.get_display_location()
	var scene_name = str(GameState.scene).strip_edges().capitalize()
	var location_parts: Array[String] = [display_location]
	if not scene_name.is_empty():
		location_parts.append(scene_name)
	_location_label.text = "  |  ".join(location_parts)


func _set_hp(hp: int, max_hp: int) -> void:
	max_hp = maxi(max_hp, 1)
	_hp_bar.max_value = max_hp
	_hp_bar.value = clampi(hp, 0, max_hp)
	_hp_label.text = "HP %d/%d" % [hp, max_hp]
	var fill_style = _hp_bar.get_theme_stylebox("fill") as StyleBoxFlat
	if fill_style == null:
		return
	var ratio := float(hp) / float(max_hp)
	if ratio > 0.6:
		fill_style.bg_color = Color(0.30, 0.68, 0.34)
	elif ratio > 0.3:
		fill_style.bg_color = Color(0.86, 0.66, 0.22)
	else:
		fill_style.bg_color = Color(0.76, 0.22, 0.22)


func _apply_bar_style(bar: ProgressBar) -> void:
	var background := StyleBoxFlat.new()
	background.bg_color = Color(0.15, 0.12, 0.12, 0.95)
	background.set_corner_radius_all(4)
	bar.add_theme_stylebox_override("background", background)

	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(0.30, 0.68, 0.34)
	fill.set_corner_radius_all(4)
	bar.add_theme_stylebox_override("fill", fill)


func _make_label(text: String, color: Color, font_size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _make_separator() -> VSeparator:
	var sep := VSeparator.new()
	sep.custom_minimum_size = Vector2(1, 0)
	return sep


func _on_map_loaded(_map_data: Dictionary) -> void:
	call_deferred("_refresh")


func _on_scene_changed(_new_scene: String) -> void:
	call_deferred("_refresh")


func _on_settlement_updated(_settlement: Dictionary) -> void:
	call_deferred("_refresh")
