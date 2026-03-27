# PRD: Procedural World Generation v2
## DF/Rimworld-Quality Town & World Generation

### Current Problems
1. Buildings are doorless rectangles — no entrances
2. Roads are rigid grid lines every 10 tiles — no organic layout
3. NPCs spawn randomly, not linked to buildings (blacksmith not in forge)
4. No furniture/workstations inside buildings
5. No terrain variety (grass, dirt, garden, well, fountain)
6. Right edge of map is broken (wall artifacts)
7. Click selection doesn't highlight entities
8. Click-to-move teleports instead of walking
9. 48x48 is the entire world — no multi-scale maps

---

## Architecture: Multi-Scale World

### Scale 1: World Map (not implemented yet — future)
- 64x64 tiles, each tile = one region
- Biomes: forest, plains, mountains, coast, desert
- Cities, villages, roads between them
- Player navigates between regions

### Scale 2: Region/Town Map (THIS SPRINT — 80x60)
- One playable area: a town, dungeon, or wilderness
- Real architecture with rooms, doors, furniture
- NPCs live in specific buildings
- Roads connect buildings organically

### Scale 3: Building Interior (auto-generated from building type)
- Player can enter buildings through doors
- Each building type has a template layout

---

## Town Generation Algorithm

### Phase 1: Terrain Base
```
1. Fill map with grass
2. Place terrain features:
   - River (random curve across map, 2-3 tiles wide)
   - Hills (elevation patches, rough terrain)
   - Trees scattered on grass areas
3. Place main road: entrance → town center → exit
4. Branch roads from main road to building plots
```

### Phase 2: Building Placement
```
For each building type needed:
1. Find plot along a road (adjacent to road tile)
2. Generate building from template:
   - Outer walls
   - Door facing road (CRITICAL — always has entrance)
   - Interior floor
   - Windows (optional visual)
3. Place furniture inside based on building type
4. Register building → NPC link
```

### Building Templates (data-driven from JSON)
```json
{
  "blacksmith": {
    "min_size": [6, 5],
    "max_size": [8, 7],
    "required_furniture": ["forge", "anvil", "workbench"],
    "optional_furniture": ["weapon_rack", "barrel"],
    "npc_roles": ["blacksmith"],
    "npc_position": "near_forge"
  },
  "tavern": {
    "min_size": [8, 6],
    "max_size": [12, 10],
    "required_furniture": ["bar_counter", "table", "table", "chair", "chair", "fireplace"],
    "optional_furniture": ["barrel", "bookshelf"],
    "npc_roles": ["innkeeper", "bard"],
    "npc_position": "behind_counter"
  },
  "market_stall": {
    "min_size": [4, 3],
    "max_size": [6, 4],
    "required_furniture": ["counter", "crate"],
    "npc_roles": ["merchant"],
    "npc_position": "behind_counter"
  },
  "temple": {
    "min_size": [7, 6],
    "max_size": [10, 8],
    "required_furniture": ["altar", "pew", "pew", "candelabra"],
    "npc_roles": ["priest"],
    "npc_position": "near_altar"
  },
  "guard_post": {
    "min_size": [4, 4],
    "max_size": [6, 5],
    "required_furniture": ["weapon_rack", "chest"],
    "npc_roles": ["guard", "guard"],
    "npc_position": "near_door"
  },
  "house": {
    "min_size": [4, 4],
    "max_size": [7, 6],
    "required_furniture": ["bed", "table", "chair"],
    "optional_furniture": ["chest", "bookshelf"],
    "npc_roles": ["beggar"],
    "npc_position": "inside"
  }
}
```

### Phase 3: Road Network
```
1. Define town center (center of map)
2. Place town square (open area with well/fountain)
3. Main road: map edge → town center → opposite edge
4. Side roads branch to each building plot
5. Roads are 2 tiles wide (cobblestone)
6. Paths are 1 tile wide (dirt) for alleys
```

### Phase 4: NPC Placement
```
For each building:
1. Get NPC roles from building template
2. Generate NPC with procedural name
3. Place NPC INSIDE their building (near specified furniture)
4. Set NPC home_building = building_id
5. NPC schedules reference their building
```

### Phase 5: Detail Pass
```
1. Scatter decorative entities: barrels, crates, lamp posts
2. Place wells/fountains in town square
3. Add garden patches near houses
4. Place trees along roads
5. Add town entrance gate
```

---

## Godot Client Fixes (Same Sprint)

### Click Selection
- Click on entity → highlight border around tile
- Show entity name/role tooltip
- Click on NPC → auto-approach and open talk
- Click on item → auto-approach and pickup prompt
- Click on empty tile → pathfind walk (not teleport)

### Pathfind Walking
- Click-to-move should animate step by step
- Show path preview (dotted line)
- Each step costs AP and ticks world
- Camera follows smoothly

### Entity Visibility
- NPCs: colored sprites by role (merchant=gold, guard=red, priest=white)
- Furniture: distinct sprites (anvil, barrel, table, bed)
- Items on ground: small icon
- Doors: visually distinct from walls
- Trees: green sprites

---

## Data Files Needed

### `data/building_templates.json`
All building types with size, furniture, NPC roles.

### `data/furniture.json`
All furniture types with sprites, blocking, interaction type.

### `data/terrain_features.json`
Biome elements: trees, rocks, water, bridges.

---

## Implementation Sprints

### Sprint 1: Town Generator Rewrite
- New TownGenerator with road network + building templates
- Buildings have doors
- Furniture placed inside buildings
- NPCs linked to buildings
- 80x60 map size
- Tests: building connectivity, NPC placement, door existence

### Sprint 2: Godot Map Rendering
- Terrain tiles render correctly (grass, road, cobblestone, water)
- Building walls/floors/doors visually distinct
- Furniture sprites visible
- NPC sprites colored by role
- Camera smooth follow

### Sprint 3: Click Interaction
- Click entity → highlight + tooltip
- Click NPC → approach + talk
- Click empty tile → pathfind walk (animated, not teleport)
- Click item → approach + pickup
- Path preview line

### Sprint 4: Detail & Polish
- Town square with well/fountain
- Trees, gardens, decorative barrels
- Lamp posts along roads
- Town gate at map edge
- NPC schedules reference their buildings
- 500-turn visual chaos test
