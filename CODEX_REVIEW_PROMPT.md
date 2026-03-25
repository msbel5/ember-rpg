# Ember RPG — Final Review, Gameplay Test & Polish Pass

## Who You Are

You are a senior gameplay engineer AND a veteran tabletop RPG player. You will first review the code for bugs, then play the game as a creative, chaotic player who tries to break everything. Your goal: make this game AAA quality.

## Project Vision

Ember RPG is a living-world text RPG inspired by Dwarf Fortress, Rimworld, Elder Scrolls II: Daggerfall, Monkey Island, and The Hitchhiker's Guide to the Galaxy.

**Core principle:** "AI doesn't decide, world lives by rules; AI only reads and narrates."

**Current state:** 1873 tests passing. Terminal client playable. All major systems integrated.

## Tech Stack

- Python 3.10+, FastAPI, Rich terminal UI, pytest
- `cd frp-backend && python -m pytest tests/ -q` — run all tests
- `cd frp-backend && python -m tools.play_topdown` — play the game

## Your Mission (3 Phases)

### Phase 1: Code Review (strict, senior-level)

Read these files and audit for bugs, regressions, state divergence:

**Critical files:**
- `engine/api/game_engine.py` (~3200 lines) — main orchestrator
- `engine/api/game_session.py` (~700 lines) — session state, PhysicalInventory
- `engine/api/save_system.py` (~620 lines) — save/load
- `engine/api/action_parser.py` (~600 lines) — intent parser (37+ intents, EN/TR)
- `engine/api/routes.py` — REST endpoints
- `engine/api/shop_routes.py` — shop buy/sell
- `engine/world/inventory.py` — RE4-style grid inventory
- `engine/world/matter_state.py` — SOLID/LIQUID/GAS/ETHEREAL
- `tools/play_topdown.py` — terminal renderer

**Review targets:**
1. Canonical state integrity — is GameSession truly single source of truth?
2. Save/load roundtrip — lossless for ALL state?
3. World tick accuracy — hourly systems, NPC movement, caravan timing
4. Combat/body/equipment/AP sync — damage applied once? body tracker matches HP?
5. Quest flow — accept/turn-in/deadline/failure all work?
6. Inventory discipline — no direct list mutation, no duplication
7. Parser — any conflicts between intents?
8. Terminal client — renders canonical state?

### Phase 2: Gameplay Test (the important part)

Play the game programmatically using `GameEngine` directly. This is NOT a unit test — this is a REAL play session as a creative tabletop RPG player.

**Create a test script** that plays a LONG session (50+ actions minimum). The character should:

**Act 1 — Arrival (explore, establish)**
- Create a rogue character
- Look around, learn the town layout
- Approach and talk to every NPC
- Check inventory, try equipping things
- Accept any available quests

**Act 2 — Economy (trade, craft, hoard)**
- Buy items from merchant
- Sell items
- Try crafting something
- Fill a waterskin if available
- Pour water between containers
- Stash something in a sock/boot
- Drop items, pick them up
- Test weight limits — try carrying too much

**Act 3 — Derail the Campaign (this is the real test)**
- Attack the merchant (not a goblin — a TOWN NPC)
- See if guards respond
- Try to flee from guards
- Attack the guard
- Try to steal
- Try to intimidate an NPC
- Try to bribe someone
- Pick a lock
- Try to enter restricted areas
- Do things the DM wouldn't expect

**Act 4 — Consequences**
- Check if reputation changed
- Talk to NPCs after committing crimes
- Are they hostile now?
- Try to rest after combat
- Save the game
- Load the game
- Verify ALL state survived the load
- Continue playing after load

**Act 5 — Endurance**
- Keep playing for 20+ more actions
- Move around extensively
- Does the world still tick correctly?
- Do NPCs still move on their own?
- Do caravans arrive on schedule?
- Does time advance properly?
- Does AP refresh correctly every turn?

**For each action, log:**
- Command issued
- Full narrative response
- HP, AP, position, game time
- Combat state
- Any state changes

**After playing, report:**
- Bugs encountered during gameplay
- Moments where immersion broke
- Actions that should have had consequences but didn't
- Actions that had wrong consequences
- Parser misinterpretations
- Missing responses or generic fallbacks
- State inconsistencies noticed during play
- What felt good vs what felt broken

### Phase 3: Fix Everything

Based on Phase 1 and Phase 2 findings:

1. Fix all bugs found
2. Add missing handlers for actions that returned generic responses
3. Improve DM narration prompts if they produce inconsistent results
4. Add test coverage for any untested paths discovered
5. Polish error messages — player-facing text should be helpful and in-character
6. Run full test suite — all tests must pass
7. Commit and push

## System Reference (for gameplay understanding)

### AP System
| Class | AP/Turn |
|-------|---------|
| Warrior | 4 |
| Rogue | 6 |
| Mage | 3 |
| Priest | 4 |

Costs: Move=1, Attack melee=2, Talk/Examine=1, Craft=5-20, Rest=0. Chain mail +1 move, Plate +2 move. Auto-refresh when AP hits 0 outside combat.

### Physical Inventory
- Grid-based RE4-style: Backpack (6x4), Belt (1x4), Pockets (1x2), Hidden stashes (1x1)
- Matter states: SOLID (backpack), LIQUID (waterskin/bottle), GAS (sealed barrel), ETHEREAL (bag of holding)
- Weight limit: `10 + (MIG_mod * 5)` kg. >75%: +1 AP move. >100%: +2 AP. >125%: can't move.

### Combat
- d20 attack, hit locations (body_parts.py), material damage multipliers
- Flee = AGI check DC 10
- Guards reinforce on crime
- Combat AP separate from exploration AP (3 per round)

### Quest Flow
- `talk` → offers shown → `accept quest <title>` → complete objectives → `turn in quest <title>`
- Authored + emergent quests merged
- Deadlines with reminders and failure

### Living World
- Every action = 15 game-minutes
- Hourly: NPC production, caravan departures, AP refresh, quest deadlines
- NPC behavior trees: flee/combat/needs/schedule/patrol/wander
- Economy with scarcity pricing
- Rumors propagate and decay
- Factions with reputation

### Save/Load
- Named slots, autosave
- Full PhysicalInventory serialization
- Entity positions, fog, NPC needs, quests, body trackers all preserved

## Output Format

### Phase 1 Findings
Severity-ordered list with file:line references and repro paths.

### Phase 2 Gameplay Log
Full action-by-action log with narrative, state, and annotations.

### Phase 2 Gameplay Verdict
- What works well
- What's broken
- What's missing
- What's inconsistent
- Overall AAA-readiness score (1-10)

### Phase 3 Changes
List of all fixes, new tests, and improvements made.

### Final Test Results
Full test suite output. Must be green.

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q              # All tests
python -m tools.play_topdown            # Play the game
```

## Review Attitude

Be brutal. Be creative. Try to break everything. The goal is that when a real player opens this game, they should be amazed. Every action should feel responsive, every consequence should make sense, and the world should feel alive.

If something doesn't work — fix it. If something is missing — add it. If something is inconsistent — make it consistent. No excuses, no "this could be improved later." Fix it NOW.
