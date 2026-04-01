# PRD: Game State System V1
**Project:** Ember RPG
**Phase:** 1
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the top-level game state container synthesizing GemRB M16 (Game.cpp — party management, area loading, global variables, journal, world time, reputation, difficulty, formation) with Ember's campaign-first deterministic kernel. The `GameState` is the root object that ties together all subsystems: party, current area, loaded areas, global variables, time, reputation, journal, and difficulty settings. It is the single serialization target for save/load.

## 2. Scope

### In scope
- `GameState`: top-level container holding all runtime state
- Party management: up to 6 active party members, inactive NPCs pool
- Current area tracking with area cache (loaded areas in memory)
- Global variables: campaign-wide flags and counters for quest/dialog tracking
- Journal: player quest log with entries, quest stages, timestamps
- World time: game tick, hour, day, weather
- Reputation: party reputation (1-20), affects dialog, store prices, NPC reactions
- Difficulty settings: easy/normal/core/hard/insane with combat multipliers
- Party formation: movement formation (line, wedge, circle, scatter, custom)
- Save/load: full GameState serialization to dict for persistence
- Campaign metadata: campaign_id, seed, creation_date, play_time

### Out of scope
- Save file format on disk (handled by persistence layer)
- Multiplayer state synchronization
- Achievement tracking

## 3. Functional Requirements (FR)

**FR-01 (GameState):** Root container with: campaign_id, seed, party (list of actor_ids), inactive_npcs, current_area_id, loaded_areas (cache), global_variables, journal, world_time, reputation, difficulty, formation, play_time_ticks.

**FR-02 (Party Management):** `add_to_party(actor_id)`: add actor to party (max 6). `remove_from_party(actor_id)`: move to inactive pool. `swap_party_member(active_id, inactive_id)`: swap. Party order determines formation positions and Player1-6 references.

**FR-03 (Area Management):** `load_area(area_id)`: load AreaDef + AreaState into cache. `transition_to_area(area_id, position)`: set current_area_id, load if not cached, place party. Max cached areas (configurable, default 4). LRU eviction when cache full.

**FR-04 (Global Variables):** `dict[str, Any]` — set/get/check variables. Used by Dialog System and GameScript for quest tracking. Scopes: "GLOBAL" (campaign-wide), "LOCALS" (per-area), "MYAREA" (current area shortcut).

**FR-05 (Journal):** Ordered list of JournalEntry: text, quest_id, quest_stage, timestamp (world tick), entry_type (info/quest/done). `add_journal_entry()`, `get_quest_entries(quest_id)`, `get_latest_stage(quest_id)`.

**FR-06 (World Time):** `game_tick` (monotonic counter), `hour` (0-23, derived), `day` (counter), `weather` (clear/rain/snow/fog/storm). `advance_time(ticks)`: advance tick, update hour/day, trigger weather changes, trigger spawn schedules. Tick-to-hour conversion: 100 ticks = 1 game hour.

**FR-07 (Reputation):** Integer 1-20. Starts at 10. Modified by: quest completion (+1 to +3), evil actions (-1 to -5), stealing caught (-2), killing innocents (-5). Affects: store prices (via Store PRD), dialog options (via Dialog PRD), NPC willingness to join party.

**FR-08 (Difficulty):** Settings: easy (0.5x enemy damage, 2x player damage), normal (1x/1x), core (1x/1x, no auto-pause), hard (1.5x/0.75x), insane (2x/0.5x). Stored as `difficulty_level` and `damage_multiplier_enemy`/`damage_multiplier_party`.

**FR-09 (Formation):** Party formation for movement: line, wedge, circle, scatter, custom. Each formation defines relative offsets from leader for members 2-6. Used by Pathfinding when party moves together.

**FR-10 (Save/Load):** `GameState.to_dict()` produces complete serializable dict. `GameState.from_dict()` reconstructs full state. Must include ALL subsystem states: party actor records, area states, variables, journal, time, inventory.

**FR-11 (Campaign Seed):** Deterministic seed used for all RNG derivation. `derive_seed(base_seed, context_string)` produces sub-seeds for worldgen, combat, loot, etc. Ensures reproducibility.

## 4. Data Structures

```python
@dataclass
class JournalEntry:
    entry_id: str
    text: str
    quest_id: str = ""
    quest_stage: int = 0
    timestamp: int = 0       # World tick
    entry_type: str = "info" # "info" | "quest" | "done"

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry": ...


@dataclass
class WorldTime:
    game_tick: int = 0
    hour: int = 12           # 0-23
    day: int = 1
    weather: str = "clear"   # "clear" | "rain" | "snow" | "fog" | "storm"
    ticks_per_hour: int = 100

    def advance(self, ticks: int) -> list[dict]:
        """Advance time. Returns events (hour_changed, day_changed, weather_changed)."""
        ...

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldTime": ...


@dataclass
class DifficultySettings:
    level: str = "normal"    # "easy" | "normal" | "core" | "hard" | "insane"
    enemy_damage_mult: float = 1.0
    party_damage_mult: float = 1.0
    enemy_hp_mult: float = 1.0

    @classmethod
    def from_level(cls, level: str) -> "DifficultySettings":
        presets = {
            "easy": cls(level="easy", enemy_damage_mult=0.5, party_damage_mult=2.0, enemy_hp_mult=0.75),
            "normal": cls(level="normal"),
            "core": cls(level="core"),
            "hard": cls(level="hard", enemy_damage_mult=1.5, party_damage_mult=0.75, enemy_hp_mult=1.5),
            "insane": cls(level="insane", enemy_damage_mult=2.0, party_damage_mult=0.5, enemy_hp_mult=2.0),
        }
        return presets.get(level, cls())

    def to_dict(self) -> dict[str, Any]: ...


FORMATIONS = {
    "line":    [(0,0), (0,1), (0,2), (0,3), (0,4), (0,5)],
    "wedge":   [(0,0), (-1,1), (1,1), (-2,2), (2,2), (0,2)],
    "circle":  [(0,0), (1,0), (0,1), (-1,0), (0,-1), (1,1)],
    "scatter": [(0,0), (2,1), (-2,1), (1,-2), (-1,2), (3,0)],
}


@dataclass
class GameState:
    campaign_id: str
    seed: int
    party: list[str] = field(default_factory=list)           # actor_ids, max 6
    inactive_npcs: list[str] = field(default_factory=list)
    current_area_id: str = ""
    loaded_area_ids: list[str] = field(default_factory=list)  # LRU cache order
    global_variables: dict[str, Any] = field(default_factory=dict)
    local_variables: dict[str, dict[str, Any]] = field(default_factory=dict)  # area_id → vars
    journal: list[JournalEntry] = field(default_factory=list)
    world_time: WorldTime = field(default_factory=WorldTime)
    reputation: int = 10
    difficulty: DifficultySettings = field(default_factory=DifficultySettings)
    formation: str = "wedge"
    play_time_ticks: int = 0
    creation_date: str = ""

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState": ...
```

## 5. Public API

```python
def create_game_state(campaign_id: str, seed: int, difficulty: str = "normal") -> GameState:
    """Create new game state with defaults."""

def add_to_party(state: GameState, actor_id: str) -> tuple[bool, str]:
    """Add actor to party. Max 6. Returns (success, message)."""

def remove_from_party(state: GameState, actor_id: str) -> None:
    """Move actor to inactive pool."""

def transition_to_area(state: GameState, area_id: str) -> dict:
    """Set current area, manage cache. Returns {loaded, evicted}."""

def set_global_variable(state: GameState, scope: str, name: str, value: Any) -> None:
    """Set variable in specified scope (GLOBAL or area_id)."""

def get_global_variable(state: GameState, scope: str, name: str, default: Any = None) -> Any:
    """Get variable from scope."""

def add_journal_entry(state: GameState, text: str, quest_id: str = "", quest_stage: int = 0) -> None:
    """Add journal entry with current timestamp."""

def advance_time(state: GameState, ticks: int) -> list[dict]:
    """Advance world time. Returns time events."""

def modify_reputation(state: GameState, delta: int) -> int:
    """Change reputation, clamp to 1-20. Returns new value."""

def set_difficulty(state: GameState, level: str) -> None:
    """Set difficulty level and update multipliers."""

def derive_seed(base_seed: int, context: str) -> int:
    """Deterministic sub-seed derivation."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-02]: Given party with 6 members, when add_to_party called, returns (False, "party full").
AC-02 [FR-02]: Given party with 5 members, add succeeds and party has 6.
AC-03 [FR-03]: Given 5 loaded areas and max_cache=4, when transition_to_area loads 5th, oldest is evicted.
AC-04 [FR-04]: set_global("GLOBAL", "quest_1_done", True) → get_global("GLOBAL", "quest_1_done") returns True.
AC-05 [FR-05]: add_journal_entry with quest_id="main_quest", stage=3 → get_latest_stage("main_quest") returns 3.
AC-06 [FR-06]: Given game_tick=0, advance_time(250) → game_tick=250, hour=14 (started at 12, +2.5 hours).
AC-07 [FR-07]: Given reputation=10, modify_reputation(-12) → reputation clamped to 1.
AC-08 [FR-08]: DifficultySettings.from_level("hard") → enemy_damage_mult=1.5, party_damage_mult=0.75.
AC-09 [FR-11]: derive_seed(42, "combat") produces same value every call with same inputs.
AC-10 [FR-10]: Full GameState with party, journal, variables, time → to_dict() → from_dict() round-trip preserves all fields.

## 7-10. (Performance, Errors, Integration, Tests)
- to_dict/from_dict for full state: < 10 ms
- Party overflow: return error, don't modify state
- Integration: ALL subsystems — this is the root container
- Tests: party management edge cases, area cache LRU, variable scopes, journal ordering, time advancement with hour rollover, reputation clamping, difficulty presets, formation positions, full round-trip serialization
