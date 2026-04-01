# Ember RPG — Game Design Document v0.2
**Project:** FRP AI Game  
**Version:** 0.2 (Research-Driven Revision)  
**Date:** 2026-03-22  
**Author:** Alcyone  
**Target:** AAA-quality 2D fantasy RPG powered by AI

---

## 1. Executive Summary

**Ember RPG** is a 2D fantasy role-playing game where AI agents act as Dungeon Master, NPCs, and world generators. Players experience a **living, reactive world** that adapts to their choices through dynamic storytelling, intelligent NPCs with memory, and procedurally generated content.

**Core Philosophy:**
- **Simple to learn, deep to master** — Elegant rules, tactical depth
- **AI-driven narrative** — No pre-scripted paths, every playthrough unique
- **Universal mechanics** — One system for PC, NPC, and monster
- **Deterministic economy** — Every item has value, weight, and purpose

**Target Platforms:** Steam (PC), Web, Mobile (future)  
**Engine:** Godot 4.x (GDScript frontend) + Python FastAPI (backend)  
**Target Audience:** CRPG fans, D&D players, roguelike enthusiasts

---

## 2. Design Pillars

### 2.1 AI-Driven Narrative
- **DM Agent:** LLM-powered storyteller creates encounters, adjudicates rules, adapts to player choices
- **Dynamic campaigns:** No fixed storylines, AI generates quests and consequences in real-time
- **Player agency:** Choices matter, world evolves based on actions

### 2.2 Intelligent NPCs
- **Memory system:** NPCs remember past interactions, build relationships
- **Personality traits:** Each NPC has consistent behavior and goals
- **Natural dialogue:** Context-aware conversations, not keyword-based

### 2.3 Strategic Turn-Based Combat
- **Action point system:** Flexible turn structure (3 points: move/attack/ability)
- **Tactical positioning:** Flanking, cover, elevation, environmental hazards
- **Resource management:** HP, spell points, consumables matter

### 2.4 Living Persistent World
- **Procedural generation:** Maps, dungeons, quests created on demand
- **Consequences:** Quest outcomes affect world state
- **Economy:** Supply/demand, merchant inventories, loot scaling

---

## 3. Core Mechanics: Ember RPG System

### 3.1 Resolution Mechanic

**Primary Roll:**
```
d20 + Stat Modifier + Proficiency ≥ Target DC
```

**Critical Success:**
- Natural 20 **OR** beat DC by 10+
- Effects: Double damage, bypass armor, auto-succeed

**Critical Failure:**
- Natural 1 **OR** fail DC by 10+
- Effects: Weapon breaks, spell fizzles, provoke attack

**Degrees of Success** (Pathfinder 2e inspired):
- Critical Success: ≥ DC + 10
- Success: ≥ DC
- Failure: < DC
- Critical Failure: < DC - 10

### 3.2 Attributes (6 Core Stats)

| Stat | Name | Governs |
|------|------|---------|
| **MIG** | Might | Physical power, melee damage, carrying capacity |
| **AGI** | Agility | Speed, reflexes, ranged attacks, AC |
| **END** | Endurance | HP, stamina, physical resistance |
| **MND** | Mind | Magic power, spell points, arcane knowledge |
| **INS** | Insight | Perception, intuition, initiative, mental resistance |
| **PRE** | Presence | Charisma, leadership, persuasion, intimidation |

**Stat Range:** 3 (feeble) to 20 (godlike), human average 10  
**Modifier Calculation:** `(Stat - 10) / 2` (rounded down)

**Starting Values (Player Characters):**
- **Point-Buy:** 27 points
  - Cost: 8→0, 9→1, 10→2, 11→3, 12→4, 13→5, 14→7, 15→9
  - Example: MIG 15 (9), AGI 14 (7), END 13 (5), MND 12 (4), INS 10 (2), PRE 8 (0) = 27
- **Random Roll:** 4d6 drop lowest, 6 times, assign to taste

### 3.3 Skills (Proficiency System)

**12 Core Skills:**

| Physical | Combat | Mental | Social |
|----------|--------|--------|--------|
| Athletics | Melee | Arcana | Persuasion |
| Stealth | Ranged | Lore | Deception |
| Survival | Defense | Perception | Intimidation |

**Proficiency Tiers:**
- **Untrained:** +0
- **Trained:** +2
- **Expert:** +4 (Level 5+)
- **Master:** +6 (Level 10+)

**Skill Check:**
```
d20 + Stat Modifier + Proficiency ≥ DC
```

**Example:** Trained rogue (AGI 16) picking a lock (DC 15)
```
d20 + 3 (AGI mod) + 2 (trained) ≥ 15
Roll: 10 + 3 + 2 = 15 → Success
```

### 3.4 Classes (4 Archetypes)

#### 3.4.1 Warrior
**Role:** Tank, frontline fighter, weapon specialist  
**Key Stats:** MIG, END  
**HP Formula:** 12 + (END × 3) per level  
**Starting HP (END 14):** 12 + (14 × 3) = 54 HP

**Class Features:**
- **L1:** Armor Proficiency (all), Weapon Mastery (+1 damage)
- **L3:** Second Wind (heal 1d10 + END, 1/rest)
- **L5:** Extra Attack (attack twice with 2 AP)
- **L7:** Improved Critical (crit on 19-20)
- **L10:** Indomitable (reroll failed save, 1/rest)

#### 3.4.2 Rogue
**Role:** Scout, skill monkey, burst damage  
**Key Stats:** AGI, INS  
**HP Formula:** 10 + (END × 2) per level  
**Starting HP (END 12):** 10 + (12 × 2) = 34 HP

**Class Features:**
- **L1:** Sneak Attack (+2d6 damage if advantage)
- **L3:** Cunning Action (Dash/Hide/Disengage costs 1 AP)
- **L5:** Uncanny Dodge (halve damage from one attack, 1/turn)
- **L7:** Evasion (take no damage on successful save vs AoE)
- **L10:** Reliable Talent (skill checks < 10 count as 10)

#### 3.4.3 Mage
**Role:** Ranged DPS, AoE control, utility caster  
**Key Stats:** MND, INS  
**HP Formula:** 8 + (END × 1.5) per level  
**Starting HP (END 10):** 8 + (10 × 1.5) = 23 HP

**Class Features:**
- **L1:** Spellcasting (spell points = MND × 2 + Level × 3)
- **L1:** Spell Library (learn 3 spells at L1, +2 per level)
- **L3:** Arcane Recovery (regain 1d6 + MND spell points, 1/rest)
- **L5:** Metamagic (spend +5 SP to empower spell: +1d6 damage or +2 DC)
- **L10:** Spell Mastery (one L1-2 spell becomes at-will)

#### 3.4.4 Priest
**Role:** Healer, support, divine caster  
**Key Stats:** MND, PRE  
**HP Formula:** 10 + (END × 2) per level  
**Starting HP (END 12):** 10 + (12 × 2) = 34 HP

**Class Features:**
- **L1:** Spellcasting (spell points = MND × 2 + Level × 3)
- **L1:** Divine Spells (healing, buffs, resurrection)
- **L3:** Channel Divinity (1/rest special ability: Turn Undead or Divine Strike)
- **L5:** Blessed Healer (when healing ally, self heals 1d6)
- **L10:** Divine Intervention (pray for miracle, MND% chance, 1/week)

### 3.5 Multiclassing

**Mechanics:**
- Character has `classes: dict[str, int]` (e.g., `{"Warrior": 5, "Mage": 3}`)
- Total Level = sum of class levels (8 in example)
- XP applies to total level
- At level-up, player chooses which class to advance
- Gain features/HP/proficiency from chosen class

**Example Builds:**
- **Spellblade:** Warrior 7 / Mage 3 (heavy armor + utility spells)
- **Shadow Priest:** Rogue 5 / Priest 5 (stealth + healing)
- **Battle Mage:** Warrior 4 / Mage 6 (frontline caster)

**Restrictions:**
- Cannot advance class if stat requirement not met:
  - Warrior: MIG 13+
  - Rogue: AGI 13+
  - Mage/Priest: MND 13+

### 3.6 Health & Damage

**Hit Points:**
```
HP = Base + (END × Multiplier)
```
- Warrior: 12 + (END × 3)
- Rogue/Priest: 10 + (END × 2)
- Mage: 8 + (END × 1.5)

**Death & Dying:**
- **0 HP:** Unconscious, make Death Saves each turn
  - d20: 10+ = success, <10 = failure
  - 3 successes = stabilize at 1 HP
  - 3 failures = dead
  - Natural 20 = regain 1 HP
  - Natural 1 = 2 failures
- **-10 HP:** Instant death (no saves)

**Damage Types:**
- **Physical:** Slashing, Piercing, Bludgeoning
- **Elemental:** Fire, Cold, Lightning
- **Arcane:** Force (pure magic)
- **Necrotic:** Death energy (heals undead)
- **Radiant:** Holy light (damages undead 2×)

**Armor Class (AC):**
```
AC = 10 + AGI Modifier + Armor Bonus + Shield
```

**Armor Types:**
- **Unarmored:** +0 AC, full AGI bonus
- **Light (leather):** +2 AC, full AGI bonus
- **Medium (chainmail):** +4 AC, max AGI +2
- **Heavy (plate):** +6 AC, no AGI bonus
- **Shield:** +2 AC

**Example AC Calculations:**
- Unarmored mage (AGI 12): 10 + 1 + 0 = 11 AC
- Rogue in leather (AGI 16): 10 + 3 + 2 = 15 AC
- Warrior in plate + shield (AGI 10): 10 + 0 + 6 + 2 = 18 AC

### 3.7 Combat System (Action Point Economy)

**Turn Structure:**
1. **Initiative:** d20 + INS modifier (highest goes first)
2. **Action Points:** Each combatant has 3 AP per turn
3. **Spend AP:** Move, attack, cast spell, use item, etc.
4. **End Turn:** Unused AP lost

**Action Costs:**

| Action | Cost | Notes |
|--------|------|-------|
| **Move** | 1 AP | Up to speed (default 6 tiles) |
| **Attack** | 2 AP | Melee or ranged |
| **Cast Spell** | 2 AP | Most spells |
| **Quick Spell** | 1 AP | Cantrips, specific spells |
| **Use Item** | 1 AP | Drink potion, use scroll |
| **Dash** | 2 AP | Move twice (total 12 tiles) |
| **Dodge** | 2 AP | Disadvantage on attacks vs you until next turn |
| **Disengage** | 1 AP | Move without provoking attacks |
| **Help** | 1 AP | Give ally advantage on next check |
| **Hide** | 1 AP | Stealth check |
| **Search** | 1 AP | Perception check |

**Example Turns:**
- **Warrior:** Move (1 AP) + Attack (2 AP) = 3 AP
- **Rogue:** Hide (1 AP) + Attack with advantage (2 AP) = 3 AP
- **Mage:** Cast Fireball (2 AP) + Move (1 AP) = 3 AP
- **Fleeing enemy:** Disengage (1 AP) + Move (1 AP) + Move (1 AP) = 3 AP (18 tiles away)

**Attack Roll:**
```
d20 + (MIG or AGI) + Proficiency ≥ Target AC
```
- **Melee Attack:** d20 + MIG modifier + Melee proficiency
- **Ranged Attack:** d20 + AGI modifier + Ranged proficiency

**Damage Roll:**
```
Weapon Dice + Stat Modifier + Bonuses
```

**Example Attack:**
Warrior (MIG 16, Melee +2) attacks goblin (AC 13) with longsword (1d10)
```
Attack: d20 + 3 (MIG) + 2 (prof) = d20 + 5
Roll: 11 + 5 = 16 ≥ 13 → HIT
Damage: 1d10 + 3 (MIG) = 7 damage
```

**Critical Hit:**
- **Natural 20** or **beat AC by 10+**
- **Effect:** Double weapon dice (not modifiers)
- **Example:** Longsword crit = 2d10 + 3 (not 1d10 × 2 + 3 × 2)

**Advantage / Disadvantage:**
- **Advantage:** Roll 2d20, take higher (flanking, hidden, prone target)
- **Disadvantage:** Roll 2d20, take lower (blind, prone attacker, heavily obscured)

**Cover:**
- **Half Cover (+2 AC):** Low wall, tree, ally
- **Three-Quarters Cover (+5 AC):** Arrow slit, large boulder
- **Total Cover:** Cannot be targeted

### 3.8 Magic System (Spell Points)

**Spell Point Pool:**
```
Spell Points (SP) = (MND × 2) + (Level × 3)
```

**Example SP Pools:**
- **Level 1 Mage (MND 14):** 28 + 3 = 31 SP
- **Level 5 Mage (MND 16):** 32 + 15 = 47 SP
- **Level 10 Priest (MND 18):** 36 + 30 = 66 SP

**Spell Costs:**

| Spell Level | Cost | Power | Examples |
|-------------|------|-------|----------|
| **Cantrip** | 0 SP | At-will | Fire Bolt, Mage Hand |
| **Level 1** | 5 SP | 1d6 + MND | Magic Missile, Cure Wounds |
| **Level 2** | 10 SP | 2d6 + MND | Scorching Ray, Lesser Restoration |
| **Level 3** | 15 SP | 3d6 + MND | Fireball, Dispel Magic |
| **Level 4** | 20 SP | 4d6 + MND | Ice Storm, Greater Invisibility |
| **Level 5** | 25 SP | 5d6 + MND | Cone of Cold, Raise Dead |

**Spell Schools:**
- **Evocation:** Damage spells (Fireball, Lightning Bolt)
- **Abjuration:** Defense (Shield, Counterspell, Dispel Magic)
- **Conjuration:** Summon creatures/objects (Summon Elemental)
- **Restoration:** Healing (Cure Wounds, Lesser Restoration)
- **Transmutation:** Buffs/debuffs (Haste, Slow, Polymorph)
- **Illusion:** Deception (Invisibility, Mirror Image, Phantasmal Force)
- **Enchantment:** Mind control (Charm Person, Sleep, Dominate)
- **Necromancy:** Life/death (Animate Dead, Blight, Vampiric Touch)

**Spell Save DC:**
```
Spell DC = 10 + MND Modifier + Proficiency
```

**Example:** Level 5 mage (MND 16, prof +2) casts Fireball
```
Spell DC = 10 + 3 + 2 = 15
Targets roll d20 + AGI modifier
≥ 15 = half damage, < 15 = full damage
Damage: 3d6 + 3 = 13 average (6 on save)
```

**Metamagic (Mage L5 feature):**
- **Empower Spell:** +5 SP, +1d6 damage
- **Quicken Spell:** +5 SP, spell costs 1 AP instead of 2
- **Twin Spell:** +10 SP, target 2 creatures

**Spell Recovery:**
- **Short Rest (1 hour):** Arcane Recovery (Mage L3) regains 1d6 + MND SP
- **Long Rest (8 hours):** Regain all SP

### 3.9 Leveling & Progression

**XP Requirements:**
```
XP to Next Level = Current Level × 100
```

| Level | XP Needed | Cumulative XP |
|-------|-----------|---------------|
| 1→2 | 100 | 100 |
| 2→3 | 200 | 300 |
| 3→4 | 300 | 600 |
| 5→6 | 500 | 1500 |
| 10→11 | 1000 | 5500 |
| 19→20 | 1900 | 19000 |

**Per Level Gains:**
- **+1 Stat Point:** Assign to any stat (max 20)
- **+HP:** Roll class die (d10/d8/d6) + END modifier (min 1)
- **Skill Upgrade:** Learn new skill (trained) OR improve existing (trained → expert → master)
- **Class Feature:** Gained at milestone levels (see class tables)

**Multiclass Level-Up:**
- Choose which class to advance (if stat requirement met)
- Gain HP/features from chosen class
- Example: Warrior 5 / Mage 3 → can advance to Warrior 6 or Mage 4

---

## 4. Character Architecture (Code Design)

### 4.1 Universal Character Class

**All entities (PC, NPC, monster) inherit from:**

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Character:
    # Identity
    name: str
    race: str = "Human"
    classes: Dict[str, int] = field(default_factory=dict)  # class_name -> level
    
    # Core Stats
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
    
    # Skills (skill_name -> proficiency level: 0/2/4/6)
    skills: Dict[str, int] = field(default_factory=dict)
    
    # Abilities
    features: List['Feature'] = field(default_factory=list)
    known_spells: List['Spell'] = field(default_factory=list)
    
    # Inventory
    inventory: List['Item'] = field(default_factory=list)
    equipment: Dict[str, 'Item'] = field(default_factory=dict)  # slot -> item
    gold: int = 0
    
    # State
    conditions: List[str] = field(default_factory=list)  # poisoned, paralyzed, etc.
    
    @property
    def total_level(self) -> int:
        return sum(self.classes.values())
    
    def stat_modifier(self, stat: str) -> int:
        return (self.stats[stat] - 10) // 2
    
    def skill_bonus(self, skill: str) -> int:
        """Returns total bonus for skill check."""
        # Get governing stat for skill
        stat_map = {
            'athletics': 'MIG', 'stealth': 'AGI', 'survival': 'INS',
            'melee': 'MIG', 'ranged': 'AGI', 'defense': 'END',
            'arcana': 'MND', 'lore': 'MND', 'perception': 'INS',
            'persuasion': 'PRE', 'deception': 'PRE', 'intimidation': 'PRE'
        }
        stat = stat_map.get(skill.lower(), 'MIG')
        prof = self.skills.get(skill.lower(), 0)
        return self.stat_modifier(stat) + prof
```

**Example Instantiations:**

```python
# Player Character
pc = Character(
    name="Aldric",
    race="Human",
    classes={'Warrior': 5},
    stats={'MIG': 16, 'AGI': 12, 'END': 14, 'MND': 8, 'INS': 10, 'PRE': 13},
    hp=54,
    max_hp=54,
    ac=18,
    skills={'melee': 2, 'athletics': 2, 'intimidation': 2},
    features=[ExtraAttack(), SecondWind()],
    equipment={'weapon': longsword, 'armor': plate_armor, 'shield': steel_shield}
)

# Simple NPC
merchant = Character(
    name="Greta the Merchant",
    race="Dwarf",
    classes={'Commoner': 0},
    stats={'MIG': 10, 'AGI': 9, 'END': 12, 'MND': 11, 'INS': 13, 'PRE': 14},
    hp=12,
    max_hp=12,
    skills={'persuasion': 2, 'lore': 2}
)

# Monster
goblin = Character(
    name="Goblin Raider",
    race="Goblin",
    classes={'Monster': 1},
    stats={'MIG': 8, 'AGI': 14, 'END': 10, 'MND': 8, 'INS': 11, 'PRE': 8},
    hp=7,
    max_hp=7,
    ac=13,
    skills={'stealth': 4},
    equipment={'weapon': short_sword, 'armor': leather_armor}
)

# Boss Monster
ancient_dragon = Character(
    name="Vorkath the Ancient",
    race="Red Dragon",
    classes={'Monster': 15},
    stats={'MIG': 24, 'AGI': 12, 'END': 26, 'MND': 20, 'INS': 18, 'PRE': 22},
    hp=300,
    max_hp=300,
    ac=20,
    spell_points=70,
    max_spell_points=70,
    skills={'perception': 6, 'arcana': 4, 'intimidation': 6},
    features=[Flight(), BreathWeapon('fire', '10d6'), FrightfulPresence(), LegendaryActions(3)],
    known_spells=[fireball, wall_of_fire, meteor_swarm]
)
```

### 4.2 Item System

**Universal Item Class:**

```python
from enum import Enum
from typing import List, Optional

class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    JUNK = "junk"
    CURRENCY = "currency"

@dataclass
class Item:
    name: str
    value: int  # gold pieces
    weight: float  # pounds
    item_type: ItemType
    description: str = ""
    
    # Weapon properties
    damage_dice: Optional[str] = None  # "1d10", "2d6", etc.
    damage_type: Optional[str] = None  # "slashing", "fire", etc.
    
    # Armor properties
    armor_bonus: int = 0
    armor_type: Optional[str] = None  # "light", "medium", "heavy"
    
    # Effects
    effects: List['Effect'] = field(default_factory=list)
    
    # Misc
    stackable: bool = False
    quantity: int = 1
```

**Example Items:**

```python
# Weapons
longsword = Item(
    name="Longsword",
    value=15,
    weight=3.0,
    item_type=ItemType.WEAPON,
    damage_dice="1d10",
    damage_type="slashing"
)

flaming_longsword = Item(
    name="Flaming Longsword +1",
    value=500,
    weight=3.0,
    item_type=ItemType.WEAPON,
    damage_dice="1d10",
    damage_type="slashing",
    effects=[ExtraDamage("1d6", "fire"), ToHitBonus(1)]
)

# Armor
plate_armor = Item(
    name="Plate Armor",
    value=1500,
    weight=45.0,
    item_type=ItemType.ARMOR,
    armor_bonus=6,
    armor_type="heavy"
)

# Consumables
healing_potion = Item(
    name="Potion of Healing",
    value=50,
    weight=0.5,
    item_type=ItemType.CONSUMABLE,
    effects=[Heal("2d6+2")],
    stackable=True
)

# Currency
gold = Item(
    name="Gold Coins",
    value=1,
    weight=0.02,
    item_type=ItemType.CURRENCY,
    stackable=True
)

# Quest item
ancient_key = Item(
    name="Ancient Runed Key",
    value=0,  # Cannot be sold
    weight=0.1,
    item_type=ItemType.QUEST,
    description="A key covered in glowing runes. It hums with ancient magic."
)
```

### 4.3 Effect System

**Base Effect Class:**

```python
from abc import ABC, abstractmethod

class Effect(ABC):
    @abstractmethod
    def apply(self, target: Character, source: Optional[Character] = None):
        """Apply effect to target."""
        pass

class Heal(Effect):
    def __init__(self, amount: str):  # "2d6+2"
        self.amount = amount
    
    def apply(self, target: Character, source=None):
        roll = roll_dice(self.amount)
        target.hp = min(target.hp + roll, target.max_hp)
        return f"{target.name} heals {roll} HP"

class Damage(Effect):
    def __init__(self, amount: str, damage_type: str):
        self.amount = amount
        self.damage_type = damage_type
    
    def apply(self, target: Character, source=None):
        roll = roll_dice(self.amount)
        # Apply resistances/immunities
        if self.damage_type in target.resistances:
            roll //= 2
        target.hp -= roll
        return f"{target.name} takes {roll} {self.damage_type} damage"

class Buff(Effect):
    def __init__(self, stat: str, bonus: int, duration: int):
        self.stat = stat
        self.bonus = bonus
        self.duration = duration  # turns
    
    def apply(self, target: Character, source=None):
        target.stats[self.stat] += self.bonus
        # Schedule removal after duration
        return f"{target.name} gains +{self.bonus} {self.stat} for {self.duration} turns"
```

---

## 5. AI Systems Architecture

### 5.1 DM Agent

**Role:** Narrative director, encounter designer, rule arbiter

**Model Options:**
- **Local:** Qwen3:7b or Qwen3:14b (on GPU)
- **API:** Claude Sonnet (for critical decisions)
- **Hybrid:** Qwen3 for routine, Claude for complex

**Memory Structure:**
```json
{
  "campaign": {
    "title": "The Shadow of Morvain",
    "session_count": 5,
    "summary": "Party investigating disappearances near Black Forest..."
  },
  "world_state": {
    "locations": {
      "Oakshire": {"status": "peaceful", "relationship": 75},
      "Black Forest": {"status": "dangerous", "bandit_presence": true}
    },
    "factions": {
      "Kingdom of Aldor": {"relationship": 50, "quest_giver": true},
      "Bandit Clan": {"relationship": -20, "hostile": true}
    }
  },
  "active_quests": [
    {
      "id": "main_001",
      "title": "Find the Missing Caravan",
      "objective": "Locate merchants in Black Forest",
      "progress": "leads found, bandit camp discovered"
    }
  ],
  "party_inventory": [
    "ancient_map", "bloodstained_letter"
  ],
  "recent_events": [
    "Party defeated goblin ambush",
    "Found clue pointing to bandit hideout",
    "Merchant Greta offered discount for helping"
  ]
}
```

**Prompt Template:**
```
System: You are the Dungeon Master for Ember RPG.
Your role: create dynamic stories, design balanced encounters, adjudicate rules.

World state: {world_state_json}
Active quests: {quests_json}
Recent events: {events_list}

Current scene: {scene_description}
Player action: {player_input}

Generate:
1. Scene outcome (what happens)
2. NPC reactions (if present)
3. Encounter (if triggered): enemies, environment, difficulty
4. Consequences (quest progress, world changes)
5. Next prompt (what player sees/hears)

Format: JSON
{
  "outcome": "...",
  "npc_dialogue": {...},
  "encounter": {...},
  "quest_updates": [...],
  "next_scene": "..."
}
```

**Capabilities:**
- Generate story beats from player actions
- Design combat encounters (balanced by party level)
- Create puzzles, traps, environmental challenges
- Adjudicate edge-case rules
- Track consequences (reputation, world events)

### 5.2 NPC Agent

**Role:** Consistent characters with memory and personality

**Model:** Qwen3:1.7b (fast, cheap) or GPT-4o-mini

**NPC Schema:**
```json
{
  "npc_id": "elara_blacksmith",
  "name": "Elara Ironhammer",
  "race": "Dwarf",
  "role": "Blacksmith",
  "personality": {
    "traits": ["gruff", "loyal", "secretive"],
    "alignment": "lawful_good",
    "voice": "gruff, short sentences, sarcastic"
  },
  "stats": {
    "level": 3,
    "skills": {"crafting": 6, "intimidation": 2}
  },
  "memory": [
    {
      "session": 3,
      "event": "Player saved shop from bandits",
      "emotion": "grateful"
    },
    {
      "session": 5,
      "event": "Player asked about magic weapons",
      "response": "Hinted at secret forge in mountains"
    }
  ],
  "relationship": 75,
  "quest_availability": [
    {
      "id": "side_003",
      "title": "Blacksmith's Secret",
      "unlock_relationship": 70
    }
  ],
  "inventory": [
    {"item": "longsword", "price": 15, "stock": 5},
    {"item": "plate_armor", "price": 1500, "stock": 1}
  ]
}
```

**Dialogue Prompt:**
```
Character: Elara Ironhammer (gruff dwarven blacksmith)
Personality: Loyal, secretive, sarcastic
Relationship with party: 75 (friendly, owes favor)
Memory: Player saved her shop (session 3)

Player says: "Can you forge me a magic sword?"

Context: Player has 500 gold, needs weapon for dragon fight

Generate: NPC response (in character, 2-3 sentences)
```

**Expected Output:**
```
"Magic sword? Pfft, not for 500 gold. But... seeing as you lot saved my forge, I might know a smith up in the mountains. Bring me dragon scales and I'll make introductions."
```

### 5.3 Map Generator

**Role:** Procedural 2D tile-based maps

**Map Types:**
1. **Dungeons:** Rooms + corridors (BSP algorithm)
2. **Towns:** Buildings + streets (Voronoi + templates)
3. **Wilderness:** Forests, mountains, rivers (Perlin noise)

**Algorithm: Binary Space Partitioning (Dungeons)**
```python
def generate_dungeon(width: int, height: int, min_room_size: int = 5):
    1. Start with full rect (width × height)
    2. Recursively split into smaller rects (BSP tree)
    3. Stop when rect < min_room_size × 2
    4. For each leaf: place room (random size within rect)
    5. Connect rooms with corridors (L-shaped)
    6. Place doors at corridor-room junctions
    7. Place entities (monsters, chests, traps)
    8. Return tile grid + entity list
```

**Output Format:**
```json
{
  "size": [40, 40],
  "tiles": [
    {"x": 0, "y": 0, "type": "wall", "variant": 1},
    {"x": 1, "y": 0, "type": "floor"},
    {"x": 2, "y": 0, "type": "door", "locked": true}
  ],
  "rooms": [
    {"id": 1, "bounds": [5, 5, 10, 10], "type": "combat"},
    {"id": 2, "bounds": [15, 5, 20, 10], "type": "treasure"},
    {"id": 3, "bounds": [10, 15, 15, 20], "type": "boss"}
  ],
  "entities": [
    {"x": 7, "y": 7, "type": "monster", "id": "goblin_1"},
    {"x": 17, "y": 7, "type": "chest", "loot": ["gold:50", "potion:healing"]},
    {"x": 12, "y": 17, "type": "boss", "id": "ogre_chief"}
  ],
  "entrance": {"x": 1, "y": 1},
  "exit": {"x": 38, "y": 38}
}
```

### 5.4 Campaign Generator

**Role:** Quest chains, story arcs, world events

**Campaign Structure:**
```json
{
  "campaign_id": "shadow_of_morvain",
  "title": "The Shadow of Morvain",
  "difficulty": "medium",
  "estimated_sessions": 8,
  
  "main_quest_chain": [
    {
      "id": "mq_001",
      "title": "Vanishing Merchants",
      "objective": "Investigate missing caravans",
      "location": "Oakshire",
      "level_requirement": 1,
      "rewards": {"xp": 200, "gold": 100}
    },
    {
      "id": "mq_002",
      "title": "Into the Black Forest",
      "objective": "Track bandits to hideout",
      "location": "Black Forest",
      "level_requirement": 2,
      "unlocked_by": "mq_001"
    },
    {
      "id": "mq_003",
      "title": "The Bandit King",
      "objective": "Defeat bandit leader",
      "location": "Bandit Stronghold",
      "level_requirement": 4,
      "boss": "bandit_king"
    }
  ],
  
  "side_quests": [
    {
      "id": "sq_001",
      "title": "Blacksmith's Secret",
      "giver": "elara_blacksmith",
      "objective": "Escort Elara to mountain forge",
      "rewards": {"xp": 100, "item": "flaming_sword_+1"}
    }
  ],
  
  "world_events": [
    {
      "trigger": "mq_002_complete",
      "event": "bandit_retaliation",
      "description": "Bandits attack Oakshire in revenge",
      "consequences": ["oakshire_damaged", "guards_request_help"]
    }
  ],
  
  "factions": [
    {
      "name": "Kingdom of Aldor",
      "alignment": "lawful_good",
      "relationship_start": 50,
      "quests": ["mq_001", "mq_002"]
    },
    {
      "name": "Shadow Cult",
      "alignment": "chaotic_evil",
      "relationship_start": -50,
      "reveal_session": 5
    }
  ]
}
```

---

## 6. Backend Architecture

### 6.1 Project Structure

```
frp-backend/
├── engine/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── character.py         # Character class
│   │   ├── item.py              # Item class
│   │   ├── effect.py            # Effect system
│   │   ├── rules.py             # Dice rolling, stat checks
│   │   └── world.py             # World state manager
│   │
│   ├── combat/
│   │   ├── __init__.py
│   │   ├── combat_manager.py    # Turn-based combat controller
│   │   ├── actions.py           # Attack, Cast, Move, etc.
│   │   ├── ai_tactics.py        # Enemy AI decision-making
│   │   └── initiative.py        # Turn order
│   │
│   ├── magic/
│   │   ├── __init__.py
│   │   ├── spell.py             # Spell class
│   │   ├── spellbook.py         # Spell database
│   │   └── spell_effects.py     # Spell-specific effects
│   │
│   └── progression/
│       ├── __init__.py
│       ├── leveling.py          # XP, level-up
│       ├── multiclass.py        # Multiclass rules
│       └── class_features.py    # Feature implementations
│
├── ai/
│   ├── __init__.py
│   ├── dm_agent.py              # LLM-powered DM
│   ├── npc_agent.py             # NPC dialogue + memory
│   ├── map_generator.py         # Procedural maps
│   ├── campaign_generator.py    # Quest chains
│   └── llm_client.py            # Unified LLM interface (Qwen3/Claude)
│
├── data/
│   ├── classes.json             # Class definitions
│   ├── spells.json              # Spell library (100+ spells)
│   ├── items.json               # Item database
│   ├── monsters.json            # Bestiary (50+ creatures)
│   ├── races.json               # Playable races
│   └── campaigns/
│       ├── shadow_of_morvain.json
│       └── ... (campaign templates)
│
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app
│   ├── dependencies.py          # Auth, session management
│   ├── routes/
│   │   ├── game.py              # Game session CRUD
│   │   ├── character.py         # Character creation/update
│   │   ├── combat.py            # Combat actions
│   │   ├── dm.py                # DM agent interactions
│   │   └── map.py               # Map generation
│   └── models.py                # Pydantic schemas
│
├── tests/
│   ├── test_character.py
│   ├── test_combat.py
│   ├── test_spells.py
│   ├── test_dm_agent.py
│   ├── test_multiclass.py
│   └── test_integration.py
│
├── requirements.txt
├── README.md
└── pyproject.toml
```

### 6.2 API Endpoints

**Game Session:**
- `POST /game/session` — Create new game
- `GET /game/session/{id}` — Get session state
- `POST /game/session/{id}/action` — Submit player action
- `DELETE /game/session/{id}` — End session

**Character:**
- `POST /character` — Create character
- `GET /character/{id}` — Get character sheet
- `PUT /character/{id}` — Update character
- `POST /character/{id}/level-up` — Apply level-up choices

**Combat:**
- `POST /combat/start` — Initialize combat
- `POST /combat/{id}/action` — Submit action (attack/cast/move)
- `GET /combat/{id}/state` — Get current combat state
- `POST /combat/{id}/end-turn` — End turn

**DM:**
- `POST /dm/generate-scene` — Generate story scene
- `POST /dm/encounter` — Create combat encounter
- `POST /dm/adjudicate` — Rule clarification

**Map:**
- `POST /map/generate` — Generate map (dungeon/town/wilderness)
- `GET /map/{id}` — Retrieve map data

---

## 7. Frontend (Godot 4.x)

### 7.1 Project Structure

```
frp-game-client/
├── scenes/
│   ├── main_menu/
│   │   └── MainMenu.tscn
│   ├── character_creation/
│   │   ├── CharacterCreator.tscn
│   │   └── StatAllocator.tscn
│   ├── world/
│   │   ├── WorldMap.tscn        # Overworld exploration
│   │   ├── Dungeon.tscn         # Dungeon exploration
│   │   └── Town.tscn            # Town hub
│   ├── combat/
│   │   ├── CombatScene.tscn     # Turn-based battle UI
│   │   ├── ActionBar.tscn       # Action point UI
│   │   └── TargetSelector.tscn  # Target picker
│   ├── ui/
│   │   ├── CharacterSheet.tscn  # Stats, inventory, spells
│   │   ├── Inventory.tscn       # Item management
│   │   ├── SpellBook.tscn       # Spell selection
│   │   ├── DialogueBox.tscn     # NPC conversations
│   │   └── QuestLog.tscn        # Active quests
│   └── game_manager/
│       └── GameManager.tscn     # Persistent game state
│
├── scripts/
│   ├── networking/
│   │   ├── api_client.gd        # HTTP client
│   │   └── session_manager.gd   # Session sync
│   ├── game_logic/
│   │   ├── character_data.gd    # Client-side character
│   │   ├── combat_controller.gd # Combat UI logic
│   │   ├── map_renderer.gd      # Tile rendering
│   │   └── dice_roller.gd       # Visual dice rolls
│   └── ui/
│       ├── action_bar.gd        # Action point display
│       ├── character_sheet.gd   # Sheet UI controller
│       └── dialogue_manager.gd  # Dialogue flow
│
├── assets/
│   ├── sprites/
│   │   ├── characters/          # PC/NPC sprites
│   │   ├── monsters/            # Enemy sprites
│   │   ├── items/               # Item icons
│   │   └── effects/             # Spell/attack VFX
│   ├── tiles/
│   │   ├── dungeon/             # Wall, floor, door tiles
│   │   ├── town/                # Building, street tiles
│   │   └── wilderness/          # Forest, mountain tiles
│   ├── audio/
│   │   ├── music/               # Background music
│   │   ├── sfx/                 # Sound effects
│   │   └── voice/               # NPC voice lines (future)
│   └── fonts/
│       └── main_font.ttf
│
└── project.godot
```

### 7.2 Communication Flow (Godot ↔ Backend)

**Example: Player Attacks in Combat**

1. **Godot:** Player clicks "Attack Goblin"
   ```gdscript
   var action = {
       "action_type": "attack",
       "target_id": "goblin_1"
   }
   var response = await api_client.post("/combat/%s/action" % combat_id, action)
   ```

2. **Backend:** Validates action, rolls dice, updates state
   ```python
   @router.post("/combat/{combat_id}/action")
   async def combat_action(combat_id: str, action: CombatAction):
       combat = get_combat(combat_id)
       
       # Validate action (has AP? In range?)
       if not combat.validate_action(action):
           raise HTTPException(400, "Invalid action")
       
       # Resolve attack
       result = combat.resolve_attack(
           attacker_id=action.actor_id,
           target_id=action.target_id
       )
       
       # AI decides enemy response
       if result['target_alive']:
           enemy_action = combat.ai_turn(action.target_id)
           result['enemy_action'] = enemy_action
       
       return result
   ```

3. **Response to Godot:**
   ```json
   {
     "success": true,
     "attack_roll": 18,
     "hit": true,
     "damage": 8,
     "critical": false,
     "target_hp": 2,
     "target_alive": true,
     "enemy_action": {
       "action_type": "attack",
       "target_id": "player_1",
       "attack_roll": 12,
       "hit": false
     },
     "combat_log": [
       "Aldric attacks Goblin: 18 vs AC 13 - HIT!",
       "Goblin takes 8 damage (2 HP remaining)",
       "Goblin attacks Aldric: 12 vs AC 18 - MISS!"
     ]
   }
   ```

4. **Godot:** Animates results
   ```gdscript
   # Animate attack
   player_sprite.play("attack")
   await get_tree().create_timer(0.5).timeout
   
   # Show damage number
   show_damage_number(goblin_sprite, response.damage)
   
   # Update HP bar
   goblin_hp_bar.value = response.target_hp
   
   # Show combat log
   for log_entry in response.combat_log:
       combat_log_text.append_text(log_entry + "\n")
   
   # Animate enemy counter-attack
   if 'enemy_action' in response:
       goblin_sprite.play("attack")
       # ... handle enemy action
   ```

---

## 8. Data Files (JSON Schemas)

### 8.1 Spell Database

**`data/spells.json` (excerpt):**
```json
[
  {
    "id": "fireball",
    "name": "Fireball",
    "level": 3,
    "school": "evocation",
    "cost": 15,
    "cast_time": "2 AP",
    "range": 20,
    "area": "4-tile radius",
    "save": "AGI",
    "effect": {
      "type": "damage",
      "dice": "3d6",
      "damage_type": "fire",
      "add_stat": "MND"
    },
    "description": "A fiery explosion erupts at target point."
  },
  {
    "id": "cure_wounds",
    "name": "Cure Wounds",
    "level": 1,
    "school": "restoration",
    "cost": 5,
    "cast_time": "2 AP",
    "range": "touch",
    "effect": {
      "type": "heal",
      "dice": "1d6",
      "add_stat": "MND"
    },
    "description": "Restore HP to one touched creature."
  }
]
```

### 8.2 Item Database

**`data/items.json` (excerpt):**
```json
[
  {
    "id": "longsword",
    "name": "Longsword",
    "type": "weapon",
    "value": 15,
    "weight": 3.0,
    "damage_dice": "1d10",
    "damage_type": "slashing",
    "properties": ["versatile"]
  },
  {
    "id": "healing_potion",
    "name": "Potion of Healing",
    "type": "consumable",
    "value": 50,
    "weight": 0.5,
    "effect": {
      "type": "heal",
      "dice": "2d6+2"
    },
    "stackable": true
  },
  {
    "id": "plate_armor",
    "name": "Plate Armor",
    "type": "armor",
    "value": 1500,
    "weight": 45.0,
    "armor_bonus": 6,
    "armor_type": "heavy",
    "required_stat": {"MIG": 15}
  }
]
```

### 8.3 Monster Bestiary

**`data/monsters.json` (excerpt):**
```json
[
  {
    "id": "goblin",
    "name": "Goblin",
    "race": "Goblin",
    "level": 1,
    "stats": {
      "MIG": 8, "AGI": 14, "END": 10,
      "MND": 8, "INS": 11, "PRE": 8
    },
    "hp": 7,
    "ac": 13,
    "skills": {"stealth": 4},
    "loot_table": [
      {"item": "gold", "quantity": "1d6"},
      {"item": "short_sword", "chance": 0.3}
    ],
    "behavior": "aggressive",
    "xp_reward": 25
  },
  {
    "id": "ancient_dragon",
    "name": "Ancient Red Dragon",
    "race": "Dragon",
    "level": 15,
    "stats": {
      "MIG": 24, "AGI": 12, "END": 26,
      "MND": 20, "INS": 18, "PRE": 22
    },
    "hp": 300,
    "ac": 20,
    "spell_points": 70,
    "known_spells": ["fireball", "wall_of_fire", "meteor_swarm"],
    "features": [
      "flight",
      "breath_weapon_fire_10d6",
      "frightful_presence",
      "legendary_actions_3"
    ],
    "loot_table": [
      {"item": "gold", "quantity": "1000d10"},
      {"item": "dragon_scale_armor", "chance": 1.0},
      {"item": "legendary_weapon", "chance": 0.8}
    ],
    "xp_reward": 15000
  }
]
```

---

## 9. Development Roadmap

### Phase 1: Design & Research ✅
- [x] GDD v0.1 (initial draft)
- [x] Deep research (D&D, Pathfinder, GURPS, Fate, OSR)
- [x] GDD v0.2 (this document)
- [ ] Spell database (100 spells, all schools/levels)
- [ ] Item database (weapons, armor, consumables, quest items)
- [ ] Monster bestiary (50+ creatures, CR 1-20)
- [ ] Class feature specifications (L1-L20 progression)

### Phase 2: Core Engine (Backend)
**Milestone:** Working combat system, character creation, spell casting

#### Module 1: Foundation
- [ ] **PRD:** Character system
  - Stat calculation, modifiers, proficiency
  - Skill checks, saving throws
  - HP/AC/initiative
- [ ] **Tests:** Character creation, stat checks, level-up
- [ ] **Code:** `character.py`, `rules.py`

#### Module 2: Items & Inventory
- [ ] **PRD:** Item system
  - Item class, effects
  - Equipment slots
  - Inventory management
- [ ] **Tests:** Item creation, equipping, stacking, effects
- [ ] **Code:** `item.py`, `effect.py`

#### Module 3: Combat Engine
- [ ] **PRD:** Turn-based combat
  - Action point system
  - Attack resolution
  - Damage calculation
  - Advantage/disadvantage
- [ ] **Tests:** Combat scenarios (2v2, 1v3, flanking, cover)
- [ ] **Code:** `combat_manager.py`, `actions.py`, `initiative.py`

#### Module 4: Magic System
- [ ] **PRD:** Spell casting
  - Spell point pool
  - Spell effects
  - Saving throws
  - AoE targeting
- [ ] **Tests:** Spell casting, spell point consumption, spell effects
- [ ] **Code:** `spell.py`, `spellbook.py`, `spell_effects.py`

#### Module 5: Leveling & Multiclass
- [ ] **PRD:** Progression system
  - XP tracking
  - Level-up choices
  - Multiclass rules
  - Feature unlocks
- [ ] **Tests:** Level-up, multiclass combos, feature grants
- [ ] **Code:** `leveling.py`, `multiclass.py`, `class_features.py`

#### Module 6: AI Tactics
- [ ] **PRD:** Enemy AI
  - Threat assessment
  - Target selection
  - Ability usage
  - Retreat logic
- [ ] **Tests:** AI behavior in combat
- [ ] **Code:** `ai_tactics.py`

### Phase 3: AI Agents
**Milestone:** DM generates story, NPCs have memory

#### Module 7: DM Agent
- [ ] **PRD:** Narrative generation
  - Story scene generation
  - Encounter creation (balanced CR)
  - Rule adjudication
  - Consequence tracking
- [ ] **Tests:** Story generation quality, encounter balance
- [ ] **Code:** `dm_agent.py`, `llm_client.py`

#### Module 8: NPC Agent
- [ ] **PRD:** NPC system
  - Memory/relationship tracking
  - Personality-driven dialogue
  - Quest availability
- [ ] **Tests:** NPC memory persistence, dialogue consistency
- [ ] **Code:** `npc_agent.py`

#### Module 9: Map Generator
- [ ] **PRD:** Procedural maps
  - Dungeon generation (BSP)
  - Town layouts
  - Wilderness (noise-based)
- [ ] **Tests:** Map validity, room connectivity
- [ ] **Code:** `map_generator.py`

#### Module 10: Campaign Generator
- [ ] **PRD:** Quest system
  - Quest chains
  - World events
  - Faction tracking
- [ ] **Tests:** Quest progression, branching
- [ ] **Code:** `campaign_generator.py`

### Phase 4: API Layer
**Milestone:** Backend exposes REST API for Godot client

- [ ] **PRD:** API endpoints (game session, character, combat, DM, map)
- [ ] **Tests:** API integration tests (CRUD, combat flow)
- [ ] **Code:** `api/routes/*.py`, `api/models.py`

### Phase 5: Frontend (Godot)
**Milestone:** Playable prototype (character creation + 1 dungeon + combat)

- [ ] **Character creation UI** (stat allocation, class select)
- [ ] **World exploration** (tile-based movement)
- [ ] **Combat UI** (action bar, target selection, animations)
- [ ] **Inventory UI** (drag-drop, equip/unequip)
- [ ] **Dialogue system** (NPC conversations)
- [ ] **Combat log** (text feed of actions)

### Phase 6: Polish & Testing
- [ ] Balance pass (class power, enemy CR, loot scaling)
- [ ] Playtesting (5-session campaign)
- [ ] Bug fixes, optimization
- [ ] Tutorial/onboarding

### Phase 7: Multiplayer (Future)
- [ ] Online co-op party (2-4 players)
- [ ] **Local co-op** (split-screen or hot-seat)
- [ ] AI fills missing roles
- [ ] Synchronization (turn-based = easier than real-time)

---

## 10. Success Criteria

### Phase 2 MVP (Core Engine):
- [ ] Create level 5 character (any class)
- [ ] Equip armor, weapon, consumables
- [ ] Complete combat (3 enemies, 5 rounds)
- [ ] Cast 3 spells (different schools)
- [ ] Level up to 6, apply stat/skill increases
- [ ] Multiclass: create Warrior 3 / Mage 2

### Phase 3 MVP (AI Agents):
- [ ] DM generates story scene from player input
- [ ] DM creates balanced encounter (CR appropriate)
- [ ] NPC remembers 3 past interactions
- [ ] NPC dialogue consistent with personality
- [ ] Generate dungeon map (10 rooms)
- [ ] Campaign generator creates 5-quest chain

### Phase 4 MVP (API):
- [ ] Create game session via API
- [ ] Submit combat action, receive result
- [ ] Request DM scene generation
- [ ] Generate map via API

### Phase 5 MVP (Godot Client):
- [ ] Character creation flow (point-buy)
- [ ] Move character on dungeon map
- [ ] Initiate combat, select actions
- [ ] View character sheet, inventory
- [ ] Talk to NPC, see dialogue

### Full Game:
- [ ] 10+ hour campaign
- [ ] 100+ spells, 200+ items
- [ ] 50+ monster types
- [ ] Player retention: 70%+ finish first campaign
- [ ] Positive reviews: 80%+ on Steam (future)

---

## 11. Technical Requirements

### Backend:
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **LLM:** Qwen3 (local) or Claude (API)
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Testing:** pytest, coverage ≥ 90%

### Frontend:
- **Engine:** Godot 4.2+
- **Language:** GDScript
- **Rendering:** 2D (tile-based)
- **Resolution:** 1920×1080 (scalable)

### Deployment:
- **Backend:** Docker container
- **Database:** Persistent volume
- **Frontend:** Standalone executable (Windows/Linux/Mac)

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AI generates inconsistent story | Medium | High | Structured prompts, memory system, rule constraints |
| Combat balance too easy/hard | High | Medium | Extensive playtesting, tunable difficulty |
| LLM API cost too high | Medium | Medium | Use local Qwen3 for 90% of calls, Claude for 10% critical |
| Multiplayer sync issues | Low | Medium | Turn-based = easier, defer to Phase 7 |
| Frontend performance | Low | Low | Godot optimized for 2D, tile-based rendering cheap |
| Scope creep | High | High | Strict phase gates, no feature adds without removal |

---

## 13. Open Questions

1. **Races:** Include multiple playable races (Elf, Dwarf, Orc) or human-only MVP?
   - **Decision:** Human-only MVP, races in Phase 7
   
2. **Voice acting:** Text-to-speech for NPCs or text-only?
   - **Decision:** Text-only MVP, TTS in Phase 6
   
3. **Permadeath:** Optional ironman mode or always respawn?
   - **Decision:** Respawn default, ironman optional

4. **DM model:** Always Qwen3 or hybrid (Qwen3 + Claude)?
   - **Decision:** Hybrid (Qwen3 for routine, Claude for boss/critical)

---

## 14. Appendices

### A. Glossary
- **AC:** Armor Class (defense rating)
- **AP:** Action Points (combat resource)
- **CR:** Challenge Rating (monster difficulty)
- **DM:** Dungeon Master (AI storyteller)
- **HP:** Hit Points (health)
- **NPC:** Non-Player Character
- **PC:** Player Character
- **SP:** Spell Points (magic resource)
- **XP:** Experience Points (progression currency)

### B. Inspiration Sources
- D&D 5e SRD (d20 system, advantage/disadvantage)
- Pathfinder 2e (action economy, proficiency tiers)
- GURPS Lite (point-buy, universal mechanics)
- Fate Core (aspects, narrative mechanics)
- Baldur's Gate 3 (UI, combat presentation)
- Divinity Original Sin 2 (environment interactions)
- Darkest Dungeon (stress, mortality, RNG)

### C. Future Expansions
- **Races:** Elf, Dwarf, Halfling, Orc (+racial features)
- **Classes:** Ranger, Bard, Paladin, Warlock (8 total)
- **Prestige Classes:** Archmage, Assassin, Champion (multiclass capstones)
- **Crafting:** Item creation, enchanting, alchemy
- **Base Building:** Player stronghold, hirelings, economy
- **PvP Arena:** Turn-based duels, tournaments
- **Mod Support:** Custom campaigns, items, spells

---

**End of GDD v0.2**

**Status:** Ready for Phase 2 (Core Engine development)

**Next Action:** Write PRD for Character System (Module 1)
