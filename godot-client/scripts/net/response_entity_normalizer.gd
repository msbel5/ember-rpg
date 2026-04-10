extends RefCounted
class_name ResponseEntityNormalizer

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
		var entity_kind = str(entry.get("entity_kind", entity_type)).strip_edges().to_lower()
		var template := guess_entity_template(entry)
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": template,
			"template_id": str(entry.get("template_id", template)).strip_edges().to_lower(),
			"entity_kind": entity_kind,
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
		if entity_kind == "item" or entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_kind in ["furniture", "object", "fixture"] or entity_type in ["furniture", "object", "fixture"] or _entry_looks_like_prop(entry, template):
			normalized["bucket"] = "furniture"
			grouped["furniture"].append(normalized)
		elif entity_kind in ["hostile", "enemy"] or entity_type == "creature" or str(entry.get("disposition", "")).to_lower() == "hostile":
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
		var entity_kind = str(entry.get("entity_kind", entity_type)).strip_edges().to_lower()
		var template := guess_entity_template(entry)
		var normalized = {
			"id": entry.get("id", ""),
			"name": entry.get("name", "Unknown"),
			"template": template,
			"template_id": str(entry.get("template_id", template)).strip_edges().to_lower(),
			"entity_kind": entity_kind,
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
		if entity_kind == "item" or entity_type == "item":
			grouped["items"].append(normalized)
		elif entity_kind in ["furniture", "object", "fixture"] or entity_type in ["furniture", "object", "fixture"] or _entry_looks_like_prop(entry, template):
			normalized["bucket"] = "furniture"
			grouped["furniture"].append(normalized)
		elif entity_kind in ["hostile", "enemy"] or entity_type == "creature" or normalized["is_hostile"]:
			grouped["enemies"].append(normalized)
		else:
			grouped["npcs"].append(normalized)
	return grouped


static func guess_entity_template(entry: Dictionary) -> String:
	var explicit_template = str(entry.get("template_id", entry.get("template", ""))).strip_edges().to_lower()
	var role = _normalize_template_token(str(entry.get("role", entry.get("job", ""))))
	var name_hint = _normalize_template_token(str(entry.get("name", "")))
	var entity_type = _normalize_template_token(str(entry.get("type", entry.get("entity_type", "npc"))))
	var entity_kind = _normalize_template_token(str(entry.get("entity_kind", entity_type)))
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
	if entity_kind in ["item", "furniture", "object", "fixture"] or entity_type in ["item", "furniture", "object", "fixture"]:
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


static func region_entities(region_payload: Dictionary) -> Array:
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


static func _guess_prop_template(name_hint: String, role_hint: String, explicit_template: String) -> String:
	for source in [name_hint, role_hint, _normalize_template_token(explicit_template)]:
		for key in PROP_TEMPLATE_KEYWORDS.keys():
			if source.contains(key):
				return str(PROP_TEMPLATE_KEYWORDS[key])
	return ""


static func _entry_looks_like_prop(entry: Dictionary, template: String = "") -> bool:
	var entity_type = _normalize_template_token(str(entry.get("type", entry.get("entity_type", ""))))
	var entity_kind = _normalize_template_token(str(entry.get("entity_kind", entity_type)))
	if entity_kind in ["npc", "hostile", "enemy", "creature"]:
		return false
	if entity_kind in ["furniture", "object", "fixture"]:
		return true
	if entity_kind == "item":
		return false
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
