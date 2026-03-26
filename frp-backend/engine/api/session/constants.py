"""Shared constants for GameSession."""

DEFAULT_EQUIPMENT_SLOTS = {
    "weapon": None,
    "armor": None,
    "shield": None,
    "helmet": None,
    "boots": None,
    "gloves": None,
    "ring": None,
    "amulet": None,
}

LEGACY_SLOT_ALIASES = {
    "offhand": "shield",
    "off_hand": "shield",
    "accessory": "ring",
}

TIMED_CONDITION_NAMES = {"back_strain"}
