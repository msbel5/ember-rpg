# PRD: GameScript & AI System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the NPC behavior scripting system synthesizing GemRB M08 (GameScript — BCS/BAF trigger/action scripting, ~200 triggers, ~300 actions, per-round evaluation) with Ember's deterministic kernel. Every scriptable entity (NPC, creature, trap, door) has one or more `ScriptDef` attached. Each tick, the script engine evaluates script blocks top-down: the first block whose triggers all pass executes its actions. This provides AI behavior without LLM dependency — the LLM adapter layer can generate/suggest scripts but the kernel runs them deterministically.

## 2. Scope

### In scope
- `ScriptDef`: ordered list of ScriptBlock (trigger_list → action_list)
- `ScriptBlock`: IF all triggers true THEN execute actions
- Core triggers (~30 essential): See, HPPercent, AttackedBy, StateCheck, HasItem, Global, InParty, Level, Alignment, Range, Time, etc.
- Core actions (~30 essential): Attack, MoveToObject, RunAway, Dialogue, ForceSpell, CreateCreature, SetGlobal, GiveItem, ChangeAIScript, DisplayString, etc.
- Per-tick evaluation: every world tick, each scriptable's active script is evaluated
- Object targeting: Myself, NearestEnemyOf, LastAttackerOf, LastSeenBy, Player1-6, IDS-filtered selection
- Script priority: scripts have priority slots (override, class, race, general, default)
- Global/local variable read/write for state tracking

### Out of scope
- Visual debugger for scripts
- Script compiler (scripts are defined as data, not compiled from BAF)
- Full 200+ trigger / 300+ action library (start with core 30/30, expand later)

## 3. Functional Requirements (FR)

**FR-01 (ScriptDef):** Ordered list of ScriptBlock. Evaluated top-to-bottom each tick. First matching block executes, rest skipped.

**FR-02 (ScriptBlock):** Contains: trigger_list (list of Trigger, ALL must be true) and action_list (list of Action, executed in order).

**FR-03 (Triggers):** Each trigger is: trigger_type + params. Core triggers:
- `see(target_filter)` — can see matching actor within visual range
- `hp_percent_lt(self_or_target, percent)` — HP below threshold
- `hp_percent_gt(self_or_target, percent)` — HP above threshold
- `attacked_by(filter)` — was attacked by matching actor
- `state_check(self_or_target, state)` — has condition (poisoned, stunned, etc.)
- `has_item(item_id, self_or_target)` — has item in inventory
- `global_eq(scope, name, value)` / `global_gt` / `global_lt` — variable check
- `in_party(actor_id)` — actor is in party
- `level_gt(self_or_target, level)` — level check
- `alignment(target, alignment)` — alignment check
- `range(self_or_target, distance)` — within distance
- `time_of_day(hour_start, hour_end)` — current time in range
- `num_enemies_gt(count)` — more than N enemies visible
- `num_allies_lt(count)` — fewer than N allies nearby
- `not(trigger)` — negate

**FR-04 (Actions):** Each action is: action_type + params. Core actions:
- `attack(target)` — engage target in combat
- `move_to(target_or_position)` — move toward target
- `run_away(target, distance)` — flee from target
- `dialogue(target)` — initiate dialog
- `force_spell(target, spell_id)` — cast spell at target
- `use_item(item_id, target)` — use item
- `set_global(scope, name, value)` — set variable
- `give_item(item_id, target)` — give item
- `create_creature(creature_id, position)` — spawn creature
- `change_script(script_id, slot)` — swap AI script
- `shout(message_id)` — alert nearby allies
- `wait(ticks)` — do nothing for N ticks
- `flee()` — flee combat entirely
- `protect(target)` — move to protect ally
- `heal(target)` — use healing ability/item on target

**FR-05 (Object Targeting):** Target resolution:
- `myself` — the scripted actor
- `nearest_enemy` — nearest hostile actor
- `last_attacker` — last actor that damaged this one
- `last_seen` — last detected actor
- `player_N` — party member N (1-6)
- `nearest_ally` — nearest friendly actor
- `filter(faction, class, race, alignment)` — IDS-filtered selection

**FR-06 (Script Slots):** Each actor has script slots with priority: override > class > race > general > default. Higher priority scripts are evaluated first. An override script can completely replace behavior.

**FR-07 (Tick Evaluation):** Each world tick: for each scriptable entity → evaluate scripts in priority order → first matching block in first matching script → execute action list → mark as "acted this tick".

**FR-08 (Shout/Communication):** `shout(message_id)` sets a flag on all allies within hearing range. Those allies can have trigger `heard_shout(message_id)` to react.

**FR-09 (Serialization):** ScriptDef, ScriptBlock, all triggers and actions round-trip via to_dict()/from_dict(). Active script state (last_action_tick, wait_counter) also serialized.

## 4. Data Structures

```python
@dataclass
class Trigger:
    trigger_type: str
    params: dict[str, Any] = field(default_factory=dict)
    negated: bool = False

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trigger": ...


@dataclass
class Action:
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action": ...


@dataclass
class ScriptBlock:
    triggers: list[Trigger] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptBlock": ...


@dataclass
class ScriptDef:
    script_id: str
    label: str
    blocks: list[ScriptBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptDef": ...


@dataclass
class ScriptState:
    actor_id: str
    scripts: dict[str, str] = field(default_factory=dict)  # slot → script_id
    wait_counter: int = 0
    last_action_tick: int = 0
    variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptState": ...
```

## 5. Public API

```python
def evaluate_trigger(
    trigger: Trigger,
    actor: ActorRecord,
    script_state: ScriptState,
    world_context: dict,
    global_variables: dict[str, Any],
) -> bool:
    """Evaluate a single trigger. Deterministic."""

def evaluate_script_block(
    block: ScriptBlock,
    actor: ActorRecord,
    script_state: ScriptState,
    world_context: dict,
    global_variables: dict[str, Any],
) -> bool:
    """Evaluate all triggers in block. Returns True if ALL pass."""

def tick_script(
    actor: ActorRecord,
    script_state: ScriptState,
    script_registry: dict[str, ScriptDef],
    world_context: dict,
    global_variables: dict[str, Any],
) -> list[Action]:
    """Evaluate scripts for actor. Returns actions from first matching block, or empty if none match."""

def execute_action(
    action: Action,
    actor: ActorRecord,
    world_context: dict,
    global_variables: dict[str, Any],
) -> dict:
    """Execute a single action. Returns event dict."""

def resolve_target(
    target_spec: str | dict,
    actor: ActorRecord,
    world_context: dict,
) -> ActorRecord | tuple[int, int] | None:
    """Resolve target specification to concrete actor or position."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01]: Given 3 script blocks where block 1 triggers fail, block 2 triggers pass, then block 2 actions are returned and block 3 is never evaluated.

AC-02 [FR-03]: Given trigger see(nearest_enemy) and an enemy within visual range 10, then trigger evaluates True.

AC-03 [FR-03]: Given trigger hp_percent_lt(myself, 50) and actor at 40% HP, then trigger evaluates True.

AC-04 [FR-03]: Given trigger global_eq("local", "alerted", 1) and variable alerted=0, then trigger evaluates False.

AC-05 [FR-04]: Given action attack(nearest_enemy), when executed, returns event {type: "attack", target_id: enemy_id}.

AC-06 [FR-04]: Given action set_global("local", "alerted", 1), when executed, variables["alerted"] becomes 1.

AC-07 [FR-06]: Given scripts in "override" and "general" slots, override script is evaluated first.

AC-08 [FR-08]: Given action shout("help"), when executed, all allies within hearing range gain "heard_shout_help" flag.

AC-09 [FR-05]: Given target "nearest_enemy" with 3 enemies at distances 5, 3, 8, then resolves to the one at distance 3.

AC-10 [FR-09]: ScriptDef round-trip via to_dict()/from_dict() preserves all blocks, triggers, actions.

## 7-10. (Performance, Errors, Integration, Tests)
- tick_script for 1 actor with 10 blocks: < 0.5 ms
- tick_script for 50 actors: < 25 ms
- Unknown trigger_type or action_type: log warning, skip (don't crash)
- Integration: Combat Resolution (attack actions), Dialog System (dialogue action), Spell System (force_spell), Effect System (state_check trigger), Actor Kernel (HP/stats for triggers)
- Tests: each core trigger type, each core action type, block priority evaluation, target resolution, shout propagation, serialization round-trip
