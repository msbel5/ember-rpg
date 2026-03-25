"""
Module 9: Procedural Naming (FR-39..FR-41)
Generates faction-specific NPC names with per-session caching.
"""
import random
from typing import Optional, Dict


# Name banks organized by faction and gender
NAME_BANKS = {
    "human": {
        "male_first": [
            "Aldric", "Bram", "Cedric", "Dorian", "Edmund", "Felix", "Gareth",
            "Hugo", "Ivan", "Jasper", "Kael", "Leander", "Marcus", "Nolan",
            "Osric", "Percival", "Quinn", "Roland", "Silas", "Theron",
            "Ulric", "Victor", "Wyatt", "Xander", "York", "Zephyr",
        ],
        "female_first": [
            "Aria", "Brenna", "Celeste", "Diana", "Elara", "Freya", "Gwen",
            "Helena", "Iris", "Juno", "Kira", "Luna", "Mira", "Nadia",
            "Ophelia", "Petra", "Quinn", "Rosalind", "Selene", "Thalia",
            "Uma", "Viola", "Wren", "Xena", "Yara", "Zara",
        ],
        "surnames": [
            "Ashford", "Blackwood", "Cromwell", "Drayton", "Everett",
            "Fairfax", "Greystone", "Hawthorne", "Ironside", "Jarrett",
            "Kingsley", "Lancaster", "Montague", "Northcott", "Oakley",
            "Pemberton", "Ravencroft", "Stonebridge", "Thornwall", "Whitmore",
        ],
    },
    "dwarf": {
        "male_first": [
            "Balin", "Dain", "Durin", "Farin", "Gimli", "Groin", "Kili",
            "Nori", "Oin", "Thorin", "Bofur", "Dwalin", "Fundin", "Gloin",
            "Hammerhand", "Ironfist", "Jorin", "Kragg", "Magni", "Ragnar",
        ],
        "female_first": [
            "Bruni", "Dagny", "Edda", "Freydis", "Grida", "Hilda",
            "Inga", "Kelda", "Lofn", "Marda", "Nessa", "Ragna",
            "Sigrid", "Thora", "Ulla", "Vala", "Wilda", "Ylva",
        ],
        "clan_names": [
            "Deepdelve", "Ironforge", "Stonehammer", "Goldvein", "Firebeard",
            "Bronzeshield", "Oakenshield", "Battleborn", "Frostaxe", "Steelgrip",
            "Darkmine", "Copperkettle", "Runecarver", "Anvilbreaker", "Gemcutter",
        ],
    },
    "elf": {
        "male_first": [
            "Aelindor", "Caelion", "Elowen", "Faenor", "Galadrim",
            "Ithilion", "Lorien", "Miriel", "Naeron", "Orophin",
            "Rilindel", "Silvan", "Thalion", "Vanyar", "Celeborn",
        ],
        "female_first": [
            "Aranel", "Celebrian", "Elanor", "Finduilas", "Galadriel",
            "Idril", "Luthien", "Melian", "Nienor", "Nimrodel",
            "Rivanel", "Silmarien", "Tinuviel", "Undome", "Vanima",
        ],
        "house_names": [
            "of the Silver Wood", "of the Starlight Vale", "of the Moonwell",
            "of the Eternal Spring", "of the Crystal Shore", "of the Whisperwind",
            "of the Dawnpeak", "of the Twilight Glade", "of the Golden Leaf",
            "of the Emerald Song", "of the Sapphire Tower", "of the Ancient Oak",
        ],
    },
    "orc": {
        "male_first": [
            "Grak", "Thog", "Murg", "Drek", "Korg", "Brug", "Zog",
            "Harg", "Skag", "Thrak", "Grom", "Narg", "Vog", "Warg",
        ],
        "female_first": [
            "Grisha", "Moga", "Shara", "Theka", "Urga", "Breka",
            "Kasha", "Naga", "Rogha", "Vorga", "Zagra", "Drekka",
        ],
        "clan_names": [
            "Bloodfang", "Skullcrusher", "Ironjaw", "Bonesnapper",
            "Goreclaw", "Doomhammer", "Warfist", "Deathbringer",
            "Shadowmaw", "Fleshrender", "Darkblade", "Stormrage",
        ],
    },
}

# Default fallback for unknown factions
NAME_BANKS["default"] = NAME_BANKS["human"]


class NameGenerator:
    """
    Generates unique NPC names per session, with faction-specific word banks.
    Names are cached to ensure consistency (same NPC always gets same name).
    """

    def __init__(self, seed: Optional[int] = None):
        self._cache: Dict[str, str] = {}  # npc_id → generated name
        self._used_names: set = set()      # all names used this session
        self._rng = random.Random(seed)

    def generate_name(self, faction: str = "human", gender: str = "male",
                      npc_id: Optional[str] = None) -> str:
        """
        Generate a unique name for an NPC.

        Args:
            faction: NPC faction (human, dwarf, elf, orc)
            gender: "male" or "female"
            npc_id: If provided, cache the name for this NPC ID

        Returns:
            Generated name string (unique within this session)
        """
        # Return cached name if NPC already has one
        if npc_id and npc_id in self._cache:
            return self._cache[npc_id]

        bank = NAME_BANKS.get(faction.lower(), NAME_BANKS["default"])
        first_key = f"{gender.lower()}_first"
        first_names = bank.get(first_key, bank.get("male_first", ["Unknown"]))

        # Generate unique name (try up to 50 times)
        for _ in range(50):
            first = self._rng.choice(first_names)
            name = self._build_full_name(first, faction, bank)
            if name not in self._used_names:
                break
        else:
            # Exhausted unique names — append number
            base = self._rng.choice(first_names)
            name = f"{base} the {self._rng.randint(2, 99)}th"

        self._used_names.add(name)
        if npc_id:
            self._cache[npc_id] = name
        return name

    def _build_full_name(self, first: str, faction: str, bank: dict) -> str:
        """Build full name based on faction naming conventions."""
        faction_lower = faction.lower()

        if faction_lower == "dwarf":
            clan = self._rng.choice(bank.get("clan_names", ["Stoneborn"]))
            return f"{first} {clan}"

        elif faction_lower == "elf":
            house = self._rng.choice(bank.get("house_names", ["of the Forest"]))
            return f"{first} {house}"

        elif faction_lower == "orc":
            clan = self._rng.choice(bank.get("clan_names", ["Warclan"]))
            return f"{first} {clan}"

        else:
            # Human-style: first + surname
            surname = self._rng.choice(bank.get("surnames", ["Smith"]))
            return f"{first} {surname}"

    def get_cached_name(self, npc_id: str) -> Optional[str]:
        """Get cached name for an NPC, or None if not generated yet."""
        return self._cache.get(npc_id)

    def clear(self):
        """Clear all cached names (for new session)."""
        self._cache.clear()
        self._used_names.clear()
