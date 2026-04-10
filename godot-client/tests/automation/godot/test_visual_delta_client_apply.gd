extends SceneTree

const GameStateScript = preload("res://autoloads/game_state.gd")

var failures: int = 0
var _game_state


func _initialize() -> void:
	await _setup()
	_test_apply_visual_delta_updates_world_entities_and_grouped_entities()
	await _cleanup()
	if failures == 0:
		print("Visual delta client apply tests passed.")
	quit(failures)


func _setup() -> void:
	_game_state = GameStateScript.new()
	_game_state.name = "GameState"
	root.add_child(_game_state)
	await process_frame
	_game_state.world_entities = [
		{
			"id": "npc_ambient",
			"entity_type": "npc",
			"entity_kind": "npc",
			"name": "Ambient NPC",
			"position": [2, 2],
			"role": "resident",
			"context_actions": ["talk", "examine"],
			"facing": "south",
			"state": "stand",
		}
	]
	_game_state.entities = _game_state._group_world_entities(_game_state.world_entities)


func _test_apply_visual_delta_updates_world_entities_and_grouped_entities() -> void:
	_game_state.apply_visual_delta(
		{
			"type": "visual_delta",
			"tick_index": 3,
			"actors": [
				{"id": "npc_ambient", "position": [4, 5], "facing": "east", "state": "walk"}
			],
		}
	)
	var raw_entry = _game_state.world_entities[0]
	_assert_true(raw_entry["position"] == [4, 5], "visual delta updates raw world_entities position")
	_assert_true(str(raw_entry.get("facing", "")) == "east", "visual delta updates raw world_entities facing")
	_assert_true(str(raw_entry.get("state", "")) == "walk", "visual delta updates raw world_entities state")
	var grouped_npcs: Array = _game_state.entities.get("npcs", [])
	_assert_true(grouped_npcs.size() == 1, "grouped NPC bucket remains populated")
	_assert_true(grouped_npcs[0]["position"] == [4, 5], "visual delta refreshes grouped entity position")
	_assert_true(str(grouped_npcs[0].get("facing", "")) == "east", "visual delta refreshes grouped entity facing")
	_assert_true(str(grouped_npcs[0].get("state", "")) == "walk", "visual delta refreshes grouped entity state")


func _cleanup() -> void:
	if _game_state != null:
		_game_state.queue_free()
	await process_frame


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)
