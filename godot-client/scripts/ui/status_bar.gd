extends PanelContainer
class_name GameStatusBar

@onready var player_info: Label = $StatusRow/PlayerInfo
@onready var hp_bar: ProgressBar = $StatusRow/HPBar
@onready var hp_label: Label = $StatusRow/HPLabel
@onready var sp_bar: ProgressBar = $StatusRow/SPBar
@onready var sp_label: Label = $StatusRow/SPLabel
@onready var xp_bar: ProgressBar = $StatusRow/XPBar
@onready var ap_label: Label = $StatusRow/APLabel
@onready var location_label: Label = $StatusRow/LocationLabel


func _ready() -> void:
	GameState.state_updated.connect(_refresh)
	GameState.settlement_updated.connect(_on_settlement_updated)
	GameState.map_loaded.connect(_on_map_loaded)
	GameState.scene_changed.connect(_on_scene_changed)
	_refresh()


func _refresh() -> void:
	var player = GameState.player
	if player.is_empty():
		player_info.text = "No active hero"
		location_label.text = "Unknown"
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
	hp_label.text = "%d/%d" % [hp, max_hp]

	var spell_points = int(player.get("spell_points", player.get("sp", 0)))
	var max_spell_points = maxi(int(player.get("max_spell_points", player.get("max_sp", 1))), 1)
	sp_bar.max_value = max_spell_points
	sp_bar.value = spell_points
	sp_label.text = "%d/%d" % [spell_points, max_spell_points]

	xp_bar.max_value = 100
	xp_bar.value = int(player.get("xp", 0)) % 100

	var ap_payload = player.get("ap", null)
	var action_points = int(player.get("action_points", 0))
	var max_action_points = int(player.get("max_action_points", player.get("max_ap", 0)))
	if ap_payload is Dictionary:
		action_points = int(ap_payload.get("current", action_points))
		max_action_points = int(ap_payload.get("max", max_action_points))
	elif ap_payload != null:
		action_points = int(ap_payload)
	max_action_points = maxi(max_action_points, 0)
	if max_action_points > 0:
		ap_label.text = "AP %d/%d" % [action_points, max_action_points]
	else:
		ap_label.text = "Scene %s" % GameState.scene.capitalize()

	var display_location = GameState.get_display_location()
	if display_location == "Unknown" and not GameState.settlement_state.is_empty():
		display_location = str(GameState.settlement_state.get("name", "Unknown"))
	location_label.text = display_location
	location_label.queue_redraw()


func _on_map_loaded(_map_data: Dictionary) -> void:
	call_deferred("_refresh")


func _on_scene_changed(_new_scene: String) -> void:
	call_deferred("_refresh")


func _on_settlement_updated(_settlement: Dictionary) -> void:
	call_deferred("_refresh")
