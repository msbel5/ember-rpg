# PRD: Living World v1 — DF-Inspired Simulation Systems

**Status**: Draft
**Priority**: P0 (Foundation for all future features)
**Author**: Mami (analysis) + Claude Code (PRD)
**Date**: 2026-03-24
**References**: Dwarf Fortress entity_default.txt, reaction_smelter.txt, world_gen.txt

---

## Overview

Transform Ember RPG from a "well-narrated reactive game" into a "living world where AI narrates what deterministic rules produce." Every system below is **zero AI cost** — pure data + rules. LLM only reads state and narrates.

---

## Module 1: World Tick Scheduler

### Purpose
The world breathes without player input. Time passes, NPC needs change, stock depletes, rumors spread.

### Functional Requirements

**FR-01**: `WorldTickScheduler.advance(hours=1)` progresses game time and runs all subsystems
**FR-02**: Tick subsystems execute in order:
  1. GameTime advance
  2. NPC schedule update (move NPCs to correct location)
  3. NPC needs decay (hunger +1, social -1 per hour)
  4. Shop stock restock/decay (deliveries arrive, ale consumed)
  5. Rumor propagation (facts spread between NPCs in same location)
  6. Faction tension check (accumulated events → faction mood shift)
  7. Pending consequence effects (delayed bounties, guard alerts)
  8. Quest timeout check
  9. Local incident generation (random events: bar fight, theft, merchant arrival)

**FR-03**: Player actions trigger 1-hour tick. Resting triggers 8-hour tick.
**FR-04**: Loaded location = full tick. Unloaded = coarse summary tick.

### Data Model
```python
class WorldTickScheduler:
    def advance(self, hours: int = 1) -> list[WorldEvent]:
        events = []
        for _ in range(hours):
            events += self._tick_time()
            events += self._tick_npc_schedules()
            events += self._tick_npc_needs()
            events += self._tick_economy()
            events += self._tick_rumors()
            events += self._tick_factions()
            events += self._tick_consequences()
            events += self._tick_incidents()
        return events
```

### Acceptance Criteria
- AC-01: 100 ticks complete in <1 second on Pi 5
- AC-02: NPC positions change based on time of day
- AC-03: Shop stock changes over time without player interaction
- AC-04: Rumors heard by NPC A reach NPC B after N ticks

---

## Module 2: NPC Needs & Emotional Drives

### Purpose
NPCs have needs that decay over time. Unmet needs → mood change → behavior change. Zero AI cost.

### Functional Requirements

**FR-05**: Each NPC has a `needs` dict with 5 core needs (0-100 scale):
  - `safety`: decreases near danger, increases in guarded areas
  - `commerce`: merchants need sales, craftsmen need materials
  - `social`: increases when talking, decreases when alone
  - `sustenance`: food/drink need, decays hourly
  - `duty`: role-specific (guard needs to patrol, priest needs to pray)

**FR-06**: Needs decay per tick: `sustenance -= 2/hour`, `social -= 1/hour`
**FR-07**: Needs satisfied by actions: NPC eats → sustenance +30, NPC talks → social +10
**FR-08**: `emotional_state` derived from needs: all needs >60 = "content", any need <20 = "distressed", safety <10 = "terrified"
**FR-09**: Behavior modifiers from emotional state:
  - distressed merchant → prices +20%
  - terrified NPC → won't talk, runs away
  - content innkeeper → free drink for regulars
  - hungry guard → accepts bribe more easily

### Data Model
```python
class NPCNeeds:
    safety: int = 70
    commerce: int = 50
    social: int = 50
    sustenance: int = 80
    duty: int = 60

    def tick(self, hours: int = 1): ...
    def satisfy(self, need: str, amount: int): ...
    def emotional_state(self) -> str: ...
    def behavior_modifiers(self) -> dict: ...
```

### Acceptance Criteria
- AC-05: NPC with sustenance=0 has emotional_state="desperate"
- AC-06: Merchant with commerce<20 offers 15% discount
- AC-07: Guard with duty<30 leaves post (available for bribery)

---

## Module 3: NPC Schedules & Movement

### Purpose
NPCs move between locations based on time of day. The tavern is empty at dawn, full at night.

### Functional Requirements

**FR-10**: Each NPC has a `schedule` dict mapping time_period → location:
```python
schedule = {
    "dawn": "home",        # 06:00-08:00
    "morning": "shop",     # 08:00-12:00
    "afternoon": "market",  # 12:00-17:00
    "evening": "tavern",   # 17:00-22:00
    "night": "home"        # 22:00-06:00
}
```

**FR-11**: `WorldTickScheduler` moves NPCs to scheduled location on time period change
**FR-12**: NPC position updates in `entities` response — Godot sees NPC appear/disappear
**FR-13**: If NPC's scheduled location is destroyed/blocked, fallback to nearest safe zone
**FR-14**: Guard schedules include patrol routes (list of positions cycled hourly)

### Acceptance Criteria
- AC-08: Tavern has 0 NPCs at 07:00, 3+ NPCs at 20:00
- AC-09: Merchant is at shop during morning, market during afternoon
- AC-10: Guard cycles through 4 patrol positions

---

## Module 4: Material & Item Properties

### Purpose
Items have physical properties derived from materials. Iron sword ≠ steel sword ≠ wooden sword. Deterministic, no AI.

### Functional Requirements

**FR-15**: Material database with properties:
```python
MATERIALS = {
    "iron":   {"density": 7.8, "hardness": 4, "value_mult": 1.0, "damage_mult": 1.0, "armor_mult": 1.0},
    "steel":  {"density": 7.9, "hardness": 6, "value_mult": 1.5, "damage_mult": 1.3, "armor_mult": 1.3},
    "bronze": {"density": 8.7, "hardness": 3, "value_mult": 0.8, "damage_mult": 0.9, "armor_mult": 0.8},
    "wood":   {"density": 0.6, "hardness": 1, "value_mult": 0.3, "damage_mult": 0.5, "armor_mult": 0.3},
    "leather":{"density": 0.9, "hardness": 1, "value_mult": 0.5, "damage_mult": 0.0, "armor_mult": 0.5},
    "mithril":{"density": 3.0, "hardness": 8, "value_mult": 5.0, "damage_mult": 1.8, "armor_mult": 2.0},
}
```

**FR-16**: Item damage = base_damage × material.damage_mult
**FR-17**: Item weight = base_weight × material.density / reference_density
**FR-18**: Item value = base_value × material.value_mult
**FR-19**: Armor rating = base_armor × material.armor_mult

### Acceptance Criteria
- AC-11: steel_sword.damage > iron_sword.damage > wooden_sword.damage
- AC-12: mithril_chainmail.weight < iron_chainmail.weight
- AC-13: Item tooltip shows material name: "Steel Longsword (1d8+2)"

---

## Module 5: Hit Location & Body Parts

### Purpose
Combat hits specific body parts. "Slash to the left arm" → arm injury → can't hold shield. Adds tactical depth at zero player cost (engine rolls everything).

### Functional Requirements

**FR-20**: Hit location table (d20 roll):
```python
HIT_LOCATIONS = {
    (1, 2):   "head",       # 10% — critical area
    (3, 5):   "torso",      # 15% — main body
    (6, 8):   "left_arm",   # 15%
    (9, 11):  "right_arm",  # 15%
    (12, 14): "left_leg",   # 15%
    (15, 17): "right_leg",  # 15%
    (18, 19): "chest",      # 10% — armor primary
    (20, 20): "neck",       # 5% — critical
}
```

**FR-21**: Each body part has HP derived from total HP: head=30%, torso=50%, limb=25%
**FR-22**: Body part at 0 HP → injury effect:
  - head: stunned 1 round
  - arm: drop held item, -50% damage with that hand
  - leg: movement halved
  - chest: bleeding (1 HP/round)
  - neck: instant critical (double damage)

**FR-23**: Armor covers specific locations:
  - helmet → head, neck
  - chainmail → torso, chest
  - shield → left_arm (active block)
  - greaves → legs

**FR-24**: DM narrates hit location: "The goblin's rusty blade catches your left arm..."

### Acceptance Criteria
- AC-14: Hit location varies per attack (d20 roll)
- AC-15: Damaged arm reduces damage output
- AC-16: Helmet reduces head damage by armor value
- AC-17: Narrative mentions body part hit

---

## Module 6: Ethics & Cultural Values (per Faction)

### Purpose
Different factions react differently to the same event. Killing a plant angers elves but goblins don't care. Deterministic, data-driven.

### Functional Requirements

**FR-25**: Each faction has an `ethics` dict:
```python
FACTION_ETHICS = {
    "harbor_guard": {
        "KILL_CITIZEN": "unthinkable",    # -100 rep
        "THEFT": "crime",                  # -30 rep, bounty
        "ASSAULT": "serious_crime",        # -50 rep, guards attack
        "KILL_ENEMY": "acceptable",        # no penalty
        "TRADE": "valued",                 # +5 rep per trade
    },
    "thieves_guild": {
        "KILL_CITIZEN": "distasteful",     # -10 rep
        "THEFT": "acceptable",             # no penalty
        "ASSAULT": "tolerated",            # -5 rep
        "BETRAYAL": "unthinkable",         # -100 rep, assassination contract
    },
}
```

**FR-26**: Each faction has `values` dict affecting NPC behavior:
```python
FACTION_VALUES = {
    "harbor_guard": {"order": 80, "commerce": 60, "tradition": 40},
    "merchant_guild": {"commerce": 90, "wealth": 80, "order": 30},
    "forest_elves": {"nature": 95, "tradition": 80, "art": 70},
}
```

**FR-27**: CascadeEngine rules parameterized by faction ethics
**FR-28**: NPC dialogue influenced by faction values (passed to LLM as context)

### Acceptance Criteria
- AC-18: Stealing from merchant → harbor_guard rep -30, thieves_guild rep +5
- AC-19: Killing a tree → forest_elves hostility, no effect on harbor_guard

---

## Module 7: World History Seed

### Purpose
Campaign starts with pre-generated history. NPCs reference past events. Zero runtime cost, maximum narrative depth.

### Functional Requirements

**FR-29**: `HistorySeed.generate(world_seed: int)` produces:
  - 3-5 past wars with names, dates, factions involved
  - 2-3 fallen kingdoms/cities
  - 1 ancient catastrophe (The Sundering, The Plague of Shadows, etc.)
  - 5-10 notable historical figures (some alive, some dead)
  - Current political tensions derived from history

**FR-30**: History stored as list of `HistoryEvent`:
```python
@dataclass
class HistoryEvent:
    year: int           # -500 to 0 (0 = campaign start)
    event_type: str     # "war", "founding", "catastrophe", "betrayal"
    name: str           # "The War of Broken Crowns"
    factions: list[str] # ["harbor_town", "iron_kingdom"]
    outcome: str        # "harbor_town victory, iron_kingdom collapsed"
    consequences: dict  # {"iron_kingdom": "destroyed", "harbor_town": "trade_monopoly"}
```

**FR-31**: NPCs auto-populate `known_facts` from history based on age/role/faction
**FR-32**: LLM context includes relevant history when player asks about past

### Acceptance Criteria
- AC-20: Each campaign generates unique but consistent history from seed
- AC-21: Innkeeper mentions "The War of Broken Crowns" when asked about town history
- AC-22: Old NPCs know more history than young NPCs

---

## Module 8: Recipe-Based Economy

### Purpose
Prices change because supply chains exist, not because a script says so. Blacksmith needs iron + coal → no iron → no weapons → prices rise.

### Functional Requirements

**FR-33**: Production recipes:
```python
RECIPES = {
    "iron_bar": {"inputs": {"iron_ore": 1, "coal": 1}, "producer": "smelter", "time": 2},
    "steel_bar": {"inputs": {"iron_bar": 1, "coal": 2, "flux": 1}, "producer": "smelter", "time": 4},
    "iron_sword": {"inputs": {"iron_bar": 2}, "producer": "blacksmith", "time": 3},
    "steel_sword": {"inputs": {"steel_bar": 2}, "producer": "blacksmith", "time": 5},
    "ale": {"inputs": {"grain": 2, "water": 1, "yeast": 1}, "producer": "brewer", "time": 8},
    "bread": {"inputs": {"grain": 1, "water": 1}, "producer": "baker", "time": 1},
    "healing_potion": {"inputs": {"herbs": 2, "water": 1}, "producer": "alchemist", "time": 4},
}
```

**FR-34**: Location stock tracks quantities: `{"iron_ore": 50, "coal": 30, "ale": 20}`
**FR-35**: Producers consume inputs and produce outputs per tick
**FR-36**: Scarcity → price modifier: stock < 20% of normal → price × 2.0
**FR-37**: Oversupply → price drop: stock > 150% of normal → price × 0.7
**FR-38**: Caravans arrive periodically, restocking raw materials

### Acceptance Criteria
- AC-23: Blacksmith can't make swords if iron_ore = 0
- AC-24: Ale price doubles when tavern stock is low
- AC-25: Caravan arrival drops raw material prices

---

## Module 9: Procedural Naming

### Purpose
NPC names generated from faction-specific word banks. Low effort, high flavor.

### Functional Requirements

**FR-39**: Name generation per faction:
```python
NAME_BANKS = {
    "human": {
        "first_male": ["Aldric", "Bram", "Cedric", "Dorn", "Erik"],
        "first_female": ["Ada", "Bree", "Cara", "Dara", "Elena"],
        "surnames": ["Blackwood", "Ironside", "Stormborn", "Ashford", "Holloway"],
    },
    "dwarf": {
        "prefix": ["Dur", "Gim", "Thor", "Bor", "Kaz"],
        "suffix": ["in", "ek", "grim", "dal", "rok"],
        "clan": ["Ironforge", "Deepdelve", "Stonefist", "Coalbeard"],
    },
    "elf": {
        "prefix": ["Ael", "Thi", "Lor", "Cel", "Gal"],
        "suffix": ["andir", "wen", "thiel", "dris", "orn"],
        "house": ["Starweave", "Moonpetal", "Dawnwhisper"],
    },
}
```

**FR-40**: `generate_name(faction, gender)` produces unique name
**FR-41**: Names cached per session — same NPC always has same name

### Acceptance Criteria
- AC-26: No two NPCs in same session have identical names
- AC-27: Dwarf names sound dwarven, elf names sound elven

---

## Module 10: Proximity Rules

### Purpose
Player can only interact with nearby entities. No examining things across the map.

### Functional Requirements

**FR-42**: Interaction ranges:
  - `talk/examine/trade/pickup`: distance ≤ 1 tile
  - `attack (melee)`: distance ≤ 1 tile
  - `attack (ranged)`: distance ≤ 5 tiles, line of sight required
  - `shout/yell`: distance ≤ 3 tiles (all NPCs in range hear)
  - `look`: unlimited range, but detail decreases with distance

**FR-43**: `move to X,Y` via click: pathfind using A*, max 5 tiles per turn
**FR-44**: Arrow key move: always 1 tile in direction, blocked by walls
**FR-45**: Out of range action → "You're too far away. Move closer."

### Acceptance Criteria
- AC-28: "talk merchant" fails if merchant is >1 tile away
- AC-29: Click on tile 10 tiles away → player walks 5 tiles toward it
- AC-30: Arrow key into wall → "You can't go that way"

---

## Implementation Priority

| Phase | Modules | Estimated Effort | Impact |
|-------|---------|-----------------|--------|
| Sprint 1 | 10 (Proximity) + 3 (Schedules) + 9 (Naming) | 2 days | "World has rules" |
| Sprint 2 | 1 (Tick Scheduler) + 2 (Needs) | 3 days | "World breathes" |
| Sprint 3 | 6 (Ethics) + 7 (History Seed) | 2 days | "World has depth" |
| Sprint 4 | 4 (Materials) + 5 (Body Parts) | 2 days | "Combat has weight" |
| Sprint 5 | 8 (Economy) | 3 days | "World has trade" |

---

## Architecture Note

ALL modules are deterministic. Zero AI/LLM calls. LLM only receives state as context:
```
"The merchant Bram Ironside is in the market_square zone.
His needs: sustenance=20 (hungry), commerce=80 (satisfied).
Emotional state: slightly irritable.
He knows: The War of Broken Crowns (his grandfather fought).
Current stock: iron_sword x2, steel_sword x0 (out of steel).
Ethics: theft=crime, trade=valued."
```
LLM reads this and produces: "Bram eyes you with a thin smile, rubbing his empty belly. 'Looking to buy? I've iron blades — good enough for the likes of you. Steel? Hah. Not since the quarry dried up.'"
