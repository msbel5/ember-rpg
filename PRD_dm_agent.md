# PRD: AI DM Agent (Module 6)
**Project:** Ember RPG — FRP AI Game  
**Module:** Phase 2, Module 6  
**Date:** 2026-03-23  
**Status:** Planning → Implementation

---

## 1. Overview

**Purpose:** Implement AI Dungeon Master agent that generates narrative responses, manages game state, and drives story events.

**Scope:**
- DM context management (party state, current scene, history)
- Narrative event generation (encounter, exploration, dialogue triggers)
- Action resolution narration (combat results → story text)
- Scene state machine (exploration, combat, dialogue, rest)
- LLM prompt builder (structured prompts for any LLM backend)

**Out of Scope:**
- Actual LLM API calls (pluggable backend, tested with mock)
- NPC Agent (Module 7)
- Map generation (Module 8)

---

## 2. Requirements

### FR1: DM Context
- Track: scene_type, party, location, turn, history (last N events)
- `DMContext` dataclass

### FR2: Scene State Machine
- States: EXPLORATION, COMBAT, DIALOGUE, REST, TRANSITION
- Valid transitions between states

### FR3: Prompt Builder
- Given DMContext + trigger event → structured prompt string
- Prompt includes: party state, scene, recent history, instruction

### FR4: Event System
- `DMEvent`: type, description, data dict
- Event types: ENCOUNTER, DISCOVERY, DIALOGUE, COMBAT_START, COMBAT_END, REST, LEVEL_UP, ITEM_FOUND

### FR5: Narrative Hook
- `DMAIAgent.narrate(event, context)` → prompt string
- Pluggable LLM backend (mock for tests)

---

## 3. Data Model

```python
class SceneType(Enum):
    EXPLORATION = "exploration"
    COMBAT = "combat"
    DIALOGUE = "dialogue"
    REST = "rest"
    TRANSITION = "transition"

class EventType(Enum):
    ENCOUNTER = "encounter"
    DISCOVERY = "discovery"
    DIALOGUE = "dialogue"
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    REST = "rest"
    LEVEL_UP = "level_up"
    ITEM_FOUND = "item_found"

@dataclass
class DMEvent:
    type: EventType
    description: str
    data: dict = field(default_factory=dict)

@dataclass
class DMContext:
    scene_type: SceneType
    location: str
    party: List[Character]
    history: List[DMEvent]
    turn: int = 0
    max_history: int = 10

class DMAIAgent:
    def build_prompt(self, event: DMEvent, context: DMContext) -> str: ...
    def narrate(self, event: DMEvent, context: DMContext, llm=None) -> str: ...
    def transition(self, context: DMContext, new_scene: SceneType) -> bool: ...
```

---

## 4. Scene Transitions (valid)

```
EXPLORATION → COMBAT, DIALOGUE, REST, TRANSITION
COMBAT → EXPLORATION, TRANSITION
DIALOGUE → EXPLORATION, COMBAT
REST → EXPLORATION
TRANSITION → EXPLORATION, COMBAT, DIALOGUE, REST
```

---

## 5. Test Cases

### TC1: DMContext creation
- Create context with party, location, scene
- History starts empty, turn = 0

### TC2: Add events to history
- add_event trims to max_history
- Most recent events preserved

### TC3: Prompt building
- build_prompt returns non-empty string
- Contains party names, location, event description

### TC4: Scene transitions (valid)
- EXPLORATION → COMBAT: OK
- COMBAT → EXPLORATION: OK

### TC5: Scene transitions (invalid)
- REST → COMBAT: raises ValueError

### TC6: Narrate with mock LLM
- narrate() calls LLM with prompt
- Returns LLM response string

### TC7: Narrate without LLM (fallback)
- narrate() without LLM returns template narrative

---

## 6. Implementation Plan
1. Write tests (TDD)
2. Write dm_agent.py
3. Run + verify 95%+ coverage
4. Commit + push
