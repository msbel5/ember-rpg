extends Control
class_name TitleMenu

signal new_game_requested()
signal continue_requested()
signal load_requested()
signal quit_requested()

const IVORY := Color(0.95, 0.93, 0.88)
const MUTED := Color(0.72, 0.67, 0.61)
const GOLD := Color(0.82, 0.66, 0.38)
const BRONZE := Color(0.39, 0.28, 0.18, 0.92)
const PANEL := Color(0.10, 0.09, 0.12, 0.95)
const PANEL_SOFT := Color(0.14, 0.12, 0.16, 0.96)

var _new_game_button: Button
var _continue_button: Button
var _load_button: Button
var _guide_button: Button
var _quit_button: Button
var _resume_hint: Label
var _guide_panel: PanelContainer
var _guide_body: RichTextLabel
var _status_card: RichTextLabel
var _guide_open := false


func _ready() -> void:
	anchors_preset = Control.PRESET_FULL_RECT
	mouse_filter = Control.MOUSE_FILTER_STOP
	_cache_nodes()
	_apply_static_styling()


func set_continue_enabled(enabled: bool, last_save_id: String = "", player_id: String = "") -> void:
	if _continue_button == null:
		return
	_continue_button.disabled = not enabled
	if enabled:
		var summary := ""
		if not last_save_id.strip_edges().is_empty():
			summary = "Resume %s" % last_save_id
		elif not player_id.strip_edges().is_empty():
			summary = "Resume saves for %s" % player_id
		else:
			summary = "Resume the last frontier chronicle."
		_resume_hint.text = summary
	else:
		_resume_hint.text = "No trusted chronicle is ready to resume yet."
	_refresh_status_card(enabled, last_save_id, player_id)


func focus_default() -> void:
	if _continue_button != null and not _continue_button.disabled:
		_continue_button.grab_focus()
	elif _new_game_button != null:
		_new_game_button.grab_focus()


func _cache_nodes() -> void:
	_continue_button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/ContinueButton")
	_new_game_button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/NewGameButton")
	_load_button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/LoadButton")
	_guide_button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/GuideButton")
	_quit_button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/QuitButton")
	_resume_hint = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/ResumeHint")
	_guide_panel = get_node_or_null("FrontDoor/RootSplit/MenuColumn/GuidePanel")
	_guide_body = get_node_or_null("FrontDoor/RootSplit/MenuColumn/GuidePanel/GuideMargin/GuideVBox/GuideBody")
	_status_card = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel/SceneMargin/SceneVBox/StatusCard")

	if _continue_button != null and not _continue_button.pressed.is_connected(_emit_continue_requested):
		_continue_button.pressed.connect(_emit_continue_requested)
	if _new_game_button != null and not _new_game_button.pressed.is_connected(_emit_new_game_requested):
		_new_game_button.pressed.connect(_emit_new_game_requested)
	if _load_button != null and not _load_button.pressed.is_connected(_emit_load_requested):
		_load_button.pressed.connect(_emit_load_requested)
	if _guide_button != null and not _guide_button.pressed.is_connected(_toggle_guide):
		_guide_button.pressed.connect(_toggle_guide)
	if _quit_button != null and not _quit_button.pressed.is_connected(_emit_quit_requested):
		_quit_button.pressed.connect(_emit_quit_requested)


func _apply_static_styling() -> void:
	var front_door: MarginContainer = get_node_or_null("FrontDoor")
	if front_door != null:
		front_door.anchors_preset = Control.PRESET_FULL_RECT
		front_door.add_theme_constant_override("margin_left", 72)
		front_door.add_theme_constant_override("margin_top", 52)
		front_door.add_theme_constant_override("margin_right", 72)
		front_door.add_theme_constant_override("margin_bottom", 52)

	var root_split: HBoxContainer = get_node_or_null("FrontDoor/RootSplit")
	if root_split != null:
		root_split.add_theme_constant_override("separation", 28)

	var lore_column: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn")
	if lore_column != null:
		lore_column.add_theme_constant_override("separation", 18)

	var crest_panel: PanelContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel")
	if crest_panel != null:
		crest_panel.add_theme_stylebox_override("panel", _panel_style(PANEL, 18, Color(0.33, 0.24, 0.16, 0.95)))

	var crest_margin: MarginContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin")
	if crest_margin != null:
		crest_margin.add_theme_constant_override("margin_left", 28)
		crest_margin.add_theme_constant_override("margin_top", 26)
		crest_margin.add_theme_constant_override("margin_right", 28)
		crest_margin.add_theme_constant_override("margin_bottom", 26)

	var crest_vbox: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox")
	if crest_vbox != null:
		crest_vbox.add_theme_constant_override("separation", 18)

	var title_block: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/TitleBlock")
	if title_block != null:
		title_block.add_theme_constant_override("separation", 8)

	var overline: Label = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/TitleBlock/OverlineLabel")
	if overline != null:
		overline.text = "ASH CHRONICLE AUTHORITY"
		overline.add_theme_font_size_override("font_size", 14)
		overline.add_theme_color_override("font_color", GOLD)

	var title_label: Label = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/TitleBlock/TitleLabel")
	if title_label != null:
		title_label.text = "EMBER RPG"
		title_label.add_theme_font_size_override("font_size", 46)
		title_label.add_theme_color_override("font_color", IVORY)

	var subtitle_label: Label = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/TitleBlock/SubtitleLabel")
	if subtitle_label != null:
		subtitle_label.text = "Deterministic frontier chronicle. Built for rumor, consequence, and hard travel."
		subtitle_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		subtitle_label.add_theme_font_size_override("font_size", 18)
		subtitle_label.add_theme_color_override("font_color", MUTED)

	var scene_panel: PanelContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel")
	if scene_panel != null:
		scene_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.13, 0.11, 0.14, 0.98), 16, BRONZE))

	var scene_margin: MarginContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel/SceneMargin")
	if scene_margin != null:
		scene_margin.add_theme_constant_override("margin_left", 20)
		scene_margin.add_theme_constant_override("margin_top", 18)
		scene_margin.add_theme_constant_override("margin_right", 20)
		scene_margin.add_theme_constant_override("margin_bottom", 18)

	var scene_vbox: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel/SceneMargin/SceneVBox")
	if scene_vbox != null:
		scene_vbox.add_theme_constant_override("separation", 12)

	var herald: Label = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel/SceneMargin/SceneVBox/Herald")
	if herald != null:
		herald.text = "Tonight's Front"
		herald.add_theme_font_size_override("font_size", 16)
		herald.add_theme_color_override("font_color", GOLD)

	var scene_text: RichTextLabel = get_node_or_null("FrontDoor/RootSplit/LoreColumn/CrestPanel/CrestMargin/CrestVBox/ScenePanel/SceneMargin/SceneVBox/SceneText")
	if scene_text != null:
		scene_text.bbcode_enabled = true
		scene_text.fit_content = true
		scene_text.scroll_active = false
		scene_text.custom_minimum_size = Vector2(0, 180)
		scene_text.text = "[b]The ashlands are not dead.[/b]\n" + \
			"Forts bargain with hunger, harbor guilds sell rumor like grain, and every oath carries a cost.\n\n" + \
			"Start a new chronicle to shape a drifter, follow leads, bargain with frightened towns, and carry your choices into combat, travel, and conversation."

	if _status_card != null:
		_status_card.bbcode_enabled = true
		_status_card.fit_content = true
		_status_card.scroll_active = false

	var menu_column: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn")
	if menu_column != null:
		menu_column.custom_minimum_size = Vector2(420, 0)
		menu_column.add_theme_constant_override("separation", 18)

	var menu_panel: PanelContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel")
	if menu_panel != null:
		menu_panel.add_theme_stylebox_override("panel", _panel_style(PANEL_SOFT, 18, GOLD))

	var menu_margin: MarginContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin")
	if menu_margin != null:
		menu_margin.add_theme_constant_override("margin_left", 24)
		menu_margin.add_theme_constant_override("margin_top", 22)
		menu_margin.add_theme_constant_override("margin_right", 24)
		menu_margin.add_theme_constant_override("margin_bottom", 22)

	var menu_vbox: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox")
	if menu_vbox != null:
		menu_vbox.add_theme_constant_override("separation", 14)

	var menu_heading: Label = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/MenuHeading")
	if menu_heading != null:
		menu_heading.text = "Chronicle Access"
		menu_heading.add_theme_font_size_override("font_size", 24)
		menu_heading.add_theme_color_override("font_color", IVORY)

	if _resume_hint != null:
		_resume_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_resume_hint.add_theme_color_override("font_color", MUTED)

	for button_name in [
		"ContinueButton",
		"NewGameButton",
		"LoadButton",
		"GuideButton",
		"QuitButton",
	]:
		var button: Button = get_node_or_null("FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/%s" % button_name)
		if button == null:
			continue
		var is_primary: bool = button_name == "ContinueButton"
		button.custom_minimum_size = Vector2(0, 58)
		button.focus_mode = Control.FOCUS_ALL
		button.add_theme_font_size_override("font_size", 18)
		button.add_theme_stylebox_override("normal", _button_style(is_primary))
		button.add_theme_stylebox_override("hover", _button_style(is_primary, true))
		button.add_theme_stylebox_override("pressed", _button_style(is_primary, true, true))
		button.add_theme_stylebox_override("focus", _focus_style())

	if _guide_panel != null:
		_guide_panel.visible = _guide_open
		_guide_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.11, 0.10, 0.12, 0.98), 16, Color(0.28, 0.34, 0.40, 0.95)))

	var guide_margin: MarginContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn/GuidePanel/GuideMargin")
	if guide_margin != null:
		guide_margin.add_theme_constant_override("margin_left", 20)
		guide_margin.add_theme_constant_override("margin_top", 18)
		guide_margin.add_theme_constant_override("margin_right", 20)
		guide_margin.add_theme_constant_override("margin_bottom", 18)

	var guide_vbox: VBoxContainer = get_node_or_null("FrontDoor/RootSplit/MenuColumn/GuidePanel/GuideMargin/GuideVBox")
	if guide_vbox != null:
		guide_vbox.add_theme_constant_override("separation", 10)

	var guide_title: Label = get_node_or_null("FrontDoor/RootSplit/MenuColumn/GuidePanel/GuideMargin/GuideVBox/GuideTitle")
	if guide_title != null:
		guide_title.text = "Field Guide"
		guide_title.add_theme_font_size_override("font_size", 22)

	if _guide_body != null:
		_guide_body.bbcode_enabled = true
		_guide_body.fit_content = true
		_guide_body.scroll_active = false
		_guide_body.text = "[b]This build is deterministic first.[/b]\n" + \
			"Travel, combat, trade, dialog, Ask About, Consult Fate, and Think all consume backend truth.\n\n" + \
			"[b]Controls[/b]\n" + \
			"Left click  focus / talk    Right click  move or open context\n" + \
			"I  items    C  dossier    M  map    J  journal    O  menu    ESC  close surface\n\n" + \
			"[b]Frontier promise[/b]\n" + \
			"The world is meant to feel authored enough for Baldur's Gate-style choices, but strict enough to support later isometric or billboard renderers without changing the simulation.\n\n" + \
			"[b]Asset credits[/b]\n" + \
			"Active terrain and prop tiles use the bundled Pixel Crawler Free Pack terms in assets/third_party/pixel_crawler/TERMS.txt. LPC town tiles remain bundled as fallback support in assets/third_party/lpc/LICENSE.TXT."

	_refresh_status_card(false, "", "")


func _emit_new_game_requested() -> void:
	new_game_requested.emit()


func _emit_continue_requested() -> void:
	continue_requested.emit()


func _emit_load_requested() -> void:
	load_requested.emit()


func _emit_quit_requested() -> void:
	quit_requested.emit()


func _toggle_guide() -> void:
	_guide_open = not _guide_open
	_guide_panel.visible = _guide_open
	_guide_button.text = "Hide Guide" if _guide_open else "Field Guide"


func _refresh_status_card(can_continue: bool, last_save_id: String, player_id: String) -> void:
	if _status_card == null:
		return
	if can_continue:
		var target := last_save_id if not last_save_id.is_empty() else player_id
		_status_card.text = "[b]Ready signal[/b]\nA previous chronicle is on record: %s" % target
	else:
		_status_card.text = "[b]Ready signal[/b]\nNo standing chronicle on this machine. Start a new one or open the load ledger."


func _panel_style(color_value: Color, radius: int, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color_value
	style.set_corner_radius_all(radius)
	style.set_border_width_all(1)
	style.border_color = border
	style.shadow_color = Color(0.0, 0.0, 0.0, 0.34)
	style.shadow_size = 8
	style.content_margin_left = 12
	style.content_margin_top = 12
	style.content_margin_right = 12
	style.content_margin_bottom = 12
	return style


func _button_style(primary: bool, hovered: bool = false, pressed: bool = false) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	if primary:
		style.bg_color = Color(0.29, 0.20, 0.12, 0.98) if not hovered else Color(0.36, 0.24, 0.14, 1.0)
	else:
		style.bg_color = Color(0.17, 0.14, 0.18, 0.98) if not hovered else Color(0.21, 0.17, 0.20, 1.0)
	if pressed:
		style.bg_color = Color(0.44, 0.28, 0.16, 1.0) if primary else Color(0.24, 0.18, 0.17, 1.0)
	style.set_corner_radius_all(10)
	style.set_border_width_all(1)
	style.border_color = GOLD if primary else Color(0.40, 0.32, 0.22, 0.92)
	style.content_margin_left = 18
	style.content_margin_top = 14
	style.content_margin_right = 18
	style.content_margin_bottom = 14
	return style


func _focus_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
	style.set_corner_radius_all(12)
	style.set_border_width_all(2)
	style.border_color = GOLD
	return style
