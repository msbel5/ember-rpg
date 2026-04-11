extends RefCounted
class_name DialogOverlayState


static func topic_entries_from_state() -> Array:
	var game_state = _game_state()
	var conversation: Dictionary = game_state.conversation_state if game_state != null and game_state.conversation_state is Dictionary else {}
	var raw_topics = conversation.get("ask_about_topic_ids", [])
	if not (raw_topics is Array):
		return []
	var selected_id := selected_topic_id_from_state()
	var entries: Array = []
	for raw_topic in raw_topics:
		var entry := normalize_topic_entry(raw_topic)
		if entry.is_empty():
			continue
		entry["selected"] = str(entry.get("topic_id", "")).strip_edges() == selected_id
		entries.append(entry)
	return entries


static func normalize_topic_entry(raw_topic) -> Dictionary:
	if raw_topic is Dictionary:
		var topic_id := str(raw_topic.get("topic_id", "")).strip_edges()
		if topic_id.is_empty():
			return {}
		return {
			"topic_id": topic_id,
			"label": str(raw_topic.get("label", topic_label(topic_id))).strip_edges(),
			"subtitle": str(raw_topic.get("subtitle", topic_category_label(topic_id))).strip_edges(),
			"category": str(raw_topic.get("category", topic_category(topic_id))).strip_edges(),
			"gating": str(raw_topic.get("gating", "")).strip_edges(),
			"priority": int(raw_topic.get("priority", 0)),
		}
	var normalized_id := str(raw_topic).strip_edges()
	if normalized_id.is_empty():
		return {}
	return {
		"topic_id": normalized_id,
		"label": topic_label(normalized_id),
		"subtitle": topic_category_label(normalized_id),
		"category": topic_category(normalized_id),
		"gating": "",
		"priority": 0,
	}


static func selected_topic_id_from_state() -> String:
	var game_state = _game_state()
	var conversation: Dictionary = game_state.conversation_state if game_state != null and game_state.conversation_state is Dictionary else {}
	var ask_about = conversation.get("ask_about", {})
	if ask_about is Dictionary:
		var topic = ask_about.get("topic", {})
		if topic is Dictionary:
			var nested_id := str(topic.get("topic_id", "")).strip_edges()
			if not nested_id.is_empty():
				return nested_id
	return str(conversation.get("ask_about_selected_topic_id", "")).strip_edges()


static func conversation_transcript_lines(npc_name: String, npc_text: String, last_dialog_options: Array) -> Array:
	var game_state = _game_state()
	var conversation: Dictionary = game_state.conversation_state if game_state != null and game_state.conversation_state is Dictionary else {}
	var transcript = conversation.get("transcript", [])
	var lines: Array = []
	if transcript is Array:
		for entry in transcript:
			if entry is Dictionary:
				var speaker := normalized_line(entry.get("speaker", entry.get("role", "")))
				var text := normalized_line(entry.get("text", entry.get("line", "")))
				if text.is_empty():
					continue
				lines.append("[b]%s[/b] %s" % [speaker if not speaker.is_empty() else "Line", text])
			else:
				var raw_text := normalized_line(entry)
				if not raw_text.is_empty():
					lines.append(raw_text)
	if lines.is_empty():
		var normalized_name := normalized_line(npc_name)
		var normalized_text := normalized_line(npc_text)
		if not normalized_name.is_empty() and not normalized_text.is_empty():
			lines.append("[b]%s[/b] %s" % [normalized_name, normalized_text])
		for option in last_dialog_options:
			if option is Dictionary:
				var option_text := normalized_line(option.get("text", ""))
				if not option_text.is_empty():
					lines.append("[i]You:[/i] %s" % option_text)
	return lines


static func resolve_trade_context(npc_name: String) -> Dictionary:
	var game_state = _game_state()
	var conversation: Dictionary = game_state.conversation_state if game_state != null and game_state.conversation_state is Dictionary else {}
	var hinted_store_id := str(conversation.get("store_id", "")).strip_edges()
	if not hinted_store_id.is_empty():
		var hinted_store: Dictionary = game_state.store_by_id(hinted_store_id) if game_state != null and game_state.has_method("store_by_id") else {}
		if not hinted_store.is_empty():
			return _trade_context_from_store(hinted_store)
	var npc_id := str(conversation.get("npc_id", "")).strip_edges()
	var effective_name := str(conversation.get("npc_name", npc_name)).strip_edges()
	var store_list: Array = game_state.stores if game_state != null and game_state.stores is Array else []
	for raw_store in store_list:
		if not (raw_store is Dictionary):
			continue
		var store: Dictionary = raw_store
		if _store_matches_conversation(store, npc_id, effective_name):
			return _trade_context_from_store(store)
	return {
		"enabled": false,
		"tooltip": "Trade stays hidden until a verified live store route is exposed.",
	}


static func resolve_leave_command(last_dialog_options: Array) -> String:
	for option in last_dialog_options:
		if not (option is Dictionary):
			continue
		var command := str(option.get("command", "")).strip_edges()
		if command.is_empty():
			continue
		var transition_id := str(option.get("transition_id", "")).strip_edges().to_lower()
		var option_text := str(option.get("text", "")).strip_edges().to_lower()
		if transition_id.contains("leave") or transition_id.contains("goodbye"):
			return command
		if option_text.contains("maybe later") or option_text.contains("goodbye") or option_text.contains("leave"):
			return command
	return ""


static func normalized_line(value) -> String:
	if value == null:
		return ""
	var normalized := str(value).strip_edges()
	return "" if normalized == "<null>" else normalized


static func topic_label(topic_id: String) -> String:
	var tokens := topic_id.split(".")
	if tokens.size() >= 2:
		return _humanize_token(" ".join(tokens.slice(1, tokens.size())))
	return _humanize_token(topic_id)


static func topic_category_label(topic_id: String) -> String:
	var category := topic_id.split(".")[0] if topic_id.contains(".") else topic_id
	return _humanize_token(category)


static func topic_category(topic_id: String) -> String:
	return topic_id.split(".")[0] if topic_id.contains(".") else topic_id


static func _humanize_token(value: String) -> String:
	var words: Array[String] = []
	for raw_word in value.replace(".", " ").replace("_", " ").split(" "):
		var word := str(raw_word).strip_edges()
		if word.is_empty():
			continue
		words.append(word.capitalize())
	return " ".join(words)


static func _store_matches_conversation(store: Dictionary, npc_id: String, npc_name: String) -> bool:
	var store_npc_id := str(store.get("npc_id", "")).strip_edges()
	if not npc_id.is_empty() and not store_npc_id.is_empty() and store_npc_id == npc_id:
		return true
	var store_npc_name := str(store.get("npc_name", "")).strip_edges()
	if not npc_name.is_empty() and not store_npc_name.is_empty() and store_npc_name.to_lower() == npc_name.to_lower():
		return true
	return false


static func _trade_context_from_store(store: Dictionary) -> Dictionary:
	var store_id := str(store.get("store_id", "")).strip_edges()
	var label := str(store.get("label", "Trader")).strip_edges()
	var services = store.get("services", [])
	var service_labels: Array[String] = []
	if services is Array:
		for service in services:
			if service is Dictionary:
				var service_label := str(service.get("label", "")).strip_edges()
				if not service_label.is_empty():
					service_labels.append(service_label)
	var tooltip := "Trade with %s." % label
	if not service_labels.is_empty():
		tooltip += " Services: %s." % ", ".join(service_labels.slice(0, 3))
	return {
		"enabled": not store_id.is_empty(),
		"store_id": store_id,
		"tooltip": tooltip,
	}


static func _game_state():
	var loop = Engine.get_main_loop()
	if loop is SceneTree:
		return loop.root.get_node_or_null("GameState")
	return null
