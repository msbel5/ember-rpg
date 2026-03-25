# Ember RPG — Code Review & Implementation Request

## Project Overview

Ember RPG is a text-based RPG with a living world simulation, inspired by Dwarf Fortress, Rimworld, Elder Scrolls II: Daggerfall, Monkey Island, and The Hitchhiker's Guide to the Galaxy. It features a top-down ASCII view, d20 skill checks, crafting, NPC behavior trees, and AI-narrated dungeon mastering.

**Current state:** Top-down ASCII terminal client is playable. 16 living world modules built. 1716 tests passing.

**Long-term vision:** Terminal ASCII view -> Godot 2D client -> AI-generated sprite assets -> post-processed POV view. The terminal client is the foundation and it must be AAA quality before we move to Godot. You should review and understand every PRD and every *.md file so you can understand our progress and vision shifts over time. After review you will implement all necessary functions and code and we will do this review again. We are aiming for top-down ASCII view in terminal first for easy testing. After our game quality is AAA level we will implement the Godot client as a new renderer. After we have a playable complete game, the top-down view can be easily rendered in 3D then from POV angle with AI-generated simple assets placed. This view will be post-processed with AI again and presented to the user for a point-and-click game feel, keeping both "The Hitchhiker's Guide to the Galaxy BBC 30th edition" and "Monkey Island" soul intact. Every asset and post-process image will be cached to keep API requests minimum. In general, the game should be playable like Elder Scrolls 2: Daggerfall. Then we will decide how to present the game to the user.

After you read and understand our vision you should do your own research. Track and find best mechanics, find what we have missing, make an implementation plan, then create/update PRDs, READMEs, roadmap, and write a new GDD or update the existing one.

**Tech stack:** Python 3.10+, FastAPI, Rich terminal UI, pytest
**Test count:** 1716 passing tests
**Run tests:** `cd frp-backend && python -m pytest tests/ -q`
**Play the game:** `cd frp-backend && python -m tools.play_topdown`

## Your Mission

You are not just reviewing — you are **implementing**. The workflow is:

1. **Read ALL `.md` files** (PRDs, ROADMAP, README, this file) to understand the full vision and history
2. **Review every source file** listed below for bugs, logic errors, edge cases
3. **Create an implementation plan** for everything that's missing or broken
4. **Update/create PRDs, GDD, ROADMAP** as needed
5. **Implement all fixes and missing features**
6. **Run `python -m pytest tests/ -q` and ensure ALL tests pass** (add new tests for new code)
7. **Play-test the game** via `python -m tools.play_topdown` — experience it as a player
8. **Commit and push** your changes
9. **Do this review cycle again** — review your own work, fix issues, iterate until AAA

## What to Review & Implement

### Core Engine (Priority: CRITICAL)

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

### World Simulation Modules (Priority: HIGH)
All in `frp-backend/engine/world/`:

5. **`entity.py`** — Entity dataclass (NPC/creature/item/building/furniture)
6. **`spatial_index.py`** — O(1) grid-based entity lookup
7. **`viewport.py`** — Camera + shadow-casting FOV
8. **`behavior_tree.py`** — Priority/Sequence NPC AI (flee/combat/needs/schedule/patrol/wander)
9. **`skill_checks.py`** — d20 system with 6 abilities, contested checks
10. **`action_points.py`** — Class-based AP pools, armor penalties
11. **`crafting.py`** — 51 recipes, 5 disciplines, quality tiers (RUINED to MASTERWORK)
12. **`interactions.py`** — 85+ context-sensitive rules, 31 interaction types
13. **`npc_needs.py`** — 5 needs (safety/commerce/social/sustenance/duty), emotional states
14. **`ethics.py`** — 6 factions, 8 action types, reputation system
15. **`economy.py`** — 10 recipes, LocationStock with scarcity pricing
16. **`rumors.py`** — RumorNetwork with propagation/decay
17. **`caravans.py`** — 3 caravan routes, tick-based arrivals, raiding
18. **`quest_timeout.py`** — Quest tracking with deadline/reminders
19. **`body_parts.py`** — d20 hit locations, per-part HP tracking, armor coverage
20. **`materials.py`** — 10 materials with density/hardness/value/damage multipliers

### Terminal Client (Priority: HIGH)
21. **`frp-backend/tools/play_topdown.py`** (~793 lines) — Top-down ASCII renderer
    - Rich Layout split: map viewport + narrative panel + nearby panel
    - Arrow key movement via readchar
    - **Check for:** rendering bugs, input handling edge cases, UX improvements

### Tests (Priority: MEDIUM — verify + expand coverage)
22. **`frp-backend/tests/test_playtest_derail.py`** — 29 integration scenarios
23. **`frp-backend/tests/test_save_system.py`** — 46 save/load roundtrip tests
24. All other test files in `frp-backend/tests/`

## Specific Review Questions

1. **Null/None dereference risks** in game_engine.py handlers? (session.spatial_index, session.ap_tracker, session.map_data can be None)

2. **Combat system balance:** Check `_execute_attack_round()` for:
   - Body part hit locations + armor reduction
   - Enemy counterattack logic
   - Guard backup spawning
   - XP rewards scaling

3. **Skill check DCs reasonable?** Most are DC 10-15. Check the full list in handlers.

4. **Crafting system complete?** Does `_handle_craft()` properly:
   - Find recipes by name
   - Check workstation proximity
   - Consume ingredients
   - Award quality-tiered products

5. **Save/load preserves ALL state?** Especially:
   - Spatial index entities (positions)
   - Fog of war (explored tiles)
   - NPC needs states
   - Quest deadlines
   - Equipment slots

6. **Infinite loops or performance issues?** Check:
   - `_world_tick()` behavior tree execution
   - `compute_fov()` shadow casting
   - `_find_walkable_near()` search loop

7. **Action parser robust?** Does it handle:
   - Empty input, very long input, special characters
   - Turkish input, English input
   - Ambiguous commands ("mine" vs "examine")

8. **Code quality:**
   - Duplicated logic
   - Functions too long (>50 lines)
   - Missing docstrings
   - Type annotation gaps
   - Magic numbers

## Gameplay Quality Requirements (AAA Standard)

These are NOT optional — the game must meet ALL of these:

1. **Living world consistency:** NPCs follow schedules, have needs, react to events. The world should feel alive even when the player does nothing.

2. **DM narration quality:** Even with less capable models (Haiku fallback), the DM must narrate logically and consistently. No random hidden passages in every corner — some places are dull, some are amazing, and it must be deterministic.

3. **Derailability:** When the player derails the campaign, the DM must adapt and the living world must react. The player should be able to do anything within the world rules — become mayor, start a business, derail a quest.

4. **NPC depth:** NPCs and factions must have consistent memory. Talking and interaction should be enjoyable. NPCs should remember past interactions.

5. **Crafting integration:** Crafting must work within the living economy. Scarcity pricing, material quality, workstation requirements.

6. **Quest completion:** Quests must finish with success OR failure properly. No hanging quests.

7. **Deterministic calculations:** All game mechanics (combat, skill checks, crafting) must be deterministic. The DM only narrates — it does not decide outcomes.

8. **Ambiguity resolution:** When the user speaks, properly resolve whether they're talking to an NPC, the DM, or themselves.

9. **World observability:** The living world should be observable from the player's perspective. NPC movements, caravan arrivals, rumors spreading — the player should see/hear about these.

10. **Enjoyability:** Is it enjoyable from the user's perspective? Game and narration should be consistent. User should be able to do whatever they want within the world, calculations should be deterministic and the DM just narrates.

## Expected Deliverables

After review AND implementation:

1. **Bug fixes** — all critical and logic bugs fixed
2. **Missing features implemented** — inventory, NPC dialogue depth, world observability
3. **Updated PRDs/GDD/ROADMAP** — reflecting current state and next steps
4. **New tests** — for all new code, maintaining 100% pass rate
5. **Polish** — UX improvements, better error messages, consistent formatting
6. **Implementation plan** — After the review you need to implement and finish the game
7. **Commit and push** — clean commits with descriptive messages

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q              # All tests
python -m pytest tests/ -q -k playtest  # Just play-tests
python -m tools.play_topdown            # Play the game
```
