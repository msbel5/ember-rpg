# PRD: Ember RPG — Top-Down Living World View
# Version 1.0 | 2026-03-25
# Based on: DF source analysis, RimWorld decompiled patterns, existing Ember codebase

---

## 1. Vision

Transform Ember RPG from text-only into a **DF/Rimworld-style top-down ASCII view** where the player sees and interacts with a living, breathing world. Every NPC has a life. Every action costs time. Every object can be interacted with. The DM (LLM) narrates consequences and asks for skill checks when outcomes are uncertain.

**Core principle:** The simulation runs deterministically. The AI only narrates — it never decides game state.

### Implementation Snapshot (2026-03-25)

- The terminal client now renders the session's real map, viewport, spatial index, AP, and equipment state instead of maintaining a disconnected `MapState`.
- Arrow-key movement and typed movement both route through `GameEngine.process_action(...)`, so movement, AP spend, world time, and NPC reactions stay unified.
- Ground items, NPC movement, and workstation entities are visible because the renderer reads the same state the API and autosave use.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                 RENDERER (curses/rich)           │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Map View │  │ Narrative │  │  Status Bar   │  │
│  │ (scroll) │  │  Panel    │  │  HP/XP/Time   │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
├─────────────────────────────────────────────────┤
│              VIEWPORT / CAMERA                   │
│  position, zoom level, fog of war               │
├─────────────────────────────────────────────────┤
│              SPATIAL INDEX                        │
│  grid[(x,y)] → [Entity, Entity, ...]            │
├─────────────────────────────────────────────────┤
│              ENTITY SYSTEM                       │
│  Entity(id, type, pos, glyph, color, state)     │
│  Components: Needs, Inventory, Skills, Body     │
├─────────────────────────────────────────────────┤
│              TICK ENGINE                          │
│  SimTick → move NPCs, decay needs, run economy  │
│  ActionTick → player input costs movement points │
├─────────────────────────────────────────────────┤
│              MAP DATA (existing)                 │
│  MapData + ZoneMap + BuildingTemplates           │
├─────────────────────────────────────────────────┤
│              WORLD STATE (existing)              │
│  16 Living World modules, all deterministic     │
└─────────────────────────────────────────────────┘
```

---

## 3. Map System

### 3.1 Multi-Scale Maps (from DF)

| Scale | Size | Tile Represents | Use |
|-------|------|-----------------|-----|
| **World Map** | 64x64 | Region (forest/mountain/ocean/city) | Fast travel, caravan routes |
| **Region Map** | 128x128 | Area (town district, dungeon level, forest clearing) | Main gameplay |
| **Building Interior** | 16x16 - 32x32 | Room detail (furniture, containers) | Indoor exploration |

### 3.2 Tile Data Structure

```python
@dataclass
class Tile:
    terrain: TerrainType          # GRASS, STONE, WATER, ROAD, WALL...
    zone: ZoneType                # MARKET, TAVERN, RESIDENTIAL...
    walkable: bool
    walk_cost: int                # 1=normal, 2=rough, 5=difficult, 99=impassable
    fertility: float              # For farming zones
    building: Optional[str]       # Building ID if occupied
    items: list[str]              # Item IDs on ground
    flags: set                    # INDOORS, DARK, AQUIFER, FLAMMABLE...
```

### 3.3 Terrain Types (30+)

**Natural:** grass, dirt, sand, mud, snow, ice, rock, clay, marsh, deep_water, shallow_water, lava, cave_floor, cave_wall

**Built:** stone_floor, wood_floor, cobblestone, marble, brick, carpet, road, bridge, dock_planks

**Walls:** stone_wall, wood_wall, brick_wall, cave_wall, iron_door, wood_door, gate

**Special:** stairs_up, stairs_down, altar, well, forge, workbench, bed, chair, table, chest, barrel

### 3.4 ASCII Glyphs

```
Terrain:
.  grass/floor     ,  dirt/path      ~  water         =  bridge
#  wall            +  door (closed)  /  door (open)   >  stairs down
<  stairs up       ^  mountain       T  tree           "  tall grass
*  flowers         %  bush           &  forge          $  chest

Entities:
@  player          M  merchant       G  guard          B  blacksmith
!  quest_giver     ?  beggar         P  priest         H  healer
g  goblin          s  skeleton       w  wolf           o  orc
r  rat             S  spider         d  dragon         z  zombie

Items on ground:
)  weapon          [  armor          !  potion         /  staff
(  shield          ]  scroll         {  gold           }  gem
```

---

## 4. Entity System (from Rimworld)

### 4.1 Entity Dataclass

```python
@dataclass
class Entity:
    id: str
    entity_type: EntityType       # NPC, CREATURE, ITEM, BUILDING, FURNITURE
    name: str
    position: tuple[int, int]
    glyph: str                    # ASCII character
    color: str                    # Terminal color name
    blocking: bool                # Blocks movement?

    # Components (optional, based on type)
    needs: Optional[NPCNeeds]
    inventory: Optional[Inventory]
    skills: Optional[SkillSet]
    body: Optional[BodyPartTracker]
    faction: Optional[str]
    schedule: Optional[Schedule]
    job: Optional[Job]
    dialogue: Optional[DialogueState]

    # State
    alive: bool = True
    hp: int = 10
    max_hp: int = 10
    disposition: str = "neutral"   # friendly/neutral/hostile/afraid
```

### 4.2 Spatial Index (from Rimworld thingGrid)

```python
class SpatialIndex:
    """O(1) lookup: what's at position (x,y)?"""
    grid: dict[tuple[int,int], list[Entity]]

    def at(self, x, y) -> list[Entity]
    def move(self, entity, new_x, new_y)
    def add(self, entity)
    def remove(self, entity)
    def in_radius(self, x, y, radius) -> list[Entity]
    def blocking_at(self, x, y) -> bool
```

---

## 5. Tick System (DF+Rimworld hybrid)

### 5.1 Dual Clock

| Clock | Rate | Drives |
|-------|------|--------|
| **SimTick** | Every player action | NPC AI decisions, need decay, schedule checks |
| **WorldTick** | Every 15 game-minutes | Economy, caravans, rumors, quest timers |

Current implementation note: long actions and rest advance the same world loop by larger minute blocks instead of bypassing simulation.

### 5.2 Action Point System

Each entity has **Action Points (AP)** per turn:

| Class | AP/Turn | Tiles/Turn | Notes |
|-------|---------|------------|-------|
| Warrior | 4 | 4 on flat, 2 on rough | Heavy armor slows |
| Rogue | 6 | 6 on flat, 3 on rough | Fastest |
| Mage | 3 | 3 on flat, 1 on rough | Slowest but spells are 1 AP |
| Priest | 4 | 4 on flat, 2 on rough | Balanced |

**AP costs:**
- Move 1 tile (flat): 1 AP
- Move 1 tile (rough/stairs): 2 AP
- Attack (melee): 2 AP
- Attack (ranged): 3 AP
- Talk/Examine/Trade: 1 AP
- Cast spell: 1-3 AP (depends on spell)
- Craft: 5-20 AP (depends on recipe)
- Rest: 0 AP (consumes 8 game-hours)
- Pick up item: 1 AP
- Open door/chest: 1 AP

### 5.3 NPC Behavior Tree (from Rimworld ThinkTree)

```
Priority (top = highest):
├── Flee (if safety < 20 AND hostile nearby)
├── Combat (if hostile player/creature in range)
├── Satisfy Critical Need
│   ├── Eat (if sustenance < 15, go to tavern)
│   ├── Sleep (if rest < 10, go to bed)
│   └── Seek Safety (if safety < 15, go to guarded area)
├── Follow Schedule
│   ├── Morning: go to workplace
│   ├── Midday: go to market/tavern
│   ├── Afternoon: work or patrol
│   ├── Evening: social at tavern
│   └── Night: go home, sleep
├── Satisfy Moderate Need
│   ├── Social (if social < 40, talk to nearby NPC)
│   └── Commerce (if commerce < 40, trade/craft)
├── Patrol (guards only: follow patrol route)
├── Wander (random movement within home zone)
└── Idle (stay in place, wait)
```

---

## 6. Crafting System

### 6.1 Design (from DF reactions + Rimworld bills)

```python
@dataclass
class CraftingRecipe:
    id: str
    name: str                      # "Iron Sword", "Healing Potion"
    workstation: str               # "forge", "alchemy_bench", "workbench", "kitchen", "any"
    skill: str                     # "smithing", "alchemy", "cooking", "carpentry"
    skill_dc: int                  # Difficulty class (10=easy, 15=medium, 20=hard, 25=master)
    ap_cost: int                   # Action points to craft
    ingredients: list[Ingredient]  # Required materials
    products: list[Product]        # What you get
    tools: list[str]               # Required tools (hammer, tongs, mortar)
    failure_result: Optional[str]  # What happens on failed check ("ruined_iron", None=nothing lost)
    xp_reward: int                 # Crafting XP gained
```

### 6.2 Recipe Examples (40+ planned)

**Smithing (forge required):**

| Recipe | Ingredients | DC | AP | Product |
|--------|------------|-----|-----|---------|
| Iron Bar | 2x iron_ore, 1x coal | 10 | 5 | 1x iron_bar |
| Steel Bar | 1x iron_bar, 1x coal, 1x flux | 14 | 8 | 1x steel_bar |
| Iron Sword | 2x iron_bar | 12 | 10 | 1x iron_sword |
| Steel Sword | 2x steel_bar | 16 | 15 | 1x steel_sword |
| Iron Shield | 3x iron_bar, 1x leather | 13 | 12 | 1x iron_shield |
| Chain Mail | 5x iron_bar | 15 | 20 | 1x chain_mail |
| Plate Armor | 4x steel_bar, 2x leather | 18 | 25 | 1x plate_armor |
| Arrowheads | 1x iron_bar | 10 | 3 | 10x iron_arrowhead |
| Iron Nails | 1x iron_bar | 8 | 2 | 20x iron_nail |

**Alchemy (alchemy_bench required):**

| Recipe | Ingredients | DC | AP | Product |
|--------|------------|-----|-----|---------|
| Healing Potion | 1x herb_heal, 1x water, 1x glass_vial | 12 | 5 | 1x healing_potion |
| Mana Potion | 1x moonflower, 1x spring_water, 1x glass_vial | 14 | 5 | 1x mana_potion |
| Poison | 1x nightshade, 1x venom_sac, 1x glass_vial | 15 | 5 | 1x poison_vial |
| Antidote | 1x herb_cure, 1x honey, 1x glass_vial | 13 | 5 | 1x antidote |
| Fire Bomb | 1x oil, 1x sulfur, 1x glass_vial | 16 | 8 | 1x fire_bomb |
| Smoke Bomb | 1x charcoal, 1x saltpeter, 1x cloth | 12 | 5 | 1x smoke_bomb |

**Cooking (kitchen/campfire required):**

| Recipe | Ingredients | DC | AP | Product |
|--------|------------|-----|-----|---------|
| Bread | 2x flour, 1x water | 8 | 3 | 2x bread |
| Stew | 1x meat, 1x vegetable, 1x water | 10 | 5 | 2x stew |
| Ale | 3x grain, 1x water, 1x yeast | 12 | 10 | 3x ale |
| Dried Meat | 2x meat, 1x salt | 8 | 8 | 3x dried_meat |
| Trail Rations | 1x bread, 1x dried_meat, 1x fruit | 10 | 5 | 3x trail_rations |

**Carpentry (workbench required):**

| Recipe | Ingredients | DC | AP | Product |
|--------|------------|-----|-----|---------|
| Wooden Shield | 3x wood_plank, 5x iron_nail | 10 | 8 | 1x wooden_shield |
| Bow | 1x wood_plank, 1x sinew | 12 | 8 | 1x bow |
| Arrow | 1x wood_stick, 1x iron_arrowhead, 1x feather | 8 | 2 | 5x arrow |
| Lockpick | 1x iron_bar | 14 | 3 | 1x lockpick |
| Torch | 1x wood_stick, 1x cloth, 1x oil | 6 | 2 | 3x torch |
| Wooden Chest | 4x wood_plank, 10x iron_nail | 12 | 10 | 1x wooden_chest |
| Bed | 3x wood_plank, 2x cloth | 10 | 8 | 1x bed |

**Leatherworking (workbench required):**

| Recipe | Ingredients | DC | AP | Product |
|--------|------------|-----|-----|---------|
| Leather | 1x hide, 1x tanning_agent | 10 | 8 | 1x leather |
| Leather Armor | 4x leather, 2x sinew | 13 | 15 | 1x leather_armor |
| Backpack | 2x leather, 1x sinew | 11 | 8 | 1x backpack |
| Waterskin | 1x leather | 8 | 3 | 1x waterskin |
| Quiver | 1x leather | 8 | 3 | 1x quiver |

### 6.3 Material Quality (from existing materials.py)

Crafting skill check result determines quality:

| Roll vs DC | Quality | Stat Modifier |
|-----------|---------|--------------|
| Fail by 5+ | **Ruined** | Ingredients lost, no product |
| Fail by 1-4 | **Shoddy** | -2 damage/armor, -30% value |
| Meet DC | **Normal** | Base stats |
| Beat by 3-5 | **Fine** | +1 damage/armor, +50% value |
| Beat by 6-9 | **Superior** | +2 damage/armor, +100% value |
| Beat by 10+ | **Masterwork** | +3 damage/armor, +200% value, unique name |

Material type (from materials.py) stacks with quality: steel_bar gives better base than iron_bar, mithril better than steel, etc.

---

## 7. Non-Combat Skill Checks

### 7.1 Check System

When the player attempts something uncertain, the DM calls for a skill check:

```
Player: "pick the lock on the chest"
DM: "The lock is rusty but intricate. Roll Dexterity (DC 14)."
[System rolls d20 + DEX modifier]
Result ≥ DC → Success (DM narrates positive outcome)
Result < DC → Failure (DM narrates consequence)
```

### 7.2 Ability Checks

| Ability | Abbr | Used For |
|---------|------|----------|
| **Might (MIG)** | STR | Break doors, bend bars, lift heavy objects, intimidate, grapple |
| **Agility (AGI)** | DEX | Pick locks, disarm traps, sneak, dodge, climb, balance, sleight of hand |
| **Endurance (END)** | CON | Resist poison, hold breath, forced march, drink contest, survive cold |
| **Mind (MND)** | INT | Identify magic items, recall lore, read ancient script, appraise value |
| **Insight (INS)** | WIS | Detect lies, spot hidden, track creatures, sense danger, medicine |
| **Presence (PRE)** | CHA | Persuade, bluff, haggle prices, inspire, calm animal, seduce |

### 7.3 Check Situations (50+ triggers)

**Physical:**
- Force open locked door (MIG DC 12-18)
- Climb wall (AGI DC 10-16)
- Swim across river (END DC 12)
- Balance on narrow bridge (AGI DC 13)
- Push heavy boulder (MIG DC 16)
- Squeeze through narrow gap (AGI DC 11)

**Social:**
- Haggle for better price (PRE DC 12, -10% to -30% price on success)
- Persuade guard to let you pass (PRE DC 14)
- Bluff past checkpoint (PRE DC 15)
- Intimidate bandit to flee (MIG or PRE DC 13)
- Calm angry mob (PRE DC 18)
- Seduce innkeeper for free room (PRE DC 14)
- Bribe official (PRE DC 10, requires gold)

**Knowledge:**
- Identify magic item (MND DC 12-20)
- Recall history of ruin (MND DC 14)
- Read ancient inscription (MND DC 16)
- Appraise gem value (MND DC 12)
- Recognize poison in drink (INS DC 15)
- Understand foreign language (MND DC 18)

**Perception:**
- Spot hidden door (INS DC 14)
- Notice pickpocket attempt (INS DC 12)
- Detect ambush (INS DC 15)
- Find trap (INS DC 13-18)
- Track creature through forest (INS DC 12)
- Read body language / detect lie (INS DC vs target PRE)

**Survival:**
- Forage for food in wilderness (INS DC 10)
- Find clean water (INS DC 8)
- Build shelter (MND DC 11)
- Start fire without tools (AGI DC 12)
- Navigate without map (INS DC 14)
- Resist disease (END DC 12-16)

**Crafting-adjacent:**
- Repair broken weapon in field (MND DC 13)
- Improvise tool (MND DC 14)
- Sabotage mechanism (AGI DC 15)
- Set trap (AGI DC 12)
- Harvest herb without destroying it (AGI DC 10)

### 7.4 Contested Checks

When two entities oppose each other:
```
Player sneaks past guard: Player AGI vs Guard INS
Player haggles: Player PRE vs Merchant PRE
Player arm-wrestles: Player MIG vs NPC MIG
Player lies: Player PRE vs NPC INS
```

Both roll d20 + modifier. Higher wins. Tie = status quo.

---

## 8. Viewport & Camera

### 8.1 Screen Layout (terminal)

```
┌─────────────────────────────────┬────────────────────────┐
│                                 │                        │
│         MAP VIEWPORT            │    NARRATIVE PANEL     │
│       (scrollable, centered     │    (DM text, events,   │
│        on player @)             │     dialogue, checks)  │
│                                 │                        │
│     T . . . # # . . T          │  > look around          │
│     . . M . + . . . .          │  You see a bustling     │
│     . . . . . . G . .          │  market square. A       │
│     # # + # # # # # #          │  merchant waves...      │
│     . . . @ . . . . .          │                        │
│     . . . . . B . . .          │  > talk merchant        │
│     # # # # + # # # #          │  [PRE check DC 12...]   │
│     . . . . . . . . .          │                        │
│                                 │                        │
├─────────────────────────────────┴────────────────────────┤
│ Mami  Warrior Lv3  HP:18/20  AP:4/4  Harbor Town         │
│ Day 3 14:30 (Afternoon)  Gold:47  XP:230  Pos:[5,7]     │
├──────────────────────────────────────────────────────────┤
│ > _                                                       │
└──────────────────────────────────────────────────────────┘
```

### 8.2 Zoom Levels

| Key | Level | View |
|-----|-------|------|
| `1` | **Local** (default) | 1 tile = 1 char. See individual entities, furniture, items |
| `2` | **District** | 4x4 tiles = 1 char. See buildings, zones, roads |
| `3` | **World** | Region = 1 char. See cities, forests, mountains, roads |

### 8.3 Fog of War

- **Visible:** Within line-of-sight (8 tiles outdoor, 5 indoor, blocked by walls)
- **Explored:** Previously seen, shown in dim/grey
- **Unknown:** Never seen, shown as blank space

---

## 9. Interaction System

### 9.1 Context-Sensitive Interactions

Player faces/selects a tile → system checks what's there → offers relevant actions:

| Target | Available Actions |
|--------|-------------------|
| NPC (friendly) | talk, trade, examine, follow, hire |
| NPC (hostile) | attack, flee, sneak past, intimidate |
| Door (locked) | pick lock (AGI), force open (MIG), use key |
| Door (unlocked) | open, close, lock (with key) |
| Chest | open, pick lock, examine (trap check) |
| Item on ground | pick up, examine, kick |
| Workstation | craft, examine, use |
| Tree | chop (get wood), examine, climb |
| Ore vein | mine (get ore), examine |
| Water | drink, fill waterskin, fish, swim across |
| Bed | rest, search under |
| NPC corpse | loot, examine, bury |
| Sign/book | read |
| Lever/button | pull/push |
| Altar | pray (faction-dependent effect) |

### 9.2 Interaction Flow

```
1. Player types "examine chest" or clicks chest tile
2. System checks proximity (must be adjacent)
3. System checks for traps (passive INS check DC 12)
4. If trapped → "You notice a needle trap! Disarm? (AGI DC 14)"
5. If not trapped or disarmed → Show contents
6. DM narrates: "Inside the weathered chest you find..."
7. Player can take items (pick up = 1 AP each)
```

---

## 10. Implementation Sprints

### Sprint 1: Foundation (Entity + Spatial + Viewport)
- FR-01: Entity dataclass with all components
- FR-02: SpatialIndex with O(1) grid lookup
- FR-03: Viewport/Camera class with scroll and center-on-player
- FR-04: ASCII map renderer (curses) with split layout
- FR-05: Fog of war (LOS-based, Bresenham)
- FR-06: Entity placement on map from zone data
- **Tests:** 30+ | **AC:** Map renders, player moves, entities visible, fog works

### Sprint 2: Movement + AP System
- FR-07: Action Point system per entity (class-based AP pool)
- FR-08: Movement costs tile walk_cost × AP
- FR-09: Click-to-move pathfinding (existing A*)
- FR-10: NPC movement via behavior tree (flee/schedule/wander)
- FR-11: Turn resolution — player acts, then all NPCs act
- FR-12: Simultaneous NPC movement (no entity collision deadlocks)
- **Tests:** 25+ | **AC:** Player moves with AP, NPCs follow schedules visually

### Sprint 3: Interaction + Skill Checks
- FR-13: Context-sensitive interaction menu per tile
- FR-14: Non-combat skill check system (d20 + mod vs DC)
- FR-15: Contested checks (entity vs entity)
- FR-16: Check consequences (success/failure/critical)
- FR-17: Lock/trap/door interaction chain
- FR-18: DM narrates all check results via LLM
- **Tests:** 30+ | **AC:** Pick locks, spot traps, persuade NPCs, all with dice rolls

### Sprint 4: Crafting
- FR-19: CraftingRecipe data-driven system
- FR-20: Workstation detection (entity must be adjacent to correct station)
- FR-21: Ingredient checking and consumption
- FR-22: Skill check determines quality
- FR-23: 40+ recipes across 5 crafting disciplines
- FR-24: NPC crafters produce goods autonomously
- **Tests:** 30+ | **AC:** Player crafts iron sword at forge, quality varies by roll

### Sprint 5: World Map + Zoom
- FR-25: World map generation (64x64 regions)
- FR-26: Three zoom levels with smooth transition
- FR-27: Fast travel between known locations
- FR-28: Random encounters during travel
- FR-29: Caravan visibility on world map
- FR-30: Region types with distinct terrain palettes
- **Tests:** 20+ | **AC:** Zoom out to see world, travel to new town, encounter bandits

### Sprint 6: Polish + Full Integration
- FR-31: Full NPC behavior tree running visually
- FR-32: Economy visible (merchant stock changes, prices fluctuate)
- FR-33: Rumor system visible (NPCs gossip, player hears news)
- FR-34: Quest markers on map
- FR-35: Save/load game state
- FR-36: Godot renderer reads same data (future bridge)
- **Tests:** 20+ | **AC:** Complete play session: explore, craft, trade, fight, quest

---

## 11. Performance Budget

| Metric | Target | Notes |
|--------|--------|-------|
| Map render | < 16ms | Only redraw dirty chunks |
| NPC tick (100 NPCs) | < 50ms | Behavior tree evaluation |
| Pathfinding (A*) | < 10ms | Max 20 tiles, cached |
| World tick | < 100ms | Economy + caravans + rumors |
| Memory | < 100MB | For 128x128 map + 200 entities |
| Terminal FPS | 15+ | Smooth scrolling |

---

## 12. What We Reuse (from existing codebase)

| Module | File | Status |
|--------|------|--------|
| Map generators | `engine/map/__init__.py` | ✅ Ready (3 generators) |
| Zone system | `engine/map/zones.py` | ✅ Ready (24 zone types) |
| A* pathfinding | `engine/world/proximity.py` | ✅ Ready |
| Line of sight | `engine/world/proximity.py` | ✅ Ready (Bresenham) |
| NPC needs | `engine/world/npc_needs.py` | ✅ Ready (5 needs) |
| NPC schedules | `engine/world/schedules.py` | ✅ Ready (5 time periods) |
| Naming | `engine/world/naming.py` | ✅ Ready (4 factions) |
| Economy | `engine/world/economy.py` | ✅ Ready (10 recipes) |
| Materials | `engine/world/materials.py` | ✅ Ready (10 materials) |
| Body parts | `engine/world/body_parts.py` | ✅ Ready (d20 hit table) |
| Ethics/factions | `engine/world/ethics.py` | ✅ Ready (6 factions) |
| History | `engine/world/history.py` | ✅ Ready (seed generator) |
| Institutions | `engine/world/institutions.py` | ✅ Ready (7 roles) |
| Caravans | `engine/world/caravans.py` | ✅ Ready (3 routes) |
| Rumors | `engine/world/rumors.py` | ✅ Ready |
| Tick scheduler | `engine/world/tick_scheduler.py` | ✅ Ready |
| Quest timeout | `engine/world/quest_timeout.py` | ✅ Ready |
| Offscreen sim | `engine/world/offscreen.py` | ✅ Ready |
| Need satisfaction | `engine/world/need_satisfaction.py` | ✅ Ready |
| GameEngine | `engine/api/game_engine.py` | ✅ Ready (action handlers) |

### What's NEW (must build):

| Component | Description |
|-----------|-------------|
| `Entity` dataclass | Unified entity with components |
| `SpatialIndex` | Grid-based O(1) entity lookup |
| `Viewport` | Camera, scroll, zoom, fog of war |
| `ASCIIRenderer` | curses-based split-panel renderer |
| `ActionPointSystem` | AP pool per entity, cost per action |
| `BehaviorTree` | NPC decision-making (priority nodes) |
| `CraftingSystem` | Recipe + workstation + skill check |
| `SkillCheckSystem` | d20 + mod vs DC, contested checks |
| `WorldMapGenerator` | 64x64 region map |
| `InteractionMenu` | Context-sensitive per-tile actions |
