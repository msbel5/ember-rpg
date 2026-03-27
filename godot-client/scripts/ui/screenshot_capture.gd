extends RefCounted

const ROOT_DIR := "user://screenshots"


static func capture_image(image: Image, folder: String, prefix: String) -> String:
	var safe_folder = folder.strip_edges().trim_prefix("/").trim_suffix("/")
	var safe_prefix = prefix.strip_edges()
	if safe_folder.is_empty():
		safe_folder = "manual"
	if safe_prefix.is_empty():
		safe_prefix = "capture"

	var timestamp = Time.get_datetime_string_from_system().replace(":", "-")
	timestamp = timestamp.replace(" ", "_")
	var user_path = "%s/%s/%s_%s.png" % [ROOT_DIR, safe_folder, safe_prefix, timestamp]
	DirAccess.make_dir_recursive_absolute(user_path.get_base_dir())
	var save_error = image.save_png(user_path)
	if save_error != OK:
		return ""
	return ProjectSettings.globalize_path(user_path)


static func capture_viewport(viewport: Viewport, folder: String, prefix: String) -> String:
	if viewport == null:
		return ""
	var image = viewport.get_texture().get_image()
	return capture_image(image, folder, prefix)
