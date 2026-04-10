extends RefCounted
class_name EntitySpriteCatalog

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")
const FALLBACK_TEMPLATE := "warrior"
const THIRD_PARTY_SPRITE_ROOT := "res://assets/third_party/pixel_crawler/extracted/sprites"
const PROP_TEXTURE_ALIASES := {
	"chest": "wooden_chest",
	"wooden_chest": "wooden_chest",
	"table": "table",
	"desk": "table",
	"workbench": "workbench",
}
const PROP_TEMPLATES := ["altar", "anvil", "barrel", "bed", "bench", "bookshelf", "chair", "chest", "crate", "desk", "door", "fountain", "pew", "rack", "shrine", "table", "tree", "well", "wooden_chest", "workbench"]
const TEMPLATE_ALIASES := {
	"player": "warrior",
	"citizen": "merchant",
	"villager": "merchant",
	"guard_captain": "guard",
	"shopkeeper": "merchant",
	"trader": "merchant",
	"cleric": "priest",
	"sorcerer": "mage",
	"wizard": "mage",
}


static func resolve_texture(template_name: String) -> Texture2D:
	var template = str(template_name).strip_edges().to_lower()
	if template.is_empty():
		template = FALLBACK_TEMPLATE

	if PROP_TEMPLATES.has(template):
		return _load_generated_prop_texture(template)

	var resolved = _load_generated_texture(template)
	if resolved != null:
		return resolved

	if TEMPLATE_ALIASES.has(template):
		template = TEMPLATE_ALIASES[template]

	if PROP_TEMPLATES.has(template):
		return _load_generated_prop_texture(template)

	resolved = _load_generated_texture(template)
	if resolved != null:
		return resolved

	var texture_path = "%s/%s.png" % [THIRD_PARTY_SPRITE_ROOT, template]
	resolved = _load_texture(texture_path)
	if resolved != null:
		return resolved

	resolved = _load_generated_item_texture(template)
	if resolved != null:
		return resolved

	resolved = _load_generated_texture(FALLBACK_TEMPLATE)
	if resolved != null:
		return resolved

	texture_path = "%s/%s.png" % [THIRD_PARTY_SPRITE_ROOT, FALLBACK_TEMPLATE]
	resolved = _load_texture(texture_path)
	if resolved != null:
		return resolved
	return null


static func _load_generated_texture(template: String) -> Texture2D:
	var relative_path = AssetManifest.resolve_relative_path("sprites", template)
	if relative_path.is_empty():
		relative_path = "sprites/%s.png" % template
	var texture_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/sprites/%s.png" % template)
	return _load_texture(texture_path)


static func _load_texture(resource_path: String) -> Texture2D:
	if resource_path.is_empty() or not FileAccess.file_exists(resource_path):
		return null

	var image = Image.new()
	var absolute_path = ProjectSettings.globalize_path(resource_path)
	if image.load(absolute_path) != OK:
		return null
	return ImageTexture.create_from_image(image)


static func _load_generated_prop_texture(template: String) -> Texture2D:
	var item_slug = str(PROP_TEXTURE_ALIASES.get(template, template))
	var relative_path = AssetManifest.resolve_relative_path("items", item_slug)
	if relative_path.is_empty():
		relative_path = "items/%s.png" % item_slug
	var item_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/items/%s.png" % item_slug)
	var resolved = _load_texture(item_path)
	if resolved != null:
		return resolved

	relative_path = AssetManifest.resolve_relative_path("tiles", template)
	if relative_path.is_empty():
		relative_path = "tiles/%s.png" % template
	var tile_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/tiles/%s.png" % template)
	return _load_texture(tile_path)


static func _load_generated_item_texture(template: String) -> Texture2D:
	var relative_path = AssetManifest.resolve_relative_path("items", template)
	if relative_path.is_empty():
		relative_path = "items/%s.png" % template
	var item_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/generated/items/%s.png" % template)
	return _load_texture(item_path)
