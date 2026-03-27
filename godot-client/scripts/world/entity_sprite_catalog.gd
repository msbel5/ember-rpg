extends RefCounted
class_name EntitySpriteCatalog

const AssetBootstrap = preload("res://scripts/asset/asset_bootstrap.gd")
const AssetManifest = preload("res://scripts/asset/asset_manifest.gd")
const FALLBACK_TEMPLATE := "warrior"
const TEMPLATE_ALIASES := {
	"player": "warrior",
	"citizen": "merchant",
	"villager": "merchant",
	"chest": "mimic",
}


static func resolve_texture(template_name: String) -> Texture2D:
	var template = str(template_name).strip_edges().to_lower()
	if template.is_empty():
		template = FALLBACK_TEMPLATE
	if TEMPLATE_ALIASES.has(template):
		template = TEMPLATE_ALIASES[template]

	var relative_path = AssetManifest.resolve_relative_path("sprites", template)
	if relative_path.is_empty():
		relative_path = "sprites/%s.png" % template
	var texture_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/sprites/%s.png" % template)
	var resolved = _load_texture(texture_path)
	if resolved != null:
		return resolved

	relative_path = AssetManifest.resolve_relative_path("sprites", FALLBACK_TEMPLATE)
	if relative_path.is_empty():
		relative_path = "sprites/%s.png" % FALLBACK_TEMPLATE
	texture_path = AssetBootstrap.resolve_asset(relative_path, "res://assets/sprites/%s.png" % FALLBACK_TEMPLATE)
	resolved = _load_texture(texture_path)
	if resolved != null:
		return resolved
	return null


static func _load_texture(resource_path: String) -> Texture2D:
	if resource_path.is_empty() or not FileAccess.file_exists(resource_path):
		return null

	var image = Image.new()
	var absolute_path = ProjectSettings.globalize_path(resource_path)
	if image.load(absolute_path) != OK:
		return null
	return ImageTexture.create_from_image(image)
