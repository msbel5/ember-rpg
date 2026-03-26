extends RefCounted
class_name GameSessionHelpers


static func predict_move(text: String, player_pos: Vector2i, player_facing: int, map_width: int = 20, map_height: int = 15) -> Dictionary:
	var next_pos := player_pos
	var next_facing := player_facing
	var lower = text.to_lower().strip_edges()

	var dir_map = {
		"north": Vector2i(0, -1),
		"south": Vector2i(0, 1),
		"east": Vector2i(1, 0),
		"west": Vector2i(-1, 0),
		"up": Vector2i(0, -1),
		"down": Vector2i(0, 1),
		"left": Vector2i(-1, 0),
		"right": Vector2i(1, 0),
	}
	var facing_map = {
		"north": 0,
		"south": 2,
		"east": 1,
		"west": 3,
		"up": 0,
		"down": 2,
		"left": 3,
		"right": 1,
	}

	for dir_name in dir_map:
		if lower.contains(dir_name):
			next_facing = facing_map[dir_name]
			next_pos += dir_map[dir_name]
			next_pos.x = clampi(next_pos.x, 0, map_width - 1)
			next_pos.y = clampi(next_pos.y, 0, map_height - 1)
			return {"position": next_pos, "facing": next_facing}

	if lower.contains("forward"):
		var forward_vectors = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
		next_pos += forward_vectors[next_facing]
		next_pos.x = clampi(next_pos.x, 0, map_width - 1)
		next_pos.y = clampi(next_pos.y, 0, map_height - 1)
		return {"position": next_pos, "facing": next_facing}

	if lower.begins_with("move to ") or lower.begins_with("move "):
		var coord_str = lower.replace("move to ", "").replace("move ", "")
		var parts = coord_str.split(",")
		if parts.size() < 2:
			parts = coord_str.split(" ")
		if parts.size() >= 2:
			var tx = parts[0].strip_edges().to_int()
			var ty = parts[1].strip_edges().to_int()
			if tx >= 0 and ty >= 0:
				var destination = Vector2i(tx, ty)
				var delta = destination - next_pos
				if abs(delta.x) > abs(delta.y):
					next_facing = 1 if delta.x > 0 else 3
				elif delta.y != 0:
					next_facing = 2 if delta.y > 0 else 0
				next_pos = Vector2i(clampi(tx, 0, map_width - 1), clampi(ty, 0, map_height - 1))

	return {"position": next_pos, "facing": next_facing}


static func build_inventory_popup(inventory: Array, gold: int) -> PopupPanel:
	var popup = PopupPanel.new()
	var vbox = VBoxContainer.new()
	vbox.custom_minimum_size = Vector2(300, 200)

	var title = Label.new()
	title.text = "⚔ Inventory"
	title.add_theme_font_size_override("font_size", 18)
	title.add_theme_color_override("font_color", Color(1, 0.85, 0.3))
	vbox.add_child(title)

	var gold_label = Label.new()
	gold_label.text = "💰 Gold: %d" % gold
	gold_label.add_theme_color_override("font_color", Color(1, 0.9, 0.4))
	vbox.add_child(gold_label)
	vbox.add_child(HSeparator.new())

	if inventory.is_empty():
		var empty_label = Label.new()
		empty_label.text = "Your pack is empty."
		empty_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.6))
		vbox.add_child(empty_label)
	else:
		for item in inventory:
			var item_label = Label.new()
			var item_name = item if item is String else item.get("name", str(item))
			item_label.text = "• %s" % item_name
			vbox.add_child(item_label)

	popup.add_child(vbox)
	return popup
