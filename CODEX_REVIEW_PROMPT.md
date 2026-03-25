# Ember RPG — Comprehensive Review & Implementation Prompt

## Project Vision

Ember RPG is a living-world text RPG inspired by Dwarf Fortress, Rimworld, Elder Scrolls II: Daggerfall, Monkey Island, and The Hitchhiker's Guide to the Galaxy. The game features deterministic mechanics with AI narration layered on top. The terminal ASCII client is the foundation — it must be AAA quality before moving to Godot.

**Core principle:** "AI doesn't decide, world lives by rules; AI only reads and narrates."

**Long-term pipeline:** Terminal ASCII → Godot 2D → AI-generated sprites → post-processed POV view with point-and-click feel.

## Tech Stack

- **Python 3.10+**, FastAPI, Rich terminal UI, pytest
- **Test count:** 1847 passing
- **Run tests:** `cd frp-backend && python -m pytest tests/ -q`
- **Play the game:** `cd frp-backend && python -m tools.play_topdown`

## Architecture Overview

### Core Engine (`engine/api/`)
| File | Purpose | Lines |
|------|---------|-------|
| `game_engine.py` | Main orchestrator — routes 37+ intents to handlers, world tick, combat | ~3200 |
| `game_session.py` | Session state container — PhysicalInventory, AP, map, entities | ~700 |
| `save_system.py` | Save/Load with PhysicalInventory serialization | ~620 |
| `action_parser.py` | NLP intent parser — 37+ intents, regex + keyword fallback, EN/TR | ~600 |
| `routes.py` | FastAPI REST endpoints | ~240 |
| `save_routes.py` | Save/Load REST endpoints | ~220 |
| `models.py` | Pydantic request/response models (ActionResponse has FR-15 fields) | ~65 |
| `shop_routes.py` | Shop buy/sell using canonical PhysicalInventory | ~375 |

### World Simulation (`engine/world/`)
| File | Purpose |
|------|---------|
| `inventory.py` | **NEW** — RE4-style grid inventory: ItemShape, ItemStack, Container, PhysicalInventory |
| `matter_state.py` | **NEW** — SOLID/LIQUID/GAS/ETHEREAL matter states, container validation |
| `entity.py` | Entity dataclass with components (needs, inventory, skills, body) |
| `spatial_index.py` | O(1) grid-based entity lookup |
| `viewport.py` | Camera + shadow-casting FOV + 3-level zoom |
| `behavior_tree.py` | Priority/Sequence NPC AI (flee/combat/needs/schedule/patrol/wander) |
| `skill_checks.py` | d20 system, 6 abilities, contested checks, nat 20/1 |
| `action_points.py` | Class-based AP pools, armor penalties, encumbrance |
| `crafting.py` | 51 recipes, 5 disciplines, quality tiers (RUINED→MASTERWORK) |
| `interactions.py` | 85+ context-sensitive rules, 31 interaction types |
| `npc_needs.py` | 5 needs (safety/commerce/social/sustenance/duty), emotional states |
| `ethics.py` | 6 factions, 8 action types, reputation system |
| `economy.py` | LocationStock with scarcity pricing |
| `rumors.py` | RumorNetwork with propagation/decay |
| `caravans.py` | 3 caravan routes, tick-based arrivals, raiding |
| `quest_timeout.py` | Quest tracking with deadline/reminders |
| `body_parts.py` | d20 hit locations, per-part HP tracking, armor coverage |
| `materials.py` | 10 materials with density/hardness/value/damage multipliers |
| `proximity.py` | A* pathfinding, distance, LOS |
| `schedules.py` | NPC daily schedules, 5 time periods |

### Terminal Client (`tools/`)
| File | Purpose |
|------|---------|
| `play_topdown.py` | Top-down ASCII renderer with Rich — map viewport + narrative + status |

## System Details

### 1. Physical Inventory System (NEW — RE4 + Dark Souls hybrid)

**Grid-based containers:** Backpack (6x4=24 cells), Belt (1x4), Pockets (1x2 each), Hidden Stashes (1x1 each)

**Item shapes:** Multi-size RE4 style. Sword=1x4, Shield=2x2, Potion=1x1, Plate Armor=2x3. Rigid items rotate 90°, non-rigid items (rope, scroll) can reshape.

**Matter states:** SOLID (backpack/belt), LIQUID (waterskin/bottle), GAS (sealed iron barrel/balloon), ETHEREAL (bag of holding only). All entities follow same rules.

**Weight & encumbrance:** `max_carry = 10 + (MIG_modifier * 5)` kg. 0-75%: free, 75-100%: +1 AP move, 100-125%: +2 AP move, >125%: cannot move.

**Hidden stashes:** 3 tiers — SIMPLE (pocket, 50% discovery), ADVANCED (sock/boot, skill check), MAGICAL (bag of holding, detect magic only).

**Liquid handling:** `fill waterskin` at water source, `pour water into bottle`.

### 2. Action Point System

| Class | AP/Turn | Notes |
|-------|---------|-------|
| Warrior | 4 | Heavy armor movement penalty |
| Rogue | 6 | Fastest, stealth-oriented |
| Mage | 3 | Slowest but spells cost 1-3 AP |
| Priest | 4 | Balanced |

**Costs:** Move flat=1, Move rough=2, Attack melee=2, Attack ranged=3, Talk/Examine/Trade=1, Craft=5-20, Rest=0 (8 game-hours), Pick up=1.

**Armor penalties:** Chain mail +1 AP per move, Plate +2 AP per move. Stacks with encumbrance.

**Auto-turn:** When AP hits 0 outside combat, world auto-ticks and AP refreshes.

**Combat AP:** Separate system — combat uses CombatManager.combatant.ap (3 per round). Exploration AP pauses during combat.

### 3. Combat System

- d20 attack rolls with hit locations (body_parts.py)
- Material-based damage multipliers
- Body part HP tracking + armor reduction per part
- Flee requires AGI check (DC 10)
- Guard reinforcement on crime
- XP rewards by enemy level

### 4. Quest System

- Explicit flow: `talk` → quest offers → `accept quest <title>` → complete objectives → `turn in quest <title>`
- Authored + emergent quest offers (merged, never overwritten)
- Delivery quests require proximity to giver for turn-in
- Hunt quests auto-complete on kill
- Quest deadlines with reminders and failure

### 5. Living World

- World ticks every action (15 game-minutes)
- Hourly: NPC production, caravan departures, AP refresh, quest deadline checks
- NPC behavior trees produce visible spatial movement
- Economy with scarcity pricing affected by caravans
- Rumors propagate and decay
- NPC needs drive behavior (flee when unsafe, trade when willing)

### 6. Map & Viewport

- 48x48 tile maps (Town/Dungeon/Wilderness generators)
- Shadow-casting FOV with fog of war
- 3 zoom levels: Normal (40x20), District (80x40), World (160x80)
- `-`/`+` keys to zoom in terminal
- Auto-pathfinding: `approach <npc>` uses A* to walk to NPC

### 7. Save/Load

- Named slot system with autosave
- Full PhysicalInventory serialization
- Entity positions, fog of war, NPC needs, quest state, body trackers all preserved
- Legacy format migration on load

### 8. Action Parser

- 37+ intents with regex + keyword fallback
- English and Turkish support
- Priority ordering prevents conflicts:
  - FISH before CAST_SPELL ("cast line")
  - STASH before SNEAK ("hide X in Y" vs bare "hide")
  - INTERACT before USE_ITEM ("use lever" vs "use potion")
  - ROTATE_ITEM uses only "rotate"/"flip" (not "turn")

## Gameplay Quality Requirements (AAA Standard)

1. **Deterministic mechanics first, narration second** — DM only narrates, never decides outcomes
2. **Living world observable** — NPC movements, caravan arrivals, rumors visible to player
3. **NPCs autonomous and stateful** — schedules, needs, memory, faction reputation
4. **Quests succeed or fail cleanly** — no hanging quests, deadlines enforced
5. **Player can derail everything** — become mayor, start business, attack anyone
6. **Boring situations allowed** — DM shouldn't fabricate excitement
7. **Consistent across long sessions** — save/load preserves all state
8. **Physical inventory rules universal** — player, NPCs, merchants, caravans all follow same weight/container/matter rules
9. **Encumbrance matters** — can't carry 100kg if strength says 10kg max
10. **Ambiguity resolution** — parser correctly distinguishes NPC speech, DM commands, self-talk

## Your Mission

You are reviewing AND implementing. The workflow:

1. **Read ALL `.md` files** to understand vision
2. **Read all source files** listed above
3. **Run tests** to verify baseline
4. **Review** for bugs, logic errors, edge cases, state divergence
5. **Create implementation plan** for fixes and missing features
6. **Implement everything** — fix bugs, add missing features, polish UX
7. **Add tests** for new code, maintain 100% pass rate
8. **Play-test** via `python -m tools.play_topdown`
9. **Commit and push** with descriptive messages
10. **Review your own work** and iterate until AAA

## Specific Review Targets

1. **PhysicalInventory integration** — is it truly the single source of truth everywhere?
2. **Save/load roundtrip** — does PhysicalInventory survive save/load with all grid positions?
3. **Weight enforcement** — can player bypass weight limits?
4. **Container rules** — can liquid be stored without vessel? Gas without sealed container?
5. **AP system** — exploration AP vs combat AP, auto-turn when AP=0
6. **Parser** — any remaining conflicts? Turkish/English overlaps?
7. **Combat** — damage, body tracking, flee, rewards
8. **Quest flow** — accept/turn-in/deadline/failure
9. **World tick** — hourly systems, NPC movement, caravan timing
10. **Terminal client** — renders from canonical session state? Zoom works?

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q              # All tests (1847)
python -m pytest tests/ -q -k playtest  # Play-test scenarios
python -m tools.play_topdown            # Play the game
```
