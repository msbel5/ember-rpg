extends PanelContainer
class_name GameStatusBar

const HP_BAR_TEXTURE := preload("res://assets/ui/hp_bar.png")
const SP_BAR_TEXTURE := preload("res://assets/ui/sp_bar.png")
const XP_BAR_TEXTURE := preload("res://assets/ui/xp_bar.png")

@onready var player_info: Label = $StatusRow/PlayerInfo
@onready var hp_bar: ProgressBar = $StatusRow/HPBar
@onready var hp_label: Label = $StatusRow/HPLabel
@onready var sp_bar: ProgressBar = $StatusRow/SPBar
@onready var sp_label: Label = $StatusRow/SPLabel
@onready var xp_bar: ProgressBar = $StatusRow/XPBar
@onready var ap_label: Label = $StatusRow/APLabel
@onready var location_label: Label = $StatusRow/LocationLabel


func _ready() -> void:
	_apply_visual_state()
	GameState.state_updated.connect(_refresh)
	GameState.settlement_updated.connect(_on_settlement_updated)
	GameState.map_loaded.connect(_on_map_loaded)
	GameState.scene_changed.connect(_on_scene_changed)
	_refresh()


func _refresh() -> void:
	var player = GameState.player
	if player.is_empty():
		player_info.text = "No active hero"
		location_label.text = "No live survey"
		ap_label.text = "Turn idle"
		return

	var player_name = str(player.get("name", "Unknown"))
	var level = int(player.get("level", 1))
	var player_class_name = "Adventurer"
	if player.has("classes") and player["classes"] is Dictionary and not player["classes"].is_empty():
		player_class_name = str(player["classes"].keys()[0]).capitalize()
	elif player.has("player_class"):
		player_class_name = str(player["player_class"]).capitalize()
	player_info.text = "%s  Lv.%d %s" % [player_name, level, player_class_name]

	var hp = int(player.get("hp", 0))
	var max_hp = maxi(int(player.get("max_hp", 1)), 1)
	hp_bar.max_value = max_hp
	hp_bar.value = hp
	hp_label.text = "HP %d/%d" % [hp, max_hp]

	var spell_points = int(player.get("spell_points", player.get("sp", 0)))
	var max_spell_points = maxi(int(player.get("max_spell_points", player.get("max_sp", 1))), 1)
	sp_bar.max_value = max_spell_points
	sp_bar.value = spell_points
	sp_label.text = "SP %d/%d" % [spell_points, max_spell_points]

	xp_bar.max_value = 100
	xp_bar.value = int(player.get("xp", 0)) % 100

	ap_label.text = _build_turn_summary(player)

	var display_location = GameState.get_display_location()
	if display_location == "Unknown" and not GameState.settlement_state.is_empty():
		display_location = str(GameState.settlement_state.get("name", "Unknown"))
	location_label.text = "%s  |  %s" % [display_location, GameState.scene.capitalize()]
	location_label.queue_redraw()


func _apply_visual_state() -> void:
	player_info.add_theme_font_size_override("font_size", 19)
	player_info.add_theme_color_override("font_color", Color(0.96, 0.92, 0.86))
	hp_label.add_theme_color_override("font_color", Color(0.96, 0.80, 0.76))
	sp_label.add_theme_color_override("font_color", Color(0.78, 0.90, 0.98))
	ap_label.add_theme_color_override("font_color", Color(0.92, 0.78, 0.42))
	location_label.add_theme_color_override("font_color", Color(0.82, 0.80, 0.74))
	_apply_bar_style(hp_bar, HP_BAR_TEXTURE)
	_apply_bar_style(sp_bar, SP_BAR_TEXTURE)
	_apply_bar_style(xp_bar, XP_BAR_TEXTURE)


func _apply_bar_style(bar: ProgressBar, texture: Texture2D) -> void:
	var fill = StyleBoxTexture.new()
	fill.texture = texture
	fill.texture_margin_left = 12.0
	fill.texture_margin_top = 10.0
	fill.texture_margin_right = 12.0
	fill.texture_margin_bottom = 10.0
	fill.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT
	fill.axis_stretch_vertical = StyleBoxTexture.AXIS_STRETCH_MODE_TILE_FIT

	var background = StyleBoxFlat.new()
	background.bg_color = Color(0.07, 0.07, 0.09, 0.96)
	background.set_corner_radius_all(7)
	background.set_border_width_all(1)
	background.border_color = Color(0.22, 0.21, 0.24, 0.92)
	background.content_margin_left = 3.0
	background.content_margin_top = 3.0
	background.content_margin_right = 3.0
	background.content_margin_bottom = 3.0

	bar.add_theme_stylebox_override("fill", fill)
	bar.add_theme_stylebox_override("background", background)


func _on_map_loaded(_map_data: Dictionary) -> void:
	call_deferred("_refresh")


func _on_scene_changed(_new_scene: String) -> void:
	call_deferred("_refresh")


func _on_settlement_updated(_settlement: Dictionary) -> void:
	call_deferred("_refresh")


func _build_turn_summary(player: Dictionary) -> String:
	var turn_resources: Dictionary = player.get("turn_resources", {})
	if turn_resources.is_empty():
		return "Turn idle"
	var action_text = "Act ready" if bool(turn_resources.get("action_available", false)) else "Act spent"
	var bonus_text = "Bonus ready" if bool(turn_resources.get("bonus_action_available", false)) else "Bonus spent"
	var reaction_text = "React ready" if bool(turn_resources.get("reaction_available", false)) else "React spent"
	return "%s  |  %s  |  %s  |  Move %d/%d" % [
		action_text,
		bonus_text,
		reaction_text,
		int(turn_resources.get("movement_remaining", 0)),
		int(turn_resources.get("speed", 0)),
	]
