# Ember RPG — Continuation Prompt for New Session

Paste this at the start of a new Claude Code conversation to restore full context.

## Project Location
- Repo: `C:\Users\msbel\projects\ember-rpg` (git, GitHub: msbel5/ember-rpg)
- Backend: `frp-backend/` (Python, FastAPI, 1700+ tests)
- Client: `godot-client/` (Godot 4.6, 183 headless tests)

## Current State (2026-03-30)

### What WORKS
- **Deterministic worldgen pipeline** (9/9 tests): seed → terrain → settlement → NPC → quest → economy → world_tick
- **Campaign-first API**: `/game/campaigns/{id}/commands`
- **Godot client**: Tab-based sidebar, tile rendering, NPC sprites, command bar
- **Backend**: D&D 5e systems (proficiency, passive checks, conditions, death saves, initiative, alignment)
- **Physical inventory**: RE4-grid, matter states, encumbrance
- **Video recording**: automation bridge with frame capture + ffmpeg stitch

### What's BROKEN or INCOMPLETE
- **Godot visual quality**: VQS 5.0/10 — tiles look repetitive, no animation, weak atmosphere
- **Tab panels**: Fixed overflow but need visual testing — Town tab may still clip
- **World generation → Godot**: Pipeline produces data but Godot render needs polish
- **NPC interaction depth**: Talk works but shallow — no deep dialog trees
- **LLM layer**: Copilot API works (gpt-4.1 free) but not hooked into NPC sessions
- **Animation**: Zero — sprites teleport

### Key Files to Read First
1. `docs/PRD_IMPLEMENTATION_MATRIX.md` — Which docs are authoritative vs superseded
2. `docs/deprecated/notes/PROMPT_deterministic_world_v1.md` — World engine prompt (all sprints defined)
3. `docs/deprecated/notes/PROMPT_director_v2.md` — VQR rubric and quality benchmarks
4. `docs/qa/vqr_scorecard.md` — Current visual quality scores
5. `CODEX_REVIEW_PROMPT.md` — Latest Codex task prompt
6. `README.md` — Architecture and vision overview

### Design Philosophy
**Deterministic first, AI second.** The game engine runs a fully algorithmic world. AI layers (DM narration, NPC conversation) are hooked in via API interfaces to enrich — not replace — the deterministic simulation. Each conscious entity (NPC, DM) will have its own persistent LLM session.

### Tool Setup
- **Codex CLI**: `codex exec --skip-git-repo-check --full-auto -C frp-backend 'prompt'`
- **Copilot API**: `npx copilot-api@latest start -p 4141` (free GPT-4.1 via GitHub Copilot)
- **Godot**: `C:\Tools\Scoop\apps\godot\current\godot.exe --path godot-client`
- **Backend**: `cd frp-backend && uvicorn main:app --host 127.0.0.1 --port 8000`
- **ffmpeg**: Available at `C:\ffmpeg\bin\ffmpeg`
- **Pi (Alcyone)**: `ssh alcyone` → `~/.openclaw/workspace/ember-rpg/`

### What To Do Next
Pick ONE of these tracks:
1. **Visual polish** — Make Godot client look like RimWorld (tile variety, NPC silhouettes, atmosphere)
2. **Gameplay depth** — NPC dialog trees, quest creativity, interaction richness
3. **AI integration** — Hook Copilot API as DM narrator + NPC conversation sessions
4. **Bug fixing** — Run 500-turn chaos test, fix everything, ship playable demo
