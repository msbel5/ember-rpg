# Ember RPG — Master Roadmap
# Based on market research: BG3, Skyrim AI mods, AI Dungeon, Hidden Door, Mantella
# Last updated: 2026-03-23

## Vision
The first 2D RPG that combines **real game mechanics** (dice, stats, grid combat) with **AI narrative** (persistent memory, emergent quests, living world). No existing game does both well.

## Market Gap We Fill
- AI Dungeon / NovelAI = AI narrative, NO game mechanics
- BG3 / Divinity = Great mechanics, scripted narrative
- Ember RPG = **Both** — deterministic engine + AI storytelling layer

---

## Phase 1: Core Engine ✅ COMPLETED
Backend game systems — the deterministic foundation.

| Module | Status | Tests |
|--------|--------|-------|
| Character System | ✅ | 39 |
| Item + Effect System | ✅ | 89 |
| Combat Engine (3AP turn-based) | ✅ | 104 |
| Magic System (spell points) | ✅ | 133 |
| Leveling & Progression | ✅ | 161 |
| AI DM Agent (template-based) | ✅ | 183 |

## Phase 2: Content & API ✅ COMPLETED
API layer, data, and content.

| Module | Status | Tests |
|--------|--------|-------|
| FastAPI REST API | ✅ | 237 |
| Map Generator (tile-based) | ✅ | 275 |
| NPC Agent (personality, dialogue) | ✅ | 308 |
| Campaign Generator | ✅ | 349 |
| Save/Load System | ✅ | 499 |
| Smart Action Parser | ✅ | 540+ |
| Enemy AI | ✅ | 550+ |
| Loot System | ✅ | 560+ |
| Shop/Merchant | ✅ | 570+ |
| Rich DM Narratives | ✅ | 620 |
| Content: 54 spells, 148 items, 37 monsters, 3 campaigns, 21 NPCs | ✅ | — |

## Phase 3: World State & Memory 🔴 NEXT PRIORITY
**This is our key differentiator.** No competitor does this well.

### 3a. World State Ledger
- Structured JSON/SQLite tracking ALL world changes
- Killed NPCs, completed quests, faction standings, building states
- Fed to AI as context for every interaction
- PRD needed: PRD_world_state.md

### 3b. Per-NPC Persistent Memory (Mantella-inspired)
- Each NPC gets a memory file (JSON)
- Stores: conversation summaries, relationship score, key facts, last interaction
- Loaded into LLM context on interaction
- NPCs reference past events naturally ("You helped me last week...")
- PRD needed: PRD_npc_memory.md

### 3c. Consequence Cascading
- Actions update world state → triggers downstream effects
- Kill merchant → prices rise → town reputation drops → guards hostile
- Quest outcomes affect faction standings
- PRD needed: PRD_consequence_system.md

### 3d. Emergent Quest Generation
- AI reads world state ledger + NPC states
- Generates quests from current world situation
- "Blacksmith needs iron because goblins overran the mine you ignored"
- Not pre-scripted quest trees — organic quest creation
- PRD needed: PRD_emergent_quests.md

## Phase 4: Real AI Integration 🔴
Connect actual LLMs to the game engine.

### 4a. LLM Router
- Claude Sonnet for complex narrative (boss encounters, key story moments)
- Haiku/GPT-mini for routine dialogue
- Local qwen3 for basic NPC chatter (when Pi has AI HAT+)
- Fallback templates when all models unavailable

### 4b. DM Agent v2 — LLM-Powered
- Real narrative generation (not just templates)
- Context: world state + NPC memory + player history + current scene
- Rule enforcement: AI narrates, engine decides mechanics
- Prompt engineering for consistent tone and world logic

### 4c. NPC Agent v2 — Personality-Driven
- Each NPC has personality profile in LLM prompt
- Consistent character voice across sessions
- Emotional state tracking (happy, angry, afraid)
- Relationship dynamics with player AND other NPCs

### 4d. Companion System
- Party members with AI personalities
- Interjections during dialogue (BG3's #1 requested feature!)
- React to player decisions ("I don't think we should trust him...")
- Personal quests triggered by relationship level

## Phase 5: Godot Client Polish 🟡
2D pixel art frontend — we build this, Alcyone maintains backend.

### 5a. Core UI
- Title screen, character creation, game session
- Chat-based interaction with DM
- Player status panel (HP, XP, inventory)

### 5b. Tile Map Renderer
- 32x32 pixel tiles
- Fog of war
- Room/corridor visualization
- NPC/monster sprites on map

### 5c. Combat UI
- Turn indicator, AP counter
- Attack/spell/item action buttons
- Enemy HP bars
- Damage numbers, status effects

### 5d. Dialogue System
- NPC portrait + dialogue box
- Player choice buttons (when applicable)
- Companion interjection bubbles

### 5e. Inventory & Shop UI
- Grid-based inventory
- Equipment slots (weapon, armor, accessory)
- Shop interface (buy/sell with merchant)

## Phase 6: Audio & Atmosphere 🟡
### 6a. Music
- Procedural ambient music (different per scene type)
- Combat music transitions

### 6b. Sound Effects
- UI clicks, combat sounds, spell effects
- Environmental ambiance

### 6c. Text-to-Speech (Optional)
- ElevenLabs or local TTS for DM narration
- Different voices per NPC

## Phase 7: Advanced Content 🟡
### 7a. Additional Races
- Elf, Dwarf, Orc, Halfling (with unique racial abilities)

### 7b. Additional Classes
- Ranger, Paladin, Bard, Monk

### 7c. Crafting System
- Combine items to create new ones
- Recipes discovered through exploration

### 7d. NPC Daily Schedules
- NPCs move on map based on time-of-day
- Merchant opens at 8am, tavern at 6pm, sleeps at 10pm

### 7e. Weather & Time System
- Day/night cycle affects gameplay
- Weather affects combat (rain = fire spells weaker)

## Phase 8: Multiplayer 🔵 FUTURE
### 8a. Local Co-op
- 2-4 players, shared screen or split

### 8b. Online Multiplayer
- WebSocket-based real-time play
- AI DM handles turn order for all players
- Shared world state

### 8c. Telegram Integration
- Play through Telegram bot
- Tile map sent as image
- Commands as text messages

## Phase 9: Release 🔵 FUTURE
### 9a. Steam Release
- Steam page, achievements, trading cards
- Early Access first, then full release

### 9b. Web Release
- Godot HTML5 export
- Play in browser, no install

### 9c. Mobile
- Touch-optimized UI
- Same backend, different input handling

---

## Who Does What

| Task | Who | Notes |
|------|-----|-------|
| Backend engine + API | Alcyone (Pi) | Autonomous, TDD |
| World state / NPC memory | Alcyone (Pi) | Phase 3 priority |
| LLM integration | Alcyone (Pi) | Phase 4 |
| Godot client scenes | Mami + Claude Code | Windows |
| Pixel art assets | AI generated + manual | Phase 5 |
| PRD writing | Mami + Claude Code | Quality control |
| Testing & QA | Both | Alcyone: unit, Mami: integration |
| Steam/Web deploy | Mami | Phase 9 |

---

## Success Metrics
- **MVP**: Playable single-player session with AI DM (30 min gameplay loop)
- **Alpha**: 3 campaigns completable, save/load, 5+ hours content
- **Beta**: Multiplayer, polished UI, Steam Early Access ready
- **Release**: 20+ hours content, stable multiplayer, positive reviews
