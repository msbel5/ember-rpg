extends PanelContainer
class_name InventoryPanelWidget

signal command_requested(command_text: String)

@onready var gold_label: Label = $InventoryMargin/InventoryVBox/GoldLabel
@onready var summary_label: Label = $InventoryMargin/InventoryVBox/SummaryLabel
@onready var item_grid: GridContainer = $InventoryMargin/InventoryVBox/ItemGrid


func _ready() -> void:
	GameState.state_updated.connect(_refresh)
	GameState.inventory_updated.connect(_refresh_inventory)
	_refresh()


func _refresh_inventory(_items: Array = []) -> void:
	_refresh()


func _refresh() -> void:
	var inventory = GameState.inventory_items
	if inventory.is_empty() and GameState.player.has("inventory") and GameState.player["inventory"] is Array:
		inventory = GameState.player["inventory"]

	gold_label.text = "Gold: %d" % int(GameState.player.get("gold", 0))
	summary_label.text = "%d item(s) ready for inspection" % inventory.size()

	for child in item_grid.get_children():
		child.queue_free()

	if inventory.is_empty():
		var empty_label = Label.new()
		empty_label.text = "Pack is empty. Scavenge, trade, or pry open something interesting."
		empty_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		item_grid.add_child(empty_label)
		return

	for entry in inventory:
		var item_name = str(entry.get("name", entry)) if entry is Dictionary else str(entry)
		var item_ref = item_name.to_lower()
		if entry is Dictionary:
			item_ref = str(entry.get("item_id", entry.get("item_def_id", item_name))).strip_edges().to_lower()
		var slot = Button.new()
		slot.custom_minimum_size = Vector2(84, 42)
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot.alignment = HORIZONTAL_ALIGNMENT_LEFT
		slot.text = item_name
		if entry is Dictionary and entry.has("quantity"):
			slot.text += "  ×%d" % int(entry.get("quantity", 1))
		slot.tooltip_text = "Examine %s using the canonical inventory command." % item_name
		slot.pressed.connect(func() -> void:
			command_requested.emit("examine %s" % item_ref)
		)
		item_grid.add_child(slot)
