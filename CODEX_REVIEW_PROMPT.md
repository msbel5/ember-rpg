# Ember RPG — Code Review Request

## Project Overview
Ember RPG is a text-based RPG with a living world simulation, inspired by Dwarf Fortress and Rimworld. It features a top-down ASCII view, d20 skill checks, crafting, NPC behavior trees, and AI-narrated dungeon mastering.

**Tech stack:** Python 3.10+, FastAPI, Rich terminal UI, pytest
**Test count:** 1716 passing tests
**Run tests:** `cd frp-backend && python -m pytest tests/ -q`
**Play the game:** `cd frp-backend && python -m tools.play_topdown`

## What to Review

### Core Engine (Priority: HIGH)
Review these files for bugs, logic errors, edge cases, and code quality:

1. **`frp-backend/engine/api/game_engine.py`** (~2200 lines) — Main orchestrator
   - `process_action()` routes 31+ intents to handlers
   - Each handler uses d20 skill checks, AP deduction, proximity checks
   - `_world_tick()` runs NPC behavior trees, need decay, caravans, rumors
   - `_populate_scene_entities()` creates Entity objects with SpatialIndex
   - **Check for:** null dereferences, missing error handling, logic bugs in combat/skill checks

2. **`frp-backend/engine/api/game_session.py`** (~210 lines) — Session state container
   - `__post_init__` generates 48x48 town map, SpatialIndex, Viewport, player Entity
   - **Check for:** initialization order dependencies, missing defaults

3. **`frp-backend/engine/api/save_system.py`** (~450 lines) — Save/Load
   - Serializes ALL session state to JSON, reconstructs via `from_dict()`
   - Uses `object.__new__(GameSession)` to bypass `__post_init__`
   - **Check for:** data loss on roundtrip, missing fields, corruption handling

4. **`frp-backend/engine/api/action_parser.py`** (~500 lines) — NLP intent parser
   - 37 ActionIntent enum values with regex + keyword fallback
   - Supports English and Turkish
   - **Check for:** conflicting regex patterns, missed intents, false positives

### World Simulation Modules (Priority: MEDIUM)
These are in `frp-backend/engine/world/`:

5. **`entity.py`** — Entity dataclass (NPC/creature/item/building/furniture)
6. **`spatial_index.py`** — O(1) grid-based entity lookup
7. **`viewport.py`** — Camera + shadow-casting FOV
8. **`behavior_tree.py`** — Priority/Sequence NPC AI (flee/combat/needs/schedule/patrol/wander)
9. **`skill_checks.py`** — d20 system with 6 abilities, contested checks
10. **`action_points.py`** — Class-based AP pools, armor penalties
11. **`crafting.py`** — 51 recipes, 5 disciplines, quality tiers (RUINED→MASTERWORK)
12. **`interactions.py`** — 85+ context-sensitive rules, 31 interaction types

### Terminal Client (Priority: MEDIUM)
13. **`frp-backend/tools/play_topdown.py`** (~793 lines) — Top-down ASCII renderer
    - Rich Layout split: map viewport + narrative panel + nearby panel
    - Arrow key movement via readchar
    - **Check for:** rendering bugs, input handling edge cases

### Tests (Priority: LOW — verify coverage)
14. **`frp-backend/tests/test_playtest_derail.py`** — 29 integration scenarios
15. **`frp-backend/tests/test_save_system.py`** — 46 save/load roundtrip tests

## Specific Review Questions

1. **Are there any null/None dereference risks** in game_engine.py handlers? (session.spatial_index, session.ap_tracker, session.map_data can be None)

2. **Is the combat system balanced?** Check `_execute_attack_round()` for:
   - Body part hit locations + armor reduction
   - Enemy counterattack logic
   - Guard backup spawning
   - XP rewards

3. **Are skill check DCs reasonable?** Most are DC 10-15. Check the full list in handlers.

4. **Is the crafting system complete?** Does `_handle_craft()` properly:
   - Find recipes by name
   - Check workstation proximity
   - Consume ingredients
   - Award quality-tiered products

5. **Does save/load preserve ALL state?** Especially:
   - Spatial index entities (positions)
   - Fog of war (explored tiles)
   - NPC needs states
   - Quest deadlines
   - Equipment slots

6. **Are there any infinite loops or performance issues?** Check:
   - `_world_tick()` behavior tree execution
   - `compute_fov()` shadow casting
   - `_find_walkable_near()` search loop

7. **Is the action parser robust?** Does it handle:
   - Empty input
   - Very long input
   - Special characters
   - Turkish input
   - Ambiguous commands ("mine" vs "examine")

8. **Code quality issues:**
   - Duplicated logic
   - Functions that are too long (>50 lines)
   - Missing docstrings
   - Type annotation gaps
   - Magic numbers

## Expected Output
Please provide:
1. **Critical bugs** (will crash or corrupt data) — with file:line
2. **Logic errors** (wrong behavior) — with file:line and explanation
3. **Edge cases** not handled — with scenario description
4. **Code quality issues** — grouped by severity
5. **Suggested improvements** — ordered by impact

## How to Run
```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q          # All 1716 tests
python -m pytest tests/ -q -k playtest  # Just play-tests
python -m tools.play_topdown        # Play the game
```
