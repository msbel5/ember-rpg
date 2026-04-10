extends RefCounted
class_name ResponseNormalizer

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
const NPC_TEMPLATE_POOL := ["merchant", "guard", "bard", "rogue", "sage", "priest", "blacksmith", "beggar"]
const ENEMY_TEMPLATE_POOL := ["orc", "goblin", "skeleton", "wolf", "rat", "spider", "bandit", "troll", "zombie"]
const GENERIC_ENTITY_TYPES := ["npc", "creature", "item", "furniture", "object", "fixture", "enemy"]
const GENERIC_CHARACTER_TEMPLATES := ["warrior", "adventurer", "commoner", "resident", "villager", "human", "person"]
const ROLE_TEMPLATE_MAP := {
	"merchant": "merchant",
	"shopkeeper": "merchant",
	"trader": "merchant",
	"vendor": "merchant",
	"guard": "guard",
	"guard_captain": "guard",
	"sentinel": "guard",
	"soldier": "guard",
	"knight": "knight",
	"innkeeper": "innkeeper",
	"blacksmith": "blacksmith",
	"smith": "blacksmith",
	"healer": "healer",
	"priest": "priest",
	"cleric": "priest",
	"mage": "mage",
	"wizard": "mage",
	"wizzard": "mage",
	"witch": "witch",
	"sage": "sage",
	"quest_giver": "quest_giver",
	"bard": "bard",
	"rogue": "rogue",
	"thief": "thief",
	"spy": "spy",
	"beggar": "beggar",
	"orc": "orc",
	"goblin": "goblin",
	"skeleton": "skeleton",
	"wolf": "wolf",
	"rat": "rat",
	"spider": "spider",
	"bandit": "bandit",
	"troll": "troll",
	"zombie": "zombie",
	"ghost": "ghost",
	"fairy": "fairy",
}
const PROP_TEMPLATE_KEYWORDS := {
	"armor_rack": "rack",
	"barrel": "barrel",
	"crate": "crate",
	"chest": "chest",
	"rack": "rack",
	"shelf": "bookshelf",
	"anvil": "anvil",
	"forge": "anvil",
	"altar": "altar",
	"shrine": "altar",
	"pew": "pew",
	"bed": "bed",
	"bench": "bench",
	"table": "table",
	"chair": "chair",
	"counter": "table",
	"desk": "table",
	"workbench": "workbench",
	"bookshelf": "bookshelf",
	"bookcase": "bookshelf",
	"door": "door",
	"well": "well",
	"fountain": "fountain",
	"tree": "tree",
}


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
	flattened["world_entities"] = campaign.get("world_entities", _entities_from_region(campaign.get("region", {})))
	if campaign.has("map_data") and campaign["map_data"] is Dictionary:
		flattened["map_data"] = _merge_and_normalize_map(campaign["map_data"], current_map)
	elif campaign.has("region") and campaign["region"] is Dictionary:
		flattened["map_data"] = campaign_region_to_map(campaign["region"], current_map)
	return flattened


static func normalize_map(data: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	if data.has("map_data") and data["map_data"] is Dictionary:
		return _merge_and_normalize_map(data["map_data"], current_map)
	if data.has("map") and data["map"] is Dictionary:
		return _merge_and_normalize_map(data["map"], current_map)
	return {}


static func normalize_entities(data: Dictionary) -> Dictionary:
	if data.has("world_entities") and data["world_entities"] is Array and not data["world_entities"].is_empty():
		return group_world_entities(data["world_entities"])
	if data.has("entities"):
		if data["entities"] is Dictionary:
			return data["entities"]
		if data["entities"] is Array:
			return group_entity_list(data["entities"])
	if data.has("world_entities") and data["world_entities"] is Array:
		return group_world_entities(data["world_entities"])
	return {}


static func group_entity_list(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": [], "furniture": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
		var template := guess_entity_template(entry)
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": template,
			"position": entry.get("position", [0, 0]),
			"role": entry.get("role", ""),
			"context_actions": context_actions_for(entry),
			"site_anchor_id": entry.get("site_anchor_id", ""),
			"anchor_kind": entry.get("anchor_kind", ""),
			"site_role": entry.get("site_role", ""),
			"placement_priority": int(entry.get("placement_priority", 0)),
			"building_id": entry.get("building_id", ""),
			"home_building_id": entry.get("home_building_id", ""),
			"work_building_id": entry.get("work_building_id", ""),
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type in ["furniture", "object", "fixture"] or _entry_looks_like_prop(entry, template):
			normalized["bucket"] = "furniture"
			grouped["furniture"].append(normalized)
		elif entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped


static func group_world_entities(raw_entities: Array) -> Dictionary:
	var grouped = {"npcs": [], "items": [], "enemies": [], "furniture": []}
	for entry in raw_entities:
		if not (entry is Dictionary):
			continue
		var entity_type = str(entry.get("entity_type", "npc")).to_lower()
		var template := guess_entity_template(entry)
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": template,
			"position": entry.get("position", [0, 0]),
			"role": entry.get("role", entry.get("job", entry.get("assignment", ""))),
			"context_actions": context_actions_for(entry),
			"is_hostile": str(entry.get("disposition", "")).to_lower() == "hostile",
			"site_anchor_id": entry.get("site_anchor_id", ""),
			"anchor_kind": entry.get("anchor_kind", ""),
			"site_role": entry.get("site_role", ""),
			"placement_priority": int(entry.get("placement_priority", 0)),
			"building_id": entry.get("building_id", ""),
			"home_building_id": entry.get("home_building_id", ""),
			"work_building_id": entry.get("work_building_id", ""),
		}
		if entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_type in ["furniture", "object", "fixture"] or _entry_looks_like_prop(entry, template):
			normalized["bucket"] = "furniture"
			grouped["furniture"].append(normalized)
		elif entity_type == "creature" or normalized["is_hostile"]:
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped


static func guess_entity_template(entry: Dictionary) -> String:
	var explicit_template = str(entry.get("template", "")).strip_edges().to_lower()
	var role = _normalize_template_token(str(entry.get("role", entry.get("job", ""))))
	var name_hint = _normalize_template_token(str(entry.get("name", "")))
	var entity_type = _normalize_template_token(str(entry.get("type", entry.get("entity_type", "npc"))))
	if not explicit_template.is_empty():
		var explicit_normalized := _normalize_template_token(explicit_template)
		if ROLE_TEMPLATE_MAP.has(explicit_normalized):
			return str(ROLE_TEMPLATE_MAP[explicit_normalized])
		if PROP_TEMPLATE_KEYWORDS.has(explicit_normalized):
			return str(PROP_TEMPLATE_KEYWORDS[explicit_normalized])
		if not GENERIC_ENTITY_TYPES.has(explicit_normalized) and not GENERIC_CHARACTER_TEMPLATES.has(explicit_normalized):
			return explicit_normalized
	if not role.is_empty():
		for key in ROLE_TEMPLATE_MAP.keys():
			if role.contains(key):
				return str(ROLE_TEMPLATE_MAP[key])
	if entity_type in ["item", "furniture", "object", "fixture"]:
		var prop_template := _guess_prop_template(name_hint, role, explicit_template)
		return prop_template
	var named_prop_template := _guess_prop_template(name_hint, "", explicit_template)
	if not named_prop_template.is_empty():
		return named_prop_template
	for candidate in ROLE_TEMPLATE_MAP.keys():
		if name_hint.contains(candidate):
			return str(ROLE_TEMPLATE_MAP[candidate])
	if entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
		return _deterministic_template_from_pool(entry, ENEMY_TEMPLATE_POOL)
	return _deterministic_template_from_pool(entry, NPC_TEMPLATE_POOL)


static func _guess_prop_template(name_hint: String, role_hint: String, explicit_template: String) -> String:
	for source in [name_hint, role_hint, _normalize_template_token(explicit_template)]:
		for key in PROP_TEMPLATE_KEYWORDS.keys():
			if source.contains(key):
				return str(PROP_TEMPLATE_KEYWORDS[key])
	return ""


static func _entry_looks_like_prop(entry: Dictionary, template: String = "") -> bool:
	var entity_type = _normalize_template_token(str(entry.get("type", entry.get("entity_type", ""))))
	if entity_type in ["item", "furniture", "object", "fixture"]:
		return entity_type != "item"
	var template_hint = _normalize_template_token(template)
	if PROP_TEMPLATE_KEYWORDS.values().has(template_hint):
		return true
	var explicit_template = _normalize_template_token(str(entry.get("template", "")))
	if PROP_TEMPLATE_KEYWORDS.has(explicit_template):
		return true
	var explicit_actor_template := not explicit_template.is_empty() and not GENERIC_ENTITY_TYPES.has(explicit_template) and not GENERIC_CHARACTER_TEMPLATES.has(explicit_template)
	if entity_type == "npc" and explicit_actor_template:
		return false
	var role_hint = _normalize_template_token(str(entry.get("role", entry.get("job", ""))))
	for key in ROLE_TEMPLATE_MAP.keys():
		if role_hint.contains(key):
			return false
	var name_hint = _normalize_template_token(str(entry.get("name", "")))
	for key in PROP_TEMPLATE_KEYWORDS.keys():
		if name_hint.contains(key):
			return true
	return false


static func _deterministic_template_from_pool(entry: Dictionary, pool: Array) -> String:
	if pool.is_empty():
		return ""
	var seed_text := "%s|%s|%s|%s" % [
		str(entry.get("id", "")),
		str(entry.get("name", "")),
		str(entry.get("role", entry.get("job", ""))),
		str(entry.get("entity_type", entry.get("type", ""))),
	]
	return str(pool[posmod(seed_text.hash(), pool.size())])


static func _normalize_template_token(value: String) -> String:
	return value.strip_edges().to_lower().replace(" ", "_").replace("-", "_")


static func context_actions_for(entry: Dictionary) -> Array:
	var template := guess_entity_template(entry)
	if _entry_looks_like_prop(entry, template):
		return ["examine"]
	if entry.has("context_actions") and entry["context_actions"] is Array:
		return entry["context_actions"]
	var entity_type = str(entry.get("type", entry.get("entity_type", "npc"))).to_lower()
	if entity_type == "item":
		return ["pick up", "examine"]
	if entity_type in ["furniture", "object", "fixture"]:
		return ["examine"]
	if entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
		return ["attack", "examine"]
	var role = str(entry.get("role", entry.get("job", ""))).to_lower()
	if ["merchant", "innkeeper", "blacksmith"].has(role):
		return ["talk", "trade", "examine"]
	return ["talk", "examine"]


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


static func _merge_and_normalize_map(map_payload: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	var normalized = current_map.duplicate(true) if not current_map.is_empty() else {}
	normalized.merge(map_payload, true)

	if normalized.has("tiles") and normalized["tiles"] is Array:
		normalized["tiles"] = _normalize_tile_rows(normalized["tiles"], _map_type_from_payload(normalized))
	return normalized


static func _map_type_from_payload(map_payload: Dictionary) -> String:
	if map_payload.has("metadata") and map_payload["metadata"] is Dictionary:
		return str(map_payload["metadata"].get("map_type", "")).to_lower()
	if map_payload.has("map_type"):
		return str(map_payload.get("map_type", "")).to_lower()
	return ""


static func _normalize_tile_rows(rows: Array, map_type: String) -> Array:
	var normalized_rows: Array = []
	for row in rows:
		if not (row is Array):
			normalized_rows.append(row)
			continue
		var normalized_row: Array = []
		for cell in row:
			normalized_row.append(_normalize_tile_symbol(cell, map_type))
		normalized_rows.append(normalized_row)
	return normalized_rows


static func campaign_region_to_map(region_payload: Dictionary, current_map: Dictionary = {}) -> Dictionary:
	var normalized = current_map.duplicate(true) if not current_map.is_empty() else {}
	normalized["width"] = int(region_payload.get("width", current_map.get("width", 0)))
	normalized["height"] = int(region_payload.get("height", current_map.get("height", 0)))
	normalized["metadata"] = {
		"map_type": "campaign_region",
		"region_id": str(region_payload.get("region_id", "")),
		"biome_id": str(region_payload.get("biome_id", "")),
	}
	var layout = region_payload.get("layout", {})
	if layout is Dictionary:
		var center_feature = layout.get("center_feature", {})
		if center_feature is Dictionary and center_feature.has("x") and center_feature.has("y"):
			normalized["spawn_point"] = [int(center_feature.get("x", 1)), mini(int(center_feature.get("y", 1)) + 2, normalized["height"] - 1)]
	var typed_tiles = region_payload.get("typed_tiles", [])
	if typed_tiles is Array and not typed_tiles.is_empty():
		var tile_rows: Array = []
		for row in typed_tiles:
			if not (row is Array):
				continue
			var normalized_row: Array = []
			for cell in row:
				if cell is Dictionary:
					normalized_row.append(str(cell.get("terrain", "grass")))
				else:
					normalized_row.append(_normalize_tile_symbol(cell, "campaign_region"))
			tile_rows.append(normalized_row)
		normalized["tiles"] = tile_rows
	return normalized


static func _entities_from_region(region_payload: Dictionary) -> Array:
	var layout = region_payload.get("layout", {})
	if not (layout is Dictionary):
		return []
	var npc_spawns = layout.get("npc_spawns", [])
	if not (npc_spawns is Array):
		return []
	var entities: Array = []
	for spawn in npc_spawns:
		if not (spawn is Dictionary):
			continue
		entities.append({
			"id": str(spawn.get("id", "")),
			"entity_type": "npc",
			"name": str(spawn.get("role", "Resident")).replace("_", " ").capitalize(),
			"position": [int(spawn.get("x", 0)), int(spawn.get("y", 0))],
			"role": str(spawn.get("role", "resident")),
			"disposition": "friendly",
		})
	return entities


static func _normalize_tile_symbol(raw_value, map_type: String) -> String:
	var tile_name = str(raw_value).strip_edges().to_lower()
	if tile_name.is_empty():
		return "grass"

	match tile_name:
		"#", "wall":
			return "wall"
		"~", "water":
			return "water"
		"t":
			return "wall"
		"d":
			return "door"
		">", "<":
			return "stone_floor"
		",":
			return "stone_floor" if map_type == "dungeon" else "dirt_path"
		"=":
			return "cobblestone" if map_type == "town" else "dirt_path"
		".":
			if map_type == "dungeon":
				return "stone_floor"
			return "grass"
		"corridor":
			return "stone_floor"
		"door":
			return "door"
		"road":
			return "cobblestone"
		"cobble", "cobblestone":
			return "cobblestone"
		"floor", "wood_floor", "stone_floor":
			return tile_name
		"well", "fountain", "tree":
			return tile_name
	return tile_name
