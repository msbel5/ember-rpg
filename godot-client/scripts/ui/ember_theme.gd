extends RefCounted
class_name EmberTheme

const IVORY := Color(0.94, 0.92, 0.86)
const INK := Color(0.07, 0.06, 0.08)
const PANEL := Color(0.12, 0.10, 0.13, 0.94)
const PANEL_ALT := Color(0.15, 0.12, 0.16, 0.96)
const ACCENT := Color(0.80, 0.66, 0.40, 1.0)
const ACCENT_SOFT := Color(0.59, 0.47, 0.28, 0.86)
const MUTED := Color(0.64, 0.61, 0.56, 1.0)
const SUCCESS := Color(0.54, 0.77, 0.59, 1.0)
const WARNING := Color(0.92, 0.73, 0.33, 1.0)


static func apply_title_screen(root: Control) -> void:
	root.theme = _build_theme()
	var background = root.get_node_or_null("Background")
	if background is ColorRect:
		background.color = Color(0.05, 0.04, 0.07, 1.0)

	var title_label = root.get_node_or_null("TitleLabel")
	if title_label is Label:
		title_label.add_theme_font_size_override("font_size", 36)
		title_label.add_theme_color_override("font_color", IVORY)

	var subtitle_label = root.get_node_or_null("SubtitleLabel")
	if subtitle_label is Label:
		subtitle_label.text = "Campaign-first colony drama with hard choices and fragile victories"
		subtitle_label.add_theme_font_size_override("font_size", 17)
		subtitle_label.add_theme_color_override("font_color", MUTED)

	var status_label = root.get_node_or_null("StatusLabel")
	if status_label is Label:
		status_label.add_theme_font_size_override("font_size", 15)
		status_label.add_theme_color_override("font_color", WARNING)

	var menu = root.get_node_or_null("VBoxContainer")
	if menu is VBoxContainer:
		menu.add_theme_constant_override("separation", 12)
		menu.offset_top = -10.0
		menu.offset_bottom = 110.0

	_style_primary_button(root.get_node_or_null("VBoxContainer/NewGameButton"))
	_style_secondary_button(root.get_node_or_null("VBoxContainer/ContinueButton"))
	_style_secondary_button(root.get_node_or_null("VBoxContainer/QuitButton"))
	_style_primary_button(root.get_node_or_null("CharacterCreation/VBox/ButtonRow/NextButton"), Vector2(124, 40))
	_style_primary_button(root.get_node_or_null("CharacterCreation/VBox/ButtonRow/StartButton"), Vector2(156, 40))
	_style_secondary_button(root.get_node_or_null("CharacterCreation/VBox/ButtonRow/BackStepButton"), Vector2(120, 40))
	_style_secondary_button(root.get_node_or_null("CharacterCreation/VBox/ButtonRow/BackButton"), Vector2(120, 40))
	_style_secondary_button(root.get_node_or_null("CharacterCreation/VBox/IdentitySection/AdvancedToggleButton"), Vector2(220, 36))
	_style_secondary_button(root.get_node_or_null("LoadBrowser/VBox/PlayerRow/RefreshButton"), Vector2(116, 36))
	_style_secondary_button(root.get_node_or_null("LoadBrowser/VBox/ButtonRow/CloseButton"), Vector2(120, 40))

	var creation_panel = root.get_node_or_null("CharacterCreation")
	if creation_panel is Panel:
		creation_panel.add_theme_stylebox_override("panel", _panel_style(PANEL_ALT, 10, ACCENT_SOFT))

	var load_browser = root.get_node_or_null("LoadBrowser")
	if load_browser is Panel:
		load_browser.add_theme_stylebox_override("panel", _panel_style(PANEL_ALT, 10, ACCENT_SOFT))

	_install_title_hero(root)


static func apply_game_session(root: Control) -> void:
	root.theme = _build_theme()
	var background = root.get_node_or_null("Background")
	if background is ColorRect:
		background.color = Color(0.05, 0.05, 0.07, 1.0)

	_style_primary_button(root.get_node_or_null("MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/SendButton"), Vector2(100, 40))
	_style_secondary_button(root.get_node_or_null("MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/QuickSaveButton"), Vector2(126, 40))
	_style_secondary_button(root.get_node_or_null("MainMargin/MainVBox/CommandBar/CommandVBox/InputRow/SavesButton"), Vector2(100, 40))

	var world_pane = root.get_node_or_null("MainMargin/MainVBox/ContentSplit/WorldPane")
	if world_pane is PanelContainer:
		world_pane.add_theme_stylebox_override("panel", _panel_style(Color(0.08, 0.08, 0.10, 0.98), 10, Color(0.33, 0.39, 0.46, 0.90)))

	var sidebar = root.get_node_or_null("MainMargin/MainVBox/ContentSplit/Sidebar")
	if sidebar != null:
		sidebar.add_theme_stylebox_override("panel", _panel_style(PANEL_ALT, 10, ACCENT_SOFT))

	var command_bar = root.get_node_or_null("MainMargin/MainVBox/CommandBar")
	if command_bar is PanelContainer:
		command_bar.add_theme_stylebox_override("panel", _panel_style(PANEL_ALT, 10, ACCENT_SOFT))


static func _install_title_hero(root: Control) -> void:
	if root.get_node_or_null("HeroPanel") != null:
		return

	var hero_panel = PanelContainer.new()
	hero_panel.name = "HeroPanel"
	hero_panel.anchors_preset = Control.PRESET_CENTER_TOP
	hero_panel.anchor_left = 0.5
	hero_panel.anchor_right = 0.5
	hero_panel.offset_left = -260.0
	hero_panel.offset_top = 148.0
	hero_panel.offset_right = 260.0
	hero_panel.offset_bottom = 250.0
	hero_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hero_panel.add_theme_stylebox_override("panel", _panel_style(PANEL_ALT, 12, ACCENT_SOFT))

	var margin = MarginContainer.new()
	margin.anchors_preset = Control.PRESET_FULL_RECT
	margin.offset_left = 16.0
	margin.offset_top = 14.0
	margin.offset_right = -16.0
	margin.offset_bottom = -14.0
	hero_panel.add_child(margin)

	var hero_text = RichTextLabel.new()
	hero_text.name = "HeroText"
	hero_text.bbcode_enabled = true
	hero_text.fit_content = true
	hero_text.scroll_active = false
	hero_text.custom_minimum_size = Vector2(0, 64)
	hero_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hero_text.text = "[b]Campaign-first demo[/b]\nShape a drifter through fear, duty, greed, and nerve.\nCommand a brittle settlement, follow rumors, and push into a world that still wants to swallow you."
	margin.add_child(hero_text)

	root.add_child(hero_panel)
	var menu = root.get_node_or_null("VBoxContainer")
	if menu != null:
		root.move_child(hero_panel, menu.get_index())


static func _build_theme() -> Theme:
	var theme = Theme.new()
	theme.set_stylebox("panel", "Panel", _panel_style(PANEL, 10, ACCENT_SOFT))
	theme.set_stylebox("panel", "PanelContainer", _panel_style(PANEL, 10, ACCENT_SOFT))
	theme.set_stylebox("panel", "ScrollContainer", _panel_style(PANEL, 10, ACCENT_SOFT))

	theme.set_stylebox("normal", "Button", _button_style(Color(0.20, 0.17, 0.20, 0.98), ACCENT_SOFT))
	theme.set_stylebox("hover", "Button", _button_style(Color(0.27, 0.22, 0.23, 0.98), ACCENT))
	theme.set_stylebox("pressed", "Button", _button_style(Color(0.33, 0.25, 0.20, 0.98), ACCENT))
	theme.set_stylebox("disabled", "Button", _button_style(Color(0.14, 0.13, 0.15, 0.80), Color(0.28, 0.27, 0.30, 0.70)))
	theme.set_stylebox("focus", "Button", _focus_style())

	theme.set_stylebox("normal", "LineEdit", _input_style(Color(0.11, 0.10, 0.12, 0.96), ACCENT_SOFT))
	theme.set_stylebox("focus", "LineEdit", _input_style(Color(0.11, 0.10, 0.12, 0.98), ACCENT))
	theme.set_stylebox("read_only", "LineEdit", _input_style(Color(0.11, 0.10, 0.12, 0.80), Color(0.28, 0.27, 0.30, 0.70)))

	theme.set_color("font_color", "Label", IVORY)
	theme.set_color("font_color", "Button", IVORY)
	theme.set_color("font_color_pressed", "Button", IVORY)
	theme.set_color("font_color_hover", "Button", IVORY)
	theme.set_color("font_color_disabled", "Button", MUTED)
	theme.set_color("font_focus_color", "Button", ACCENT)
	theme.set_color("font_color", "LineEdit", IVORY)
	theme.set_color("font_placeholder_color", "LineEdit", MUTED)
	theme.set_color("caret_color", "LineEdit", ACCENT)
	theme.set_color("font_color", "OptionButton", IVORY)
	theme.set_color("font_color_hover", "OptionButton", IVORY)
	theme.set_color("font_color_pressed", "OptionButton", IVORY)
	theme.set_color("font_color_disabled", "OptionButton", MUTED)
	theme.set_color("default_color", "RichTextLabel", IVORY)

	theme.set_font_size("font_size", "Label", 18)
	theme.set_font_size("font_size", "Button", 18)
	theme.set_font_size("font_size", "LineEdit", 18)
	theme.set_font_size("font_size", "OptionButton", 18)
	theme.set_font_size("font_size", "RichTextLabel", 17)

	return theme


static func _style_primary_button(node: Node, minimum_size: Vector2 = Vector2(164, 42)) -> void:
	if not (node is Button):
		return
	var button := node as Button
	button.custom_minimum_size = minimum_size
	button.add_theme_stylebox_override("normal", _button_style(Color(0.25, 0.18, 0.12, 0.98), ACCENT))
	button.add_theme_stylebox_override("hover", _button_style(Color(0.34, 0.23, 0.14, 1.0), ACCENT))
	button.add_theme_stylebox_override("pressed", _button_style(Color(0.41, 0.26, 0.15, 1.0), SUCCESS))
	button.add_theme_stylebox_override("disabled", _button_style(Color(0.15, 0.14, 0.15, 0.76), Color(0.24, 0.23, 0.26, 0.80)))
	button.add_theme_stylebox_override("focus", _focus_style())
	button.add_theme_color_override("font_color", IVORY)
	button.add_theme_font_size_override("font_size", 18)


static func _style_secondary_button(node: Node, minimum_size: Vector2 = Vector2(148, 38)) -> void:
	if not (node is Button):
		return
	var button := node as Button
	button.custom_minimum_size = minimum_size
	button.add_theme_stylebox_override("normal", _button_style(Color(0.16, 0.14, 0.17, 0.96), ACCENT_SOFT))
	button.add_theme_stylebox_override("hover", _button_style(Color(0.20, 0.17, 0.20, 1.0), ACCENT))
	button.add_theme_stylebox_override("pressed", _button_style(Color(0.24, 0.19, 0.18, 1.0), ACCENT))
	button.add_theme_stylebox_override("disabled", _button_style(Color(0.15, 0.14, 0.15, 0.76), Color(0.24, 0.23, 0.26, 0.80)))
	button.add_theme_stylebox_override("focus", _focus_style())
	button.add_theme_color_override("font_color", IVORY)
	button.add_theme_font_size_override("font_size", 17)


static func _panel_style(bg_color: Color, radius: int, border_color: Color) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = bg_color
	style.set_corner_radius_all(radius)
	style.set_border_width_all(1)
	style.border_color = border_color
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.35)
	style.shadow_size = 5
	style.content_margin_left = 12
	style.content_margin_top = 10
	style.content_margin_right = 12
	style.content_margin_bottom = 10
	return style


static func _button_style(bg_color: Color, border_color: Color) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = bg_color
	style.set_corner_radius_all(8)
	style.set_border_width_all(1)
	style.border_color = border_color
	style.content_margin_left = 14
	style.content_margin_top = 8
	style.content_margin_right = 14
	style.content_margin_bottom = 8
	return style


static func _input_style(bg_color: Color, border_color: Color) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = bg_color
	style.set_corner_radius_all(6)
	style.set_border_width_all(1)
	style.border_color = border_color
	style.content_margin_left = 10
	style.content_margin_top = 8
	style.content_margin_right = 10
	style.content_margin_bottom = 8
	return style


static func _focus_style() -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
	style.set_corner_radius_all(9)
	style.set_border_width_all(2)
	style.border_color = ACCENT
	return style
