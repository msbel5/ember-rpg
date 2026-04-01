## BG2-style equipment paperdoll — equipment slots + backpack grid + item details.
## Replaces the flat item list in the current inventory_panel.
extends PanelContainer
class_name EquipmentPanel

signal command_requested(command_text: String)

const EQUIPMENT_SLOTS := [
	"helmet", "amulet", "armor", "cloak",
	"ring_l", "shield", "ring_r",
	"gloves", "belt", "boots",
	"weapon_1", "weapon_2",
	"quiver",
]
const BACKPACK_COLS := 4
const BACKPACK_ROWS := 4

var _slot_buttons: Dictionary = {}
var _backpack_grid: GridContainer
var _detail_name: Label
var _detail_desc: RichTextLabel
var _equip_button: Button
var _drop_button: Button
var _selected_item: Dictionary = {}
var _selected_slot: String = ""


func _ready() -> void:
	name = "EquipmentPanel"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 8)
	add_child(vbox)

	# Equipment section header
	vbox.add_child(_make_header("Equipment"))

	# Equipment slot grid (layout inspired by BG2 paperdoll)
	var equip_grid := GridContainer.new()
	equip_grid.columns = 4
	equip_grid.add_theme_constant_override("h_separation", 4)
	equip_grid.add_theme_constant_override("v_separation", 4)
	vbox.add_child(equip_grid)

	for slot_name in EQUIPMENT_SLOTS:
		var btn := Button.new()
		btn.text = _slot_display(slot_name)
		btn.custom_minimum_size = Vector2(70, 32)
		btn.add_theme_font_size_override("font_size", 10)
		btn.tooltip_text = slot_name.replace("_", " ").capitalize()
		btn.pressed.connect(_on_slot_clicked.bind(slot_name))
		equip_grid.add_child(btn)
		_slot_buttons[slot_name] = btn

	# Separator
	vbox.add_child(HSeparator.new())

	# Backpack header
	vbox.add_child(_make_header("Backpack"))

	# Backpack grid
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)

	_backpack_grid = GridContainer.new()
	_backpack_grid.columns = BACKPACK_COLS
	_backpack_grid.add_theme_constant_override("h_separation", 3)
	_backpack_grid.add_theme_constant_override("v_separation", 3)
	scroll.add_child(_backpack_grid)

	# Separator
	vbox.add_child(HSeparator.new())

	# Item detail section
	_detail_name = Label.new()
	_detail_name.text = "Select an item"
	_detail_name.add_theme_font_size_override("font_size", 14)
	_detail_name.add_theme_color_override("font_color", Color(0.80, 0.66, 0.26))
	vbox.add_child(_detail_name)

	_detail_desc = RichTextLabel.new()
	_detail_desc.bbcode_enabled = true
	_detail_desc.fit_content = true
	_detail_desc.custom_minimum_size = Vector2(0, 48)
	_detail_desc.add_theme_font_size_override("normal_font_size", 12)
	vbox.add_child(_detail_desc)

	var btn_row := HBoxContainer.new()
	btn_row.add_theme_constant_override("separation", 6)
	vbox.add_child(btn_row)

	_equip_button = Button.new()
	_equip_button.text = "Equip"
	_equip_button.visible = false
	_equip_button.pressed.connect(_on_equip)
	btn_row.add_child(_equip_button)

	_drop_button = Button.new()
	_drop_button.text = "Drop"
	_drop_button.visible = false
	_drop_button.pressed.connect(_on_drop)
	btn_row.add_child(_drop_button)

	if get_node_or_null("/root/GameState") != null:
		GameState.state_updated.connect(_refresh)
		GameState.inventory_updated.connect(_refresh)
	_refresh()


func _refresh(_data = null) -> void:
	_refresh_equipment_slots()
	_refresh_backpack()


func _refresh_equipment_slots() -> void:
	var equipment: Dictionary = GameState.player.get("equipment", {})
	for slot_name in EQUIPMENT_SLOTS:
		var btn: Button = _slot_buttons.get(slot_name)
		if btn == null:
			continue
		var item = equipment.get(slot_name, null)
		if item is Dictionary and not item.is_empty():
			btn.text = str(item.get("name", _slot_display(slot_name)))
			btn.tooltip_text = "%s: %s" % [slot_name.replace("_", " ").capitalize(), str(item.get("name", ""))]
		else:
			btn.text = _slot_display(slot_name)
			btn.tooltip_text = "%s: empty" % slot_name.replace("_", " ").capitalize()


func _refresh_backpack() -> void:
	for child in _backpack_grid.get_children():
		child.queue_free()
	var items: Array = GameState.player.get("inventory_items", GameState.inventory_items)
	if not (items is Array):
		items = []
	for item in items:
		if not (item is Dictionary):
			continue
		var btn := Button.new()
		btn.text = str(item.get("name", "?"))
		btn.custom_minimum_size = Vector2(65, 28)
		btn.add_theme_font_size_override("font_size", 10)
		btn.tooltip_text = str(item.get("description", item.get("name", "")))
		btn.pressed.connect(_on_backpack_item_clicked.bind(item))
		_backpack_grid.add_child(btn)
	# Fill remaining slots with empty placeholders
	var filled := items.size()
	for i in range(filled, BACKPACK_COLS * BACKPACK_ROWS):
		var placeholder := Button.new()
		placeholder.text = "-"
		placeholder.custom_minimum_size = Vector2(65, 28)
		placeholder.add_theme_font_size_override("font_size", 10)
		placeholder.disabled = true
		placeholder.add_theme_color_override("font_color", Color(0.3, 0.3, 0.3))
		_backpack_grid.add_child(placeholder)


func _on_slot_clicked(slot_name: String) -> void:
	_selected_slot = slot_name
	var equipment: Dictionary = GameState.player.get("equipment", {})
	var item = equipment.get(slot_name, {})
	if item is Dictionary and not item.is_empty():
		_show_item_detail(item, true)
	else:
		_detail_name.text = "%s: empty" % slot_name.replace("_", " ").capitalize()
		_detail_desc.text = ""
		_equip_button.visible = false
		_drop_button.visible = false


func _on_backpack_item_clicked(item: Dictionary) -> void:
	_selected_item = item
	_show_item_detail(item, false)


func _show_item_detail(item: Dictionary, is_equipped: bool) -> void:
	_selected_item = item
	_detail_name.text = str(item.get("name", "Unknown Item"))
	var desc_parts: Array[String] = []
	if item.has("damage"):
		desc_parts.append("Damage: %s" % str(item.get("damage", "")))
	if item.has("armor_bonus"):
		desc_parts.append("AC: +%s" % str(item.get("armor_bonus", "")))
	if item.has("weight"):
		desc_parts.append("Weight: %s lbs" % str(item.get("weight", "")))
	if item.has("description"):
		desc_parts.append(str(item.get("description", "")))
	_detail_desc.text = "\n".join(desc_parts)
	_equip_button.text = "Unequip" if is_equipped else "Equip"
	_equip_button.visible = true
	_drop_button.visible = true


func _on_equip() -> void:
	var item_name := str(_selected_item.get("name", "")).strip_edges().to_lower()
	if item_name.is_empty():
		return
	if _equip_button.text == "Unequip":
		command_requested.emit("unequip %s" % item_name)
	else:
		command_requested.emit("equip %s" % item_name)


func _on_drop() -> void:
	var item_name := str(_selected_item.get("name", "")).strip_edges().to_lower()
	if not item_name.is_empty():
		command_requested.emit("drop %s" % item_name)


func _slot_display(slot_name: String) -> String:
	match slot_name:
		"helmet": return "[Head]"
		"amulet": return "[Neck]"
		"armor": return "[Body]"
		"cloak": return "[Back]"
		"ring_l": return "[Ring]"
		"shield": return "[Off]"
		"ring_r": return "[Ring]"
		"gloves": return "[Hand]"
		"belt": return "[Waist]"
		"boots": return "[Feet]"
		"weapon_1": return "[Main]"
		"weapon_2": return "[Alt]"
		"quiver": return "[Ammo]"
	return "[%s]" % slot_name


func _make_header(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 14)
	label.add_theme_color_override("font_color", Color(0.80, 0.66, 0.26))
	return label
