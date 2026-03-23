# Ember RPG — Game Design Document v0.3
**Project:** Ember RPG
**Version:** 0.3 (World Simulation + AI Art Vision)
**Date:** 2026-03-24
**Authors:** Mami + Alcyone + Claude Code
**Status:** Active Development

---

## What Changed from v0.2

v0.2 defined core mechanics (d20, 6 stats, 3AP combat, spell points). All implemented, 872+ tests.

v0.3 adds three transformative layers:
1. **Dwarf Fortress-inspired world simulation** — coherent, living maps
2. **AI-generated layered art pipeline** — unique illustrations per scene
3. **Hitchhiker's Guide interface** — text adventure + illustrated POV

---

## 1. Vision Statement

> "DM anlatir, sen hayal edersin, gozunun onunde canlandirir." — Mami

Ember RPG is the first game that combines:
- **Real tabletop mechanics** (dice, stats, grid combat) — like BG3
- **AI narrative** (persistent memory, emergent quests) — like AI Dungeon
- **Deterministic world simulation** (without AI) — like Dwarf Fortress
- **AI-generated unique art** (per scene, per entity) — like nothing else

No existing game does all four. That is our market gap.

---

## 2. The Three Pillars (Updated)

### Pillar 1: Deterministic Simulation (Dwarf Fortress Legacy)

The world runs on **rules, not AI**. AI agents observe the world state and narrate — they don't control it. This separation is critical:

```
WRONG: AI decides "the merchant is angry"
RIGHT: Rules compute merchant.disposition = -30 (player stole from him)
       AI agent reads disposition and narrates accordingly
```

**World simulation principles (from DF):**
- **Cascading systems**: Actions → consequences → world state changes → new situations
- **Individual as unit**: Every NPC has personality, memory, relationships, goals
- **Emergent behavior**: Complex outcomes from simple rules interacting
- **Deterministic core**: Same input = same output. AI adds flavor, not decisions.

**What this means for gameplay:**
- Kill a merchant → prices rise in that town (supply/demand rule)
- Help the thieves guild → guard patrols increase (faction reaction rule)
- Ignore the goblin mine → goblins raid the town (world event timer)
- None of this needs AI — it's pure simulation. AI just narrates it beautifully.

### Pillar 2: AI-Generated Unique Art (Hitchhiker's Guide Legacy)

Every scene is illustrated with AI-generated art in a consistent style (comic book ink lines + watercolor). This is NOT random — it follows a **layered compositing pipeline**:

```
Layer 0: Far Background  — mountains/sea (4 per map, one per direction)
Layer 1: Mid Background  — buildings/streets (per zone + direction)
Layer 2: Items/Objects   — barrel, chest, notice board (per type)
Layer 3: Entities        — NPCs, monsters (per template, palette swaps for variants)
Layer 4: FX/Weather      — fog, rain, torch glow (procedural)
```

**Smart caching (the Mario memory trick):**
- Generate once, cache forever. Same tile + same direction = same image.
- A "barrel" is ONE image used everywhere barrels appear.
- Different guards = same guard image + HSV color shift.
- 20 generations per new location. ~50MB per campaign.
- Cross-campaign shared assets (generic items/NPCs).

**Cost: Near zero.** HuggingFace Flux Schnell is free. ~3 seconds per image.

### Pillar 3: Living Narrative (AI Agent Layer)

AI agents READ the deterministic world state and NARRATE. They don't control game logic.

```
World State:   merchant.disposition = -30, town.security = "high"
DM Agent:      "The merchant eyes you coldly. Guards stand closer than before."
NPC Agent:     "I have nothing to say to a thief." (reads relationship_score)
```

**Multi-model strategy:**
- Claude Sonnet: Complex narrative (boss encounters, key story moments)
- Claude Haiku: Routine dialogue, heartbeat, NPC chatter
- GPT-5-mini: Free fallback for simple responses
- Template: Guaranteed fallback when all models offline

---

## 3. World Simulation Architecture (DF-Inspired)

### 3.1 Multi-Layer Tile System

Current system stores `tile = "cobblestone"` (single string). Upgrade to:

```python
@dataclass
class Tile:
    terrain: str      # ground type: grass, stone, water, sand, wood
    structure: str     # what's built: wall, door, floor, road, none
    zone: str          # area purpose: market, residential, docks, wilderness
    passable: bool     # can entities walk here?
    elevation: int     # 0=ground, 1=raised, -1=below
    metadata: dict     # extra: light_level, moisture, etc.
```

### 3.2 Zone-Based Map Generation

Maps are generated top-down, NOT randomly:

```
Step 1: ZONE LAYOUT
  Define zones: market_square(center), docks(south), residential(NW, NE),
                gate(north), tavern_district(SE)

Step 2: ROAD NETWORK
  Connect zones with road tiles. Every zone reachable from every other.

Step 3: BUILDING TEMPLATES
  Stamp pre-defined building shapes into zones:
  - Tavern(3x3): wall/door/wall, wall/floor/wall, wall/wall/wall
  - Shop(2x3): wall/door, wall/floor, wall/wall
  - Market_stall(2x2): floor/floor, floor/floor (open air)

Step 4: ENTITY PLACEMENT
  NPC type → matching zone:
  - merchant → market zone, inside shop template
  - guard → gate zone or patrol route
  - innkeeper → tavern_district, inside tavern template
  - beggar → market zone, on road tile

Step 5: VALIDATION
  Check: every building touches a road, no NPC in walls,
         all zones connected, at least one map edge entrance.
  If fails → regenerate (DF's world rejection principle).
```

### 3.3 Building Template Library

```python
TEMPLATES = {
    "tavern_3x3": {
        "dim": (3, 3),
        "tiles": [
            [("wall","building"), ("door","building"), ("wall","building")],
            [("wall","building"), ("wood_floor","building"), ("wall","building")],
            [("wall","building"), ("wall","building"), ("wall","building")]
        ],
        "entities": {(1,1): "innkeeper"},
        "zone_affinity": ["tavern_district", "market"]
    },
    "market_stall_2x2": {
        "dim": (2, 2),
        "tiles": [
            [("cobblestone","stall"), ("cobblestone","stall")],
            [("cobblestone","stall"), ("cobblestone","stall")]
        ],
        "entities": {(0,0): "merchant"},
        "zone_affinity": ["market"]
    },
    "guard_post_1x1": {
        "dim": (1, 1),
        "tiles": [[("cobblestone","guard_post")]],
        "entities": {(0,0): "guard"},
        "zone_affinity": ["gate", "market"]
    }
}
```

### 3.4 NPC Simulation (DF Individual Principle)

Each NPC is a full individual with:
```python
@dataclass
class NPCState:
    # Identity
    name: str
    role: str           # merchant, guard, innkeeper, quest_giver
    personality: dict   # {friendly: 0.7, honest: 0.3, brave: 0.8}

    # Memory (Mantella-inspired)
    conversations: list # last 10 conversation summaries
    relationship: int   # -100 to +100 with player
    known_facts: list   # what this NPC knows
    emotional_state: str # calm, angry, afraid, happy

    # World interaction
    faction: str        # town_guard, merchants_guild, thieves_guild
    schedule: dict      # {morning: "shop", evening: "tavern", night: "home"}
    inventory: list     # what they carry/sell
    position: tuple     # (x, y) on map
```

AI agents receive this state as context. They don't decide the state — they narrate it.

---

## 4. Interface Design (Hitchhiker's Guide Model)

### 4.1 Layout

```
+---------------------------+------------------+
|                           |                  |
|     POV / Tile Map        |   Narrative      |
|     (AI-illustrated       |   (DM text,      |
|      or procedural)       |    scrolling)    |
|                           |                  |
+---------------------------+------------------+
| > What do you do?...                   [Send]|
+----------------------------------------------+
| Lv.1 Mage msbel    HP ████████ 12/12        |
+----------------------------------------------+
```

### 4.2 Controls

| Key | Action |
|-----|--------|
| Arrow keys | Rotate POV facing direction |
| INSERT | Toggle POV ↔ Tile Map |
| HOME | Inventory |
| Type + Enter | Send command to DM |
| Click entity | Context menu (examine/talk/trade/attack) |

### 4.3 Visual Progression

```
Phase 1 (NOW):    Procedural colored shapes (silhouettes)
Phase 2 (NEXT):   AI-generated backgrounds + silhouette entities
Phase 3 (AFTER):  Full AI-generated layered scenes
Phase 4 (FUTURE): Storyboard moments (item closeups, reflections)
```

---

## 5. Technical Architecture

```
┌─────────────────────────────────────────┐
│         Godot 4.6 Client (Windows)      │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ │
│  │POV      │ │Narrative │ │Input     │ │
│  │Renderer │ │Panel     │ │System    │ │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ │
│       │           │             │       │
│  ┌────┴───────────┴─────────────┴────┐  │
│  │        Asset Compositor           │  │
│  │  (layered AI image compositing)   │  │
│  └────────────────┬──────────────────┘  │
└───────────────────┼─────────────────────┘
                    │ HTTP REST API
┌───────────────────┼─────────────────────┐
│     Raspberry Pi 5 (alcyone)            │
│  ┌────────────────┴──────────────────┐  │
│  │        FastAPI Backend            │  │
│  │  ┌──────────┐ ┌────────────────┐  │  │
│  │  │Game      │ │Map Generator   │  │  │
│  │  │Engine    │ │(DF-style zones)│  │  │
│  │  └──────────┘ └────────────────┘  │  │
│  │  ┌──────────┐ ┌────────────────┐  │  │
│  │  │DM Agent  │ │World State     │  │  │
│  │  │(LLM)     │ │(simulation)    │  │  │
│  │  └──────────┘ └────────────────┘  │  │
│  │  ┌──────────┐ ┌────────────────┐  │  │
│  │  │NPC Agent │ │Asset Generator │  │  │
│  │  │(LLM)     │ │(HuggingFace)   │  │  │
│  │  └──────────┘ └────────────────┘  │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  OpenClaw Gateway + Telegram Bot  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 6. What Makes Ember RPG Unique

| Feature | AI Dungeon | BG3 | Dwarf Fortress | Ember RPG |
|---------|-----------|-----|----------------|-----------|
| Real dice/stats | No | Yes | No | **Yes** |
| AI narrative | Yes | No | No | **Yes** |
| World simulation | No | Scripted | **Yes** | **Yes** |
| Persistent NPC memory | No | Limited | **Yes** | **Yes** |
| AI-generated art | No | No | No | **Yes** |
| Consequence cascading | No | Scripted | **Yes** | **Yes** |
| Cost to play | $20/mo | $60 | Free | **Free** |

---

## 7. Content Targets

### MVP (Current Sprint)
- 1 playable location (Harbor Town)
- 5-10 NPCs with personality + memory
- Combat system working (3AP, spells)
- POV + tile map views
- AI narrative for all actions
- 30-minute play session possible

### Alpha
- 3 locations (town, dungeon, wilderness)
- 20+ NPCs, 5+ quest lines
- AI-generated art for all locations
- Save/load working
- 5+ hours content

### Beta
- World simulation (faction dynamics, consequence cascading)
- 5+ locations, 50+ NPCs
- Full AI art pipeline
- Multiplayer (local + online)
- 20+ hours content

---

## Appendix: Inspiration Sources

- **Dwarf Fortress** — World simulation, emergent behavior, individual-level NPC modeling
- **BBC Hitchhiker's Guide 30th Anniversary** — Text adventure + illustrated side panel
- **Monkey Island** — Point-and-click adventure feel, humor, character interaction
- **Baldur's Gate 3** — D&D mechanics, NPC companions, consequence-driven story
- **Doom (1993)** — First-person perspective with static sprites, storyboard feel
- **AI Dungeon** — AI-powered narrative (but lacks real game mechanics)
- **Mantella (Skyrim mod)** — NPC memory persistence, personality-driven dialogue
