# PRD: API Layer (FastAPI)
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Implemented  

---

## 1. Purpose

The API Layer exposes all game engine functionality as an HTTP REST API. It bridges the gap between player natural language ("ejderhaya saldırıyorum") and the backend game systems (combat, narrative, progression). A session-based design allows multiple concurrent players. Auto-generated OpenAPI docs (`/docs`) enable frontend integration without manual documentation.

---

## 2. Scope

**In scope:**
- ActionParser: natural language → structured intent (Turkish + English)
- GameSession: per-player state container (UUID-keyed)
- GameEngine: orchestrates Phase 2 systems per action intent
- FastAPI routes: session CRUD + action endpoint
- Pydantic request/response models
- In-memory session store (MVP)

**Out of scope:**
- Authentication / authorization (→ future Multiplayer phase)
- Persistent session storage (→ Database phase)
- WebSocket for real-time updates (→ Multiplayer phase)
- Rate limiting (→ Production Ops phase)
- NPC interaction endpoint (→ Phase 5 API extension)
- Map endpoint (→ Phase 4 API extension)

---

## 3. Functional Requirements

**FR-01:** `ActionParser.parse(text)` detects one of 8 intents (ATTACK, CAST_SPELL, USE_ITEM, MOVE, TALK, EXAMINE, REST, OPEN) or UNKNOWN. Supports Turkish and English.

**FR-02:** `ActionParser` uses priority-ordered keyword matching; more specific intents are checked before generic ones to avoid false matches.

**FR-03:** `ActionParser` extracts a target noun from input, stripping Turkish case suffixes.

**FR-04:** `GameEngine.new_session()` creates a session with a UUID, initializes Character with class-appropriate stats, and sets scene to EXPLORATION.

**FR-05:** `GameEngine.process_action()` routes each intent to a handler, advances the turn counter, and returns an `ActionResult` with narrative and state.

**FR-06:** `POST /game/session/new` returns session_id, narrative, player state, scene, and location.

**FR-07:** `POST /game/session/{id}/action` accepts `{"input": str}`, returns narrative + player state + optional combat state.

**FR-08:** `GET /game/session/{id}` returns full session state.

**FR-09:** `DELETE /game/session/{id}` removes session; subsequent GET returns 404.

**FR-10:** REST action restores HP (max_hp//4) and spell_points to max when not in combat.

**FR-11:** REST action during active combat returns a refusal narrative without healing.

**FR-12:** When no LLM is configured, `GameEngine` uses template-based `DMAIAgent.narrate()` for all narratives.

**FR-13:** When an LLM callable is injected into `GameEngine`, it is passed to `DMAIAgent.narrate()` for every action.

---

## 4. Data Structures

```python
# Request models (Pydantic)
class NewSessionRequest(BaseModel):
    player_name: str
    player_class: str = "warrior"    # warrior|rogue|mage|priest
    location: Optional[str] = None

class ActionRequest(BaseModel):
    input: str                        # Raw player text

# Response models (Pydantic)
class NewSessionResponse(BaseModel):
    session_id: str
    narrative: str
    player: dict
    scene: str
    location: str

class ActionResponse(BaseModel):
    narrative: str
    scene: str
    player: dict
    combat: Optional[dict]
    state_changes: dict
    level_up: Optional[dict]

class SessionStateResponse(BaseModel):
    session_id: str
    scene: str
    location: str
    player: dict
    in_combat: bool
    turn: int
```

---

## 5. Public API

### Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check — returns name + version + status |
| `POST` | `/game/session/new` | Create new game session |
| `GET` | `/game/session/{id}` | Get session state |
| `POST` | `/game/session/{id}/action` | Submit player action |
| `DELETE` | `/game/session/{id}` | End session |

### `GameEngine.new_session(player_name, player_class, location=None) -> GameSession`
- Default stats per class: warrior (MIG 16), mage (MND 16), rogue (AGI 16), priest (INS 16)
- Random opening location if none provided

### `GameEngine.process_action(session, input_text) -> ActionResult`
- Always advances `session.dm_context.turn`
- Routes to handler: attack, spell, talk, rest, move, examine, open, use_item, unknown
- Returns `ActionResult(narrative, events, state_changes, scene_type, combat_state, level_up)`

---

## 6. Acceptance Criteria

**AC-01 [FR-01]:** `parser.parse("attack the goblin").intent == ActionIntent.ATTACK`

**AC-02 [FR-01]:** `parser.parse("ejderhaya saldırıyorum").intent == ActionIntent.ATTACK`

**AC-03 [FR-01]:** `parser.parse("büyü atıyorum").intent == ActionIntent.CAST_SPELL`

**AC-04 [FR-01]:** `parser.parse("heal the warrior").intent == ActionIntent.CAST_SPELL`

**AC-05 [FR-01]:** `parser.parse("xyzzy plugh").intent == ActionIntent.UNKNOWN`

**AC-06 [FR-02]:** `parser.parse("dinlenmek istiyorum").intent == ActionIntent.REST` (not EXAMINE despite "dinle" in EXAMINE keywords)

**AC-07 [FR-03]:** `parser.parse("gobline saldırıyorum").target` is not None.

**AC-08 [FR-04]:** `engine.new_session("Aria", "mage").player.max_spell_points > 0`

**AC-09 [FR-04]:** `engine.new_session("Aria").dm_context.scene_type == SceneType.EXPLORATION`

**AC-10 [FR-05]:** After `process_action(session, "incele")`, `session.dm_context.turn == 1`

**AC-11 [FR-06]:** `POST /game/session/new` → 200, body contains "session_id", "narrative", "player"

**AC-12 [FR-07]:** `POST /game/session/{id}/action {"input":"odayı incele"}` → 200, body contains "narrative"

**AC-13 [FR-08]:** `GET /game/session/{id}` → 200, body contains "session_id", "in_combat", "turn"

**AC-14 [FR-09]:** After `DELETE /game/session/{id}`, `GET /game/session/{id}` → 404

**AC-15 [FR-10]:** After rest action with player at 5 HP (max 20), `session.player.hp > 5`

**AC-16 [FR-11]:** Rest action during active combat → narrative contains refusal; HP unchanged

**AC-17 [FR-13]:** `GameEngine(llm=mock_fn).process_action(session, "incele")` → narrative == mock_fn return value

---

## 7. Performance Requirements

- `ActionParser.parse()`: < 1ms
- `process_action()` (no LLM, no combat): < 10ms
- `POST /game/session/{id}/action`: < 100ms end-to-end (no LLM)

---

## 8. Error Handling

- `GET/POST/DELETE` on unknown session_id → 404 `{"detail": "Session not found"}`
- `ActionParser.parse("")` → returns `ParsedAction(intent=UNKNOWN, raw_input="")`
- Attack with no valid target → returns narrative "no target found" (no exception)
- Spell with 0 spell_points → returns narrative "spell points exhausted" (no exception)

---

## 9. Integration Points

- **Upstream:** All Phase 2 engine modules (Character, Combat, Magic, Progression, DM Agent)
- **Downstream:** Frontend (Godot / Web) sends ActionRequest, displays ActionResponse.narrative
- **Peer:** NPC Agent (`_handle_talk`), Map Generator (future map endpoint)

---

## 10. Test Coverage Target

- Minimum: **90%** across `engine/api/` and `main.py`
- Must test: all 8 ActionParser intents (TR+EN), all route endpoints (TestClient), LLM mock path, rest in/out of combat, session lifecycle

---

## Changelog

- 2026-03-23: Rewritten to PRD standard (post-implementation)
