## Focus summary and action helpers for the world viewport.
## Shows contextual information about what the player is looking at.
extends RefCounted
class_name WorldFocus


static func default_summary(location: String, entities: Dictionary) -> String:
	var contact_name := _first_entity_name(entities, "npcs")
	var threat_name := _first_entity_name(entities, "enemies")
	var parts: Array[String] = ["Focus: %s" % location]
	if not contact_name.is_empty():
		parts.append("Contact: %s" % contact_name)
	else:
		parts.append("%d locals" % _bucket_size(entities, "npcs"))
	if not threat_name.is_empty():
		parts.append("Threat: %s" % threat_name)
	elif _bucket_size(entities, "enemies") > 0:
		parts.append("%d threats" % _bucket_size(entities, "enemies"))
	else:
		parts.append("Area calm")
	return "  |  ".join(parts)


static func tile_summary(tile_name: String, tile_position: Vector2i, entity: Dictionary) -> String:
	if not entity.is_empty():
		var entity_name := WorldInteraction.display_entity_name(entity)
		return "Focus: %s  |  Action ready" % [entity_name]
	if tile_name.is_empty():
		return ""
	return "Focus: %s  |  Examine or rest here" % [WorldInteraction.display_tile_name(tile_name)]


static func default_actions(entities: Dictionary) -> Array:
	var actions: Array = []
	var contact := _first_entity(entities, "npcs")
	if not contact.is_empty():
		actions.append({
			"verb": "talk",
			"label": "Talk to %s" % _short_label(WorldInteraction.display_entity_name(contact)),
			"command": "talk %s" % str(contact.get("name", "contact")).strip_edges().to_lower(),
		})
	var threat := _first_entity(entities, "enemies")
	if not threat.is_empty():
		actions.append({
			"verb": "attack",
			"label": "Attack %s" % _short_label(WorldInteraction.display_entity_name(threat)),
			"command": "attack %s" % str(threat.get("name", "threat")).strip_edges().to_lower(),
		})
	var loot := _first_entity(entities, "items")
	if not loot.is_empty():
		actions.append({
			"verb": "use",
			"label": "Use %s" % _short_label(WorldInteraction.display_entity_name(loot)),
			"command": WorldInteraction.command_for_entity(loot),
		})
	actions.append({"verb": "examine", "label": "Examine the area", "command": "look around"})
	actions.append({"verb": "rest", "label": "Rest and recover", "command": "rest"})
	return actions


static func actions_for_tile(tile_position: Vector2i, tile_name: String, entity: Dictionary) -> Array:
	if not entity.is_empty():
		var ctx_actions = entity.get("context_actions", [])
		var entity_name := str(entity.get("name", "target")).strip_edges().to_lower()
		var result: Array = []
		if ctx_actions is Array:
			for action in ctx_actions:
				var norm := str(action).strip_edges().to_lower()
				if norm.is_empty():
					continue
				result.append({
					"verb": _verb_for_action(norm, str(entity.get("bucket", "npc"))),
					"label": _label_for_action(norm, entity_name),
					"command": WorldInteraction.command_for_context_action(norm, entity_name, str(entity.get("bucket", "npc"))),
				})
				if result.size() >= 4:
					return result
		result.append(_named_action_for_entity(entity))
		result.append({"verb": "examine", "label": "Examine %s" % _short_label(WorldInteraction.display_entity_name(entity)), "command": "examine %s" % entity_name})
		result.append({"verb": "rest", "label": "Rest", "command": "rest"})
		return result
	if tile_name.is_empty():
		return [
			{"verb": "examine", "label": "Examine the area", "command": "look around"},
			{"verb": "rest", "label": "Rest", "command": "rest"},
		]
	var primary_command := WorldInteraction.command_for_tile(tile_position, tile_name)
	var actions: Array = []
	if not str(primary_command).begins_with("move to"):
		actions.append({"verb": "use", "label": _label_for_tile_command(primary_command, tile_name), "command": primary_command})
	actions.append({"verb": "examine", "label": "Examine %s" % WorldInteraction.display_tile_name(tile_name), "command": "examine %s" % tile_name})
	actions.append({"verb": "rest", "label": "Rest", "command": "rest"})
	return actions


# --- helpers ---------------------------------------------------------------

static func _first_entity(entities: Dictionary, bucket: String) -> Dictionary:
	var entries = entities.get(bucket, [])
	for entry in entries:
		if entry is Dictionary:
			return entry
	return {}


static func _first_entity_name(entities: Dictionary, bucket: String) -> String:
	var entry := _first_entity(entities, bucket)
	if entry.is_empty():
		return ""
	return WorldInteraction.display_entity_name(entry)


static func _bucket_size(entities: Dictionary, bucket: String) -> int:
	return entities.get(bucket, []).size()


static func _short_label(label: String) -> String:
	var trimmed := label.strip_edges()
	if trimmed.length() <= 14:
		return trimmed
	return trimmed.substr(0, 13) + "…"


static func _named_action_for_entity(entity: Dictionary) -> Dictionary:
	var bucket := str(entity.get("bucket", "npc")).strip_edges().to_lower()
	var name := _short_label(WorldInteraction.display_entity_name(entity))
	match bucket:
		"enemy":
			return {"verb": "attack", "label": "Attack %s" % name, "command": "attack %s" % str(entity.get("name", "threat")).strip_edges().to_lower()}
		"item":
			return {"verb": "use", "label": "Use %s" % name, "command": WorldInteraction.command_for_entity(entity)}
		"furniture":
			return {"verb": "use", "label": "Use %s" % name, "command": WorldInteraction.command_for_entity(entity)}
		_:
			return {"verb": "talk", "label": "Talk to %s" % name, "command": WorldInteraction.command_for_entity(entity)}


static func _label_for_action(action: String, entity_name: String) -> String:
	var display_name := _short_label(WorldInteraction.display_entity_name({"name": entity_name}))
	match action:
		"talk":
			return "Talk to %s" % display_name
		"attack":
			return "Attack %s" % display_name
		"trade", "pick up":
			return "Use %s" % display_name
		"examine":
			return "Examine %s" % display_name
		"rest":
			return "Rest"
	return "Use %s" % display_name


static func _label_for_tile_command(command: String, tile_name: String) -> String:
	if command.begins_with("open "):
		return "Use %s" % WorldInteraction.display_tile_name(tile_name)
	if command.begins_with("examine "):
		return "Examine %s" % WorldInteraction.display_tile_name(tile_name)
	return "Use %s" % WorldInteraction.display_tile_name(tile_name)


static func _verb_for_action(action: String, bucket: String) -> String:
	match action:
		"talk":
			return "talk"
		"attack":
			return "attack"
		"trade", "pick up":
			return "use"
		"examine":
			return "examine"
		"rest":
			return "rest"
	if bucket == "enemy":
		return "attack"
	if bucket == "item" or bucket == "furniture":
		return "use"
	return "talk"
