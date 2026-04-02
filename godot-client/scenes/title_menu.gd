extends Control
class_name TitleMenu

signal new_game_requested()
signal continue_requested()
signal quit_requested()

var _new_game_button: Button
var _continue_button: Button


func _ready() -> void:
	anchors_preset = Control.PRESET_FULL_RECT
	mouse_filter = Control.MOUSE_FILTER_STOP
	if get_child_count() == 0:
		_build_ui()


func set_continue_enabled(enabled: bool) -> void:
	if _continue_button != null:
		_continue_button.disabled = not enabled


func focus_default() -> void:
	if _new_game_button != null:
		_new_game_button.grab_focus()


func _build_ui() -> void:
	var shell := MarginContainer.new()
	shell.name = "Shell"
	shell.anchors_preset = Control.PRESET_FULL_RECT
	shell.add_theme_constant_override("margin_left", 180)
	shell.add_theme_constant_override("margin_top", 72)
	shell.add_theme_constant_override("margin_right", 180)
	shell.add_theme_constant_override("margin_bottom", 72)
	add_child(shell)

	var vbox := VBoxContainer.new()
	vbox.name = "RootVBox"
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 28)
	shell.add_child(vbox)

	var title_block := VBoxContainer.new()
	title_block.name = "TitleBlock"
	title_block.alignment = BoxContainer.ALIGNMENT_CENTER
	title_block.add_theme_constant_override("separation", 8)
	vbox.add_child(title_block)

	var title_label := Label.new()
	title_label.name = "TitleLabel"
	title_label.text = "EMBER RPG"
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override("font_size", 42)
	title_block.add_child(title_label)

	var subtitle_label := Label.new()
	subtitle_label.name = "SubtitleLabel"
	subtitle_label.text = "Campaign-first colony drama with hard choices and fragile victories"
	subtitle_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	subtitle_label.add_theme_font_size_override("font_size", 20)
	title_block.add_child(subtitle_label)

	var hero_panel := PanelContainer.new()
	hero_panel.name = "HeroPanel"
	hero_panel.custom_minimum_size = Vector2(0, 156)
	hero_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_child(hero_panel)

	var hero_margin := MarginContainer.new()
	hero_margin.add_theme_constant_override("margin_left", 18)
	hero_margin.add_theme_constant_override("margin_top", 16)
	hero_margin.add_theme_constant_override("margin_right", 18)
	hero_margin.add_theme_constant_override("margin_bottom", 16)
	hero_panel.add_child(hero_margin)

	var hero_text := RichTextLabel.new()
	hero_text.name = "HeroText"
	hero_text.bbcode_enabled = true
	hero_text.fit_content = true
	hero_text.scroll_active = false
	hero_text.custom_minimum_size = Vector2(0, 90)
	hero_text.text = "[b]Campaign-first demo[/b]\nShape a drifter through fear, duty, greed, and nerve.\nCommand a brittle settlement, follow rumors, and push into a world that still wants to swallow you."
	hero_margin.add_child(hero_text)

	var menu_panel := PanelContainer.new()
	menu_panel.name = "MenuPanel"
	menu_panel.custom_minimum_size = Vector2(0, 220)
	menu_panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vbox.add_child(menu_panel)

	var menu_margin := MarginContainer.new()
	menu_margin.name = "MenuMargin"
	menu_margin.add_theme_constant_override("margin_left", 28)
	menu_margin.add_theme_constant_override("margin_top", 24)
	menu_margin.add_theme_constant_override("margin_right", 28)
	menu_margin.add_theme_constant_override("margin_bottom", 24)
	menu_panel.add_child(menu_margin)

	var menu_vbox := VBoxContainer.new()
	menu_vbox.name = "MenuVBox"
	menu_vbox.add_theme_constant_override("separation", 14)
	menu_margin.add_child(menu_vbox)

	_new_game_button = Button.new()
	_new_game_button.name = "NewGameButton"
	_new_game_button.text = "New Game"
	_new_game_button.custom_minimum_size = Vector2(280, 56)
	_new_game_button.tooltip_text = "Start a new campaign from a clean creation flow."
	_new_game_button.pressed.connect(func() -> void:
		new_game_requested.emit()
	)
	menu_vbox.add_child(_new_game_button)

	_continue_button = Button.new()
	_continue_button.name = "ContinueButton"
	_continue_button.text = "Continue"
	_continue_button.custom_minimum_size = Vector2(280, 56)
	_continue_button.tooltip_text = "Resume the most recent canonical campaign save."
	_continue_button.pressed.connect(func() -> void:
		continue_requested.emit()
	)
	menu_vbox.add_child(_continue_button)

	var quit_button := Button.new()
	quit_button.name = "QuitButton"
	quit_button.text = "Quit"
	quit_button.custom_minimum_size = Vector2(280, 52)
	quit_button.tooltip_text = "Exit Ember RPG."
	quit_button.pressed.connect(func() -> void:
		quit_requested.emit()
	)
	menu_vbox.add_child(quit_button)
