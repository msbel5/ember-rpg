## Catalog data helpers for the creation wizard.
## Parses adapter, class, and ability data from the backend catalog.
## Extracted from title_screen.gd for SOLID compliance.
extends RefCounted
class_name CreationCatalog


static func catalog_from(creation_payload: Dictionary, cached_catalog: Dictionary) -> Dictionary:
	if creation_payload.has("catalog") and creation_payload["catalog"] is Dictionary:
		return creation_payload["catalog"]
	return cached_catalog


static func catalog_entries(catalog: Dictionary, key: String) -> Array:
	var raw = catalog.get(key, [])
	return raw if raw is Array else []


static func adapter_entries(catalog: Dictionary) -> Array:
	return catalog_entries(catalog, "adapter_catalog")


static func class_entries(catalog: Dictionary) -> Array:
	return catalog_entries(catalog, "class_catalog")


static func ability_order(catalog: Dictionary) -> Array:
	var order = catalog.get("ability_order", [])
	if order is Array and not order.is_empty():
		return order
	return ["MIG", "AGI", "END", "MND", "INS", "PRE"]


static func default_class_id(catalog: Dictionary) -> String:
	return str(catalog.get("default_class_id", "warrior"))


static func default_adapter_id(catalog: Dictionary) -> String:
	return str(catalog.get("default_adapter_id", "fantasy_ember"))


static func default_profile_id(catalog: Dictionary) -> String:
	return str(catalog.get("default_profile_id", "standard"))


static func class_entry(catalog: Dictionary, class_id: String) -> Dictionary:
	for entry in class_entries(catalog):
		if entry is Dictionary and str(entry.get("id", "")) == class_id:
			return entry
	return {}


static func class_priorities(catalog: Dictionary, class_id: String) -> Array:
	var entry := class_entry(catalog, class_id)
	var priorities = entry.get("stat_priorities", entry.get("priority_stats", []))
	if priorities is Array:
		return priorities
	return []


static func humanize_id(raw_id: String) -> String:
	return raw_id.replace("_", " ").capitalize()


static func modifier(value: int) -> int:
	return int(floor(float(value - 10) / 2.0))


static func roll_text(values) -> String:
	if values == null:
		return "—"
	if values is Array:
		var parts: Array[String] = []
		for v in values:
			parts.append(str(v))
		return ", ".join(parts)
	return str(values)


static func adapter_label_map(catalog: Dictionary) -> Dictionary:
	var result := {}
	for entry in adapter_entries(catalog):
		if entry is Dictionary:
			result[str(entry.get("id", ""))] = str(entry.get("label", entry.get("id", "")))
	return result


static func settlement_label_map(catalog: Dictionary) -> Dictionary:
	var raw = catalog.get("settlement_labels", {})
	return raw if raw is Dictionary else {}


static func faction_label_map(catalog: Dictionary) -> Dictionary:
	var raw = catalog.get("faction_labels", {})
	return raw if raw is Dictionary else {}


static func genesis_defaults(catalog: Dictionary) -> Dictionary:
	var raw = catalog.get("genesis_defaults", {})
	return raw if raw is Dictionary else {}


static func suggested_stats_for(catalog: Dictionary, class_id: String, pool: Array) -> Dictionary:
	var priorities := class_priorities(catalog, class_id)
	var abilities := ability_order(catalog)
	var sorted_pool := pool.duplicate()
	sorted_pool.sort()
	sorted_pool.reverse()
	var result := {}
	for i in range(abilities.size()):
		if i < sorted_pool.size():
			result[abilities[i]] = sorted_pool[i]
		else:
			result[abilities[i]] = 10
	# Assign highest values to priority stats
	if not priorities.is_empty() and sorted_pool.size() >= abilities.size():
		var priority_values := sorted_pool.slice(0, priorities.size())
		var remaining_values := sorted_pool.slice(priorities.size())
		var non_priority_abilities: Array[String] = []
		for a in abilities:
			if not priorities.has(a):
				non_priority_abilities.append(a)
		for i in range(priorities.size()):
			if i < priority_values.size():
				result[priorities[i]] = priority_values[i]
		for i in range(non_priority_abilities.size()):
			if i < remaining_values.size():
				result[non_priority_abilities[i]] = remaining_values[i]
	return result
