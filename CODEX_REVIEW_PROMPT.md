# Ember RPG — Final Godot Visual QA + Backend Hardening

## Phase 1: Backend Quick Fixes (Before Godot)

### 1A. Fix the 3 known test failures
Run `cd frp-backend && python -m pytest tests/ -q --tb=short` and fix every failure. Do NOT skip or mark as xfail. Common culprits:
- `test_runtime_audit.py` — regenerate runtime doc if stale
- `test_chaos_session.py` — seed isolation between tests
- Any test referencing old starter kit item IDs

### 1B. Fix terminal `play_topdown.py` character creation
The terminal client crashes or doesn't work on first launch because character creation flow is broken. Fix:
- Ensure `python -m tools.play_topdown` launches cleanly with name + class selection
- If character creation wizard fails, fall back to simple name/class prompt
- Game must be playable within 10 seconds of launching

### 1C. AP auto-refresh when 0 outside combat
When AP hits 0 and player is NOT in combat, automatically end turn:
- World tick runs (15 minutes pass)
- AP refreshes to max
- Player sees "(New turn — AP refreshed)" appended to narrative
- This must be seamless — player should never see "Not enough AP" more than once per turn

### 1D. Talk to DM should NOT cost AP
`talk`, `think`, `say`, `to self`, `address dm` — these are free meta-commands. Only direct NPC interactions cost AP.

### 1E. 500-turn chaos backend test
Run a seeded 500-turn chaos session covering:
- Explore, approach every NPC, talk/persuade/bribe/deceive/intimidate
- THINK about History, Arcana, Religion, Nature
- Combat: attack, disengage, flee, death saves
- Short rest, long rest
- Craft, accept quest, complete quest, turn in quest
- Save and load (verify full state roundtrip)
- Steal from merchant (verify crime consequences)
- Passive Perception reveals
- Alignment shifts
- **Derail the campaign** — solve quests the most unexpected creative ways
- **Every skill and mechanic must be tested**

Fix every bug found. Re-run. Repeat until 0 bugs.

Commit and push after Phase 1 is fully green.

---

## Phase 2: Godot Client — Visual QA Protocol

### MANDATORY: Run Godot in GRAPHICAL mode
- Do NOT use `--headless`
- The Godot window MUST open and be visible
- Do NOT declare success without seeing the actual rendered output

### Visual Verification Protocol (EVERY test step)

At each step you MUST:
1. Launch the game: `cd godot-client && godot --path . res://scenes/main.tscn`
2. Verify window opened (check process exists + responds)
3. Verify the scene actually renders (not black screen)
4. Wait at least 5 seconds observing
5. Capture screenshot from viewport: use `get_viewport().get_texture().get_image().save_png(path)`
6. Send keyboard/mouse input to interact
7. Check player, camera, UI, error overlays
8. Only THEN report results

### Report Format (per test step)
```
- step: "description"
  window_opened: true/false
  scene_visible: true/false
  input_tested: true/false
  screenshot_path: "res://screenshots/step_N.png"
  observed_visual_issues: [...]
  console_errors: [...]
  status: pass/fail
```

If you CANNOT get window screenshots, use viewport capture:
```gdscript
# Add to any node's _ready():
await get_tree().create_timer(2.0).timeout
var img = get_viewport().get_texture().get_image()
img.save_png("user://screenshot.png")
```

### Godot Sprint Checklist

#### Sprint 1: Window + Tilemap
- [ ] Project opens without errors
- [ ] Main scene loads and renders
- [ ] 16x16 pixel tilemap visible (Rimworld-style)
- [ ] Player character sprite visible and centered
- [ ] Camera follows player
- [ ] Screenshot captured proving render works

#### Sprint 2: Movement + Input
- [ ] Arrow keys move player on tilemap
- [ ] WASD also works
- [ ] Camera follows smoothly
- [ ] Tile collision works (can't walk through walls)
- [ ] Movement animates (not teleport)

#### Sprint 3: Backend Connection
- [ ] Godot connects to FastAPI backend via HTTP
- [ ] `POST /game/session/new` creates session
- [ ] `POST /game/session/{id}/action` sends commands
- [ ] Narrative text displays in UI panel
- [ ] HP/AP/Gold shown in HUD

#### Sprint 4: NPC + Interaction
- [ ] NPCs rendered on map at correct positions
- [ ] Walk near NPC → interaction prompt appears
- [ ] Talk to NPC → narrative response shows
- [ ] NPC sprites distinct by role (merchant/guard/blacksmith)

#### Sprint 5: Combat + Effects
- [ ] Combat UI overlay when in combat
- [ ] Attack animation/flash
- [ ] HP bar visible during combat
- [ ] Death/flee transitions
- [ ] Damage numbers or indicators

#### Sprint 6: Sprite Pipeline
- [ ] Missing sprites trigger AI generation pipeline
- [ ] Generated sprites cached in `assets/sprites/`
- [ ] Fallback to colored rectangles if pipeline unavailable
- [ ] Items, NPCs, terrain all have distinct sprites

### After Each Sprint
1. Run visual verification protocol
2. Capture screenshots
3. Fix any visual/functional issues
4. Commit and push
5. Move to next sprint

---

## Phase 3: 500-Turn Visual Chaos Test

After all Godot sprints complete, play 500 turns through the Godot client:

### Act 1 (turns 1-50): Arrival & Exploration
- Create character (name, class selection in Godot UI)
- Move around town, visit every building
- Approach and talk to every NPC
- Verify map renders correctly, NPCs at right positions
- Screenshot every 10 turns

### Act 2 (turns 51-150): Social & Quests
- Persuade, bribe, deceive, intimidate NPCs
- Accept quests, track objectives
- THINK about lore topics
- Trade with merchants
- Verify UI updates for quest/inventory changes

### Act 3 (turns 151-250): Combat & Skills
- Attack enemies, use all combat mechanics
- Disengage, flee, test opportunity attacks
- Cast spells, use items in combat
- Get to 0 HP — test death saves
- Short rest, long rest, verify recovery
- Screenshot combat UI

### Act 4 (turns 251-350): Crime & Consequences
- Steal from merchants
- Attack NPCs, verify guard response
- Check attitude shifts (hostile markers visible)
- Try social actions on hostile NPCs
- Alignment shifts visible in UI

### Act 5 (turns 351-500): Creative Chaos
- **Solve quests the UNEXPECTED way** — this is MANDATORY:
  - Delivery quest? Steal the item instead of buying it
  - Kill quest? Persuade the target to leave instead
  - Escort quest? Intimidate bandits to flee
  - Fetch quest? Craft the item instead of finding it
- Save game, load game, verify all state preserved
- Try to become mayor through pure social manipulation
- Try to crash the economy by hoarding/dumping items
- Break into every locked door
- Fish, mine, chop — test all gathering

### Bug Protocol
For every bug found:
1. Log: turn number, command, expected behavior, actual behavior
2. Continue playing (don't stop)
3. After 500 turns, fix ALL logged bugs
4. Re-run 500 turns
5. Repeat until 0 bugs

---

## How to Run

```bash
# Backend
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q              # All tests must pass
python -m tools.play_topdown            # Terminal client

# Godot
cd godot-client
godot --path . res://scenes/main.tscn   # Launch game
```

## Attitude

This is the FINAL polish pass. The game must:
- Launch without errors
- Render visually (not headless, not black screen)
- Be playable from turn 1 — no broken character creation
- Have working AP auto-refresh (no AP trap)
- Pass 500-turn chaos test with 0 bugs
- Every quest solvable through creative unexpected paths
- Screenshots proving every sprint works

Ship it.
