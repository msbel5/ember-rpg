extends SceneTree

const GameStateScript = preload("res://autoloads/game_state.gd")
const TopicProbeModalScene = preload("res://scenes/components/topic_probe_modal.tscn")
const DialogOverlayScript = preload("res://scripts/ui/dialog_overlay.gd")

var failures: int = 0
var _game_state
var _modal
var _dialog_overlay


func _initialize() -> void:
	await _setup()
	await _test_modal_renders_topic_rows_and_gating()
	await _test_modal_emits_structured_action_for_selected_topic()
	await _test_modal_renders_empty_state_when_no_topics_exist()
	await _test_modal_auto_closes_when_dialog_state_ends()
	await _test_dialog_overlay_opens_modal_with_f4()
	await _cleanup()
	if failures == 0:
		print("Frontend ask-about tests passed.")
	quit(failures)


func _setup() -> void:
	_game_state = root.get_node_or_null("GameState")
	if _game_state == null:
		_game_state = GameStateScript.new()
		_game_state.name = "GameState"
		root.add_child(_game_state)
	await process_frame
	_game_state.reset()
	_game_state.dialog_npc = "Harbor Guard"
	_game_state.dialog_text = "State your business."
	_game_state.dialog_options = [{"text": "Goodbye", "command": "dialog leave_guard", "available": true}]
	_game_state.conversation_state = {
		"npc_id": "guard_1",
		"npc_name": "Harbor Guard",
		"ask_about_topic_ids": [
			{
				"topic_id": "rumor.harbor_work",
				"label": "Harbor Work",
				"subtitle": "Dockhands whisper about open shifts.",
				"category": "rumor",
				"gating": "",
			},
			{
				"topic_id": "lore.barrows",
				"label": "Old Barrows",
				"subtitle": "Ancient graves beyond the ferry road.",
				"category": "lore",
				"gating": "Requires Lore 40",
			},
			"quest.river_patrol",
		],
		"ask_about_selected_topic_id": "rumor.harbor_work",
	}
	_modal = TopicProbeModalScene.instantiate()
	root.add_child(_modal)
	_dialog_overlay = DialogOverlayScript.new()
	root.add_child(_dialog_overlay)
	await process_frame


func _test_modal_renders_topic_rows_and_gating() -> void:
	_modal.open_for_current_dialog()
	await process_frame
	_assert_true(_modal.visible, "Ask About modal opens for the active dialog")
	_assert_true(_modal.topic_list.get_child_count() == 3, "Ask About modal renders exactly three topic rows from conversation state")
	var first_row = _modal.topic_list.get_child(0)
	var second_row = _modal.topic_list.get_child(1)
	_assert_true(first_row is Button and first_row.text.contains("Harbor Work"), "Ask About modal renders the topic label")
	_assert_true(first_row.text.contains("Dockhands whisper"), "Ask About modal renders the topic subtitle")
	_assert_true(first_row.text.contains("RUMOR"), "Ask About modal renders the topic category badge text")
	_assert_true(second_row is Button and second_row.disabled, "Ask About modal disables gated topics")
	_assert_true(str(second_row.tooltip_text).contains("Requires Lore 40"), "Ask About modal exposes gating reason in the tooltip")


func _test_modal_emits_structured_action_for_selected_topic() -> void:
	var actions: Array = []
	var selections: Array = []
	_modal.topic_selected_changed.connect(func(topic_id: String) -> void:
		selections.append(topic_id)
	, CONNECT_ONE_SHOT)
	_modal.structured_action_requested.connect(func(shortcut: String, args: Dictionary, history_text: String) -> void:
		actions.append({"shortcut": shortcut, "args": args.duplicate(true), "history_text": history_text})
	, CONNECT_ONE_SHOT)
	_modal._move_selection(1)
	await process_frame
	_assert_true(not selections.is_empty() and selections[-1] == "quest.river_patrol", "Ask About keyboard navigation skips gated topics and updates selection")
	var enter := InputEventKey.new()
	enter.pressed = true
	enter.keycode = KEY_ENTER
	_modal._gui_input(enter)
	await process_frame
	var action: Dictionary = actions[-1] if not actions.is_empty() else {}
	_assert_true(action.get("shortcut", "") == "dialog", "Ask About confirm emits the dialog structured shortcut")
	_assert_true(action.get("args", {}).get("action_id", "") == "ask_about", "Ask About confirm emits dialog ask_about action_id")
	_assert_true(action.get("args", {}).get("topic_id", "") == "quest.river_patrol", "Ask About confirm keeps the selected canonical topic id")
	_assert_true(not _modal.visible, "Ask About modal closes after submit")


func _test_modal_renders_empty_state_when_no_topics_exist() -> void:
	_game_state.conversation_state["ask_about_topic_ids"] = []
	_modal.open_for_current_dialog()
	await process_frame
	_assert_true(_modal.topic_list.get_child_count() == 1, "Ask About modal renders a single empty-state row when no topics are available")
	var empty_row = _modal.topic_list.get_child(0)
	_assert_true(empty_row is Button and empty_row.disabled, "Ask About empty-state row is visibly disabled")
	_assert_true(empty_row.text.contains("No deterministic ask-about topics"), "Ask About empty-state row explains why the list is empty")
	_modal.hide_modal()
	await process_frame
	_game_state.conversation_state["ask_about_topic_ids"] = [
		{
			"topic_id": "rumor.harbor_work",
			"label": "Harbor Work",
			"subtitle": "Dockhands whisper about open shifts.",
			"category": "rumor",
			"gating": "",
		}
	]


func _test_modal_auto_closes_when_dialog_state_ends() -> void:
	_modal.open_for_current_dialog()
	await process_frame
	_game_state.dialog_npc = ""
	_game_state.dialog_text = ""
	_game_state.dialog_options = []
	_game_state.conversation_state = {}
	_game_state.dialog_state_changed.emit({})
	await process_frame
	_assert_true(not _modal.visible, "Ask About modal auto-closes when dialog state ends")
	_game_state.dialog_npc = "Harbor Guard"
	_game_state.dialog_text = "State your business."
	_game_state.dialog_options = [{"text": "Goodbye", "command": "dialog leave_guard", "available": true}]
	_game_state.conversation_state = {
		"npc_id": "guard_1",
		"npc_name": "Harbor Guard",
		"ask_about_topic_ids": ["rumor.harbor_work"],
		"ask_about_selected_topic_id": "rumor.harbor_work",
	}


func _test_dialog_overlay_opens_modal_with_f4() -> void:
	_dialog_overlay.show_dialog("Harbor Guard", "State your business.", _game_state.dialog_options)
	await process_frame
	var f4 := InputEventKey.new()
	f4.pressed = true
	f4.keycode = KEY_F4
	_dialog_overlay._unhandled_key_input(f4)
	await process_frame
	var topic_modal = _dialog_overlay.get_node_or_null("TopicProbeModal")
	_assert_true(topic_modal != null and topic_modal.visible, "Dialog overlay opens the Ask About modal from the F4 hotkey")


func _cleanup() -> void:
	if _dialog_overlay != null:
		_dialog_overlay.queue_free()
	if _modal != null:
		_modal.queue_free()
	await process_frame


func _assert_true(condition: bool, message: String) -> void:
	if condition:
		print("PASS: %s" % message)
		return
	failures += 1
	push_error("FAIL: %s" % message)