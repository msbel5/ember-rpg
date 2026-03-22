# PRD: Phase 3 — API Layer (FastAPI)
**Project:** Ember RPG — FRP AI Game  
**Phase:** 3  
**Date:** 2026-03-23  
**Status:** Design → Implementation

---

## 1. The Vision

Kullanıcı sadece şunu yapar:
```
POST /game/action
{ "input": "kapıyı açıyorum" }
```

Ve şunu alır:
```json
{
  "narrative": "Ağır meşe kapı gıcırdayarak açılır. İçeride soluk bir ışık titreşiyor...",
  "state": { "scene": "exploration", "hp": 28, "location": "Karanlık Kule" }
}
```

Bütün mekanik (zar, AC, spell point) arka planda. Kullanıcı sadece hikayeyi yaşar.

---

## 2. Architecture

```
HTTP Client (Godot / Web / Telegram)
        ↓
   FastAPI Layer
        ↓
  ActionParser          ← "ejderhaya saldırıyorum" → {intent: ATTACK, target: "ejderha"}
        ↓
  GameEngine            ← Tüm sistemleri orkestre eder
    ├── CombatManager   ← combat resolution
    ├── ProgressionSystem ← XP, level-up
    └── DMAIAgent       ← narrative generation
        ↓
  Response Builder      ← narrative + state + events
```

---

## 3. Modules

### 3.1 ActionParser
Natural language → structured intent

```python
class ActionIntent(Enum):
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    USE_ITEM = "use_item"
    MOVE = "move"
    TALK = "talk"
    EXAMINE = "examine"
    REST = "rest"
    OPEN = "open"
    UNKNOWN = "unknown"

@dataclass
class ParsedAction:
    intent: ActionIntent
    target: Optional[str]       # "ejderha", "kapı", "tüccar"
    action_detail: Optional[str] # "kılıçla", "ateş büyüsüyle"
    raw_input: str

class ActionParser:
    INTENT_KEYWORDS = {
        ActionIntent.ATTACK: ["saldır", "vur", "attack", "strike", "hit", "öldür", "kill"],
        ActionIntent.CAST_SPELL: ["büyü", "spell", "cast", "magic", "ateş", "şimşek"],
        ActionIntent.USE_ITEM: ["kullan", "iç", "use", "drink", "eat", "open bag"],
        ActionIntent.TALK: ["konuş", "söyle", "talk", "say", "ask", "sor", "pazarlık"],
        ActionIntent.EXAMINE: ["bak", "incele", "look", "examine", "search", "ara"],
        ActionIntent.REST: ["dinlen", "rest", "camp", "kamp", "uy", "sleep"],
        ActionIntent.OPEN: ["aç", "open", "unlock", "kır", "break"],
        ActionIntent.MOVE: ["git", "yürü", "go", "move", "run", "kaç", "flee"],
    }
    
    def parse(self, text: str) -> ParsedAction: ...
```

### 3.2 GameSession
Per-player game state (in-memory for MVP, Redis later)

```python
@dataclass
class GameSession:
    session_id: str
    player: Character
    dm_context: DMContext
    combat: Optional[CombatManager]
    created_at: datetime
    last_action: datetime
```

### 3.3 GameEngine
Orchestrates all Phase 2 systems

```python
class GameEngine:
    def process_action(self, session: GameSession, action: ParsedAction) -> ActionResult: ...
    def start_combat(self, session: GameSession, enemies: List[Character]) -> ActionResult: ...
    def end_combat(self, session: GameSession) -> ActionResult: ...

@dataclass  
class ActionResult:
    narrative: str          # DM-generated story text
    events: List[DMEvent]   # What happened mechanically
    state_changes: dict     # HP changes, items, level-ups
    scene_type: SceneType
    combat_state: Optional[dict]  # If in combat
```

### 3.4 FastAPI Routes

```
POST /session/new          → Create new game session
GET  /session/{id}         → Get session state
POST /session/{id}/action  → Submit player action → narrative response
GET  /session/{id}/state   → Full game state (party HP, scene, location)
POST /session/{id}/combat/start → Initiate combat
GET  /session/{id}/combat/state → Combat status
DELETE /session/{id}       → End session
```

---

## 4. ActionParser Design

### Keyword Matching (MVP)
Turkish + English bilingual support.

### Fallback
Unrecognized → `UNKNOWN` intent → DM narrates "Tam olarak ne yapmak istiyorsun?"

### Target Extraction
Basit: input'tan keyword çıkar, active entities ile eşleştir.
"ejderhaya saldır" → target="ejderha" → match with combat.combatants

---

## 5. Test Cases

### TC1: ActionParser — Attack Intent
```python
parser = ActionParser()
result = parser.parse("ejderhaya saldırıyorum")
assert result.intent == ActionIntent.ATTACK
assert "ejderha" in result.target
```

### TC2: ActionParser — Turkish + English
```python
assert parser.parse("attack the goblin").intent == ActionIntent.ATTACK
assert parser.parse("orka saldır").intent == ActionIntent.ATTACK
```

### TC3: ActionParser — Spell Intent
```python
result = parser.parse("ateş büyüsü atıyorum")
assert result.intent == ActionIntent.CAST_SPELL
```

### TC4: ActionParser — Unknown Intent
```python
result = parser.parse("xyzzy plugh")
assert result.intent == ActionIntent.UNKNOWN
```

### TC5: GameSession Creation
```python
engine = GameEngine()
session = engine.new_session(player_name="Aria")
assert session.session_id is not None
assert session.player.name == "Aria"
assert session.dm_context.scene_type == SceneType.EXPLORATION
```

### TC6: Full Action Loop (no LLM)
```python
session = engine.new_session("Aria")
result = engine.process_action(session, ParsedAction(
    intent=ActionIntent.EXAMINE, target="oda", raw_input="odayı inceliyorum"
))
assert isinstance(result.narrative, str)
assert len(result.narrative) > 0
```

### TC7: Combat Flow
```python
session = engine.new_session("Aria")
engine.start_combat(session, enemies=[Character(name="Goblin", hp=10, max_hp=10)])

attack_action = ParsedAction(intent=ActionIntent.ATTACK, target="goblin", raw_input="goblina saldır")
result = engine.process_action(session, attack_action)

assert result.combat_state is not None
```

---

## 6. FastAPI Endpoint Design

```python
# Request/Response models (Pydantic)

class ActionRequest(BaseModel):
    input: str              # "ejderhaya saldırıyorum"
    session_id: str

class ActionResponse(BaseModel):
    narrative: str          # "Kılıcın ejderhanın pulunu sıyırır..."
    scene: str             # "combat"
    hp: int
    max_hp: int
    spell_points: int
    level: int
    events: List[dict]     # Mechanical events list
    combat: Optional[dict] # Combat state if active

class NewSessionRequest(BaseModel):
    player_name: str
    player_class: str = "warrior"
    
class NewSessionResponse(BaseModel):
    session_id: str
    narrative: str  # Opening scene narration
    player: dict
```

---

## 7. Implementation Order

1. `engine/api/action_parser.py` (ActionParser, ParsedAction, ActionIntent)
2. `engine/api/game_session.py` (GameSession dataclass)
3. `engine/api/game_engine.py` (GameEngine orchestrator)
4. `engine/api/models.py` (Pydantic request/response models)
5. `engine/api/routes.py` (FastAPI router)
6. `main.py` (FastAPI app entry point)
7. Tests for each module
8. Integration test (full request → response flow)

---

## 8. Dependencies

```toml
fastapi>=0.110.0
uvicorn>=0.27.0
pydantic>=2.0.0
```

---

## 9. Success Metrics
- [ ] ActionParser: 90%+ correct intent on test phrases
- [ ] Full action loop < 100ms (without LLM)  
- [ ] 95%+ test coverage
- [ ] OpenAPI docs auto-generated (/docs)
- [ ] Session create → action → narrative works end-to-end
