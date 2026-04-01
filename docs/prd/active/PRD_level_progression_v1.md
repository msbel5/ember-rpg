# PRD: Level & Progression System V1
**Project:** Ember RPG
**Phase:** 1
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the XP → level up → stat/ability progression pipeline synthesizing GemRB M15 (Level Up — HP roll, THAC0 update, saving throw update, proficiency points, spell slots, feat selection, ability score increase, high level abilities) with DF M02 (skill XP with usage-based learning and rust). Actors gain XP from combat, quest completion, and skill usage. Level thresholds trigger multi-step level-up pipeline.

## 2. Scope

### In scope
- XP tracking and sources (combat kills, quest rewards, skill usage, discovery)
- Level thresholds: XP table per class
- Level-up pipeline (8 steps from GemRB M15)
- HP gain: class-based hit die + CON modifier, capped at level threshold
- BAB/THAC0 progression per class
- Saving throw progression per class
- Proficiency points allocation
- Spell slot progression (feeds Spell System)
- Ability score increase every 4 levels
- Skill point allocation (thief skills, general skills)
- Multi-class: XP split, HP averaging
- Class definitions: fighter, mage, thief, cleric, ranger, paladin, bard, sorcerer, druid, monk + custom
- DF-style skill learning: usage → XP → skill level with named tiers (Dabbling through Legendary)

### Out of scope
- High Level Abilities (HLA) — future expansion
- Prestige classes
- Feat trees (simplified to proficiency points)
- Character creation (separate concern)

## 3. Functional Requirements (FR)

**FR-01 (XP Tracking):** Each actor has `xp: int` and `xp_sources: dict[str, int]` tracking where XP came from. XP sources: "combat", "quest", "skill_use", "discovery", "bonus".

**FR-02 (Level Thresholds):** Class-specific XP tables. Fighter example: level 2=2000, 3=4000, 4=8000, 5=16000, 6=32000, 7=64000, 8=125000, 9=250000, 10=500000, ... Level cap: 20 (configurable). `can_level_up(actor)` returns True if XP >= next level threshold.

**FR-03 (HP Gain):** On level up: `hp_gain = roll_hit_die(class_hit_die) + CON_modifier`. Class hit dice: fighter/paladin/ranger=d10, cleric/druid/monk=d8, thief/bard=d6, mage/sorcerer=d4. CON modifier = (CON - 10) // 2. Minimum HP gain = 1. After level cap (varies by class, typically 9-10): fixed HP per level (3 for fighter, 2 for thief, 1 for mage).

**FR-04 (BAB Progression):** BAB increases per class. Fighter: +1/level. Thief/Cleric: +3/4 levels. Mage: +1/2 levels. Stored as `bab: int` on actor. Feeds Combat Resolution PRD.

**FR-05 (Saving Throw Progression):** Three saves: fortitude, reflex, will. Good save progression: +2 at level 1, +1 every 2 levels. Poor save: +0 at level 1, +1 every 3 levels. Class determines which saves are "good": Fighter(fort), Thief(ref), Mage(will), Cleric(fort+will).

**FR-06 (Proficiency Points):** Fighter: 1 proficiency point every 3 levels. Others: every 4 levels. Points spent on weapon proficiencies: 1 point = trained (+1 attack), 2 = proficient (+1/+1), 3 = specialized (+2/+2, fighter only).

**FR-07 (Spell Slot Progression):** On level up, recalculate max_spell_slots from class table. New slots become available. Feeds Spell System PRD.

**FR-08 (Ability Score Increase):** Every 4th level (4, 8, 12, 16, 20): actor gains +1 to one ability score of choice.

**FR-09 (Skill Points):** Thief: gains skill_points per level distributed among: open_locks, find_traps, pickpocket, move_silently, hide_in_shadows, detect_illusion, set_traps, backstab. Other classes: general skill points per level to distribute.

**FR-10 (Multi-Class):** Actor with 2+ classes: XP is split evenly. Level up when any class reaches threshold. HP = average of all class HP. BAB = best of all classes. Saves = best of each type.

**FR-11 (DF Skill Learning):** Separate from class XP. Each skill has its own XP counter. Using a skill adds XP: `skill_xp += usage_amount * learning_rate`. Thresholds for named levels: Dabbling(0), Novice(500), Adequate(1100), Competent(1800), Skilled(2600), Proficient(3500), Talented(4500), Adept(5600), Expert(6800), Professional(8100), Accomplished(9500), Great(11000), Master(12600), High Master(14300), Grand Master(16100), Legendary(16100+). Skill rust from Job Kernel PRD applies.

**FR-12 (Level-Up Pipeline):** Full pipeline must execute in order:
1. XP_CHECK → verify threshold met
2. HP_ROLL → roll hit die + CON mod
3. BAB_UPDATE → increment BAB per class table
4. SAVE_UPDATE → recalculate saves
5. PROFICIENCY_POINTS → award if applicable
6. SKILL_POINTS → award if applicable
7. SPELL_SLOTS → recalculate spell slots
8. ABILITY_INCREASE → if level % 4 == 0, award +1

## 4. Data Structures

```python
@dataclass
class ClassDef:
    class_id: str
    label: str
    hit_die: int             # d4, d6, d8, d10
    bab_rate: str            # "full" (+1/level) | "three_quarter" | "half"
    good_saves: list[str]    # ["fortitude"] or ["reflex", "will"] etc.
    proficiency_rate: int    # Levels per proficiency point
    skill_points_per_level: int = 0
    spell_type: str = ""     # "" | "wizard" | "priest" | "sorcerer"
    hp_after_cap: int = 0    # Fixed HP per level after hit die cap
    hit_die_cap_level: int = 20  # Level after which fixed HP applies
    xp_table: list[int] = field(default_factory=list)  # XP threshold per level

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassDef": ...


@dataclass
class LevelUpResult:
    new_level: int
    hp_gained: int
    bab_new: int
    saves_new: dict[str, int]
    proficiency_points: int
    skill_points: int
    new_spell_slots: dict[int, int]
    ability_increase: bool

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class ProgressionState:
    actor_id: str
    xp: int = 0
    xp_sources: dict[str, int] = field(default_factory=dict)
    level: int = 1
    classes: list[str] = field(default_factory=list)  # ["fighter", "thief"] for multi
    class_levels: dict[str, int] = field(default_factory=dict)  # {"fighter": 5, "thief": 3}
    bab: int = 0
    saves: dict[str, int] = field(default_factory=dict)  # {"fortitude": 4, "reflex": 2, "will": 1}
    proficiency_points_available: int = 0
    skill_points_available: int = 0
    ability_increases_available: int = 0

    # DF-style skill XP
    skill_xp: dict[str, int] = field(default_factory=dict)
    skill_levels: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressionState": ...


# XP thresholds for DF-style skill levels
SKILL_XP_THRESHOLDS = [0, 500, 1100, 1800, 2600, 3500, 4500, 5600, 6800, 8100, 9500, 11000, 12600, 14300, 16100]
SKILL_LEVEL_NAMES = ["Dabbling", "Novice", "Adequate", "Competent", "Skilled", "Proficient", "Talented", "Adept", "Expert", "Professional", "Accomplished", "Great", "Master", "High Master", "Grand Master"]
```

## 5. Public API

```python
def award_xp(progression: ProgressionState, amount: int, source: str) -> None:
    """Add XP from a source. Updates xp and xp_sources."""

def can_level_up(progression: ProgressionState, class_defs: dict[str, ClassDef]) -> bool:
    """Check if actor has enough XP for next level in any class."""

def execute_level_up(
    progression: ProgressionState,
    class_id: str,
    class_def: ClassDef,
    hit_die_roll: int,
    con_modifier: int,
) -> LevelUpResult:
    """Execute level up pipeline. Returns result with all gains."""

def compute_bab(class_levels: dict[str, int], class_defs: dict[str, ClassDef]) -> int:
    """Compute BAB from all class levels (best progression for multi-class)."""

def compute_saves(class_levels: dict[str, int], class_defs: dict[str, ClassDef]) -> dict[str, int]:
    """Compute saving throws from all class levels (best of each type)."""

def award_skill_xp(progression: ProgressionState, skill_id: str, amount: int) -> int:
    """Add skill XP from usage. Returns new skill level if changed, else -1."""

def get_skill_level(skill_xp: int) -> int:
    """Convert skill XP to level index (0-14)."""

def get_skill_level_name(level: int) -> str:
    """Return named tier for skill level."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-02]: Given fighter with xp=7999, when can_level_up checked (threshold 8000 for level 4), returns False. At xp=8000, returns True.

AC-02 [FR-03]: Given fighter (d10), CON=14 (+2), hit_die_roll=7, then hp_gained = 7 + 2 = 9.

AC-03 [FR-03]: Given mage (d4), CON=8 (-1), hit_die_roll=2, then hp_gained = max(1, 2 - 1) = 1.

AC-04 [FR-04]: Given fighter at level 5, BAB = 5. Given thief at level 8, BAB = 6 (3/4 rate).

AC-05 [FR-05]: Given fighter (good fort) at level 6, fort save = 2 + 3 = 5. Reflex (poor) = 0 + 2 = 2.

AC-06 [FR-08]: Given actor reaching level 4, ability_increase = True. At level 5, ability_increase = False.

AC-07 [FR-10]: Given fighter 5 / thief 3, BAB = max(5, 2) = 5. Fort = max(4, 1). Reflex = max(1, 3).

AC-08 [FR-11]: Given skill_xp=2500, skill level = 4 ("Skilled"). After +200 XP (total 2700), level = 5 ("Proficient").

AC-09 [FR-11]: Given skill_xp=16100+, skill level = 14 ("Grand Master").

AC-10 [FR-12]: Full level-up pipeline for a fighter going from level 3 to 4 returns all correct values.

AC-11 [FR-01]: award_xp with source="combat" adds to both xp and xp_sources["combat"].

AC-12 [FR-12]: ProgressionState round-trip via to_dict()/from_dict() preserves all fields.

## 7-10. (Performance, Errors, Integration, Tests)
- execute_level_up: < 0.1 ms
- Invalid class_id: raise KeyError
- Level up without sufficient XP: raise ValueError
- Integration: Actor (stats feed modifiers), Combat Resolution (BAB), Spell System (slot calculation), Job Kernel (skill XP from work)
- Tests: every class type, multi-class combinations, all hit die boundaries, BAB rates, save progressions, skill XP thresholds at boundaries, ability increase at levels 4/8/12/16/20
