# PRD: Campaign Generator
**Project:** Ember RPG  
**Phase:** 6  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Implemented  

---

## 1. Purpose

The Campaign Generator creates procedural story arcs — chains of quests, world events, and narrative premises that give the player a sense of progression beyond individual encounters. Each arc has a beginning (premise), middle (quest chain), and end (arc completion). The system is seed-based and deterministic, allowing campaigns to be replayed or shared.

---

## 2. Scope

**In scope:**
- Quest data model (objectives, rewards, status FSM)
- Quest types: KILL, FETCH, EXPLORE, DIALOGUE, SURVIVE, ESCORT
- QuestObjective progress tracking
- WorldEvent model (choices, outcomes)
- StoryArc (ordered quest list + world events)
- CampaignGenerator (seed-based arc + side quest generation)
- CampaignManager (arc registry, objective completion, reward dispatch)

**Out of scope:**
- Quest UI / dialogue presentation (→ DM Agent / Frontend)
- Persistent campaign save/load (→ future Database phase)
- Branching narrative trees (→ future advanced campaign system)
- Quest failure conditions beyond explicit `fail()` call

---

## 3. Functional Requirements

**FR-01:** `QuestObjective.progress(n)` increments `current_count` by n, capped at `required_count`. Returns True on the turn it reaches completion, False otherwise.

**FR-02:** Once a `QuestObjective` is `completed=True`, subsequent `progress()` calls return False and do not change state.

**FR-03:** `Quest.is_complete()` returns True only when ALL objectives have `completed=True`.

**FR-04:** `Quest.activate()` transitions status from AVAILABLE → ACTIVE. Has no effect if status is not AVAILABLE.

**FR-05:** `Quest.complete()` sets status to COMPLETED and returns the rewards dict.

**FR-06:** `StoryArc.advance()` moves to the next quest (activates it) and returns it. Returns None and sets `arc.completed=True` when no quests remain.

**FR-07:** `CampaignGenerator.generate_arc(num_quests=3)` returns a `StoryArc` where the first quest is already ACTIVE, and subsequent quests are AVAILABLE.

**FR-08:** Two calls to `CampaignGenerator(seed=N).generate_arc()` with the same seed produce arcs with identical premises and quest titles (determinism).

**FR-09:** `CampaignManager.complete_objective(arc_id, quest_id, target, amount)` progresses matching objectives; if the quest completes, calls `arc.advance()` and returns the rewards dict.

**FR-10:** `WorldEvent.trigger()` marks `triggered=True` and returns the event description.

**FR-11:** `StoryArc.random_event(rng)` returns a random untriggered WorldEvent and triggers it. Returns None if all events are triggered.

**FR-12:** `CampaignManager.active_quests()` returns all quests with status=ACTIVE across all registered arcs.

---

## 4. Data Structures

```python
class QuestStatus(Enum):
    AVAILABLE | ACTIVE | COMPLETED | FAILED

class QuestType(Enum):
    KILL | FETCH | ESCORT | EXPLORE | DIALOGUE | SURVIVE

class EventType(Enum):
    AMBUSH | DISCOVERY | NPC_ENCOUNTER | WEATHER | PLOT_TWIST | REWARD | TRAP

@dataclass
class QuestObjective:
    description: str
    target: str
    required_count: int = 1
    current_count: int = 0
    completed: bool = False

@dataclass
class Quest:
    id: str
    title: str
    description: str
    quest_type: QuestType
    giver: str
    objectives: List[QuestObjective]
    rewards: dict                    # {"gold": int, "xp": int, "items": [...]}
    status: QuestStatus = AVAILABLE
    location: str = "Unknown"
    difficulty: int = 1              # 1–5

@dataclass
class WorldEvent:
    event_type: EventType
    title: str
    description: str
    options: List[str] = []
    outcomes: Dict[int, str] = {}    # option_index → outcome_text
    triggered: bool = False

@dataclass
class StoryArc:
    id: str
    title: str
    premise: str
    quests: List[Quest]
    world_events: List[WorldEvent]
    completed: bool = False
    current_quest_idx: int = 0
```

---

## 5. Public API

### `QuestObjective.progress(amount=1) -> bool`
Returns True exactly once — the call that completes the objective. Idempotent after completion.

### `QuestObjective.progress_text() -> str`
Returns `"{current}/{required}"` format string.

### `Quest.activate() -> None`
AVAILABLE → ACTIVE only. Silent no-op on other statuses.

### `Quest.is_complete() -> bool`
Returns `all(obj.completed for obj in objectives)`.

### `Quest.complete() -> dict`
Sets COMPLETED, returns rewards dict.

### `Quest.fail() -> None`
Sets FAILED regardless of current status.

### `Quest.summary() -> str`
One-line: `[STATUS] Title: obj (X/Y); ...`

### `StoryArc.current_quest() -> Optional[Quest]`
Returns `quests[current_quest_idx]` or None.

### `StoryArc.advance() -> Optional[Quest]`
Increments index, activates next quest, returns it. Sets `completed=True` if exhausted.

### `StoryArc.random_event(rng) -> Optional[WorldEvent]`
Random choice from untriggered events; triggers it; returns it. None if all triggered.

### `CampaignGenerator(seed=0).generate_arc(title=None, num_quests=3, location="Unknown") -> StoryArc`
Generates mixed-type quest chain. First quest is ACTIVE. Arc has 2 world events.

### `CampaignGenerator.generate_side_quest(location, difficulty=1) -> Quest`
Single quest for use outside an arc.

### `CampaignManager.start_arc(arc) -> StoryArc`
Registers arc; returns it.

### `CampaignManager.complete_objective(arc_id, quest_id, target, amount=1) -> Optional[dict]`
- Returns None if arc/quest not found or quest not ACTIVE
- Progresses matching objectives
- Returns rewards dict if quest completes (and auto-advances arc)

### `CampaignManager.active_quests() -> List[Quest]`
All ACTIVE quests across all arcs.

### `CampaignManager.available_quests() -> List[Quest]`
All AVAILABLE quests across all arcs.

---

## 6. Acceptance Criteria

**AC-01 [FR-01]:** `QuestObjective("kill", "goblin", 3).progress(2)` → current_count=2, returns False.

**AC-02 [FR-01]:** `QuestObjective("kill", "goblin", 1).progress(1)` → completed=True, returns True.

**AC-03 [FR-01]:** `progress(10)` on `required_count=2` → current_count==2 (clamped).

**AC-04 [FR-02]:** After completion, `progress(1)` returns False and `current_count` unchanged.

**AC-05 [FR-03]:** `Quest.is_complete()` with one incomplete objective → False.

**AC-06 [FR-03]:** After all objectives completed → `is_complete()` True.

**AC-07 [FR-04]:** `quest.activate()` on AVAILABLE → status=ACTIVE.

**AC-08 [FR-04]:** `quest.activate()` on COMPLETED → status unchanged.

**AC-09 [FR-05]:** `quest.complete()` → status=COMPLETED, returns dict with "gold" key.

**AC-10 [FR-06]:** `arc.advance()` returns quest[1] and activates it; second `advance()` from arc of 2 quests returns None and sets `arc.completed=True`.

**AC-11 [FR-07]:** Generated arc: `quests[0].status == ACTIVE`, `quests[1].status == AVAILABLE`.

**AC-12 [FR-08]:** `CampaignGenerator(seed=7).generate_arc().premise == CampaignGenerator(seed=7).generate_arc().premise`.

**AC-13 [FR-09]:** `complete_objective` with wrong arc_id → None.

**AC-14 [FR-09]:** `complete_objective` on AVAILABLE (not ACTIVE) quest → None.

**AC-15 [FR-09]:** Completing all objectives returns rewards dict with "gold" and "xp" keys.

**AC-16 [FR-09]:** After quest completes, `arc.current_quest_idx` increments.

**AC-17 [FR-10]:** `event.trigger()` → `event.triggered=True`, returns description string.

**AC-18 [FR-11]:** `random_event()` with no untriggered events → None.

**AC-19 [FR-12]:** `active_quests()` returns exactly 1 quest after generating a 3-quest arc (only first is active).

---

## 7. Performance Requirements

- `generate_arc(num_quests=5)`: < 10ms
- `complete_objective()`: < 1ms

---

## 8. Error Handling

- `complete_objective()` with unknown arc_id or quest_id → return None (no exception)
- `Quest.complete()` called twice → idempotent (status stays COMPLETED, returns same rewards)
- `generate_arc(num_quests=10)` → capped at available templates (no exception, returns max available)

---

## 9. Integration Points

- **Upstream:** `GameEngine` checks `CampaignManager.active_quests()` to detect kill/fetch progress
- **Downstream:** `DMAIAgent` uses quest description in narrative context; `NPC.quest` field references quest titles
- **API:** Future `GET /game/session/{id}/quests` endpoint returns active quest list

---

## 10. Test Coverage Target

- Minimum: **95%** on `engine/campaign/__init__.py`
- Must test: all QuestStatus transitions, multi-objective quests, arc advance + completion, CampaignManager reward dispatch, determinism

---

## Changelog

- 2026-03-23: Initial version written to PRD standard (post-implementation)
