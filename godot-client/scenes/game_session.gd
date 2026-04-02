extends Control

const ScreenshotCapture = preload("res://scripts/ui/screenshot_capture.gd")
# ResponseNormalizer, EmberTheme, ProfileStorage, StatusBarWidget,
# DialogOverlay, CombatOverlay, SessionSaveSync, SessionWorldSync
# are all available globally via class_name — no preload needed.

const PROFILE_PATH := ProfileStorage.PROFILE_PATH
const QUICKSAVE_SLOT := "quicksave"

@onready var world_view = $MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer
@onready var sidebar_nav: HBoxContainer = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarNav
@onready var sidebar_tabs: TabContainer = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs
@onready var narrative_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs/NarrativePanel
@onready var inventory_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs/InventoryPanel
@onready var settlement_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs/SettlementPanel
@onready var minimap_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs/MinimapPanel
@onready var command_bar = $MainMargin/MainVBox/CommandBar
@onready var quest_panel = $MainMargin/MainVBox/ContentSplit/Sidebar/SidebarTabs/QuestPanel
@onready var save_load_panel = $OverlayCanvas/SaveLoadPanel

var is_waiting := false
var _pending_sync_callbacks := 0
var _sidebar_button_group: ButtonGroup = ButtonGroup.new()
var _sidebar_buttons: Dictionary = {}
var _dialog_overlay = null
var _combat_overlay_widget = null
var _save_sync
var _world_sync
var _queued_world_commands: Array[String] = []


func _ready() -> void:
	_save_sync = SessionSaveSync.new(self)
	_world_sync = SessionWorldSync.new(self)
	EmberTheme.apply_game_session(self)
	_install_status_bar()
	_install_dialog_overlay()
	_install_combat_overlay()
	_setup_sidebar_tabs()
	if GameState.has_active_campaign():
		sidebar_tabs.current_tab = 5

	command_bar.command_submitted.connect(_submit_action)
	command_bar.quick_save_requested.connect(_save_sync.on_quick_save_requested)
	command_bar.saves_requested.connect(_save_sync.open_save_load_panel)
	world_view.command_requested.connect(_on_world_command_requested)
	world_view.command_sequence_requested.connect(_on_world_command_sequence_requested)
	world_view.focus_changed.connect(command_bar.set_focus_summary)
	world_view.focus_actions_changed.connect(command_bar.set_focus_actions)
	inventory_panel.command_requested.connect(_submit_action)
	settlement_panel.command_requested.connect(_submit_action)
	minimap_panel.travel_requested.connect(_on_world_graph_travel_requested)
	quest_panel.command_requested.connect(_submit_action)
	save_load_panel.save_requested.connect(_save_sync.on_save_requested)
	save_load_panel.load_requested.connect(_save_sync.on_load_requested)
	save_load_panel.delete_requested.connect(_save_sync.on_delete_save_requested)
	save_load_panel.refresh_requested.connect(_save_sync.refresh_save_list)
	save_load_panel.closed.connect(_save_sync.on_save_load_closed)

	GameState.state_updated.connect(_on_state_updated)
	GameState.combat_started.connect(_on_combat_started)
	GameState.combat_ended.connect(_on_combat_ended)
	GameState.level_up_occurred.connect(_on_level_up)
	Backend.request_error.connect(_on_backend_error)

	_save_sync.remember_player_id()
	_world_sync.initialize_runtime()
	command_bar.set_focus_summary(world_view.get_focus_summary())
	command_bar.set_focus_actions(world_view.get_focus_actions())
	command_bar.focus_input()


func _install_status_bar() -> void:
	var main_vbox = $MainMargin/MainVBox
	if main_vbox == null:
		return
	var status_bar := StatusBarWidget.new()
	main_vbox.add_child(status_bar)
	main_vbox.move_child(status_bar, 0)


func _install_dialog_overlay() -> void:
	_dialog_overlay = DialogOverlay.new()
	var world_pane = $MainMargin/MainVBox/ContentSplit/WorldPane
	if world_pane != null:
		world_pane.add_child(_dialog_overlay)
		_dialog_overlay.command_requested.connect(_submit_action)


func _install_combat_overlay() -> void:
	_combat_overlay_widget = CombatOverlay.new()
	var overlay_canvas = $OverlayCanvas
	var world_pane = $MainMargin/MainVBox/ContentSplit/WorldPane
	if overlay_canvas != null:
		overlay_canvas.add_child(_combat_overlay_widget)
	if _combat_overlay_widget != null and world_pane != null and _combat_overlay_widget.has_method("attach_to_surface"):
		_combat_overlay_widget.attach_to_surface(world_pane)
		_combat_overlay_widget.command_requested.connect(_submit_action)


func _setup_sidebar_tabs() -> void:
	var tab_titles := {
		"NarrativePanel": "Narrative",
		"CharacterPanel": "Hero",
		"SettlementPanel": "Town",
		"QuestPanel": "Quests",
		"InventoryPanel": "Items",
		"MinimapPanel": "Map",
	}
	for child in sidebar_nav.get_children():
		child.queue_free()
	sidebar_tabs.tabs_visible = false
	for index in range(sidebar_tabs.get_tab_count()):
		var child = sidebar_tabs.get_tab_control(index)
		if child != null and tab_titles.has(child.name):
			var title := str(tab_titles[child.name])
			sidebar_tabs.set_tab_title(index, title)
			var button := Button.new()
			button.name = "%sTabButton" % child.name
			button.toggle_mode = true
			button.button_group = _sidebar_button_group
			button.text = title
			button.tooltip_text = "%s panel" % title
			button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			button.pressed.connect(_on_sidebar_tab_button_pressed.bind(index))
			sidebar_nav.add_child(button)
			_sidebar_buttons[index] = button
	if _sidebar_buttons.has(sidebar_tabs.current_tab):
		(_sidebar_buttons[sidebar_tabs.current_tab] as Button).button_pressed = true
	sidebar_tabs.tab_changed.connect(_on_sidebar_tab_changed)


func _on_sidebar_tab_button_pressed(index: int) -> void:
	sidebar_tabs.current_tab = index


func _on_sidebar_tab_changed(index: int) -> void:
	for tab_index in _sidebar_buttons.keys():
		var button: Button = _sidebar_buttons[tab_index]
		button.button_pressed = int(tab_index) == index


func _submit_action(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or is_waiting:
		return
	command_bar.remember_command(text)
	if GameState.campaign_id.is_empty():
		narrative_panel.append_system_text("[color=red]No active game. Start a new adventure.[/color]")
		return
	var hp := int(GameState.player.get("hp", 1))
	if hp <= 0 and not text.to_lower().begins_with("rest"):
		narrative_panel.append_system_text("[color=red]You have fallen. Type 'rest' to recover or start anew.[/color]")
		return
	_set_waiting(true)
	command_bar.clear_input()
	Backend.submit_campaign_command(GameState.campaign_id, text, _on_campaign_action_response.bind(text))
	await get_tree().create_timer(3.0).timeout
	if is_waiting:
		narrative_panel.show_thinking_indicator()


func _on_campaign_action_response(data, _issued_text: String) -> void:
	if data == null:
		if _dialog_overlay != null and _dialog_overlay.is_dialog_active():
			_dialog_overlay.hide_dialog()
		_finish_turn_sync()
		return
	GameState.update_from_response(data)
	if _dialog_overlay != null and data.has("dialog_options") and data["dialog_options"] is Array and not data["dialog_options"].is_empty():
		var npc_name := str(data.get("dialog_npc", data.get("speaker", "NPC")))
		var npc_text := str(data.get("dialog_text", data.get("narrative", "")))
		_dialog_overlay.show_dialog(npc_name, npc_text, data["dialog_options"])
	elif _dialog_overlay != null and _dialog_overlay.is_dialog_active():
		_dialog_overlay.hide_dialog()
	_finish_turn_sync()


func _set_waiting(waiting: bool) -> void:
	is_waiting = waiting
	command_bar.set_waiting(waiting)
	if _combat_overlay_widget != null and _combat_overlay_widget.has_method("set_waiting"):
		_combat_overlay_widget.set_waiting(waiting)
	if quest_panel.has_method("set_waiting"):
		quest_panel.set_waiting(waiting)
	if settlement_panel.has_method("set_waiting"):
		settlement_panel.set_waiting(waiting)
	save_load_panel.set_busy(waiting)


func _finish_turn_sync() -> void:
	_pending_sync_callbacks = 0
	_set_waiting(false)
	if not _queued_world_commands.is_empty():
		_submit_next_queued_world_command()
		return
	if not save_load_panel.visible:
		command_bar.focus_input()


func _on_state_updated() -> void:
	_save_sync.remember_player_id()


func _on_combat_started() -> void:
	narrative_panel.append_system_text("[color=red]Combat begins.[/color]")


func _on_combat_ended() -> void:
	narrative_panel.append_system_text("[color=green]Combat ended.[/color]")


func _on_level_up(new_level: int) -> void:
	narrative_panel.append_system_text("[color=yellow]Level up. You reached level %d.[/color]" % new_level)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed):
		return
	if event.keycode == KEY_F12:
		_capture_visual_proof("phase2/game", "game_session", event.shift_pressed)
		get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_F5 or (event.ctrl_pressed and event.keycode == KEY_S):
		_save_sync.on_quick_save_requested()
		get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_F9 or (event.ctrl_pressed and event.keycode == KEY_L):
		_save_sync.open_save_load_panel()
		get_viewport().set_input_as_handled()
		return
	if save_load_panel.visible:
		if event.keycode == KEY_ESCAPE:
			save_load_panel.close_panel()
			get_viewport().set_input_as_handled()
		return
	if event.keycode == KEY_HOME or (event.keycode == KEY_I and not command_bar.has_input_focus()):
		_submit_action("inventory")
		get_viewport().set_input_as_handled()
		return
	if event.keycode in [KEY_ENTER, KEY_KP_ENTER]:
		if _should_focus_command_bar_on_enter():
			command_bar.focus_input()
			get_viewport().set_input_as_handled()
		return
	if not command_bar.has_input_focus():
		var direction := ""
		match event.keycode:
			KEY_UP, KEY_W:
				direction = "north"
			KEY_DOWN, KEY_S:
				direction = "south"
			KEY_LEFT, KEY_A:
				direction = "west"
			KEY_RIGHT, KEY_D:
				direction = "east"
		if direction != "":
			_submit_action("move %s" % direction)
			get_viewport().set_input_as_handled()


func _should_focus_command_bar_on_enter() -> bool:
	return not save_load_panel.visible and not command_bar.has_input_focus()


func _on_backend_error(message: String) -> void:
	_pending_sync_callbacks = 0
	_queued_world_commands.clear()
	_set_waiting(false)
	save_load_panel.set_status(message)
	narrative_panel.append_system_text("[color=red][%s][/color]" % message)


func _on_world_command_requested(command_text: String) -> void:
	_queued_world_commands.clear()
	_submit_action(command_text)


func _on_world_command_sequence_requested(commands: Array[String]) -> void:
	_queued_world_commands.clear()
	for command in commands:
		var normalized := str(command).strip_edges()
		if not normalized.is_empty():
			_queued_world_commands.append(normalized)
	if not is_waiting:
		_submit_next_queued_world_command()


func _submit_next_queued_world_command() -> void:
	if _queued_world_commands.is_empty() or is_waiting:
		return
	var next_command: String = str(_queued_world_commands.pop_front())
	_submit_action(next_command)


func _on_world_graph_travel_requested(destination_region_id: String, destination_settlement_id: String) -> void:
	if is_waiting or GameState.campaign_id.is_empty():
		return
	command_bar.remember_command("travel %s" % destination_region_id)
	_set_waiting(true)
	Backend.submit_campaign_command(
		GameState.campaign_id,
		"",
		_on_campaign_action_response.bind("travel %s" % destination_region_id),
		"travel",
		{
			"destination_region_id": destination_region_id,
			"destination_settlement_id": destination_settlement_id,
		},
	)


func _capture_visual_proof(folder: String, prefix: String, include_world: bool) -> void:
	var frame_path := ScreenshotCapture.capture_viewport(get_viewport(), folder, "%s_frame" % prefix)
	var world_path := ""
	if include_world and world_view != null and world_view.has_method("capture_world_screenshot"):
		world_path = world_view.capture_world_screenshot(folder, "%s_world" % prefix)
	var parts: Array[String] = []
	if not frame_path.is_empty():
		parts.append("frame=%s" % frame_path)
	if not world_path.is_empty():
		parts.append("world=%s" % world_path)
	if parts.is_empty():
		narrative_panel.append_system_text("[color=red]Viewport capture failed.[/color]")
		return
	narrative_panel.append_system_text("[color=gray]Visual proof saved: %s[/color]" % " | ".join(parts))


func _on_save_completed(data, keep_panel_open: bool) -> void:
	_save_sync.on_save_completed(data, keep_panel_open)
