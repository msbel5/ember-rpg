# PRD: Consequence Cascading System
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

## 1. Overview
Every player action ripples through the world. Kill a merchant → prices rise → town reputation drops → guards become hostile → new quest appears to restore order. This is the system that makes Ember RPG feel alive.

## 2. Architecture

```
Player Action
    ↓
Action Classifier (what type of action?)
    ↓
Direct Consequence (immediate effect)
    ↓
Cascade Engine (check all trigger rules)
    ↓
World State Update
    ↓
NPC Memory Update
    ↓
Quest System Check (new quests? quest failures?)
    ↓
AI Context Refresh
```

## 3. Consequence Rules

### Rule Format
```python
class ConsequenceRule:
    trigger: str          # "npc_killed", "quest_completed", "item_stolen"
    conditions: dict      # {"npc_role": "merchant", "faction": "town_guild"}
    effects: list[Effect] # list of world state changes
    delay: int = 0        # game hours before effect triggers
    probability: float = 1.0  # chance of triggering
```

### Core Rules

#### Violence Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Kill NPC | role=merchant | Prices +30% in location | 0 |
| Kill NPC | role=merchant | Faction reputation -20 | 0 |
| Kill NPC | witnessed=True | Guards alerted | 1 hour |
| Kill NPC | witnessed=True | Bounty placed on player | 24 hours |
| Kill NPC | role=quest_giver | Related quests fail | 0 |
| Attack NPC | any | NPC disposition -50 | 0 |
| Attack NPC | faction=guards | All guards hostile | 0 |

#### Social Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Help NPC | any | NPC disposition +15 | 0 |
| Help NPC | role=merchant | Discount 10% | 0 |
| Lie to NPC | detected=True | NPC disposition -20, trust broken | 0 |
| Steal from NPC | detected=True | Guards alerted, reputation -15 | 0 |
| Steal from NPC | detected=False | Item obtained, no immediate effect | 0 |
| Bribe NPC | any | NPC disposition +10, gold lost | 0 |

#### Quest Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Quest complete | reward_type=faction | Faction reputation +15 | 0 |
| Quest complete | has_choice | World flag set based on choice | 0 |
| Quest fail | has_penalty | Reputation -10 | 0 |
| Quest ignore | timeout=True | NPC disappointment, new consequence | 7 days |

#### Economic Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Buy all stock | item_type=weapons | Price +20% next restock | 24 hours |
| Sell rare item | to=merchant | Merchant sells it to others | 48 hours |
| Flood market | same_item > 5 | Price crash for that item | 0 |

## 4. Cascade Engine

```python
class CascadeEngine:
    rules: list[ConsequenceRule]
    pending_effects: list[PendingEffect]  # delayed effects

    def process_action(self, action, world_state):
        triggered = []

        for rule in self.rules:
            if rule.matches(action):
                if rule.delay == 0:
                    effects = rule.apply(world_state)
                    triggered.extend(effects)
                else:
                    self.pending_effects.append(
                        PendingEffect(rule, trigger_time=world_state.time + rule.delay)
                    )

        # Check if any effects trigger further cascades
        for effect in triggered:
            self.process_action(effect.as_action(), world_state)  # recursive!

        return triggered

    def tick(self, world_state):
        """Called on time passage — check delayed effects"""
        ready = [e for e in self.pending_effects if e.trigger_time <= world_state.time]
        for effect in ready:
            effect.apply(world_state)
            self.pending_effects.remove(effect)
```

## 5. Acceptance Criteria

### AC-1: Direct Consequences
- [ ] Kill merchant → prices rise immediately
- [ ] Help NPC → disposition increases
- [ ] Steal detected → guards alerted

### AC-2: Delayed Consequences
- [ ] Witnessed kill → bounty after 24 game hours
- [ ] Ignored quest → NPC disappointment after 7 days
- [ ] Time tick processes all pending effects

### AC-3: Cascade Chains
- [ ] Kill merchant → prices rise → poor NPCs complain → new quest to find new merchant
- [ ] At least 3-deep cascade chain works correctly
- [ ] No infinite loops (max cascade depth = 5)

### AC-4: World State Integration
- [ ] All consequences update world state ledger
- [ ] AI DM narrative reflects consequences
- [ ] NPCs reference consequences in dialogue

### AC-5: Save/Load
- [ ] Pending delayed effects saved
- [ ] Consequence history preserved
- [ ] Rules state preserved

### AC-6: API Endpoints
- [ ] GET /game/session/{id}/consequences — active consequences
- [ ] GET /game/session/{id}/pending — delayed effects queue

## 6. Test Scenarios
1. Kill merchant → verify price increase + reputation drop
2. Wait 24 game hours after witnessed kill → verify bounty appears
3. Complete quest → verify faction reputation + world flag changes
4. Chain: help merchant → get discount → buy cheap → sell expensive elsewhere
5. Save/load with pending delayed effects → verify they still trigger
6. Max cascade depth → verify no infinite loop

---

## Header
**Project:** Ember RPG
**Phase:** 3c
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-23
**Status:** Draft

---

## 7. Functional Requirements

**FR-01:** `CascadeEngine.process_action(action, world_state)` must evaluate all registered rules, apply matching rules with `delay=0` immediately, and queue rules with `delay>0` as `PendingEffect`.

**FR-02:** Recursive cascade chains must be limited to a maximum depth of 5 to prevent infinite loops.

**FR-03:** `ConsequenceRule` with `probability < 1.0` must only trigger with the specified probability (random check per evaluation).

**FR-04:** `CascadeEngine.tick(world_state)` must process all `PendingEffect` entries whose `trigger_time <= world_state.time` and remove them after application.

**FR-05:** Killing an NPC with `role=merchant` must immediately trigger: prices +30% in location AND faction reputation -20.

**FR-06:** A witnessed kill must queue a bounty `PendingEffect` with `delay=24` game hours.

**FR-07:** `GET /game/session/{id}/consequences` must return a list of active (applied) consequences for the session.

**FR-08:** `GET /game/session/{id}/pending` must return a list of queued pending effects with their trigger times.

**FR-09:** Pending effects must be included in save/load serialization so they survive session restart.

**FR-10:** Each consequence application must append an entry to `world_state.history`.

---

## 8. Data Structures

```python
@dataclass
class ConsequenceRule:
    trigger: str           # e.g. "npc_killed", "quest_completed"
    conditions: dict       # e.g. {"npc_role": "merchant"}
    effects: List[Effect]  # World state changes to apply
    delay: int = 0         # Game hours before effect fires
    probability: float = 1.0  # 0.0 - 1.0

@dataclass
class PendingEffect:
    rule: ConsequenceRule
    trigger_time: int      # Game time when effect fires (world_state.time + delay)

class CascadeEngine:
    rules: List[ConsequenceRule]
    pending_effects: List[PendingEffect]

    def process_action(self, action, world_state, depth: int = 0) -> List: ...
    def tick(self, world_state) -> None: ...
```

---

## 9. Public API

```python
class CascadeEngine:
    def __init__(self, rules: List[ConsequenceRule])

    def process_action(self, action, world_state, depth: int = 0) -> List[Effect]:
        """Evaluates all rules against action. Applies immediate effects, queues delayed.
        Recursive up to depth=5. Returns list of triggered effects."""

    def tick(self, world_state) -> None:
        """Processes all pending effects whose trigger_time <= world_state.time.
        Removes processed effects from queue."""
```

---

## 10. Acceptance Criteria (Standard Format)

AC-01 [FR-01]: Given a CascadeEngine with a merchant-kill rule, when `process_action({"type": "npc_killed", "npc_role": "merchant"}, world_state)` is called, then location prices increase by 30% and faction reputation decreases by 20 in world_state.

AC-02 [FR-02]: Given a set of rules that could cascade indefinitely, when `process_action()` is called, then the recursion stops at depth 5 and no infinite loop occurs.

AC-03 [FR-03]: Given a rule with `probability=0.0`, when `process_action()` evaluates it, then the rule never fires.

AC-04 [FR-04]: Given a pending effect with `trigger_time=100` and `world_state.time=99`, when `tick()` is called, then the effect does not fire. When `world_state.time=100`, then the effect fires and is removed from the queue.

AC-05 [FR-05]: Given a kill action with `witnessed=True`, when processed, then a bounty `PendingEffect` appears in the queue with `trigger_time = world_state.time + 24`.

AC-06 [FR-09]: Given a session with pending effects, when saved and reloaded, then pending effects are present in the reloaded session and fire at the correct time.

---

## 11. Performance Requirements

- `process_action()` for 20 rules: < 10ms
- `tick()` for 50 pending effects: < 5ms
- Cascade chain depth 5: < 50ms total

---

## 12. Error Handling

| Condition | Behavior |
|---|---|
| Cascade depth > 5 | Stop recursion silently, log warning |
| Rule with invalid effect type | Skip rule, log error |
| `tick()` called with no pending effects | No-op, no error |
| Missing world_state field | Rule condition check returns False (no match) |

---

## 13. Integration Points

- **World State (Phase 3a):** All effects mutate `world_state` fields (prices, reputation, flags)
- **NPC Memory (Phase 3b):** Kill/social consequences update NPC dispositions
- **Quest System (Phase 4):** Quest completion/failure triggers consequence rules
- **DM Agent (Module 6):** Receives updated world context after cascade for narrative
- **Save/Load:** `pending_effects` serialized with session

---

## 14. Test Coverage Target

- **Target:** ≥ 90% line coverage
- **Must cover:** immediate effect, delayed effect, cascade chain, max depth stop, probability=0 no-fire, probability=1 always-fires, tick with expired and non-expired effects, save/load round-trip of pending effects
