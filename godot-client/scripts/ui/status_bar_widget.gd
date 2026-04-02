## Top status bar showing location, time, weather, gold, HP.
## Created programmatically and added to the top of game_session layout.
extends PanelContainer
class_name StatusBarWidget

var _location_label: Label
var _time_label: Label
var _gold_label: Label
var _hp_bar: ProgressBar
var _hp_label: Label


func _ready() -> void:
	name = "StatusBar"
	custom_minimum_size = Vector2(0, 32)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.08, 0.07, 0.10, 0.92)
	bg.border_color = Color(0.80, 0.66, 0.39, 0.4)
	bg.border_width_bottom = 1
	bg.content_margin_left = 12
	bg.content_margin_right = 12
	bg.content_margin_top = 4
	bg.content_margin_bottom = 4
	add_theme_stylebox_override("panel", bg)

	var hbox := HBoxContainer.new()
	hbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_theme_constant_override("separation", 24)
	add_child(hbox)

	_location_label = _make_label("Location", Color(0.94, 0.92, 0.88))
	hbox.add_child(_location_label)

	hbox.add_child(_make_separator())

	_time_label = _make_label("Day 1, 12:00", Color(0.75, 0.73, 0.68))
	hbox.add_child(_time_label)

	hbox.add_child(_make_separator())

	_gold_label = _make_label("Gold: 0", Color(0.80, 0.66, 0.26))
	hbox.add_child(_gold_label)

	hbox.add_child(_make_separator())

	var hp_container := HBoxContainer.new()
	hp_container.add_theme_constant_override("separation", 6)
	hbox.add_child(hp_container)

	_hp_label = _make_label("HP: 0/0", Color(0.84, 0.30, 0.30))
	hp_container.add_child(_hp_label)

	_hp_bar = ProgressBar.new()
	_hp_bar.custom_minimum_size = Vector2(120, 16)
	_hp_bar.max_value = 100
	_hp_bar.value = 100
	_hp_bar.show_percentage = false
	var bar_bg := StyleBoxFlat.new()
	bar_bg.bg_color = Color(0.15, 0.12, 0.12)
	bar_bg.corner_radius_top_left = 3
	bar_bg.corner_radius_top_right = 3
	bar_bg.corner_radius_bottom_left = 3
	bar_bg.corner_radius_bottom_right = 3
	_hp_bar.add_theme_stylebox_override("background", bar_bg)
	var bar_fill := StyleBoxFlat.new()
	bar_fill.bg_color = Color(0.72, 0.22, 0.22)
	bar_fill.corner_radius_top_left = 3
	bar_fill.corner_radius_top_right = 3
	bar_fill.corner_radius_bottom_left = 3
	bar_fill.corner_radius_bottom_right = 3
	_hp_bar.add_theme_stylebox_override("fill", bar_fill)
	hp_container.add_child(_hp_bar)

	# Spacer to push remaining content right
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)

	if get_node_or_null("/root/GameState") != null:
		GameState.state_updated.connect(_refresh)
	_refresh()


func _refresh(_data = null) -> void:
	_location_label.text = GameState.get_display_location()

	var game_time = GameState.player.get("game_time", {})
	if game_time is Dictionary and not game_time.is_empty():
		var day := int(game_time.get("day", 1))
		var hour := int(game_time.get("hour", 12))
		var weather := str(game_time.get("weather", "Clear"))
		_time_label.text = "Day %d, %d:00 | %s" % [day, hour, weather]
	else:
		_time_label.text = ""

	var inventory_state = GameState.player.get("inventory", [])
	var inventory_gold := 0
	if inventory_state is Dictionary:
		inventory_gold = int(inventory_state.get("gold", 0))
	var gold := int(GameState.player.get("gold", inventory_gold))
	_gold_label.text = "Gold: %d" % gold

	var hp := int(GameState.player.get("hp", GameState.player.get("current_hp", 0)))
	var max_hp := int(GameState.player.get("max_hp", GameState.player.get("maximum_hp", hp)))
	if max_hp <= 0:
		max_hp = maxi(hp, 1)
	_hp_label.text = "HP: %d/%d" % [hp, max_hp]
	_hp_bar.max_value = max_hp
	_hp_bar.value = hp

	var fill_style: StyleBoxFlat = _hp_bar.get_theme_stylebox("fill")
	if fill_style != null:
		var ratio := float(hp) / float(max_hp) if max_hp > 0 else 0.0
		if ratio > 0.5:
			fill_style.bg_color = Color(0.30, 0.65, 0.30)
		elif ratio > 0.25:
			fill_style.bg_color = Color(0.85, 0.65, 0.20)
		else:
			fill_style.bg_color = Color(0.72, 0.22, 0.22)


func _make_label(text: String, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 14)
	label.add_theme_color_override("font_color", color)
	return label


func _make_separator() -> VSeparator:
	var sep := VSeparator.new()
	sep.custom_minimum_size = Vector2(1, 0)
	return sep
