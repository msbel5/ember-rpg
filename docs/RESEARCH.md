# FRP Research Notes — System Design Deep Dive

## Research Phase (2026-03-22)

### 1. D&D 5e SRD Analysis

**Core mechanic strengths:**
- d20 + modifier vs DC (simple, intuitive)
- Advantage/disadvantage (elegant probability manipulation)
- Proficiency bonus scaling (linear progression)

**Core mechanic weaknesses:**
- Too many damage dice types (d4/d6/d8/d10/d12/d20)
- Spell slot system complex (1st-9th level slots)
- Multiclassing overly complicated (stat requirements, dead levels)

**What to keep:**
- Attribute modifier math: (stat - 10) / 2
- Proficiency scaling (+2 to +6)
- Saving throw categories (physical/mental)
- Action economy clarity

**What to improve:**
- Simplify dice (d20/d10/d6 only)
- Unified spell point system instead of slots
- Class balance (casters too strong late game)

---

### 2. Pathfinder 2e Insights

**Strengths:**
- Three-action economy (move/strike/cast all cost actions)
- Critical success/failure on ±10 (not just nat 20/1)
- Proficiency tiers (untrained/trained/expert/master/legendary)

**Applicable to Ember RPG:**
- Action point system > move+action+bonus
- Degrees of success (critical/success/failure/fumble)
- Skill progression beyond binary trained/untrained

---

### 3. GURPS Lite Lessons

**Strengths:**
- Point-buy character creation (total control)
- Universal mechanic (3d6 roll under skill)
- Modular advantages/disadvantages

**Weaknesses for our use:**
- Too crunchy (realistic but slow combat)
- No classes (complete sandbox = decision paralysis)

**Takeaway:**
- Point-buy for stats (player choice)
- Keep classes for structure (AI needs boundaries)
- Modular traits system (simple version)

---

### 4. Fate Core Philosophy

**Strengths:**
- Aspects (narrative tags with mechanical weight)
- Fate points (resource for player agency)
- "Fiction first" approach

**For Ember RPG:**
- Character aspects (3-5 traits that define personality + mechanics)
- Action points (spend for advantage, special moves)
- AI DM uses aspects to drive story

---

### 5. OSR (Old School Renaissance) Principles

**Strengths:**
- Rulings over rules (DM flexibility)
- Lethality (tension, stakes)
- Resource management (light/rations/ammo matter)

**For AI DM:**
- Clear rules baseline + AI improvisation
- Death is real (but resurrection possible)
- Encumbrance system (simple, not bean-counting)

---

## Core Design Decisions (Revised)

### Decision 1: Dice Philosophy
**Choice:** d20 (main) + d10 (damage/big effects) + d6 (small effects)
**Rationale:**
- d20: Industry standard, intuitive probabilities
- d10: Clean 10% increments, easy mental math
- d6: Ubiquitous, stackable (2d6, 3d6 for scaling)
- No d4/d8/d12: Reduces dice bloat, AI doesn't care but players do

### Decision 2: Action Economy
**Choice:** Action Point system (3 points/turn)
**Rationale:**
- Move: 1 point
- Standard action (attack/cast): 2 points
- Minor action (draw weapon/drink potion): 1 point
- Flexibility > rigid categories
- Pathfinder 2e proven this works

**Example:**
- Move + Attack: 1 + 2 = 3 points
- Move + Move + Minor: 1 + 1 + 1 = 3 points
- Attack + Minor + Minor: 2 + 1 + 0 (can't, only 3 points)

### Decision 3: Spell System
**Choice:** Spell Points instead of slots
**Rationale:**
- Spell slots confusing (1st/2nd/3rd level slots)
- Spell points: simple pool, spend = cast
- Spell cost = spell power level (1-5)
- More flexible, easier for AI to balance

**Calculation:**
```
Spell Points = (MND × 2) + (Level × 3)
Level 1 Mage (MND 14): 28 + 3 = 31 SP
Cast 5 L1 spells (5 SP each) = 25 SP used, 6 left
```

### Decision 4: Class System (Unified Base)
**Every entity (PC/NPC/monster) inherits from:**
```python
class Character:
    # Core stats (universal)
    stats: dict[str, int]  # MIG, AGI, END, MND, INS, PRE
    hp: int
    level: int
    
    # Combat
    ac: int
    initiative_bonus: int
    
    # Skills
    skills: dict[str, int]  # skill_name -> proficiency level
    
    # Class features (modular)
    features: list[Feature]
    
    # Inventory (universal)
    inventory: list[Item]
    equipment: dict[str, Item]  # slot -> item
    
    # Spells (if caster)
    spell_points: int
    known_spells: list[Spell]
```

**Peasant NPC:**
```python
Character(
    stats={'MIG': 10, 'AGI': 10, 'END': 10, ...},
    level=0,
    features=[],
    skills={'farming': 2}
)
```

**Ancient Dragon:**
```python
Character(
    stats={'MIG': 24, 'AGI': 12, 'END': 26, 'MND': 20, 'INS': 18, 'PRE': 22},
    level=15,
    features=[Flight(), BreathWeapon(10d6), FrightfulPresence()],
    skills={'perception': 6, 'arcana': 4},
    hp=300
)
```

### Decision 5: Item System (Everything is an Item)
```python
class Item:
    name: str
    value: int  # gold pieces
    weight: float  # pounds
    item_type: str  # weapon/armor/consumable/quest/junk
    
    # Optional effects
    damage_dice: str  # "1d6" or None
    armor_bonus: int  # +2 AC or 0
    effects: list[Effect]  # [Heal(2d6), Buff(AGI, +2, 1h)]
```

**Examples:**
```python
# Weapon
longsword = Item(
    name="Longsword",
    value=15,
    weight=3.0,
    item_type="weapon",
    damage_dice="1d10",
    effects=[]
)

# Magic weapon
flaming_sword = Item(
    name="Flaming Longsword +1",
    value=500,
    weight=3.0,
    item_type="weapon",
    damage_dice="1d10",
    effects=[ExtraDamage("1d6", "fire"), ToHitBonus(1)]
)

# Consumable
healing_potion = Item(
    name="Potion of Healing",
    value=50,
    weight=0.5,
    item_type="consumable",
    effects=[Heal("2d6+2")]
)

# Quest item
ancient_key = Item(
    name="Ancient Runed Key",
    value=0,  # Priceless but can't sell
    weight=0.1,
    item_type="quest"
)

# Gold (yes, even currency is an Item)
gold_pile = Item(
    name="Gold Coins",
    value=1,  # 1 gold = 1 gold
    weight=0.02,  # 50 coins = 1 pound
    item_type="currency"
)
```

### Decision 6: Multiclass System
**Simple approach:**
- Character has `classes: dict[str, int]` (class_name -> level)
- Total level = sum of class levels
- XP applies to total level, player chooses which class to advance
- Features granted at class_level milestones

**Example:**
```python
warrior_mage = Character(
    classes={'Warrior': 5, 'Mage': 3},
    total_level=8,
    features=[
        ExtraAttack(),      # Warrior L5
        ArmorMastery(),     # Warrior L3
        Spellcasting(3),    # Mage L1+
        SpellLibrary(6)     # Mage learns 2/level
    ]
)
```

**XP for next level:**
```
800 XP needed (level 8 -> 9)
Player chooses: level up Warrior to 6 OR Mage to 4
```

### Decision 7: Simple but Deep Combat
**Depth comes from:**
- Positioning (flanking, cover, elevation)
- Resource management (HP, spell points, action points)
- Threat assessment (focus fire? Divide damage? Control?)
- Environmental hazards (fire, ice, pit traps)

**Not from:**
- 50 special moves per class
- Attack-of-opportunity spaghetti
- Grapple/shove/trip mini-games

**Keep it turn-based, tactical, AI-friendly.**

---

## Revised Core Rules (Ember RPG v0.2)

### Attributes (6 stats, unchanged)
MIG / AGI / END / MND / INS / PRE

**Starting values:** Point-buy (27 points, min 8, max 15)
- 8 costs 0, 9 costs 1, 10 costs 2, ... 15 costs 9
- Or roll 4d6 drop lowest, 6 times

### Skills (Proficiency tiers)
- Untrained: +0
- Trained: +2
- Expert: +4
- Master: +6

**Skill check:** d20 + stat mod + proficiency ≥ DC

### Health & Damage
**HP = Base + (END × Multiplier)**
- Warrior: 12 + (END × 3)
- Rogue/Priest: 10 + (END × 2)
- Mage: 8 + (END × 1.5)

**Damage types:** Physical, Fire, Cold, Lightning, Necrotic, Radiant

### Combat (Action Point System)
**3 action points per turn**

**Costs:**
- Move (up to speed): 1 AP
- Attack: 2 AP
- Cast spell: 2 AP
- Use item: 1 AP
- Dash (double move): 2 AP
- Disengage (safe retreat): 1 AP
- Help ally: 1 AP

**Attack roll:** d20 + (MIG or AGI) + proficiency ≥ AC
**Damage roll:** weapon dice + stat mod + bonuses

**Critical hit:** Natural 20 OR beat AC by 10+
**Critical damage:** Double dice (not mods)

### Magic (Spell Point System)
**Spell Points = (MND × 2) + (Level × 3)**

**Spell costs:**
- Cantrip: 0 SP (at-will)
- Level 1: 5 SP
- Level 2: 10 SP
- Level 3: 15 SP
- Level 4: 20 SP
- Level 5: 25 SP

**Spell power:** 1d6 per spell level + MND mod
- Level 3 Fireball: 3d6 + MND mod

### Leveling (Simplified XP)
**XP needed = Current Level × 100**

**Per level gained:**
- +1 to any stat (max 20)
- +HP (roll class die + END mod)
- Choose: new skill proficiency OR upgrade existing
- Class feature (if milestone level)

---

## Architecture (Backend + Frontend)

### Backend (Python FastAPI)
```
frp-backend/
├── engine/
│   ├── core/
│   │   ├── character.py       # Character base class
│   │   ├── item.py            # Item base class
│   │   ├── rules.py           # Dice, stat checks, modifiers
│   │   └── world.py           # World state, quests
│   │
│   ├── combat/
│   │   ├── combat_engine.py   # Turn-based combat manager
│   │   ├── actions.py         # Attack, Cast, Move, etc.
│   │   └── ai_tactics.py      # Enemy AI decision making
│   │
│   └── progression/
│       ├── leveling.py        # XP, level-up logic
│       └── multiclass.py      # Class mixing rules
│
├── ai/
│   ├── dm_agent.py            # Story generation (LLM)
│   ├── npc_agent.py           # NPC dialogue + memory
│   ├── map_generator.py       # Procedural maps
│   └── campaign_generator.py  # Quest chains
│
├── data/
│   ├── classes.json           # Class definitions
│   ├── spells.json            # Spell library
│   ├── items.json             # Item database
│   ├── monsters.json          # Bestiary
│   └── campaigns/             # Campaign templates
│
├── api/
│   ├── main.py                # FastAPI app
│   ├── routes/
│   │   ├── game.py            # Game session endpoints
│   │   ├── character.py       # Character CRUD
│   │   └── combat.py          # Combat actions
│   └── models.py              # Pydantic schemas
│
└── tests/
    ├── test_character.py
    ├── test_combat.py
    ├── test_dm_agent.py
    └── test_multiclass.py
```

### Frontend (Godot + GDScript)
```
frp-game/
├── scenes/
│   ├── world/
│   │   ├── WorldMap.tscn      # Overworld
│   │   └── Dungeon.tscn       # Dungeon maps
│   │
│   ├── combat/
│   │   ├── CombatScene.tscn   # Turn-based battle
│   │   └── ActionUI.tscn      # Action point UI
│   │
│   └── ui/
│       ├── CharacterSheet.tscn
│       ├── Inventory.tscn
│       └── DialogueBox.tscn
│
├── scripts/
│   ├── networking/
│   │   ├── api_client.gd      # HTTP client for backend
│   │   └── session_manager.gd # Game state sync
│   │
│   └── game_logic/
│       ├── character.gd       # Client-side character
│       ├── combat_ui.gd       # Combat UI controller
│       └── map_renderer.gd    # Tile rendering
│
└── assets/
    ├── sprites/
    ├── tiles/
    └── audio/
```

### Communication Flow
```
Godot Client → HTTP POST → FastAPI Backend → AI Agent (if needed) → Response → Godot
```

**Example:**
1. Player clicks "Attack Goblin"
2. Godot sends: `POST /combat/action {"action": "attack", "target_id": "goblin_1"}`
3. Backend:
   - Validates action (has 2 AP? In range?)
   - Rolls attack: d20 + mods vs goblin AC
   - Calculates damage
   - Updates combat state
   - AI decides goblin's response
4. Backend responds: `{"hit": true, "damage": 8, "goblin_hp": 2, "goblin_action": "flee"}`
5. Godot animates hit, updates HP bars, moves goblin

---

## Next Steps (Revised)

1. **Finalize GDD v0.2** with research insights
2. **Write detailed subsystems:**
   - Spell database (100 spells, all 5 levels)
   - Item database (weapons, armor, consumables, quest items)
   - Monster bestiary (50 creatures, CR 1-20)
   - Class features (all 4 classes, L1-L20)
3. **Prototype core engine:**
   - `character.py` (base class + tests)
   - `item.py` (base class + examples)
   - `rules.py` (dice, checks, modifiers)
   - `combat_engine.py` (action point system)
4. **Test combat scenario:**
   - 2 warriors vs 3 goblins
   - Multiclass mage/rogue vs owlbear
   - Dragon boss fight
5. **AI DM prototype:**
   - Generate story scene from prompt
   - Create combat encounter (balanced CR)
   - NPC dialogue with memory

---

**Status:** Research phase complete, ready for deep GDD v0.2 writing.
