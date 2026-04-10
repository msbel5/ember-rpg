extends RefCounted
class_name ResponseNormalizer

const ResponseEntityNormalizer = preload("res://scripts/net/response_entity_normalizer.gd")
const ResponseMapNormalizer = preload("res://scripts/net/response_map_normalizer.gd")

const INVENTORY_COMMAND_MARKERS := [
	"inventory",
	"inv",
	"pick up",
	"pickup",
	"take ",
	"loot",
	"drop ",
	"equip",
	"unequip",
	"use ",
	"consume",
	"drink ",
	"buy ",
	"sell ",
	"trade",
	"craft",
	"wear ",
	"remove ",
]
static func normalize_combat(data: Dictionary) -> Dictionary:
	var combat_state: Dictionary = {}
	if data.has("combat_state") and data["combat_state"] is Dictionary:
		combat_state = data["combat_state"]
	elif data.has("combat") and data["combat"] is Dictionary:
		combat_state = data["combat"]
	if combat_state.is_empty():
		return {}
	var normalized := combat_state.duplicate(true)
	var normalized_actions: Array = []
	for raw_action in normalized.get("available_actions", []):
		var action_id := str(raw_action).strip_edges().to_lower()
		if action_id.is_empty() or normalized_actions.has(action_id):
			continue
		normalized_actions.append(action_id)
	if not normalized_actions.is_empty():
		normalized["available_actions"] = normalized_actions
	var normalized_combatants: Array = []
	for combatant in normalized.get("combatants", []):
		if not (combatant is Dictionary):
			normalized_combatants.append(combatant)
			continue
		var normalized_combatant: Dictionary = combatant.duplicate(true)
		if not normalized_combatant.has("turn_resources"):
			if normalized_combatant.has("resources") and normalized_combatant["resources"] is Dictionary:
				normalized_combatant["turn_resources"] = normalized_combatant["resources"]
			else:
				normalized_combatant["turn_resources"] = {
					"action_available": true,
					"bonus_action_available": true,
					"reaction_available": true,
					"movement_remaining": 6,
					"speed": 6,
				}
		normalized_combatants.append(normalized_combatant)
	normalized["combatants"] = normalized_combatants
	return normalized


static func normalize_dialog(data: Dictionary) -> Dictionary:
	var dialog_source: Dictionary = {}
	if data.has("dialog") and data["dialog"] is Dictionary:
		dialog_source = data["dialog"]
	else:
		dialog_source = data
	var npc_name := _nullable_string(dialog_source.get("dialog_npc", dialog_source.get("speaker", "")))
	var dialog_text := _nullable_string(dialog_source.get("dialog_text", ""))
	var raw_options = dialog_source.get("dialog_options", [])
	var normalized_options: Array = []
	if raw_options is Array:
		for option in raw_options:
			if not (option is Dictionary):
				continue
			var normalized_option: Dictionary = option.duplicate(true)
			if not normalized_option.has("enabled"):
				normalized_option["enabled"] = bool(normalized_option.get("available", true))
			if not normalized_option.has("disabled_reason"):
				normalized_option["disabled_reason"] = str(normalized_option.get("reason", ""))
			normalized_options.append(normalized_option)
	if npc_name.is_empty() and dialog_text.is_empty() and normalized_options.is_empty():
		return {}
	return {
		"dialog_npc": npc_name,
		"dialog_text": dialog_text,
		"dialog_options": normalized_options,
	}


static func _nullable_string(value) -> String:
	if value == null:
		return ""
	var normalized := str(value).strip_edges()
	return "" if normalized == "<null>" else normalized


static func flatten_campaign_response(data: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	var flattened: Dictionary = {}
	if not (data.has("campaign") and data["campaign"] is Dictionary):
		return flattened

	var campaign: Dictionary = data["campaign"]
	var campaign_location := str(campaign.get("location", "")).strip_edges()
	if campaign_location.is_empty():
		var settlement = campaign.get("settlement", {})
		if settlement is Dictionary:
			campaign_location = str(settlement.get("name", "")).strip_edges()
	if data.has("campaign_id"):
		flattened["campaign_id"] = data["campaign_id"]
	if data.has("adapter_id"):
		flattened["adapter_id"] = data["adapter_id"]
	if data.has("profile_id"):
		flattened["profile_id"] = data["profile_id"]
	if data.has("transport") and data["transport"] is Dictionary:
		flattened["transport"] = data["transport"]
		flattened["runtime_transport"] = str(data["transport"].get("mode", "http"))
		flattened["bootstrap_transport"] = str(data["transport"].get("bootstrap", "http"))
		flattened["ws_url"] = str(data["transport"].get("ws_url", ""))
		flattened["ws_path"] = str(data["transport"].get("ws_path", ""))
	if data.has("runtime_mode"):
		flattened["runtime_mode"] = str(data["runtime_mode"]).strip_edges().to_lower()
	if data.has("tick_state") and data["tick_state"] is Dictionary:
		flattened["tick_state"] = data["tick_state"]
	if data.has("world_ready"):
		flattened["world_ready"] = bool(data["world_ready"])
	if data.has("narrative"):
		flattened["narrative"] = data["narrative"]

	flattened["player"] = campaign.get("player", {})
	flattened["scene"] = campaign.get("scene", "exploration")
	flattened["location"] = campaign_location
	flattened["combat"] = campaign.get("combat", {})
	flattened["conversation_state"] = campaign.get("conversation_state", {})
	flattened["knowledge"] = campaign.get("knowledge", {})
	var normalized_dialog := normalize_dialog(campaign)
	if normalized_dialog.is_empty():
		normalized_dialog = normalize_dialog(data)
	if not normalized_dialog.is_empty():
		flattened.merge(normalized_dialog, true)
	flattened["world"] = campaign.get("world", {})
	flattened["world_state"] = campaign.get("world_state", campaign.get("world", {}))
	flattened["stores"] = campaign.get("stores", [])
	flattened["active_store_id"] = str(campaign.get("active_store_id", ""))
	flattened["travel_state"] = campaign["travel_state"] if campaign.has("travel_state") else null
	flattened["crime_state"] = campaign.get("crime_state", {})
	flattened["game_state_root"] = campaign.get("game_state", {})
	flattened["actor_roster"] = campaign.get("actors", [])
	flattened["job_records"] = campaign.get("jobs", [])
	flattened["reaction_defs"] = campaign.get("reactions", [])
	flattened["worksite_records"] = campaign.get("worksites", [])
	flattened["colony_pressure"] = campaign.get("colony_pressure", {})
	flattened["production_ledger"] = campaign.get("production_ledger", {})
	flattened["path_authority"] = campaign.get("path_authority", {})
	flattened["local_map_state"] = campaign.get("local_map_state", {})
	flattened["military_state"] = campaign.get("military", {})
	flattened["systems_state"] = campaign.get("systems", {})
	flattened["world_graph"] = campaign.get("world_graph", {})
	flattened["travel_options"] = campaign.get("travel_options", [])
	flattened["current_region_summary"] = campaign.get("current_region_summary", {})
	if flattened["current_region_summary"] is Dictionary:
		flattened["selected_world_node"] = str(flattened["current_region_summary"].get("settlement_node_id", ""))
	flattened["settlement_state"] = campaign.get("settlement", {})
	flattened["character_sheet"] = campaign.get("character_sheet", {})
	flattened["recent_event_log"] = campaign.get("recent_event_log", [])
	flattened["active_quests"] = campaign.get("active_quests", [])
	flattened["quest_offers"] = campaign.get("quest_offers", [])
	flattened["advisor_view"] = data.get("advisor_view", {}) if data.has("advisor_view") and data["advisor_view"] is Dictionary else {}
	flattened["knowledge_view"] = data.get("knowledge_view", {}) if data.has("knowledge_view") and data["knowledge_view"] is Dictionary else {}
	flattened["ground_items"] = campaign.get("ground_items", [])
	flattened["world_entities"] = campaign.get("world_entities", ResponseEntityNormalizer.region_entities(campaign.get("region", {})))
	if campaign.has("map_data") and campaign["map_data"] is Dictionary:
		flattened["map_data"] = ResponseMapNormalizer.normalize_map({"map_data": campaign["map_data"]}, current_map)
	elif campaign.has("region") and campaign["region"] is Dictionary:
		flattened["map_data"] = ResponseMapNormalizer.campaign_region_to_map(campaign["region"], current_map)
	return flattened


static func normalize_map(data: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	return ResponseMapNormalizer.normalize_map(data, current_map)


static func normalize_entities(data: Dictionary) -> Dictionary:
	return ResponseEntityNormalizer.normalize_entities(data)


static func group_entity_list(raw_entities: Array) -> Dictionary:
	return ResponseEntityNormalizer.group_entity_list(raw_entities)


static func group_world_entities(raw_entities: Array) -> Dictionary:
	return ResponseEntityNormalizer.group_world_entities(raw_entities)


static func guess_entity_template(entry: Dictionary) -> String:
	return ResponseEntityNormalizer.guess_entity_template(entry)


static func context_actions_for(entry: Dictionary) -> Array:
	return ResponseEntityNormalizer.context_actions_for(entry)


static func campaign_region_to_map(region_payload: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	return ResponseMapNormalizer.campaign_region_to_map(region_payload, current_map)


static func player_position_from(player_data: Dictionary, fallback: Vector2i = Vector2i.ZERO) -> Vector2i:
	if player_data.has("position") and player_data["position"] is Array and player_data["position"].size() >= 2:
		return Vector2i(int(player_data["position"][0]), int(player_data["position"][1]))
	if player_data.has("position") and player_data["position"] is Dictionary:
		var position: Dictionary = player_data["position"]
		if position.has("x") and position.has("y"):
			return Vector2i(int(position["x"]), int(position["y"]))
	if player_data.has("map_position") and player_data["map_position"] is Array and player_data["map_position"].size() >= 2:
		return Vector2i(int(player_data["map_position"][0]), int(player_data["map_position"][1]))
	if player_data.has("map_position") and player_data["map_position"] is Dictionary:
		var map_position: Dictionary = player_data["map_position"]
		if map_position.has("x") and map_position.has("y"):
			return Vector2i(int(map_position["x"]), int(map_position["y"]))
	return fallback


static func facing_to_int(facing: String, fallback: int = 2) -> int:
	match facing.to_lower():
		"north":
			return 0
		"east":
			return 1
		"south":
			return 2
		"west":
			return 3
	return fallback


static func command_requires_inventory_refresh(text: String) -> bool:
	var lower = text.to_lower().strip_edges()
	if lower.is_empty():
		return false
	for marker in INVENTORY_COMMAND_MARKERS:
		if lower == marker or lower.begins_with(marker) or lower.contains(marker):
			return true
	return false
