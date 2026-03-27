# PRD: Living World Simulation — Complete System
## "DM narration olmadan bile oynanabilir" seviyesinde simülasyon

---

## Felsefe

Rimworld'de "Play" tuşuna basarsın, dünya yaşamaya başlar. NPC'ler yemek yer, uyur, çalışır, birbiriyle konuşur, kavga eder. Oyuncu müdahale etmese bile dünya değişir. Bizim oyun da böyle olmalı.

**Kural:** DM narration SADECE süslemedir. Altındaki simülasyon deterministik ve tutarlıdır. DM çıkarılsa bile oyun çalışır.

---

## Sprint Planı (Öncelik Sırasına Göre)

### Sprint 1: Data Catalog Expansion (JSON only, no code)
Yeni/genişletilmiş JSON dosyaları. Hiçbir Python kodu değişmez.

#### `data/biomes.json`
```json
{
  "biomes": {
    "temperate_forest": {
      "name": "Temperate Forest",
      "terrain_weights": {"grass": 40, "tree": 30, "bush": 10, "dirt": 10, "rock": 5, "water": 5},
      "animals": ["deer", "rabbit", "wolf", "bear", "fox", "boar"],
      "resources": ["wood", "herbs", "berries", "mushrooms"],
      "temperature_range": [5, 25],
      "rainfall": "moderate"
    },
    "plains": { ... },
    "mountain": { ... },
    "coast": { ... },
    "desert": { ... },
    "swamp": { ... }
  }
}
```

#### `data/building_templates.json` (detailed)
Each building: size range, wall material, required/optional furniture, NPC roles, door count, window count.

#### `data/furniture.json`
30+ furniture types: forge, anvil, workbench, altar, pew, bed, table, chair, barrel, crate, chest, bookshelf, weapon_rack, bar_counter, fireplace, oven, loom, tanning_rack, well, fountain, lamp_post, hitching_post, trough, cauldron, lectern, throne, jail_cell, stocks.

Each with: sprite_id, blocking (bool), interaction_type, tile_size.

#### `data/animals.json`
Domestic: chicken, cow, horse, donkey, dog, cat, pig, sheep, goat.
Wild: deer, rabbit, fox, wolf, bear, boar, eagle, snake, rat.
Each with: hp, speed, behavior (passive/aggressive/flee), drops (meat, hide, feather), tameable.

#### `data/factions.json`
Crown, Merchant Guild, Thieves Guild, Church, Mages Circle, Farmers Union.
Each with: alignment, allies, enemies, controlled buildings, taxes, laws.

### Sprint 2: Town Generator Rewrite
Complete rewrite of `engine/map/__init__.py` TownGenerator.

Algorithm:
1. **Place terrain** — biome determines base tiles
2. **Carve main road** — from edge to center, curves naturally (not straight)
3. **Place town square** — well/fountain, open area
4. **Plot building lots** — along roads, variable sizes
5. **Generate buildings** — from templates, with doors facing roads, furniture inside
6. **Branch roads** — connect buildings to main road
7. **Detail pass** — trees, gardens, barrels, lamp posts
8. **NPC placement** — each NPC in their building, with schedule

Output: 80x60 map where every building has doors, every NPC has a home, every road connects.

### Sprint 3: NPC Life Simulation
NPCs live independently:
- **Schedule**: wake up → go to work → lunch at tavern → back to work → evening at tavern → sleep at home
- **Needs**: hunger, thirst, rest, social, safety (already exists, needs wiring)
- **Movement**: A* pathfinding between schedule locations, visible on map
- **Relationships**: like/dislike other NPCs based on faction, past interactions
- **Economy**: merchants buy/sell based on stock, prices change with supply/demand (already partially exists)
- **Animals**: wander in biome-appropriate areas, flee from combat, can be hunted

### Sprint 4: World Events (tick-driven)
- **Caravan arrives** — new goods, prices drop (exists, needs visual)
- **Crime report** — guard investigates, witnesses talk
- **Weather** — rain reduces visibility, cold increases fire need
- **Night/Day** — torches matter, some NPCs sleep, thieves active
- **Random encounter** — wolves attack farms, bandits on roads
- **Festival/Market day** — NPCs gather, special prices

### Sprint 5: Godot Rendering
- All new tile types render with 16x16 sprites
- Furniture sprites distinct and recognizable
- NPCs have role-colored sprites
- Animals have unique sprites
- Doors visually distinct (openable)
- Day/night lighting
- Weather particles (rain, snow)

### Sprint 6: Click & Interact
- Click entity → highlight, tooltip, context menu
- Click NPC → approach + talk options
- Click furniture → use (forge → craft, bed → rest, chair → sit)
- Click animal → approach (hunt/pet/ride depending on type)
- Click door → open/close
- Click ground item → pickup
- Pathfind walk animation (not teleport)

---

## What "Complete Simulation" Means

When player presses start:
1. World seed generates entire town
2. Every building placed with correct architecture
3. Every NPC spawned in their home/workplace
4. Every animal in their habitat
5. Clock starts ticking
6. NPCs begin their schedules (go to work, eat, socialize)
7. Economy starts (merchants stock up, prices set)
8. **Player hasn't done anything yet — world is already alive**

When player does nothing for 100 turns:
- NPCs have moved between buildings
- At least one caravan has arrived
- Prices have changed
- NPCs have had conversations (eavesdroppable)
- Night has fallen, torches lit
- Some animals have wandered

THIS is what makes it feel like Dwarf Fortress.

---

## File Count Targets

| Category | Current | Target |
|----------|---------|--------|
| Biomes | 0 | 6 |
| Building templates | 7 basic | 15 detailed |
| Furniture types | 0 | 30 |
| Animal types | 7 | 20 |
| Faction definitions | 0 | 6 |
| NPC schedules | rudimentary | per-role detailed |
| Terrain tile types | 5 | 15 |
| Total items | 198 | 250+ |
| Monster types | 37 | 50+ |
| Crafting recipes | 55 | 80+ |
