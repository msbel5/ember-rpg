# Ember RPG — Code Review Request

## Project Overview

Ember RPG is a text-based RPG with a living world simulation, inspired by many games. It features a top-down ASCII view, d20 skill checks, crafting, NPC behavior trees, and AI-narrated dungeon mastering for now later we will implement POV view, details can be found in PRDs. You should review and understand every PRDs and every *.md files so you can understand our progress and shift in time. After review you will implement all neceesary functions and code and we will do this review again. We are going to aim top-down ASCII view in terminal, this is for ewasy testing for you and me, wo we can play it without GODOT client. After our game quality is AAA level we will implement GODOT client as new renderer and make sure its playable with godot too. After we have playable complete of the game this top down view can be easly rendered in 3D then from POV angle with ai generated simple assets placed, this view will be post processed with AI again and presented to user for point and click game feel both keeping `The Hitch hiker guides to the galaxy BBC 30th edition` and `monkey island` soul intact. Every asset and post procces image will be cached in order to keep api requests minimum.In general game will be should be playable like Elder Scrolls 2 Daggerfall. Then we will decide how we should present the game to User. So after you read and understand our vision you should do your own Resarch. Track find best mechanics and find what we have missing and make and implemantation plan then create/update PRDs, readmes, roadmap and write a new gdd or update the existing one. After your review you should implement everything and make game playable then make this review again.

__Tech stack:__ Python 3.10+, FastAPI, Rich terminal UI, pytest
__Test count:__ 1716 passing tests
__Run tests:__ `cd frp-backend && python -m pytest tests/ -q`
__Play the game:__ `cd frp-backend && python -m tools.play_topdown`

## What to Review

### Core Engine (Priority: HIGH)

Review these files for bugs, logic errors, edge cases, and code quality:

1. __`frp-backend/engine/api/game_engine.py`__ (~2200 lines) — Main orchestrator

   - `process_action()` routes 31+ intents to handlers
   - Each handler uses d20 skill checks, AP deduction, proximity checks
   - `_world_tick()` runs NPC behavior trees, need decay, caravans, rumors
   - `_populate_scene_entities()` creates Entity objects with SpatialIndex
   - **Check for:** null dereferences, missing error handling, logic bugs in combat/skill checks

2. __`frp-backend/engine/api/game_session.py`__ (~210 lines) — Session state container

   - `__post_init__` generates 48x48 town map, SpatialIndex, Viewport, player Entity
   - **Check for:** initialization order dependencies, missing defaults

3. __`frp-backend/engine/api/save_system.py`__ (~450 lines) — Save/Load

   - Serializes ALL session state to JSON, reconstructs via `from_dict()`
   - Uses `object.__new__(GameSession)` to bypass `__post_init__`
   - **Check for:** data loss on roundtrip, missing fields, corruption handling

4. __`frp-backend/engine/api/action_parser.py`__ (~500 lines) — NLP intent parser

   - 37 ActionIntent enum values with regex + keyword fallback
   - Supports English and Turkish
   - **Check for:** conflicting regex patterns, missed intents, false positives

### World Simulation Modules (Priority: MEDIUM)

These are in `frp-backend/engine/world/`:

5. **`entity.py`** — Entity dataclass (NPC/creature/item/building/furniture)
6. __`spatial_index.py`__ — O(1) grid-based entity lookup
7. **`viewport.py`** — Camera + shadow-casting FOV
8. __`behavior_tree.py`__ — Priority/Sequence NPC AI (flee/combat/needs/schedule/patrol/wander)
9. __`skill_checks.py`__ — d20 system with 6 abilities, contested checks
10. __`action_points.py`__ — Class-based AP pools, armor penalties
11. **`crafting.py`** — 51 recipes, 5 disciplines, quality tiers (RUINED→MASTERWORK)
12. **`interactions.py`** — 85+ context-sensitive rules, 31 interaction types

### Terminal Client (Priority: MEDIUM)

13. __`frp-backend/tools/play_topdown.py`__ (~793 lines) — Top-down ASCII renderer
   - Rich Layout split: map viewport + narrative panel + nearby panel
   - Arrow key movement via readchar
   - **Check for:** rendering bugs, input handling edge cases

### Tests (Priority: LOW — verify coverage)

14. __`frp-backend/tests/test_playtest_derail.py`__ — 29 integration scenarios
15. __`frp-backend/tests/test_save_system.py`__ — 46 save/load roundtrip tests

## Specific Review Questions

1. __Are there any null/None dereference risks__ in game_engine.py handlers? (session.spatial_index, session.ap_tracker, session.map_data can be None)
2. __Is the combat system balanced?__ Check `_execute_attack_round()` for:

   - Body part hit locations + armor reduction
   - Enemy counterattack logic
   - Guard backup spawning
   - XP rewards

3. **Are skill check DCs reasonable?** Most are DC 10-15. Check the full list in handlers.
4. __Is the crafting system complete?__ Does `_handle_craft()` properly:

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
   - English input
   - Ambiguous commands ("mine" vs "examine")

8. **Code quality issues:**

   - Duplicated logic
   - Functions that are too long (>50 lines)
   - Missing docstrings
   - Type annotation gaps
   - Magic numbers

9. **Game Play**

   - Is it enjoyable from user perspective
   - We have reachead rate limit and using less capable models like Haiku, but DM should nerrate the game logically
   - Game and narration should be consisted
   - When user derail the campaign Dm should adapt living world should react
   - Living world should be consistent and can be observable from user persepective
   - Talking and interaction should be enjoyable and consistent NPC`s and faction should have consistent memory
   - Crafting should be consisted and should be used in living world with proper economy
   - Quest should be finished with success or fail with properly
   - User should be able do whatever they want within our world, calculations should be deterministic and DM will just narrates.
   - DM should be proper not every corner have a hidden path, some places are just dull some places is awesome they should be consisted and deterministic
   - User may talk directly DM or some NPC or to themselves this ambiguity should be resolved properly

## Expected Output

Please provide:

1. **Critical bugs** (will crash or corrupt data) — with file:line
2. **Logic errors** (wrong behavior) — with file:line and explanation
3. **Edge cases** not handled — with scenario description
4. **Code quality issues** — grouped by severity
5. **Suggested improvements** — ordered by impact
6. **Implementation Plan** — After the review you need to implement and finish the game 

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q          # All 1716 tests
python -m pytest tests/ -q -k playtest  # Just play-tests
python -m tools.play_topdown        # Play the game

```
