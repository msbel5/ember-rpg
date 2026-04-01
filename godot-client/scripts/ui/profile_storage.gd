## Reads and writes player profile values to a local config file.
## Extracted from title_screen.gd for SOLID compliance.
extends RefCounted
class_name ProfileStorage

const PROFILE_PATH := "user://client_profile.cfg"


static func store(key: String, value) -> void:
	var config := ConfigFile.new()
	config.load(PROFILE_PATH)
	config.set_value("profile", key, value)
	config.save(PROFILE_PATH)


static func load_value(key: String, fallback = ""):
	var config := ConfigFile.new()
	if config.load(PROFILE_PATH) != OK:
		return fallback
	return config.get_value("profile", key, fallback)


static func store_last_player_id(player_id: String) -> void:
	store("last_player_id", player_id)


static func last_player_id() -> String:
	return str(load_value("last_player_id", ""))


static func store_last_resume_player_id(player_id: String) -> void:
	store("last_resume_player_id", player_id)


static func last_resume_player_id() -> String:
	return str(load_value("last_resume_player_id", ""))


static func preferred_resume_player_id() -> String:
	var resume_id := last_resume_player_id()
	if not resume_id.is_empty():
		return resume_id
	return last_player_id()


static func store_last_adapter_id(value: String) -> void:
	store("last_adapter_id", value)


static func last_adapter_id() -> String:
	return str(load_value("last_adapter_id", ""))


static func store_last_campaign_save_id(save_id: String) -> void:
	store("last_campaign_save_id", save_id)


static func last_campaign_save_id() -> String:
	return str(load_value("last_campaign_save_id", ""))
