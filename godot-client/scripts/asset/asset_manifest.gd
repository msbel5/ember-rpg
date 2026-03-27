extends RefCounted
class_name AssetManifest

const GENERATED_ROOT := "assets/generated"
const MANIFEST_PATH := "manifest.json"


static func load_manifest() -> Dictionary:
	var user_manifest = "user://%s/%s" % [GENERATED_ROOT, MANIFEST_PATH]
	var manifest = _read_manifest(user_manifest)
	if not manifest.is_empty():
		return manifest

	var res_manifest = "res://%s/%s" % [GENERATED_ROOT, MANIFEST_PATH]
	return _read_manifest(res_manifest)


static func resolve_relative_path(kind: String, asset_name: String) -> String:
	var manifest = load_manifest()
	if manifest.is_empty():
		return ""
	var bucket = manifest.get(kind, {})
	if not (bucket is Dictionary):
		return ""
	var entry = bucket.get(asset_name, {})
	if not (entry is Dictionary):
		return ""
	return str(entry.get("relative_path", ""))


static func _read_manifest(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var content = FileAccess.get_file_as_string(path)
	var parsed = JSON.parse_string(content)
	if parsed is Dictionary:
		return parsed
	return {}
