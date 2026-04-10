extends PanelContainer
class_name InventoryPanelWidget

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")

signal command_requested(command_text: String)

@onready var gold_label: Label = $InventoryMargin/InventoryVBox/GoldLabel
@onready var summary_label: Label = $InventoryMargin/InventoryVBox/SummaryLabel
@onready var item_grid: GridContainer = $InventoryMargin/InventoryVBox/ItemGrid

var _icon_cache: Dictionary = {}


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
		slot.custom_minimum_size = Vector2(180, 52)
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot.alignment = HORIZONTAL_ALIGNMENT_LEFT
		slot.icon_alignment = HORIZONTAL_ALIGNMENT_LEFT
		slot.text = item_name
		var icon_texture = _load_item_icon(item_ref)
		if icon_texture != null:
			slot.icon = icon_texture
		if entry is Dictionary and entry.has("quantity"):
			slot.text += "  ×%d" % int(entry.get("quantity", 1))
		slot.tooltip_text = "Examine %s using the canonical inventory command." % item_name
		slot.pressed.connect(func() -> void:
			command_requested.emit("examine %s" % item_ref)
		)
		item_grid.add_child(slot)


func _load_item_icon(item_ref: String) -> Texture2D:
	var slug = _asset_slug(item_ref)
	if slug.is_empty():
		return null
	if _icon_cache.has(slug):
		return _icon_cache[slug]

	var relative_path = AssetManifest.resolve_relative_path("items", slug)
	if relative_path.is_empty():
		relative_path = "items/%s.png" % slug
	var icon_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/items/%s.png" % slug)
	var texture = _load_texture(icon_path)
	_icon_cache[slug] = texture
	return texture


func _load_texture(resource_path: String) -> Texture2D:
	if resource_path.is_empty() or not FileAccess.file_exists(resource_path):
		return null
	var image = Image.new()
	if image.load(ProjectSettings.globalize_path(resource_path)) != OK:
		return null
	return ImageTexture.create_from_image(image)


func _asset_slug(raw_value: String) -> String:
	var raw = raw_value.strip_edges().to_lower()
	var slug := ""
	var previous_was_separator := false
	for i in range(raw.length()):
		var character = raw.substr(i, 1)
		var code = character.unicode_at(0)
		var is_alnum = (code >= 48 and code <= 57) or (code >= 97 and code <= 122)
		if is_alnum:
			slug += character
			previous_was_separator = false
		elif not previous_was_separator:
			slug += "_"
			previous_was_separator = true
	while slug.begins_with("_"):
		slug = slug.substr(1)
	while slug.ends_with("_"):
		slug = slug.substr(0, slug.length() - 1)
	return slug
