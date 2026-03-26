extends RefCounted
class_name PovRendererConfig


const PALETTES = {
	"tavern": {
		"sky": Color(0.12, 0.08, 0.05),
		"wall": Color(0.25, 0.18, 0.10),
		"floor": Color(0.20, 0.14, 0.08),
		"ambient": Color(0.9, 0.7, 0.3, 0.15)
	},
	"forest": {
		"sky": Color(0.15, 0.25, 0.35),
		"wall": Color(0.10, 0.20, 0.08),
		"floor": Color(0.18, 0.22, 0.10),
		"ambient": Color(0.4, 0.8, 0.3, 0.08)
	},
	"dungeon": {
		"sky": Color(0.04, 0.04, 0.06),
		"wall": Color(0.15, 0.14, 0.16),
		"floor": Color(0.10, 0.09, 0.11),
		"ambient": Color(0.3, 0.3, 0.5, 0.10)
	},
	"harbor": {
		"sky": Color(0.35, 0.55, 0.75),
		"wall": Color(0.30, 0.25, 0.18),
		"floor": Color(0.45, 0.40, 0.30),
		"ambient": Color(0.9, 0.85, 0.6, 0.1)
	},
	"cave": {
		"sky": Color(0.03, 0.03, 0.04),
		"wall": Color(0.12, 0.10, 0.08),
		"floor": Color(0.08, 0.07, 0.06),
		"ambient": Color(0.2, 0.15, 0.1, 0.05)
	},
	"default": {
		"sky": Color(0.20, 0.25, 0.35),
		"wall": Color(0.25, 0.22, 0.18),
		"floor": Color(0.22, 0.20, 0.16),
		"ambient": Color(0.5, 0.5, 0.5, 0.08)
	}
}

const ENTITY_COLORS = {
	"warrior": Color(0.2, 0.4, 0.8),
	"mage": Color(0.6, 0.2, 0.8),
	"rogue": Color(0.3, 0.3, 0.3),
	"priest": Color(0.9, 0.85, 0.5),
	"merchant": Color(0.8, 0.6, 0.2),
	"guard": Color(0.5, 0.5, 0.6),
	"innkeeper": Color(0.7, 0.5, 0.3),
	"quest_giver": Color(0.9, 0.8, 0.1),
	"blacksmith": Color(0.6, 0.3, 0.1),
	"beggar": Color(0.4, 0.35, 0.3),
	"goblin": Color(0.3, 0.5, 0.2),
	"skeleton": Color(0.85, 0.85, 0.8),
	"wolf": Color(0.4, 0.35, 0.3),
	"orc": Color(0.3, 0.4, 0.2),
	"spider": Color(0.2, 0.15, 0.2),
	"bandit": Color(0.4, 0.2, 0.2),
	"dragon": Color(0.7, 0.15, 0.1),
	"zombie": Color(0.3, 0.4, 0.3),
	"notice_board": Color(0.5, 0.35, 0.15),
	"well": Color(0.3, 0.4, 0.5),
	"crate": Color(0.45, 0.35, 0.2),
	"barrel": Color(0.4, 0.3, 0.15),
	"chest": Color(0.6, 0.5, 0.1),
	"market_stall": Color(0.5, 0.4, 0.2),
	"fountain": Color(0.3, 0.5, 0.7),
	"campfire": Color(0.8, 0.4, 0.1),
	"default": Color(0.5, 0.5, 0.5),
}

const OBJECT_TEMPLATES = [
	"notice_board", "well", "crate", "barrel", "chest",
	"market_stall", "fountain", "campfire",
]

const FACING_VECTORS = [
	Vector2i(0, -1),
	Vector2i(1, 0),
	Vector2i(0, 1),
	Vector2i(-1, 0),
]

const VIEW_DEPTH = 5
const VIEW_WIDTH = 3

const BACKGROUNDS = {
	"harbor": "res://assets/generated/test_harbor_bg.jpg",
	"town": "res://assets/generated/test_harbor_bg.jpg",
	"dungeon": "res://assets/generated/test_dungeon_bg.jpg",
	"cave": "res://assets/generated/test_dungeon_bg.jpg",
}


static func resolve_background(location: String) -> String:
	for key in BACKGROUNDS:
		if location.contains(key):
			return BACKGROUNDS[key]
	return ""
