extends PanelContainer
class_name ModalHostWidget

signal host_closed()

const OPTIONAL_PANEL_SCENES := {
	"pause": {
		"path": "res://scenes/components/pause_menu.tscn",
		"name": "PauseMenu",
		"title": "Menu",
	}
}
const PANEL_IDS := {
	"NarrativePanel": "narrative",
	"CharacterPanel": "hero",
	"SettlementPanel": "town",
	"QuestPanel": "quests",
	"InventoryPanel": "items",
	"MinimapPanel": "map",
	"PauseMenu": "pause",
}
const PANEL_TITLES := {
	"narrative": "Transcript",
	"hero": "Hero",
	"town": "Town",
	"quests": "Quests",
	"items": "Items",
	"map": "Map",
	"pause": "Menu",
}

@onready var _title_label: Label = $HeaderRow/TitleLabel
@onready var _close_button: Button = $HeaderRow/CloseButton
@onready var sidebar_tabs: TabContainer = $SidebarTabs

var _panel_index_by_id: Dictionary = {}


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	sidebar_tabs.tabs_visible = false
	_close_button.pressed.connect(hide_host)
	_rebuild_panel_index()


func available_panel_ids() -> Array[String]:
	var panel_ids: Array[String] = []
	for panel_id in _panel_index_by_id.keys():
		panel_ids.append(str(panel_id))
	panel_ids.sort()
	return panel_ids


func has_panel(panel_id: String) -> bool:
	return _panel_index_by_id.has(panel_id.strip_edges().to_lower())


func active_panel_id() -> String:
	if not visible:
		return ""
	var current = sidebar_tabs.get_tab_control(sidebar_tabs.current_tab)
	if current == null:
		return ""
	return str(PANEL_IDS.get(current.name, "")).strip_edges().to_lower()


func panel_node(panel_id: String) -> Control:
	var normalized := panel_id.strip_edges().to_lower()
	if not _panel_index_by_id.has(normalized):
		return null
	return sidebar_tabs.get_tab_control(int(_panel_index_by_id[normalized]))


func show_panel(panel_id: String) -> bool:
	var normalized := panel_id.strip_edges().to_lower()
	if not _panel_index_by_id.has(normalized):
		return false
	sidebar_tabs.current_tab = int(_panel_index_by_id[normalized])
	_title_label.text = PANEL_TITLES.get(normalized, "Panel")
	visible = true
	var current = sidebar_tabs.get_current_tab_control()
	if current != null:
		if current.has_method("open_menu"):
			current.open_menu()
		else:
			current.visible = true
	return true


func toggle_panel(panel_id: String) -> bool:
	var normalized := panel_id.strip_edges().to_lower()
	if normalized.is_empty() or not _panel_index_by_id.has(normalized):
		return false
	if visible and active_panel_id() == normalized:
		hide_host()
		return true
	return show_panel(normalized)


func hide_host() -> void:
	if not visible:
		return
	var current = sidebar_tabs.get_current_tab_control()
	if current != null:
		current.visible = false
	visible = false
	host_closed.emit()


func _rebuild_panel_index() -> void:
	_panel_index_by_id.clear()
	for index in range(sidebar_tabs.get_tab_count()):
		var child = sidebar_tabs.get_tab_control(index)
		if child == null:
			continue
		var panel_id := str(PANEL_IDS.get(child.name, "")).strip_edges().to_lower()
		if panel_id.is_empty():
			continue
		_panel_index_by_id[panel_id] = index
		sidebar_tabs.set_tab_title(index, PANEL_TITLES.get(panel_id, child.name))
