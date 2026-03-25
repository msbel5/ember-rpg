# Ember RPG — Master Roadmap
# Based on market research: BG3, Skyrim AI mods, AI Dungeon, Hidden Door, Mantella
# Last updated: 2026-03-25

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

## Phase 3: World State & Memory 🟡 CORE LOOP IMPLEMENTED
**This is our key differentiator.** The core runtime pass is now in place; remaining work is content depth and tuning.

### 3a. World State Ledger
- Canonical `GameSession` now owns world, map, entities, inventory, quests, narration context, and persistence
- Full-fidelity save/load preserves combat, entity schedules, body state, ground items, fog, rumors, campaign state, and narration context
- Fed to AI as context for every interaction
- Ongoing: broaden cross-location persistence and faction-specific authored consequences

### 3b. Per-NPC Persistent Memory (Mantella-inspired)
- NPC memory is stored with session state and stamped with in-game time instead of wall-clock time
- Dialogue/trade prompts now receive stable world and relationship context
- NPC schedules and patrol routes are serialized and restored with the session
- Ongoing: richer long-term summarization across campaign-length play

### 3c. Consequence Cascading
- World tick now advances economy, caravans, rumor decay/spread, quest reminders/failures, and simple role-based production
- Quest and derail actions surface visible downstream effects in state and narration
- Combat outcomes sync back onto live entities, including HP/body-state changes
- Ongoing: deeper faction politics and authored incident tables

### 3d. Emergent Quest Generation
- Deterministic quest flow now supports acceptance, reminder, completion, and failure in the shared world loop
- Lightweight emergent quest offers are generated from shortages, unrest, deaths, and ignored threats
- Merchant/guard/quest-giver conversations can surface these offers directly
- Ongoing: expand authored quest archetypes and follow-up branches

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

### 5b. AI Asset Pipeline + POV Compositor 🔥 NEW
**Hitchhiker's Guide meets AI art — every scene uniquely illustrated**
- Layered compositing: Far BG → Mid BG → Items → Entities → FX
- AI-generated assets (HuggingFace SDXL/Flux, free tier)
- Smart caching: generate once, reuse everywhere (same tile+direction = same image)
- Color palette swapping for NPC/item variations (no API call needed)
- Procedural renderer as fallback while assets load (crossfade)
- ~20 generations per new location, ~50MB per campaign
- Cross-campaign shared asset library (barrel, chest, torch = universal)
- PRD: `docs/PRD_asset_pipeline.md`

### 5b-legacy. Tile Map Renderer (Top-down view)
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

### 7c. Crafting System 🟡 V1 IMPLEMENTED
- Recipe-based crafting now consumes canonical structured inventory records
- Workstation entities exist on maps and long crafts can span multiple turns/AP windows
- Ongoing: add more recipes, profession depth, and location-specific production chains

### 7d. NPC Daily Schedules 🟡 V1 IMPLEMENTED
- NPCs now spawn with schedules and patrol routes and move on the live spatial index
- Behavior trees tick every action; rest and long actions advance the same loop
- Ongoing: denser authored schedules, social gatherings, and reactive rerouting

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
| AI Asset Pipeline | Mami + Claude Code | HuggingFace API, Godot compositor |
| Asset Generation Worker | Alcyone (Pi) | Background generation, caching |
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
