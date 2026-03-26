"""
Ember RPG - Core Engine
Monster bestiary (MonsterDatabase, Monster dataclass)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from engine.data_loader import load_registry_list_from_path


class MonsterType(Enum):
    """Monster categories."""
    BEAST = "beast"
    UNDEAD = "undead"
    HUMANOID = "humanoid"
    ELEMENTAL = "elemental"
    BOSS = "boss"
    ABERRATION = "aberration"


@dataclass
class Attack:
    """Single attack action for a monster."""
    name: str
    damage_dice: str
    damage_type: str
    attack_bonus: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "damage_dice": self.damage_dice,
            "damage_type": self.damage_type,
            "attack_bonus": self.attack_bonus,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attack":
        return cls(
            name=data["name"],
            damage_dice=data["damage_dice"],
            damage_type=data["damage_type"],
            attack_bonus=data["attack_bonus"],
        )


@dataclass
class Abilities:
    """Special abilities, resistances, and immunities."""
    special_moves: List[str] = field(default_factory=list)
    resistances: List[str] = field(default_factory=list)
    immunities: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "special_moves": self.special_moves,
            "resistances": self.resistances,
            "immunities": self.immunities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Abilities":
        return cls(
            special_moves=data.get("special_moves", []),
            resistances=data.get("resistances", []),
            immunities=data.get("immunities", []),
        )


@dataclass
class Stats:
    """D&D-style ability scores."""
    str: int
    dex: int
    con: int
    int: int
    wis: int
    cha: int

    def modifier(self, stat: str) -> int:
        """Return ability modifier for a given stat name."""
        value = getattr(self, stat)
        return (value - 10) // 2

    def to_dict(self) -> dict:
        return {
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "int": self.int,
            "wis": self.wis,
            "cha": self.cha,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Stats":
        return cls(
            str=data["str"],
            dex=data["dex"],
            con=data["con"],
            int=data["int"],
            wis=data["wis"],
            cha=data["cha"],
        )


@dataclass
class Monster:
    """
    Full monster definition for Ember RPG.

    Attributes:
        id: Unique identifier (slug)
        name: Display name
        type: MonsterType category
        cr: Challenge rating (0.125–30)
        hp: Hit points
        armor_class: AC value
        speed: Movement speed in feet
        stats: Ability scores (str/dex/con/int/wis/cha)
        attacks: List of attack actions
        abilities: Special moves, resistances, immunities
        xp_reward: XP granted on defeat
        loot_table: List of item id references
    """
    id: str
    name: str
    type: MonsterType
    cr: float
    hp: int
    armor_class: int
    speed: int
    stats: Stats
    attacks: List[Attack]
    abilities: Abilities
    xp_reward: int
    loot_table: List[str] = field(default_factory=list)

    def is_resistant_to(self, damage_type: str) -> bool:
        """Check if monster resists a damage type."""
        return damage_type.lower() in [r.lower() for r in self.abilities.resistances]

    def is_immune_to(self, damage_type: str) -> bool:
        """Check if monster is immune to a damage type."""
        return damage_type.lower() in [i.lower() for i in self.abilities.immunities]

    def has_ability(self, ability_name: str) -> bool:
        """Check if monster has a named special move."""
        return any(a.lower() == ability_name.lower() for a in self.abilities.special_moves)

    def to_dict(self) -> dict:
        """Serialize monster to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "cr": self.cr,
            "hp": self.hp,
            "armor_class": self.armor_class,
            "speed": self.speed,
            "stats": self.stats.to_dict(),
            "attacks": [a.to_dict() for a in self.attacks],
            "abilities": self.abilities.to_dict(),
            "xp_reward": self.xp_reward,
            "loot_table": self.loot_table,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Monster":
        """Deserialize monster from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            type=MonsterType(data["type"]),
            cr=data["cr"],
            hp=data["hp"],
            armor_class=data["armor_class"],
            speed=data["speed"],
            stats=Stats.from_dict(data["stats"]),
            attacks=[Attack.from_dict(a) for a in data.get("attacks", [])],
            abilities=Abilities.from_dict(data.get("abilities", {})),
            xp_reward=data["xp_reward"],
            loot_table=[
                entry["id"] if isinstance(entry, dict) else entry
                for entry in data.get("loot_table", [])
            ],
        )

    def __repr__(self) -> str:
        return f"<Monster {self.name} (CR {self.cr}, {self.type.value}) HP={self.hp}>"


class MonsterDatabase:
    """Load and manage monster definitions from JSON.

    Mirrors the interface of ItemDatabase / SpellDatabase.
    """

    def __init__(self, filepath: Optional[str] = None):
        """
        Initialize monster database.

        Args:
            filepath: Path to monsters JSON file (optional).
                      Expected structure: {"monsters": [...]}
        """
        self.monsters: List[Monster] = []
        if filepath:
            self.load(filepath)

    def load(self, filepath: str):
        """
        Load monsters from a JSON file.

        Args:
            filepath: Path to JSON file containing monster definitions.
        """
        for monster_data in load_registry_list_from_path(filepath, "monsters"):
            monster = Monster.from_dict(monster_data)
            self.monsters.append(monster)

    def add(self, monster: Monster):
        """Add a monster to the database."""
        self.monsters.append(monster)

    def get(self, name: str) -> Optional[Monster]:
        """
        Get monster by name (case-insensitive).

        Args:
            name: Monster name or id

        Returns:
            Monster if found, None otherwise
        """
        name_lower = name.lower()
        for monster in self.monsters:
            if monster.name.lower() == name_lower or monster.id.lower() == name_lower:
                return monster
        return None

    def filter(
        self,
        monster_type: Optional[MonsterType] = None,
        min_cr: Optional[float] = None,
        max_cr: Optional[float] = None,
    ) -> List[Monster]:
        """
        Filter monsters by criteria.

        Args:
            monster_type: Filter by MonsterType
            min_cr: Minimum challenge rating (inclusive)
            max_cr: Maximum challenge rating (inclusive)

        Returns:
            List of matching monsters
        """
        results = self.monsters

        if monster_type is not None:
            results = [m for m in results if m.type == monster_type]
        if min_cr is not None:
            results = [m for m in results if m.cr >= min_cr]
        if max_cr is not None:
            results = [m for m in results if m.cr <= max_cr]

        return results
