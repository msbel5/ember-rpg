# PRD: DM Agent
**Project:** Ember RPG  
**Phase:** 2 — Module 6  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Implemented  

---

## 1. Purpose

The DM Agent is the narrative engine of Ember RPG. It translates raw mechanical game events (combat hits, discoveries, level-ups) into immersive prose that players read as story. It maintains scene context, tracks narrative history, manages scene-type transitions, and provides a pluggable LLM backend with a template fallback for offline use.

---

## 2. Scope

**In scope:**
- Converting `DMEvent` objects into narrative text
- Tracking scene type (exploration, combat, dialogue, rest, cutscene)
- Maintaining a capped event history (last N events) for LLM context
- Building structured prompts for LLM backends
- Template-based fallback narration (no LLM required)
- Scene-type transition validation

**Out of scope:**
- Parsing player natural language input (→ ActionParser)
- Combat resolution mechanics (→ CombatManager)
- Persistent storage of narrative logs (→ future Campaign Archive)
- Multiplayer narrative synchronization

---

## 3. Functional Requirements

**FR-01:** The DM Agent must narrate any `DMEvent` and return a non-empty string.

**FR-02:** When an LLM callable is provided, the DM Agent must call it with a structured prompt and return its response verbatim.

**FR-03:** When no LLM is provided, the DM Agent must use per-event-type template strings to generate narrative.

**FR-04:** `DMContext` must maintain a history list capped at `max_history` entries (default 10).

**FR-05:** `DMContext` must support scene-type transitions and reject invalid transitions (e.g., COMBAT → CUTSCENE) according to `VALID_TRANSITIONS`.

**FR-06:** `DMContext.advance_turn()` must increment the turn counter by 1 on each call.

**FR-07:** `DMContext.party_summary()` must return a string listing each party member's name, HP, and level.

**FR-08:** The LLM prompt must include: scene type, location, last 3 history entries, and the triggering event description.

**FR-09:** `DMAIAgent` must be stateless — all state lives in `DMContext`, not in the agent itself.

---

## 4. Data Structures

```python
class EventType(Enum):
    ENCOUNTER = "encounter"
    DISCOVERY = "discovery"
    DIALOGUE = "dialogue"
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    REST = "rest"
    LEVEL_UP = "level_up"
    ITEM_FOUND = "item_found"

class SceneType(Enum):
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    REST = "rest"
    CUTSCENE = "cutscene"

@dataclass
class DMEvent:
    type: EventType
    description: str          # Raw mechanical description
    data: dict = {}           # Optional structured payload

@dataclass
class DMContext:
    scene_type: SceneType
    location: str
    party: List[Character]
    history: List[DMEvent] = []
    turn: int = 0
    max_history: int = 10

class DMAIAgent:
    def narrate(event: DMEvent, context: DMContext, llm=None) -> str
    def transition(context: DMContext, new_scene: SceneType) -> bool
    def build_prompt(event: DMEvent, context: DMContext) -> str
    def party_summary(context: DMContext) -> str
```

---

## 5. Public API

### `DMAIAgent.narrate(event, context, llm=None) -> str`
- **Pre:** `event` is a valid `DMEvent`, `context` is a valid `DMContext`
- **Post:** Returns a non-empty narrative string; appends event to context.history
- **Behavior:** If `llm` provided → `llm(build_prompt(event, context))`; else → template format

### `DMAIAgent.transition(context, new_scene) -> bool`
- **Pre:** `new_scene` is a `SceneType`
- **Post:** If transition is valid, updates `context.scene_type`; returns True. If invalid, returns False without mutation.

### `DMAIAgent.build_prompt(event, context) -> str`
- **Post:** Returns a multi-line string with scene, location, history, and event description

### `DMContext.advance_turn() -> None`
- **Post:** `context.turn` incremented by 1

### `DMContext.party_summary() -> str`
- **Post:** Returns comma-separated "Name HP/MaxHP Lv.N" entries

---

## 6. Acceptance Criteria

**AC-01 [FR-01]:** Given any valid `DMEvent`, `narrate()` returns a string with `len > 0`.

**AC-02 [FR-02]:** Given a mock LLM callable that returns "LLM output", `narrate()` returns exactly "LLM output".

**AC-03 [FR-03]:** Given no LLM, `narrate()` returns a string that contains the event's description text.

**AC-04 [FR-04]:** Given 15 consecutive events added to a `DMContext` with `max_history=10`, `len(context.history) == 10`.

**AC-05 [FR-05]:** Given `scene_type=EXPLORATION`, `transition(COMBAT)` returns True and updates scene. `transition(CUTSCENE)` from EXPLORATION returns False.

**AC-06 [FR-06]:** Given initial `turn=0`, after calling `advance_turn()` three times, `turn == 3`.

**AC-07 [FR-07]:** Given a party of two characters (Aria HP 20/20 Lv1, Kael HP 12/12 Lv2), `party_summary()` contains both names with their HP and level.

**AC-08 [FR-08]:** `build_prompt()` output contains the location string and event description.

**AC-09 [FR-09]:** Two `DMAIAgent` instances created independently share no state; each call to `narrate()` is idempotent given the same context.

---

## 7. Performance Requirements

- `narrate()` without LLM: < 1ms
- `build_prompt()`: < 1ms

---

## 8. Error Handling

- `narrate()` with `None` event: raises `TypeError`
- `transition()` to invalid SceneType value: raises `ValueError`
- Empty `party` in `party_summary()`: returns empty string `""`

---

## 9. Integration Points

- **Upstream:** `CombatManager` (generates ENCOUNTER/COMBAT_END events), `ProgressionSystem` (generates LEVEL_UP events), `GameEngine` (generates all event types)
- **Downstream:** LLM backend (OpenAI, Ollama, or mock); `ActionResponse` in API layer

---

## 10. Test Coverage Target

- Minimum: **95%** line coverage on `dm_agent.py`
- Must test: all 8 EventType templates, LLM path, non-LLM path, history trimming, all valid/invalid transitions

---

## Changelog

- 2026-03-23: Initial version (post-implementation, retroactively documented to standard)
