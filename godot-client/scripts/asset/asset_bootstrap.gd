extends RefCounted
class_name AssetBootstrap

const HF_TOKEN_ENV := "HF_TOKEN"
const HUGGINGFACE_ENV := "HUGGINGFACE_API_KEY"
const GENERATED_ROOT := "assets/generated"


static func resolve_hf_token() -> String:
	var token := OS.get_environment(HF_TOKEN_ENV).strip_edges()
	if not token.is_empty():
		return token
	return OS.get_environment(HUGGINGFACE_ENV).strip_edges()


static func resolve_generated_asset(relative_path: String) -> String:
	var user_path := "user://%s/%s" % [GENERATED_ROOT, relative_path]
	if FileAccess.file_exists(user_path):
		return user_path

	var res_path := "res://%s/%s" % [GENERATED_ROOT, relative_path]
	if ResourceLoader.exists(res_path):
		return res_path

	return ""


static func resolve_asset(relative_path: String, fallback_res_path: String = "") -> String:
	var generated_path = resolve_generated_asset(relative_path)
	if not generated_path.is_empty():
		return generated_path
	if not fallback_res_path.is_empty() and FileAccess.file_exists(fallback_res_path):
		return fallback_res_path
	return ""


static func can_generate_runtime() -> bool:
	return not OS.has_feature("web") and not resolve_hf_token().is_empty()
