# Codex Prompt: Deterministic World Engine — All Sprints

Do NOT stop until all sprints are complete, all tests pass, and visual QA is done.
If the build is broken, fix it. If tests fail, fix them. Loop until green.

---

## Design Philosophy

**Deterministic first, AI second.** Think Daggerfall + Dwarf Fortress + RimWorld + Zork + Bard's Tale.

The world is generated algorithmically from a seed. Every playthrough creates a unique but internally consistent world. NPCs have schedules, economies tick, quests trigger from world state, combat resolves with dice. Zero LLM dependency for core gameplay.

AI layers (DM narration, NPC conversation) come later as API hooks to ENRICH the deterministic simulation — not replace it.

## Current State

- Backend: FastAPI at `frp-backend/`, 1700+ tests, 96% coverage
- Client: Godot 4.6 at `godot-client/`, 183 headless tests, tab-based sidebar (Narrative/Hero/Town/Quests/Items/Map)
- Campaign-first API: `/game/campaigns/{id}/commands`
- Content adapters: `fantasy_ember`, `scifi_frontier`
- Automation bridge: headless Godot with JSON command/result protocol
- Video recording: `record_start`/`record_stop` commands capture PNG frames, stitch with `stitch_video.py`
- Current world gen: basic grid map with hardcoded tile types — NOT adequate

---

## Sprint 1: Deterministic World Seed + Generators

Create `frp-backend/engine/worldgen/` module:

### 1. `world_seed.py` — Master seed
```python
class WorldSeed:
    def __init__(self, seed: int | str):
        # Convert string seeds to int via hash
        # Derive sub-seeds for terrain, settlement, npc, quest, economy
    def terrain_seed(self) -> int: ...
    def settlement_seed(self) -> int: ...
    def npc_seed(self) -> int: ...
    def quest_seed(self) -> int: ...
    def economy_seed(self) -> int: ...
```

### 2. `terrain_generator.py` — Procedural terrain using noise
- Use `opensimplex` (pure Python, pip install opensimplex)
- Heightmap → biome assignment → tile placement
- 6 biomes minimum: forest, plains, mountain, coast, desert, swamp
- Each biome: terrain weights, temperature, vegetation density, resources
- Output: 2D tile array
- Sizes: settlement (40x40), region (120x120), world (400x400)

### 3. `settlement_generator.py` — Organic town layout
- Main road as curved spine (NOT grid, NOT straight)
- Branch roads off main road
- Building plots along roads
- Town square at center with well/fountain
- 13+ building types from templates (blacksmith, tavern, market_stall, temple, guard_post, house, town_hall, library, alchemist, bakery, stable, warehouse, jail)
- Each building: size range, wall material, furniture list, door facing road
- Furniture placed inside (forge in blacksmith, altar in temple, beds in houses)
- Output: tile map + building list + furniture list + door positions

### 4. `npc_generator.py` — NPC population
- NPCs spawned per building type (blacksmith in blacksmith, etc.)
- Name, role, schedule, home building, work building
- Schedule: `[(hour, building_id, activity), ...]`
- Personality traits from seed
- Inventory appropriate to role

### 5. `quest_generator.py` — Procedural quests
- Types: fetch, kill, escort, deliver, investigate, defend
- Generated from world state conditions
- Quest givers linked to NPCs
- Reward scaling, quest chains

### Data Catalog (create in `frp-backend/engine/worldgen/data/`):
- `biomes.json` — 6 biomes with terrain weights, animals, resources, temperature
- `building_templates.json` — 15 types with size, walls, furniture, NPC roles, doors
- `furniture.json` — 30+ types with blocking, interaction_type, tile_size
- `npc_templates.json` — 12+ roles with inventory, skills, dialogue tags
- `quest_templates.json` — 6+ types with prerequisites, rewards, difficulty

### Sprint 1 Tests
```bash
python -m pytest frp-backend/tests/test_worldgen_seed.py -v
python -m pytest frp-backend/tests/test_worldgen_terrain.py -v
python -m pytest frp-backend/tests/test_worldgen_settlement.py -v
python -m pytest frp-backend/tests/test_worldgen_npc.py -v
python -m pytest frp-backend/tests/test_worldgen_quest.py -v
```

### Sprint 1 Exit Criteria
- All worldgen tests green
- `WorldSeed(42)` produces identical output every time
- Settlement has organic roads, buildings with doors+furniture, NPCs inside
- Existing 28 backend tests still pass
- Generation completes in <5 seconds
- Commit and push

---

## Sprint 2: World Tick + Economy

### 6. `world_tick.py` — Simulation loop
- Runs every player action
- NPC movement: follow schedule (work→tavern→home)
- Time advancement: hour counter, day/night, seasons
- Event triggers: bandit raid (low guards), plague (no healer), famine (no farms)
- Weather: deterministic from seed + day number

### 7. `economy.py` — Supply/demand
- Settlement resource tracking: food, ore, wood, gold
- Merchant pricing from local supply
- Trade routes between settlements
- Scarcity drives quest generation

### Sprint 2 Tests
```bash
python -m pytest frp-backend/tests/test_worldgen_tick.py -v
python -m pytest frp-backend/tests/test_worldgen_economy.py -v
```

### Sprint 2 Exit Criteria
- World tick advances NPC positions every action
- Economy adjusts prices based on supply/demand
- Events trigger from world state
- All previous tests still pass
- Commit and push

---

## Sprint 3: Integration — Backend + Godot Client

### 8. Hook worldgen into campaign creation
- Campaign creation generates world from seed
- Store world state in campaign data (JSON serializable)
- Settlement map replaces hardcoded map
- NPCs from worldgen populate entity list
- Questionnaire seed flows into `WorldSeed`

### 9. Hook world tick into action processing
- Every `submit_campaign_command` triggers world tick
- NPC positions update per schedule
- Economy updates
- Events check and trigger

### 10. Update Godot client
- Tile map renders worldgen output (new tile types map to existing textures)
- NPCs appear at scheduled positions
- Buildings have doors and furniture visible on map
- Day/night darkens tiles at night
- Tab panels update: Town tab shows settlement info, Quests tab shows generated quests

### Sprint 3 Tests
```bash
python -m pytest frp-backend/tests/test_worldgen_integration.py -v
python -m pytest frp-backend/tests/test_campaign_creation_v2.py frp-backend/tests/test_campaign_api_v2.py frp-backend/tests/test_play.py frp-backend/tests/test_play_topdown.py -v
```

### Sprint 3 Godot Tests
```powershell
& 'C:\Tools\Scoop\apps\godot\current\godot.console.exe' --headless --path 'C:\Users\msbel\projects\ember-rpg\godot-client' --script res://tests/run_headless_tests.gd
```
Must be 183+ PASS, 0 FAIL.

### Sprint 3 Exit Criteria
- Campaign creation uses worldgen
- Client renders generated world with buildings, NPCs, furniture
- Player walks through town, sees NPCs at positions
- All tests pass (backend + Godot headless)
- Commit and push

---

## Sprint 4: Visual QA + Fix Loop

### Visual Verification
After Sprint 3, run visual QA:

1. Start backend:
```powershell
cd frp-backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

2. Run headless automation with recording:
```powershell
& 'C:\Tools\Scoop\apps\godot\current\godot.console.exe' --headless --path 'C:\Users\msbel\projects\ember-rpg\godot-client' --script res://tests/automation/godot/automation_bridge_runner.gd -- --scene res://scenes/game_session.tscn --command-file user://automation/command.json --result-file user://automation/result.json --status-file user://automation/status.json
```

3. Issue commands via JSON to play through 50+ turns:
   - Create campaign with seed
   - Move in all directions
   - Talk to NPCs
   - Check inventory
   - Enter buildings
   - Capture viewport screenshots every 5 turns

4. Use `record_start` command to capture continuous frames:
```json
{"seq": 1, "action": "record_start", "folder": "qa_recording", "interval": 1.0}
```

5. After 50+ turns, stop recording:
```json
{"seq": 99, "action": "record_stop"}
```

6. Stitch frames into video:
```powershell
python godot-client/tests/automation/stitch_video.py <frames_dir> qa_recording.mp4 --fps 2
```

### Fix Loop
After visual QA:
- Review screenshots for rendering bugs
- Check: buildings visible? Doors placed? NPCs inside? Furniture rendered?
- Check: organic roads (NOT grid)? Town square with well?
- If ANY visual issue found → fix → re-run tests → re-run visual QA → loop
- Do NOT stop until all visual checks pass

### Sprint 4 Exit Criteria
- 50+ turn play session recorded with screenshots
- Video stitched and saved to `tmp/visual_automation/`
- No rendering bugs in screenshots
- Buildings, doors, furniture, NPCs all visible and correctly placed
- Organic road layout confirmed (not grid)
- All tests still green
- Commit and push

---

## Technical Constraints

- Pure Python backend, no heavy deps (opensimplex is OK, numpy/scipy are NOT)
- Raspberry Pi 5 friendly — 4GB RAM, no GPU
- Deterministic: same seed = same world, always
- Serializable: world state saves to JSON (campaign save/load must work)
- No backwards compatibility needed — old PRDs are superseded
- No LLM calls in world generation
- Campaign API contract: extend, don't break

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

## What NOT to Do

- Do NOT use LLM calls for world generation
- Do NOT use grid-based town layout
- Do NOT break existing tests
- Do NOT add numpy, scipy, or heavy deps
- Do NOT change campaign API contract — extend only
- Do NOT mark anything done without running tests
- Do NOT stop if tests fail — fix and loop
- Do NOT skip visual QA

## Commit Strategy

Commit after each sprint:
1. `feat(worldgen): add seed system and terrain generator` (Sprint 1a)
2. `feat(worldgen): add settlement and NPC generators` (Sprint 1b)
3. `feat(worldgen): add quest generator and data catalog` (Sprint 1c)
4. `feat(worldgen): add world tick and economy` (Sprint 2)
5. `feat(worldgen): integrate with campaign and Godot client` (Sprint 3)
6. `fix(worldgen): visual QA fixes` (Sprint 4, as needed)

Push after each commit. Do not accumulate uncommitted changes.

## Final Acceptance

The build is DONE when:
1. `python -m pytest frp-backend/tests/ -q` — ALL green
2. Godot headless tests — 183+ PASS, 0 FAIL
3. `WorldSeed(42)` generates a town with organic roads, 10+ buildings, 10+ NPCs, 5+ quests
4. 50+ turn visual playthrough recorded with no rendering bugs
5. Video saved for human review

If any criterion fails, fix and loop. Do not stop.
