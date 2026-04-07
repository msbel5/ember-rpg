extends PanelContainer
class_name PauseMenuWidget

signal close_requested()
signal command_requested(command_text: String)
signal structured_action_requested(shortcut: String, args: Dictionary, history_text: String)

@onready var summary_label: Label = $PauseMargin/PauseVBox/SummaryLabel
@onready var state_label: Label = $PauseMargin/PauseVBox/StateLabel
@onready var ask_dm_button: Button = $PauseMargin/PauseVBox/ActionRow/AskDmButton
@onready var think_button: Button = $PauseMargin/PauseVBox/ActionRow/ThinkButton
@onready var close_button: Button = $PauseMargin/PauseVBox/ActionRow/CloseButton
@onready var blocker_label: Label = $PauseMargin/PauseVBox/BlockerLabel
@onready var tabs: TabContainer = $PauseMargin/PauseVBox/ContentTabs
@onready var ask_dm_panel: Control = $PauseMargin/PauseVBox/ContentTabs/AskDmPanel
@onready var think_panel: Control = $PauseMargin/PauseVBox/ContentTabs/ThinkPanel


func _ready() -> void:
	name = "PauseMenu"
	visible = false
	tabs.tabs_visible = false
	ask_dm_button.pressed.connect(func() -> void:
		tabs.current_tab = 0
	)
	think_button.pressed.connect(func() -> void:
		tabs.current_tab = 1
	)
	close_button.pressed.connect(func() -> void:
		visible = false
		close_requested.emit()
	)
	ask_dm_panel.command_requested.connect(func(command_text: String) -> void:
		command_requested.emit(command_text)
	)
	ask_dm_panel.structured_action_requested.connect(func(shortcut: String, args: Dictionary, history_text: String) -> void:
		structured_action_requested.emit(shortcut, args, history_text)
	)
	think_panel.command_requested.connect(func(command_text: String) -> void:
		command_requested.emit(command_text)
	)
	GameState.state_updated.connect(sync_from_game_state)
	sync_from_game_state()


func sync_from_game_state() -> void:
	var in_dialog := GameState.has_active_dialog()
	var in_combat := GameState.is_in_combat()
	var disabled := in_dialog or in_combat
	visible = visible and not disabled
	summary_label.text = "Pause intelligence surfaces render only live `advisor_view` and `knowledge_view` payloads."
	state_label.text = "Scene: %s  |  Location: %s" % [GameState.current_shell_mode().capitalize(), GameState.get_display_location()]
	blocker_label.text = ""
	ask_dm_button.disabled = disabled
	think_button.disabled = disabled
	if in_dialog:
		blocker_label.text = "Ask DM and Think stay closed during active dialogue."
	elif in_combat:
		blocker_label.text = "Ask DM and Think stay closed during combat."
	think_panel.sync_from_game_state()


func open_menu() -> void:
	sync_from_game_state()
	if ask_dm_button.disabled and think_button.disabled:
		visible = false
		return
	tabs.current_tab = 0
	visible = true


func set_advisor_view(view: Dictionary) -> void:
	ask_dm_panel.set_view(view)


func set_knowledge_view(view: Dictionary) -> void:
	think_panel.set_view(view)
