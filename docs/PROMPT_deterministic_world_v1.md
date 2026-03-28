# Codex Prompt: Deterministic World Engine — Phase 1

You are building the deterministic core of Ember RPG. The game must work WITHOUT any LLM calls. AI enrichment comes later as an optional layer.

## Design Philosophy

Think Daggerfall + Dwarf Fortress + RimWorld + Zork + Bard's Tale.

The world is generated algorithmically from a seed. Every playthrough creates a unique but internally consistent world. NPCs have schedules, economies tick, quests trigger from world state, combat resolves with dice. Zero LLM dependency for core gameplay.

Later phases will add:
- DM AI interface (narration enrichment via API hooks)
- NPC AI sessions (each NPC gets a persistent LLM session for conversation)
- World description AI (sensory prose layer)

But those are HOOKS, not the engine. The engine is deterministic.

## Current State

- Backend: FastAPI at `frp-backend/`, 1700+ tests, 96% coverage
- Client: Godot 4.6 at `godot-client/`, 183 headless tests, tab-based sidebar
- Campaign-first API: `/game/campaigns/{id}/commands`
- Content adapters: `fantasy_ember`, `scifi_frontier`
- Current world gen: basic grid map with hardcoded tile types — NOT adequate

## What Needs to Change

### Sprint 1: Deterministic World Seed System

Create `frp-backend/engine/worldgen/` module:

1. **`world_seed.py`** — Master seed that deterministically derives all sub-seeds
   ```python
   class WorldSeed:
       def __init__(self, seed: int | str):
           # Convert string seeds to int via hash
           # Derive sub-seeds: terrain_seed, settlement_seed, npc_seed, quest_seed, economy_seed
       def terrain_seed(self) -> int: ...
       def settlement_seed(self) -> int: ...
       def npc_seed(self) -> int: ...
   ```

2. **`terrain_generator.py`** — Procedural terrain using noise
   - Use simplex/perlin noise (pure Python, no heavy deps — `opensimplex` is fine)
   - Generate heightmap → biome assignment → tile placement
   - Biomes: forest, plains, mountain, coast, desert, swamp (minimum 6)
   - Each biome has: terrain weights, temperature range, vegetation density, resource types
   - Output: 2D tile array with terrain type per cell
   - Map sizes: settlement (40x40), region (120x120), world (400x400)

3. **`settlement_generator.py`** — Organic town layout (NOT grid)
   - Main road as a spine (curved/angled, not straight)
   - Branch roads off the main road
   - Building plots placed along roads
   - Town square at center with well/fountain
   - Building types from templates: blacksmith, tavern, market_stall, temple, guard_post, house, town_hall, library, alchemist, bakery, stable, warehouse, jail
   - Each building has: size range, wall material, required furniture list, door facing road
   - Furniture placed inside buildings (forge in blacksmith, altar in temple, beds in houses)
   - Output: tile map + building list + furniture list + door positions

4. **`npc_generator.py`** — Deterministic NPC population
   - NPCs spawned per building (blacksmith NPC in blacksmith, priest in temple, etc.)
   - Each NPC has: name (generated from seed), role, schedule, home building, work building
   - Schedule: array of (hour, location, activity) tuples
   - Personality traits derived from seed (friendly/hostile/neutral, greedy/generous, etc.)
   - NPCs have inventory (items appropriate to their role)

5. **`quest_generator.py`** — Procedural quest templates
   - Quest types: fetch, kill, escort, deliver, investigate, defend
   - Quests generated from world state (if bandit camp exists → kill quest available)
   - Quest givers linked to NPCs
   - Rewards scaled to difficulty
   - Quest chains: completing one quest can unlock the next

### Sprint 2: World Tick System

6. **`world_tick.py`** — Simulation loop (runs every player action)
   - NPC movement: follow schedule (go to work, go home, go to tavern)
   - Economy tick: merchants restock, prices fluctuate based on supply/demand
   - Time advancement: day/night cycle, seasons
   - Event triggers: bandit raid if guard count low, plague if no healer, famine if no farms
   - Weather: deterministic from seed + day number

7. **`economy.py`** — Supply/demand model
   - Each settlement tracks resources: food, ore, wood, gold
   - Merchants buy/sell based on local supply
   - Trade routes between settlements affect prices
   - Scarcity drives quest generation

### Sprint 3: Integration with Existing Systems

8. Hook worldgen into campaign creation:
   - When player creates a campaign, generate world from seed
   - Store generated world state in campaign data
   - Settlement map replaces the current hardcoded map
   - NPCs from worldgen populate the entity list

9. Hook world tick into action processing:
   - Every `submit_campaign_command` triggers a world tick
   - NPC positions update based on schedule
   - Economy updates
   - Events check and trigger

10. Update Godot client to display generated world:
    - Tile map renders from worldgen output
    - NPCs appear at their scheduled positions
    - Buildings have doors and furniture
    - Day/night affects tile rendering (darken at night)

## Technical Constraints

- Pure Python, no heavy dependencies (opensimplex is OK, numpy is NOT)
- Raspberry Pi 5 friendly — 4GB RAM, no GPU
- Deterministic: same seed = same world, always
- Serializable: world state saves to JSON
- Testable: every generator has unit tests with fixed seeds

## Test Requirements

For each module, write tests FIRST (TDD):
- Fixed seed tests: `seed=42` always produces the same output
- Boundary tests: empty world, 1-tile world, max-size world
- Integration tests: worldgen → campaign creation → gameplay loop
- Performance tests: world generation completes in <5 seconds on Pi 5

## File Structure

```
frp-backend/engine/worldgen/
    __init__.py
    world_seed.py
    terrain_generator.py
    settlement_generator.py
    npc_generator.py
    quest_generator.py
    world_tick.py
    economy.py
    data/
        biomes.json
        building_templates.json
        furniture.json
        npc_templates.json
        quest_templates.json

frp-backend/tests/
    test_worldgen_seed.py
    test_worldgen_terrain.py
    test_worldgen_settlement.py
    test_worldgen_npc.py
    test_worldgen_quest.py
    test_worldgen_tick.py
    test_worldgen_economy.py
    test_worldgen_integration.py
```

## Data Catalog (Sprint 1 deliverable)

Create these JSON files in `frp-backend/engine/worldgen/data/`:

### biomes.json
```json
{
  "temperate_forest": {
    "terrain_weights": {"grass": 0.4, "dirt_path": 0.1, "stone_floor": 0.05, "water": 0.05, "wood_floor": 0.02},
    "trees": {"density": 0.3, "types": ["oak", "birch", "pine"]},
    "animals": ["deer", "rabbit", "fox", "wolf", "bear"],
    "resources": ["wood", "herbs", "mushrooms", "berries"],
    "temperature": {"min": -5, "max": 30},
    "humidity": 0.6
  }
  // ... 5 more biomes
}
```

### building_templates.json
15 building types with size range, wall material, required furniture + positions, NPC roles, door count.

### furniture.json
30+ furniture types with blocking, interaction_type, tile_size.

### npc_templates.json
Role-based templates: blacksmith, innkeeper, priest, guard, merchant, farmer, healer, mage, thief, noble, beggar, bard.

### quest_templates.json
Quest type templates with prerequisites, rewards, difficulty scaling.

## What NOT to Do

- Do NOT use LLM calls for world generation
- Do NOT use grid-based town layout (organic roads only)
- Do NOT break existing tests (28 backend + 183 Godot headless must pass)
- Do NOT add numpy, scipy, or other heavy deps
- Do NOT change the campaign API contract — extend, don't replace
- Do NOT touch Godot client code in Sprint 1 (backend only)

## Success Criteria

After Sprint 1:
- `python -m pytest frp-backend/tests/test_worldgen_*.py -v` all green
- `WorldSeed(42)` produces identical terrain, settlement, NPCs, quests every time
- Settlement map has organic roads, buildings with doors and furniture, NPCs inside
- Existing 28 backend tests still pass
- World generates in <5 seconds

After Sprint 2:
- World tick advances NPC positions every action
- Economy model tracks resources and adjusts prices
- Events trigger from world state conditions

After Sprint 3:
- Campaign creation uses worldgen
- Godot client renders generated world
- Player can walk through a generated town and interact with NPCs at their scheduled positions

Start with Sprint 1 only. Write tests first. Commit each module separately.
