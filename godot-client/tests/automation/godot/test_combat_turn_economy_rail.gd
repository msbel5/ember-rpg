extends SceneTree

const InstrumentRailScene = preload("res://scenes/components/instrument_rail.tscn")

var failures: int = 0
var _game_state
var _rail


func _initialize() -> void:
	await _setup()
	await _test_combat_strip_renders_turn_economy_surface()
	await _test_combat_strip_hides_outside_combat()
	await _cleanup()
	if failures == 0:
		print("Combat turn economy rail tests passed.")
	quit(failures)


func _setup() -> void:
	_game_state = root.get_node_or_null("GameState")
	_assert_true(_game_state != null, "GameState autoload is available for combat rail test")
	if _game_state != null and _game_state.has_method("reset"):
		_game_state.reset()
	_rail = InstrumentRailScene.instantiate()
	root.add_child(_rail)
	await process_frame


func _test_combat_strip_renders_turn_economy_surface() -> void:
	_game_state.scene = "combat"
	_game_state.combat_state = {
		"round": 2,
		"turn_actor_id": "player",
		"ended": false,
		"combatants": [
			{
				"actor_id": "player",
				"name": "Chaos",
				"is_player": true,
				"alive": true,
				"initiative": 17,
				"turn_resources": {
					"action_available": false,
					"bonus_action_available": true,
					"reaction_available": false,
					"movement_remaining": 2,
					"speed": 6,
				},
				"combat_info": {
					"in_combat": true,
					"initiative": 17,
					"action_available": false,
					"bonus_action_available": true,
					"reaction_available": false,
					"movement_remaining": 2,
				},
			}
		],
	}
	_game_state.state_updated.emit()
	_rail._refresh_monitor()
	await process_frame
	var combat_strip = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip")
	var initiative_label = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatTopRow/CombatInitiativeLabel")
	var action_badge = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatTopRow/ActionBadge")
	var bonus_badge = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatTopRow/BonusBadge")
	var reaction_badge = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatTopRow/ReactionBadge")
	var movement_label = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatMoveRow/MovementLabel")
	var movement_bar = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip/CombatMoveRow/MovementBar")
	_assert_true(combat_strip.visible, "Instrument rail shows combat strip while shell mode is combat")
	_assert_true(initiative_label.text.contains("17"), "Instrument rail surfaces initiative number")
	_assert_true(action_badge.text.contains("spent"), "Instrument rail shows spent action badge state")
	_assert_true(bonus_badge.text.contains("ready"), "Instrument rail shows ready bonus badge state")
	_assert_true(reaction_badge.text.contains("spent"), "Instrument rail shows spent reaction badge state")
	_assert_true(movement_label.text.contains("2/6"), "Instrument rail shows movement remaining summary")
	_assert_true(int(movement_bar.value) == 2 and int(movement_bar.max_value) == 6, "Instrument rail updates movement progress bar")


func _test_combat_strip_hides_outside_combat() -> void:
	_game_state.scene = "exploration"
	_game_state.combat_state = {}
	_game_state.state_updated.emit()
	_rail._refresh_monitor()
	await process_frame
	var combat_strip = _rail.get_node("RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/CombatStrip")
	_assert_true(not combat_strip.visible, "Instrument rail hides combat strip outside combat")


func _cleanup() -> void:
	if _rail != null:
		_rail.queue_free()
	if _game_state != null and _game_state.has_method("reset"):
		_game_state.reset()
	await process_frame


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)
