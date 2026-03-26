"""
Ember RPG - Core Engine
Universal Character class for PC, NPC, and monsters.

The character model now carries both legacy Ember fields and the canonical
D&D-style state used by the final rules pass.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ProficiencyLevel(Enum):
    """Skill proficiency tiers."""
    UNTRAINED = 0
    TRAINED = 2
    EXPERT = 4
    MASTER = 6


@dataclass
class Character:
    """
    Universal character representation for all entities.
    
    Attributes:
        name: Character name
        race: Race/species (default "Human")
        classes: Dictionary of class_name -> level (supports multiclass)
        stats: Six core stats (MIG, AGI, END, MND, INS, PRE), range 3-20
        hp: Current hit points
        max_hp: Maximum hit points
        ac: Armor class (defense)
        initiative_bonus: Bonus to initiative rolls
        spell_points: Current spell points
        max_spell_points: Maximum spell points
        skills: Dictionary of skill_name -> proficiency bonus
        gold: Gold pieces
        inventory: List of item IDs
        equipment: Dictionary of slot -> item_id
        conditions: List of active conditions (poisoned, stunned, etc.)
        xp: Current experience points
        level: Character level (1-20)
    """
    
    # Identity
    name: str
    race: str = "Human"
    classes: Dict[str, int] = field(default_factory=dict)
    
    # Core Stats (3-20 range, default 10)
    stats: Dict[str, int] = field(default_factory=lambda: {
        'MIG': 10, 'AGI': 10, 'END': 10,
        'MND': 10, 'INS': 10, 'PRE': 10
    })
    
    # Combat
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    initiative_bonus: int = 0
    
    # Resources
    spell_points: int = 0
    max_spell_points: int = 0
    
    # Progression
    xp: int = 0
    level: int = 1
    
    # Skills (skill_name -> numeric override / legacy proficiency bonus)
    skills: Dict[str, int] = field(default_factory=dict)
    skill_proficiencies: List[str] = field(default_factory=list)
    expertise_skills: List[str] = field(default_factory=list)

    # Inventory
    gold: int = 0
    inventory: List[str] = field(default_factory=list)
    equipment: Dict[str, str] = field(default_factory=dict)

    # State
    conditions: List[str] = field(default_factory=list)
    condition_states: List[Dict[str, Any]] = field(default_factory=list)
    exhaustion_level: int = 0
    hit_dice_total: int = 0
    hit_dice_remaining: int = 0
    last_long_rest_hour: Optional[float] = None
    death_save_successes: int = 0
    death_save_failures: int = 0
    is_stable: bool = False
    use_death_saves: bool = False
    alignment: str = "TN"
    alignment_axes: Dict[str, int] = field(default_factory=lambda: {
        "law_chaos": 0,
        "good_evil": 0,
    })
    creation_answers: List[Dict[str, Any]] = field(default_factory=list)
    creation_profile: Dict[str, Any] = field(default_factory=dict)
    
    # --- Skill -> Stat Mapping ---
    DND_SKILL_STATS = {
        'athletics': 'MIG',
        'acrobatics': 'AGI',
        'sleight_of_hand': 'AGI',
        'stealth': 'AGI',
        'arcana': 'MND',
        'history': 'MND',
        'investigation': 'MND',
        'nature': 'MND',
        'religion': 'MND',
        'animal_handling': 'INS',
        'insight': 'INS',
        'medicine': 'INS',
        'perception': 'INS',
        'survival': 'INS',
        'deception': 'PRE',
        'intimidation': 'PRE',
        'performance': 'PRE',
        'persuasion': 'PRE',
    }

    LEGACY_SKILL_STATS = {
        'melee': 'MIG',
        'ranged': 'AGI',
        'defense': 'END',
        'lore': 'MND',
        'trade': 'PRE',
        'appraisal': 'MND',
        'smithing': 'MIG',
        'cooking': 'MND',
        'healing': 'INS',
        'herbalism': 'INS',
        'divine_magic': 'PRE',
        'patrol': 'INS',
        'lockpick': 'AGI',
        'climb': 'AGI',
        'sneak': 'AGI',
    }

    SKILL_STATS = {**DND_SKILL_STATS, **LEGACY_SKILL_STATS}

    CLASS_HIT_DICE = {
        "warrior": 10,
        "rogue": 8,
        "mage": 6,
        "priest": 8,
    }
    
    # --- Derived Properties ---

    def __post_init__(self) -> None:
        default_stats = {
            'MIG': 10, 'AGI': 10, 'END': 10,
            'MND': 10, 'INS': 10, 'PRE': 10,
        }
        merged_stats = dict(default_stats)
        merged_stats.update(dict(self.stats or {}))
        self.stats = merged_stats
        self.sync_derived_progression()
    
    @property
    def total_level(self) -> int:
        """
        Calculate total level across all classes.
        
        Returns:
            Sum of all class levels, or 0 if no classes
        """
        return sum(self.classes.values()) if self.classes else 0

    @property
    def effective_level(self) -> int:
        """Level used for proficiency and hit-dice calculations."""
        return max(1, int(self.level or 1), int(self.total_level or 0))

    @property
    def dominant_class(self) -> Optional[str]:
        """
        Get the class with the highest level.
        
        Returns:
            Class name with highest level, or None if no classes
            (if tie, returns first by insertion order)
        """
        if not self.classes:
            return None
        return max(self.classes.items(), key=lambda x: x[1])[0]

    @property
    def proficiency_bonus(self) -> int:
        return ((self.effective_level - 1) // 4) + 2

    @property
    def hit_die_size(self) -> int:
        dominant = str(self.dominant_class or "warrior").lower()
        return self.CLASS_HIT_DICE.get(dominant, 8)

    @property
    def passive_perception(self) -> int:
        return self.passive_score("perception")

    @property
    def passive_investigation(self) -> int:
        return self.passive_score("investigation")

    @property
    def passive_insight(self) -> int:
        return self.passive_score("insight")

    @property
    def passives(self) -> Dict[str, int]:
        return {
            "perception": self.passive_perception,
            "investigation": self.passive_investigation,
            "insight": self.passive_insight,
        }
    
    # --- Methods ---
    
    def stat_modifier(self, stat: str) -> int:
        """
        Calculate the modifier for a given stat.
        
        Formula: (stat_value - 10) // 2
        
        Args:
            stat: Stat name (MIG, AGI, END, MND, INS, PRE)
        
        Returns:
            Modifier value (e.g., 16 -> +3, 8 -> -1)
        
        Raises:
            ValueError: If stat name is invalid
        """
        if stat not in self.stats:
            raise ValueError(f"Unknown stat: {stat}")
        return (self.stats[stat] - 10) // 2

    def has_proficiency(self, skill: str) -> bool:
        skill_lower = skill.lower()
        return skill_lower in {value.lower() for value in self.skill_proficiencies}

    def has_expertise(self, skill: str) -> bool:
        skill_lower = skill.lower()
        return skill_lower in {value.lower() for value in self.expertise_skills}

    def passive_score(self, skill: str) -> int:
        return 10 + self.skill_bonus(skill)

    def skill_bonus(self, skill: str) -> int:
        """
        Calculate total bonus for a skill check.
        
        Formula: governing_stat_modifier + proficiency_bonus
        
        Args:
            skill: Skill name (lowercase, e.g., 'stealth', 'arcana')
        
        Returns:
            Total skill bonus
        
        Raises:
            ValueError: If skill name is invalid
        """
        skill_lower = skill.lower().strip().replace(" ", "_")
        if skill_lower not in self.SKILL_STATS:
            raise ValueError(f"Unknown skill: {skill}")

        governing_stat = self.SKILL_STATS[skill_lower]
        stat_mod = self.stat_modifier(governing_stat)
        legacy_bonus = int(self.skills.get(skill_lower, 0))

        if skill_lower in self.DND_SKILL_STATS:
            prof_bonus = 0
            if self.has_expertise(skill_lower):
                prof_bonus = self.proficiency_bonus * 2
            elif self.has_proficiency(skill_lower):
                prof_bonus = self.proficiency_bonus
            elif legacy_bonus:
                prof_bonus = legacy_bonus
                legacy_bonus = 0
            return stat_mod + prof_bonus + legacy_bonus

        return stat_mod + legacy_bonus
    
    def add_class(self, class_name: str, levels: int = 1):
        """
        Add or increase levels in a class.
        
        Args:
            class_name: Name of the class (e.g., 'Warrior', 'Mage')
            levels: Number of levels to add (default 1)
        """
        if class_name in self.classes:
            self.classes[class_name] += levels
        else:
            self.classes[class_name] = levels
        if self.level < self.total_level:
            self.level = self.total_level
        if self.hit_dice_total <= 0:
            self.hit_dice_total = self.effective_level
        self.hit_dice_total = max(self.hit_dice_total, self.effective_level)
        self.hit_dice_remaining = max(self.hit_dice_remaining, min(self.hit_dice_total, self.hit_dice_remaining or self.hit_dice_total))

    def sync_derived_progression(self) -> None:
        """Backfill rest/combat progression fields after migration or creation."""
        self.level = max(1, int(self.level or 1), int(self.total_level or 0))
        if self.hit_dice_total <= 0:
            self.hit_dice_total = self.effective_level
        if self.hit_dice_remaining <= 0:
            self.hit_dice_remaining = self.hit_dice_total
        self.hit_dice_remaining = min(self.hit_dice_remaining, self.hit_dice_total)
        self.exhaustion_level = max(0, min(6, int(self.exhaustion_level or 0)))
        self.death_save_successes = max(0, min(3, int(self.death_save_successes or 0)))
        self.death_save_failures = max(0, min(3, int(self.death_save_failures or 0)))
        if not self.alignment:
            self.alignment = "TN"
        canonical_conditions: List[str] = []
        for condition in list(self.conditions or []):
            if condition and condition not in canonical_conditions:
                canonical_conditions.append(str(condition))
        for condition_state in list(self.condition_states or []):
            condition_name = str(condition_state.get("name", "")).strip()
            if condition_name and condition_name not in canonical_conditions:
                canonical_conditions.append(condition_name)
        self.conditions = canonical_conditions

    def set_alignment_from_axes(self) -> str:
        law_axis = int((self.alignment_axes or {}).get("law_chaos", 0))
        good_axis = int((self.alignment_axes or {}).get("good_evil", 0))
        law = "L" if law_axis >= 30 else "C" if law_axis <= -30 else "N"
        good = "G" if good_axis >= 30 else "E" if good_axis <= -30 else "N"
        self.alignment = f"{law}{good}"
        return self.alignment
    
    def equip_item(self, slot: str, item_id: str):
        """
        Equip an item to an equipment slot.
        
        Args:
            slot: Equipment slot (weapon, offhand, armor, accessory)
            item_id: Item identifier to equip
        
        Raises:
            ValueError: If slot name is invalid
        """
        valid_slots = ['weapon', 'offhand', 'armor', 'accessory']
        if slot not in valid_slots:
            raise ValueError(f"Invalid slot: {slot}. Valid slots: {valid_slots}")
        self.equipment[slot] = item_id
    
    def unequip_item(self, slot: str) -> Optional[str]:
        """
        Remove an item from an equipment slot.
        
        Args:
            slot: Equipment slot to clear
        
        Returns:
            Item ID that was removed, or None if slot was empty
        """
        return self.equipment.pop(slot, None)
    
    def to_dict(self) -> dict:
        """
        Serialize character to a dictionary.
        
        Returns:
            Dictionary containing all character data
        """
        self.sync_derived_progression()
        data = {
            'name': self.name,
            'race': self.race,
            'classes': self.classes,
            'stats': self.stats,
            'hp': self.hp,
            'max_hp': self.max_hp,
            'ac': self.ac,
            'initiative_bonus': self.initiative_bonus,
            'spell_points': self.spell_points,
            'max_spell_points': self.max_spell_points,
            'xp': self.xp,
            'level': self.level,
            'skills': self.skills,
            'skill_proficiencies': self.skill_proficiencies,
            'expertise_skills': self.expertise_skills,
            'proficiency_bonus': self.proficiency_bonus,
            'alignment': self.alignment,
            'alignment_axes': self.alignment_axes,
            'passives': self.passives,
            'gold': self.gold,
            'inventory': self.inventory,
            'equipment': self.equipment,
            'conditions': self.conditions,
            'condition_states': self.condition_states,
            'exhaustion_level': self.exhaustion_level,
            'hit_dice_total': self.hit_dice_total,
            'hit_dice_remaining': self.hit_dice_remaining,
            'hit_die_size': self.hit_die_size,
            'last_long_rest_hour': self.last_long_rest_hour,
            'death_save_successes': self.death_save_successes,
            'death_save_failures': self.death_save_failures,
            'is_stable': self.is_stable,
            'use_death_saves': self.use_death_saves,
            'creation_answers': self.creation_answers,
            'creation_profile': self.creation_profile,
        }
        base_ac = getattr(self, 'base_ac', None)
        stored_base_ac = getattr(self, '_base_ac', base_ac)
        if base_ac is not None:
            data['base_ac'] = base_ac
        if stored_base_ac is not None:
            data['_base_ac'] = stored_base_ac
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """
        Deserialize character from a dictionary.
        
        Args:
            data: Dictionary containing character data
        
        Returns:
            Character instance
        """
        payload = dict(data or {})
        payload.pop('proficiency_bonus', None)
        payload.pop('passives', None)
        payload.pop('hit_die_size', None)
        base_ac = payload.pop('base_ac', None)
        stored_base_ac = payload.pop('_base_ac', base_ac)
        character = cls(**payload)
        if base_ac is not None:
            character.base_ac = base_ac
        if stored_base_ac is not None:
            character._base_ac = stored_base_ac
        character.sync_derived_progression()
        return character
    
    def __repr__(self) -> str:
        """String representation of character."""
        class_str = ", ".join(f"{c} {lvl}" for c, lvl in self.classes.items()) if self.classes else "Level 0"
        return f"<Character {self.name} ({self.race}) - {class_str} - HP {self.hp}/{self.max_hp}>"
