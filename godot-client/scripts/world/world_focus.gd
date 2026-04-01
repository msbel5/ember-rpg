## Focus summary and action helpers for the world viewport.
## Shows contextual information about what the player is looking at.
extends RefCounted
class_name WorldFocus


static func default_summary(location: String, entities: Dictionary) -> String:
	var contact_name := _first_entity_name(entities, "npcs")
	var threat_name := _first_entity_name(entities, "enemies")
	var loot_count := _bucket_size(entities, "items")
	var parts: Array[String] = ["Focus: %s" % location]
	if not contact_name.is_empty():
		parts.append("Start with %s" % contact_name)
	else:
		parts.append("%d locals on the survey" % _bucket_size(entities, "npcs"))
	if not threat_name.is_empty():
		parts.append("%s is the nearest pressure" % threat_name)
	elif _bucket_size(entities, "enemies") > 0:
		parts.append("%d threat markers in range" % _bucket_size(entities, "enemies"))
	else:
		parts.append("%d loot pings" % loot_count)
	return "  |  ".join(parts)


static func tile_summary(tile_name: String, tile_position: Vector2i, entity: Dictionary) -> String:
	if not entity.is_empty():
		var entity_name := WorldInteraction.display_entity_name(entity)
		return "Focus: %s  |  Primary: %s" % [entity_name, WorldInteraction.command_for_entity(entity)]
	if tile_name.is_empty():
		return ""
	return "Focus: %s  |  Primary: %s" % [
		WorldInteraction.display_tile_name(tile_name),
		WorldInteraction.command_for_tile(tile_position, tile_name),
	]


static func default_actions(entities: Dictionary) -> Array:
	var actions: Array = []
	var contact := _first_entity(entities, "npcs")
	if not contact.is_empty():
		actions.append({
			"label": "Talk: %s" % _short_label(WorldInteraction.display_entity_name(contact)),
			"command": WorldInteraction.command_for_entity(contact),
		})
	var threat := _first_entity(entities, "enemies")
	if not threat.is_empty():
		actions.append({
			"label": "Scout: %s" % _short_label(WorldInteraction.display_entity_name(threat)),
			"command": "examine %s" % str(threat.get("name", "threat")).strip_edges().to_lower(),
		})
	var loot := _first_entity(entities, "items")
	if actions.size() < 2 and not loot.is_empty():
		actions.append({
			"label": "Loot: %s" % _short_label(WorldInteraction.display_entity_name(loot)),
			"command": WorldInteraction.command_for_entity(loot),
		})
	if actions.size() < 2:
		actions.append({"label": "Inventory", "command": "inventory"})
	if actions.size() < 2:
		actions.append({"label": "Look Around", "command": "look around"})
	return actions.slice(0, 2)


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
					"label": norm.capitalize(),
					"command": WorldInteraction.command_for_context_action(norm, entity_name, str(entity.get("bucket", "npc"))),
				})
				if result.size() >= 2:
					return result
		result.append({"label": "Primary", "command": WorldInteraction.command_for_entity(entity)})
		result.append({"label": "Inventory", "command": "inventory"})
		return result
	if tile_name.is_empty():
		return []
	var actions: Array = [{"label": "Primary", "command": WorldInteraction.command_for_tile(tile_position, tile_name)}]
	if not str(actions[0].get("command", "")).begins_with("move to"):
		actions.append({"label": "Move There", "command": "move to %d,%d" % [tile_position.x, tile_position.y]})
	else:
		actions.append({"label": "Look Around", "command": "look around"})
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
