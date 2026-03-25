# PRD: World State Ledger
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

## 1. Overview
A persistent, structured data store tracking ALL changes to the game world. Every action the player takes modifies this ledger. The AI DM reads from it to generate contextually aware narrative.

## 2. Problem Statement
Current AI RPGs (AI Dungeon, NovelAI) have no persistent world state. The AI "forgets" that you burned a village or killed a merchant. BG3 has world state but it's pre-scripted. We need dynamic, emergent world state.

## 3. Architecture

```
Player Action → Game Engine → World State Update → AI Context
                                    ↓
                            Consequence Cascade
                                    ↓
                            NPC Memory Update
                                    ↓
                            Quest State Change
```

## 4. Data Model

### WorldState (SQLite or JSON)
```python
class WorldState:
    game_id: str
    current_time: GameTime  # day, hour, minute

    # Locations
    locations: dict[str, LocationState]
    # {location_id: {discovered: bool, cleared: bool, hostile: bool, ...}}

    # NPCs
    npc_states: dict[str, NPCState]
    # {npc_id: {alive: bool, location: str, disposition: int, ...}}

    # Factions
    factions: dict[str, FactionState]
    # {faction_id: {reputation: int, hostile: bool, active_quests: list}}

    # Quests
    quest_log: list[QuestEntry]
    # [{quest_id, status, objectives, rewards, consequences}]

    # Global flags
    flags: dict[str, Any]
    # {"bridge_destroyed": True, "plague_cured": False, ...}

    # Event history (append-only log)
    history: list[WorldEvent]
    # [{timestamp, event_type, description, affected_entities}]
```

### LocationState
```python
class LocationState:
    id: str
    name: str
    discovered: bool = False
    cleared: bool = False  # all enemies defeated
    hostile: bool = False
    loot_collected: bool = False
    npcs_present: list[str] = []
    items_on_ground: list[str] = []
    custom_flags: dict = {}
```

### NPCState
```python
class NPCState:
    id: str
    alive: bool = True
    location: str
    disposition: int = 0  # -100 (hostile) to +100 (devoted)
    met_player: bool = False
    quest_giver: bool = False
    merchant: bool = False
    inventory: list[str] = []
    dialogue_flags: dict = {}
```

## 5. State Update Rules

### On Player Action:
| Action | State Update |
|--------|-------------|
| Kill NPC | npc.alive = False, faction.reputation -= 20, history.append() |
| Complete quest | quest.status = "completed", rewards applied, flags set |
| Enter new area | location.discovered = True |
| Clear dungeon | location.cleared = True, loot available |
| Help NPC | npc.disposition += 15, faction.reputation += 5 |
| Steal from merchant | npc.disposition -= 30, faction.reputation -= 10 |
| Destroy building | location.custom_flags["destroyed"] = True |

### On Time Passage:
| Trigger | Effect |
|---------|--------|
| 24 hours since kill | Guards investigate if witnessed |
| 7 days since quest offered | Quest expires if not started |
| NPC disposition < -50 | NPC refuses to interact |
| Faction reputation < -30 | Faction becomes hostile |

## 6. AI Context Generation
When AI DM generates narrative, inject relevant world state:

```python
def build_ai_context(world_state, current_scene):
    context = []

    # Recent events (last 5)
    for event in world_state.history[-5:]:
        context.append(f"Recently: {event.description}")

    # Current location state
    loc = world_state.locations[current_scene.location]
    if loc.cleared:
        context.append("This area has been cleared of enemies.")

    # Nearby NPC dispositions
    for npc_id in loc.npcs_present:
        npc = world_state.npc_states[npc_id]
        if npc.disposition < -20:
            context.append(f"{npc_id} is hostile toward the player.")

    # Active quests in this area
    for quest in world_state.quest_log:
        if quest.location == current_scene.location:
            context.append(f"Active quest: {quest.description}")

    return "\n".join(context)
```

## 7. Acceptance Criteria

### AC-1: State Persistence
- [ ] World state survives game save/load
- [ ] All NPC deaths are permanent
- [ ] Quest completions are permanent
- [ ] Location discovery is permanent

### AC-2: State Updates
- [ ] Every player action that changes the world updates the ledger
- [ ] History log is append-only (never deleted)
- [ ] State updates are atomic (no partial updates)

### AC-3: AI Context
- [ ] AI DM receives relevant world state in every prompt
- [ ] NPC dialogue changes based on disposition
- [ ] Dead NPCs never appear in scenes

### AC-4: Consequence Triggers
- [ ] Killing an NPC affects faction reputation
- [ ] Low reputation triggers hostile behavior
- [ ] Quest outcomes modify world flags

### AC-5: API Endpoints
- [ ] GET /game/session/{id}/world-state — full state dump
- [ ] GET /game/session/{id}/history — event log
- [ ] GET /game/session/{id}/factions — faction standings
- [ ] World state included in save/load

## 8. Dependencies
- Save/Load system (Phase 2) ✅ DONE
- Game session management ✅ DONE
- NPC system ✅ DONE

## 9. Test Scenarios
1. Kill merchant → verify merchant.alive = False, reputation decreased
2. Complete quest → verify quest.status, rewards, flag changes
3. Save/load → verify world state round-trip
4. AI context → verify dead NPC not mentioned
5. Time passage → verify timed consequences trigger
6. Concurrent sessions → verify session isolation

---

## Header
**Project:** Ember RPG
**Phase:** 3a
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-23
**Status:** Draft

---

## 10. Functional Requirements

**FR-01:** `WorldState` must persist all location discovery, NPC alive/dead state, faction reputation, quest log, and world flags across save/load.

**FR-02:** `WorldState.history` must be append-only — entries are never deleted.

**FR-03:** Every player action that changes the world must call the appropriate state update method before returning (atomic update per action).

**FR-04:** `build_ai_context(world_state, current_scene)` must return a context string including recent events (last 5), current location state, NPC dispositions, and active quests in the area.

**FR-05:** Dead NPCs (alive=False) must never appear in `build_ai_context()` output.

**FR-06:** Killing an NPC with `role=merchant` must reduce faction reputation by 20.

**FR-07:** `GET /game/session/{id}/world-state` must return the full WorldState as JSON.

**FR-08:** `GET /game/session/{id}/history` must return the append-only event log.

**FR-09:** `GET /game/session/{id}/factions` must return all faction standings with reputation scores.

**FR-10:** Session isolation must be guaranteed — two concurrent sessions must have independent WorldState instances.

---

## 11. Public API

```python
class WorldState:
    def update_npc(self, npc_id: str, **kwargs) -> None:
        """Updates NPCState fields. Appends WorldEvent to history."""

    def update_location(self, location_id: str, **kwargs) -> None:
        """Updates LocationState fields. Appends WorldEvent to history."""

    def update_faction(self, faction_id: str, reputation_delta: int) -> None:
        """Adjusts faction reputation by delta. Clamps to [-100, 100]."""

    def set_flag(self, flag: str, value: Any) -> None:
        """Sets a world flag. Appends to history."""

    def build_ai_context(self, current_scene: str) -> str:
        """Returns formatted context string for LLM prompt injection."""

    def to_dict(self) -> dict:
        """Full JSON-serializable snapshot."""

    @classmethod
    def from_dict(cls, data: dict) -> 'WorldState':
        """Reconstructs from snapshot."""
```

---

## 12. Acceptance Criteria (Standard Format)

AC-01 [FR-01]: Given a WorldState with an NPC killed and a quest completed, when `to_dict()` and `from_dict()` are called, then the restored state has `npc.alive=False` and `quest.status="completed"`.

AC-02 [FR-02]: Given a WorldState with 3 history entries, when `update_npc()` is called, then `len(history) == 4` and previous entries are unchanged.

AC-03 [FR-05]: Given `npc.alive = False`, when `build_ai_context()` is called for the NPC's location, then the output string does not contain the dead NPC's name or reference.

AC-04 [FR-06]: Given faction "town_guild" with reputation=50, when an NPC with role=merchant is killed, then `faction.reputation == 30`.

AC-05 [FR-07]: Given a running session, when `GET /game/session/{id}/world-state` is called, then it returns a JSON object with keys: locations, npc_states, factions, quest_log, flags, history.

AC-06 [FR-10]: Given two active sessions A and B, when session A kills an NPC, then session B's world state is unaffected.

---

## 13. Performance Requirements

- `build_ai_context()`: < 5ms
- `to_dict()` / `from_dict()`: < 10ms for typical game state (100 NPCs, 50 locations)
- `update_*` methods: < 1ms each
- `GET /world-state` API response: < 50ms

---

## 14. Error Handling

| Condition | Behavior |
|---|---|
| Unknown NPC ID in `update_npc()` | Creates new NPCState entry (upsert behavior) |
| Unknown faction ID in `update_faction()` | Creates new FactionState with reputation=delta |
| `from_dict()` missing optional fields | Uses defaults (dataclass field defaults) |
| Reputation outside [-100, 100] | Clamped automatically |

---

## 15. Integration Points

- **Consequence System (Phase 3c):** All cascade effects call WorldState update methods
- **NPC Memory (Phase 3b):** `npc_states.disposition` mirrors NPCMemory.relationship_score
- **DM Agent (Module 6):** `build_ai_context()` injected into every LLM narrative call
- **Campaign Generator (Phase 6):** Quest completions update quest_log via `update_quest()`
- **Save/Load:** `WorldState.to_dict()` / `from_dict()` used by save/load system

---

## 16. Test Coverage Target

- **Target:** ≥ 90% line coverage
- **Must cover:** history append-only invariant, dead NPC exclusion from context, faction reputation clamping, save/load round-trip, session isolation (two independent WorldState instances)
