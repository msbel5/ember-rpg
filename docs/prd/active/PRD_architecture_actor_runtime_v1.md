# PRD: Architecture — Actor Runtime Data Model
**Project:** Ember RPG
**Phase:** Phase 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-10
**Status:** Draft

---

## 1. Purpose

Specify the canonical **actor data model** — the minimum field set and operations every actor (player, NPC, creature) MUST support at runtime. This is the data foundation that ambient_life, actor_animation, spawning, pathfinding, and the combat kernel all operate on. Today, `frp-backend/engine/world/entity.py` provides partial coverage; this PRD formalizes the full contract so Copilot can extend it to match BG1 behavior.

### Reference sources
- **GemRB behavior:** `C:\Users\msbel\Downloads\gemrb-extracted\gemrb-master\gemrb\core\Scriptable\Actor.h` (1109 LOC — read first 300 lines for member fields, flags, script slots) + `gemrb/core/Scriptable/Scriptable.h` (435 LOC — base class with script slots, IF_ACTIVE/IF_VISIBLE/IF_IDLE flags, Calendar integration) + `CombatInfo.h` (136 LOC) + `PCStatStruct.h` (160 LOC)
- **Ember target:** `frp-backend/engine/world/entity.py` (existing — extend) + `frp-backend/engine/world/actor_runtime.py` (NEW helpers)

**Clean-room rule applies.**

## 2. Scope

**In scope:**
- Canonical actor fields: id, kind, position, facing, state flags, 8 script slots, stats reference, combat info, animation state, current path, trigger queue
- 8 script slot constants (SCR_OVERRIDE..SCR_DEFAULT)
- State flag constants (IF_ACTIVE, IF_VISIBLE, IF_IDLE, IF_JUSTDIED, IF_REALLYDIED, IF_FROMGAME, IF_RUNNING, IF_USEEXIT)
- Operations: get/set stat, position, facing; attach/detach script tree; tick; apply damage; check death; query state
- Dataclass definitions + helper module

**Out of scope:**
- Stat kernel rules (backend has its own subsystem)
- Combat resolution algorithms
- Specific animation state transitions (covered by `PRD_architecture_actor_animation_v1`)
- Script VM execution (covered by `PRD_architecture_ambient_life_v1` behavior_tree)

## 3. Functional Requirements (FR)

**FR-01:** Define `class Actor` with fields: `id: str`, `kind: str`, `position: tuple[int, int]`, `facing: str`, `state_flags: int`, `script_slots: list[BehaviorNode]`, `stats_ref: ActorStats`, `combat_info: CombatInfo`, `animation_state: ActorAnimationState`, `current_path: list[tuple[int, int]]`, `trigger_queue: list[TriggerEvent]`.

**FR-02:** Define 8 script slot constants: `SCR_OVERRIDE = 0`, `SCR_AREA = 1`, `SCR_SPECIFICS = 2`, `SCR_RESERVED = 3`, `SCR_CLASS = 4`, `SCR_RACE = 5`, `SCR_GENERAL = 6`, `SCR_DEFAULT = 7`. Total `MAX_SCRIPTS = 8`.

**FR-03:** Define state flag constants matching GemRB values:
- `IF_JUSTDIED = 2`
- `IF_FROMGAME = 4`
- `IF_REALLYDIED = 8`
- `IF_NORETICLE = 16`
- `IF_NOINT = 32`
- `IF_CLEANUP = 64`
- `IF_RUNNING = 128`
- `IF_INITIALIZED = 0x200`
- `IF_USEEXIT = 0x1000`
- `IF_ACTIVE = 0x10000`
- `IF_VISIBLE = 0x40000`
- `IF_IDLE = 0x100000`
- `IF_FORCEUPDATE = 0x400000`

**FR-04:** Provide query methods: `is_active() -> bool`, `is_visible() -> bool`, `is_idle() -> bool`, `is_dead() -> bool`, `is_running() -> bool`.

**FR-05:** Provide mutation methods: `set_flag(flag: int)`, `clear_flag(flag: int)`, `toggle_flag(flag: int)`, `has_flag(flag: int) -> bool`.

**FR-06:** Provide position methods: `get_position() -> tuple[int, int]`, `set_position(pos: tuple[int, int])`, `get_facing() -> str`, `set_facing(facing: str)`.

**FR-07:** Provide stat methods: `get_stat(stat_id: str) -> int`, `set_stat(stat_id: str, value: int)`, `modify_stat(stat_id: str, delta: int)`.

**FR-08:** Provide script slot management: `attach_script(slot: int, tree: BehaviorNode)`, `detach_script(slot: int)`, `get_script(slot: int) -> BehaviorNode | None`.

**FR-09:** Provide combat methods: `apply_damage(amount: int, source_id: str = "")`, `apply_heal(amount: int)`, `get_hp() -> int`, `get_max_hp() -> int`.

**FR-10:** Provide tick method: `tick(context: BehaviorContext)` — runs active script slots in priority order (SCR_OVERRIDE first, SCR_DEFAULT last), short-circuits on first SUCCESS or RUNNING.

**FR-11:** On death (hp <= 0), MUST set `IF_JUSTDIED`. On subsequent tick, transition to `IF_REALLYDIED` and clear `IF_ACTIVE`.

**FR-12:** Provide serialization: `to_dict() -> dict`, `from_dict(data: dict) -> Actor`.

## 4. Data Structures

    # frp-backend/engine/world/actor_runtime.py
    
    from dataclasses import dataclass, field
    from typing import Optional
    from engine.world.behavior_tree import BehaviorNode, BehaviorContext, Status
    
    # Script slots (matches GemRB)
    SCR_OVERRIDE = 0
    SCR_AREA = 1
    SCR_SPECIFICS = 2
    SCR_RESERVED = 3
    SCR_CLASS = 4
    SCR_RACE = 5
    SCR_GENERAL = 6
    SCR_DEFAULT = 7
    MAX_SCRIPTS = 8
    
    # State flags (matches GemRB values)
    IF_JUSTDIED = 0x2
    IF_FROMGAME = 0x4
    IF_REALLYDIED = 0x8
    IF_NORETICLE = 0x10
    IF_NOINT = 0x20
    IF_CLEANUP = 0x40
    IF_RUNNING = 0x80
    IF_INITIALIZED = 0x200
    IF_USEEXIT = 0x1000
    IF_ACTIVE = 0x10000
    IF_VISIBLE = 0x40000
    IF_IDLE = 0x100000
    IF_FORCEUPDATE = 0x400000
    
    @dataclass
    class ActorStats:
        str_val: int = 10
        dex_val: int = 10
        con_val: int = 10
        int_val: int = 10
        wis_val: int = 10
        cha_val: int = 10
        hp: int = 1
        max_hp: int = 1
        ac: int = 10
        thac0: int = 20
        level: int = 1
        xp: int = 0
    
    @dataclass
    class CombatInfo:
        in_combat: bool = False
        initiative: int = 0
        action_available: bool = True
        bonus_action_available: bool = True
        reaction_available: bool = True
        movement_remaining: int = 6
    
    @dataclass
    class ActorAnimationState:
        current_state: str = "stand"
        facing: str = "south"
        frame_cursor: int = 0
    
    @dataclass
    class Actor:
        id: str
        kind: str = "npc"                          # "player", "npc", "creature"
        position: tuple[int, int] = (0, 0)
        facing: str = "south"
        state_flags: int = IF_ACTIVE | IF_VISIBLE
        script_slots: list[Optional[BehaviorNode]] = field(default_factory=lambda: [None] * MAX_SCRIPTS)
        stats_ref: ActorStats = field(default_factory=ActorStats)
        combat_info: CombatInfo = field(default_factory=CombatInfo)
        animation_state: ActorAnimationState = field(default_factory=ActorAnimationState)
        current_path: list[tuple[int, int]] = field(default_factory=list)
        trigger_queue: list[dict] = field(default_factory=list)

## 5. Public API — methods that MUST exist

    # ---- query ----
    def is_active(self) -> bool
    def is_visible(self) -> bool
    def is_idle(self) -> bool
    def is_dead(self) -> bool
    def is_running(self) -> bool
    def is_in_combat(self) -> bool
    
    # ---- flag helpers ----
    def set_flag(self, flag: int) -> None
    def clear_flag(self, flag: int) -> None
    def toggle_flag(self, flag: int) -> None
    def has_flag(self, flag: int) -> bool
    def get_flags(self) -> int
    
    # ---- position / facing ----
    def get_position(self) -> tuple[int, int]
    def set_position(self, pos: tuple[int, int]) -> None
    def get_facing(self) -> str
    def set_facing(self, facing: str) -> None
    def face_toward(self, target: tuple[int, int]) -> None
    
    # ---- stats ----
    def get_stat(self, stat_id: str) -> int
    def set_stat(self, stat_id: str, value: int) -> None
    def modify_stat(self, stat_id: str, delta: int) -> None
    def get_hp(self) -> int
    def get_max_hp(self) -> int
    def set_hp(self, value: int) -> None
    
    # ---- combat ----
    def apply_damage(self, amount: int, source_id: str = "") -> None
    def apply_heal(self, amount: int) -> None
    def check_death(self) -> None                                                # sets IF_JUSTDIED if hp <= 0
    def on_real_death(self) -> None                                              # called on tick after IF_JUSTDIED
    
    # ---- script slots ----
    def attach_script(self, slot: int, tree: BehaviorNode) -> None
    def detach_script(self, slot: int) -> None
    def get_script(self, slot: int) -> Optional[BehaviorNode]
    def has_script(self, slot: int) -> bool
    
    # ---- tick ----
    def tick(self, context: BehaviorContext) -> Status
    def tick_script_slot(self, slot: int, context: BehaviorContext) -> Status
    
    # ---- path ----
    def set_path(self, path: list[tuple[int, int]]) -> None
    def get_path(self) -> list[tuple[int, int]]
    def clear_path(self) -> None
    def has_path(self) -> bool
    def advance_path_step(self) -> Optional[tuple[int, int]]
    
    # ---- trigger queue ----
    def push_trigger(self, event: dict) -> None
    def pop_trigger(self) -> Optional[dict]
    def peek_trigger(self) -> Optional[dict]
    def has_triggers(self) -> bool
    def clear_triggers(self) -> None
    
    # ---- serialization ----
    def to_dict(self) -> dict
    @classmethod
    def from_dict(cls, data: dict) -> "Actor"

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** `Actor(id="test")` creates an instance with default fields populated. `actor.position == (0, 0)`, `actor.state_flags == (IF_ACTIVE | IF_VISIBLE)`.

**AC-02 [FR-02]:** All 8 script slot constants are defined with the correct integer values. `MAX_SCRIPTS == 8`.

**AC-03 [FR-03]:** `IF_ACTIVE == 0x10000`, `IF_VISIBLE == 0x40000`, `IF_IDLE == 0x100000` (verified by literal assertion).

**AC-04 [FR-04]:** A newly-created actor has `is_active() == True` and `is_visible() == True`.

**AC-05 [FR-05]:** `actor.set_flag(IF_RUNNING)` then `actor.has_flag(IF_RUNNING) == True`. `actor.clear_flag(IF_RUNNING)` then `has_flag == False`.

**AC-06 [FR-06]:** `actor.set_position((10, 20))` then `get_position() == (10, 20)`. `actor.face_toward((10, 21))` sets facing toward south.

**AC-07 [FR-09]:** `actor.apply_damage(5)` reduces `stats_ref.hp` by 5. If hp reaches 0, `check_death` sets `IF_JUSTDIED`.

**AC-08 [FR-10]:** `actor.tick(ctx)` iterates all attached script slots in priority order. A SUCCESS in SCR_OVERRIDE stops further slots.

**AC-09 [FR-11]:** An actor with `IF_JUSTDIED` set, ticked once, transitions to `IF_REALLYDIED` and has `IF_ACTIVE` cleared.

**AC-10 [FR-12]:** `actor.to_dict()` returns a dict with all fields serialized. `Actor.from_dict(d)` round-trips correctly.

**AC-11 [reflection]:** A test MUST import `Actor` and use `inspect.getmembers` to verify every method in §5 exists as a callable attribute. The method name list is:
`["is_active", "is_visible", "is_idle", "is_dead", "is_running", "is_in_combat", "set_flag", "clear_flag", "toggle_flag", "has_flag", "get_flags", "get_position", "set_position", "get_facing", "set_facing", "face_toward", "get_stat", "set_stat", "modify_stat", "get_hp", "get_max_hp", "set_hp", "apply_damage", "apply_heal", "check_death", "on_real_death", "attach_script", "detach_script", "get_script", "has_script", "tick", "tick_script_slot", "set_path", "get_path", "clear_path", "has_path", "advance_path_step", "push_trigger", "pop_trigger", "peek_trigger", "has_triggers", "clear_triggers", "to_dict", "from_dict"]`

## 7. Performance Requirements

- `tick()` per actor with 2 attached scripts: **< 1ms**
- Flag operations: **< 0.1ms**
- Serialization (to_dict): **< 0.5ms**
- 30 actors × 30 Hz visual tick: total **< 30ms / second**

## 8. Error Handling

- Invalid stat_id: raise `KeyError` or return default
- Negative HP: clamp to 0, set `IF_JUSTDIED`
- Script slot out of range: raise `IndexError`
- `from_dict` with missing fields: use defaults, log at WARNING

## 9. Integration Points

**Backend (editable):**
- `frp-backend/engine/world/actor_runtime.py` — NEW helper module with `Actor`, `ActorStats`, `CombatInfo`, `ActorAnimationState`, flag + slot constants
- `frp-backend/engine/world/entity.py` — may need to re-export `Actor` or wrap it
- `frp-backend/tests/test_actor_runtime.py` — NEW

**Backend (consumed, NOT modified):**
- `frp-backend/engine/world/behavior_tree.py` — imports BehaviorNode, BehaviorContext, Status
- Stat kernel (in `frp-backend/engine/kernel/...`) — MUST NOT be modified; Actor delegates stat queries

**Forbidden:**
- No edits under `frp-backend/engine/kernel/**` (kernel is frozen)
- No edits to any other PRD file
- No new HTTP endpoints
- No new autoloads
- No GemRB code port (clean-room rule)

## 10. Test Coverage Target

- `test_actor_runtime.py` MUST cover AC-01..AC-11
- ≥90% branch coverage on `actor_runtime.py`
- Existing backend test suite stays green

## 11. Verification

    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_actor_runtime.py -q
    C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q
