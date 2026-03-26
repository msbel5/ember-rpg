# Ember RPG — Final Review, Fix & Play Prompt

## Current State
- **1884 tests passing** (1 flaky chaos test, non-blocking)
- game_engine.py refactored into 8 mixin files (~700 lines each)
- Data-driven: classes loaded from `data/classes.json`
- D&D systems implemented: proficiency, passive checks, advantage/disadvantage, 15 conditions, exhaustion, short/long rest, NPC attitudes, social DCs, conversation targets, THINK intent, initiative, death saves, opportunity attacks, disengage, alignment

## Known Bugs to Fix

### BUG 1: CRITICAL — Approach doesn't get close enough for interaction
`approach merchant` walks to NPC but often stops 2 tiles away. Then `talk to merchant` says "too far away". The approach path-walker (`_handle_go_to` in `exploration_handlers.py`) stops when `distance(step_pos, target_pos) <= 1` but this checks NEXT step, not final position. It should walk until the PLAYER is within 1 tile of the TARGET.

**Fix:** After approach, if player is still >1 tile from target, continue walking until adjacent (Manhattan distance <= 1).

### BUG 2: HIGH — Bribe/social commands fail proximity when NPC is nearby but not adjacent
`bribe merchant 5 gold` returns "There's no clear person here to bribe" even when merchant is 2-3 tiles away. Social commands should work within conversation range (2 tiles), not just melee range (1 tile).

**Fix:** Social handlers (bribe, persuade, intimidate, deceive) should use a range of 2 tiles, not 1.

### BUG 3: MEDIUM — NPC movement can break approach mid-action
After `approach merchant`, the world tick runs and NPC may move away. Player arrives at NPC's old position but NPC is gone.

**Fix:** Lock NPC position during approach action, or re-check distance after approach and auto-adjust.

### BUG 4: MEDIUM — Spawn point sometimes surrounded by walls
48x48 map gen sometimes places spawn inside a room with no open exits nearby. Player can't move at all.

**Fix:** After map generation, verify spawn point has at least 2 walkable adjacent tiles. If not, find the nearest open area and relocate spawn.

### BUG 5: LOW — Flaky chaos session test
`test_chaos_session.py::test_seeded_100_turn_chaos_session` passes alone but fails in full suite. Likely seed/state bleed between tests.

**Fix:** Ensure chaos test creates a completely isolated session with explicit seed.

## Data-Driven Architecture Requirement

**NO HARDCODED DATA.** Everything must come from JSON files in `data/`:
- `data/classes.json` — class definitions (AP, skills, equipment, abilities) ✅ Done
- `data/items.json` — all items (already exists but not fully wired)
- `data/monsters.json` — all enemies (already exists but combat_handlers uses hardcoded list)
- `data/npc_templates.json` — NPC roles and behaviors
- `data/spells.json` — all spells
- `data/recipes.json` — crafting recipes (currently hardcoded in crafting.py)
- `data/locations.json` — NEW: location definitions, hidden features, NPC spawn rules

Use `engine/data_loader.py` as the single import point. Adding a new class, item, enemy, or location should require ZERO code changes — only JSON edits.

The game must be genre-agnostic: medieval fantasy today, space adventure tomorrow. Hardcoded "iron_sword" in Python code prevents this.

## What to Do

1. **Fix all 5 bugs above** — approach, social range, spawn, flaky test
2. **Complete data-driven migration:**
   - Wire `data/monsters.json` into `combat_handlers._spawn_enemy()` instead of hardcoded enemy list
   - Wire `data/items.json` into item lookups
   - Move crafting recipes from `crafting.py` constants to `data/recipes.json`
   - Move NPC role production from `ROLE_PRODUCTION` dict in `game_engine.py` to `data/npc_templates.json`
3. **Play-test 100 turns** programmatically and fix every bug found
4. **Commit and push after each fix batch**

## Play-Test Requirements

The 100-turn session must cover:
- Explore and approach every NPC (**verify approach works**)
- Talk, persuade, bribe, deceive, intimidate (**verify social range**)
- THINK about various topics (History, Arcana, Religion)
- Combat: attack, disengage, flee, death saves
- Short rest, long rest
- Craft something
- Accept quest, complete quest, turn in quest
- Save and load (**verify state preserved**)
- Steal from merchant (**verify crime consequences**)
- Check passive Perception reveals
- Check alignment shifts

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q          # 1884 tests
python -m tools.play_topdown        # Play interactively
```

## Attitude

Fix bugs first. Then data-driven migration. Then play-test. Ship a game that works from turn 1. No "too far away" on the first NPC interaction. No walls trapping the player. A game where approach → talk → quest → adventure flows naturally.
