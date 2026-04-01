# PRD: NPC Agent System
**Project:** Ember RPG  
**Phase:** 5  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Implemented  

---

## 1. Purpose

The NPC Agent System gives non-player characters personality, memory, and contextual responses. Each NPC has a role archetype, a disposition toward the player, an inventory/quest, and a reputation memory. NPCs respond differently based on what the player says, their own personality, and accumulated interaction history. A pluggable LLM backend enables rich dialogue; template fallback ensures offline functionality.

---

## 2. Scope

**In scope:**
- NPC data model (name, role, disposition, personality, memory)
- Disposition-based greetings (5 levels: HOSTILE → ALLIED)
- Role-based personality lines (8 archetypes)
- Keyword-driven contextual reactions (trade, quest, info, reputation)
- Reputation system (-100 to +100, clamped)
- Event memory (last 10 interactions per NPC)
- LLM prompt builder
- NPCManager (registry, find, interact, spawn defaults)

**Out of scope:**
- Full branching dialogue trees (→ future Advanced Dialogue phase)
- NPC combat AI (→ AI Tactics phase)
- NPC pathfinding / movement (→ future AI phase)
- Persistent NPC memory across sessions (→ Database phase)

---

## 3. Functional Requirements

**FR-01:** `NPC.greet()` returns a non-empty string specific to the NPC's current disposition.

**FR-02:** `NPC.react_to_player(input)` returns a contextual response based on trade/quest/info keywords and reputation.

**FR-03:** An NPC with `disposition=HOSTILE` always refuses to cooperate, regardless of player input.

**FR-04:** `NPCMemory.add_event()` stores events and trims to `MAX_EVENTS=10`.

**FR-05:** `NPCMemory.adjust_reputation(delta)` clamps result to [-100, 100].

**FR-06:** `NPC.build_prompt()` returns a string containing the NPC's name, role, disposition, reputation, and recent events.

**FR-07:** `NPCManager.find(name)` supports case-insensitive exact and partial matching.

**FR-08:** `NPCManager.interact(npc, input)` marks `has_met_player=True` on first interaction and records the exchange in memory.

**FR-09:** When an LLM callable is provided to `NPCManager.interact()`, it is called with `build_prompt()` output and the result returned verbatim.

**FR-10:** `NPCManager.spawn_default_npcs(location)` creates a Barkeep (with quest + inventory) for inn/tavern locations and always creates a Guard.

---

## 4. Data Structures

```python
class Disposition(Enum):
    HOSTILE | UNFRIENDLY | NEUTRAL | FRIENDLY | ALLIED

class NPCRole(Enum):
    MERCHANT | GUARD | INNKEEPER | QUEST_GIVER | VILLAIN | ALLY | COMMONER | MONSTER

@dataclass
class NPCMemory:
    player_name: Optional[str] = None
    events: List[str] = []       # capped at MAX_EVENTS=10
    reputation: int = 0          # -100 to 100
    has_met_player: bool = False

@dataclass
class NPC:
    name: str
    role: NPCRole = COMMONER
    disposition: Disposition = NEUTRAL
    personality: str = "..."
    location: str = "Unknown"
    memory: NPCMemory
    inventory: List[str] = []
    quest: Optional[str] = None
```

---

## 5. Public API

### `NPC.greet() -> str`
Returns disposition-keyed greeting string containing NPC name.

### `NPC.react_to_player(player_input: str) -> str`
Priority order: HOSTILE check → trade keywords → quest keywords → info keywords → reputation → personality fallback.

### `NPC.build_prompt(player_input: str) -> str`
Multi-line LLM prompt with: name, role, personality, disposition, reputation, last 3 events, player input.

### `NPCManager.add_npc(npc) -> None`
Registers NPC by lowercased name key.

### `NPCManager.find(name: str) -> Optional[NPC]`
Exact match first, then partial. Case-insensitive.

### `NPCManager.interact(npc, player_input, llm=None) -> str`
Marks met, records input event, generates response (LLM or template), records response event.

### `NPCManager.spawn_default_npcs(location: str) -> List[NPC]`
Returns list of spawned NPCs (Barkeep for inn/tavern/town + always Guard).

---

## 6. Acceptance Criteria

**AC-01 [FR-01]:** `NPC(name="Test", disposition=d).greet()` returns non-empty string containing "Test" for all 5 Disposition values.

**AC-02 [FR-02]:** NPC with `inventory=["Sword"]`, react to "satın almak istiyorum" → response contains "Sword".

**AC-03 [FR-02]:** NPC with `quest="Fetch the stone."`, react to "görev var mı" → response contains "Fetch the stone."

**AC-04 [FR-03]:** NPC with `disposition=HOSTILE`, react to any input → response does not offer help (contains refusal language).

**AC-05 [FR-04]:** Adding 15 events to NPCMemory → `len(events) == 10`.

**AC-06 [FR-05]:** `adjust_reputation(200)` → reputation == 100. `adjust_reputation(-200)` → reputation == -100.

**AC-07 [FR-05]:** `adjust_reputation(20)` then `adjust_reputation(-10)` → reputation == 10.

**AC-08 [FR-06]:** `build_prompt("hello")` output contains NPC name, role value, and "hello".

**AC-09 [FR-07]:** `find("GUARD")` and `find("guard")` both return same NPC.

**AC-10 [FR-07]:** `find("town")` with NPC named "Town Guard" → returns the NPC (partial match).

**AC-11 [FR-07]:** `find("nobody")` → returns None.

**AC-12 [FR-08]:** First `interact()` call → `npc.memory.has_met_player == True`.

**AC-13 [FR-08]:** After `interact()`, `len(npc.memory.events) >= 1`.

**AC-14 [FR-09]:** `interact(npc, "hello", llm=mock_fn)` → returns exactly mock_fn's return value.

**AC-15 [FR-10]:** `spawn_default_npcs("Taş Köprü Meyhanesi")` → includes NPC named "Barkeep" with non-None `quest` and non-empty `inventory`.

**AC-16 [FR-10]:** `spawn_default_npcs(any_location)` → always includes NPC named "Guard".

---

## 7. Performance Requirements

- `react_to_player()` (no LLM): < 1ms
- `build_prompt()`: < 1ms
- `find()` with 100 NPCs: < 1ms

---

## 8. Error Handling

- `find()` on empty NPCManager → returns None
- `react_to_player("")` (empty input) → returns a valid string (personality fallback)
- `build_prompt()` with no memory events → returns prompt with "(none)" in history section

---

## 9. Integration Points

- **Upstream:** `GameEngine._handle_talk()` looks up NPC via `NPCManager.find()` and calls `interact()`
- **Downstream:** `DMAIAgent` may use NPC responses as dialogue events
- **API:** Future `POST /game/session/{id}/npc/{name}/talk` endpoint

---

## 10. Test Coverage Target

- Minimum: **95%** on `engine/npc/__init__.py`
- Must test: all dispositions, all roles, LLM path, template path, memory trimming, reputation clamping, find partial/case, spawn defaults

---

## Changelog

- 2026-03-23: Initial version written to PRD standard (post-implementation)
