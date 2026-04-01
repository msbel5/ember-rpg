# PRD: Dialog System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the dialog/conversation system synthesizing GemRB M09 (DLG — state/transition trees with conditional triggers, actions, journal entries, multi-dialog jumps) with Ember's campaign-first architecture. Dialog is data-driven: `DialogDef` files define conversation trees as state machines. Each state has NPC text + transitions (player responses). Transitions have conditions, actions, and targets. The kernel evaluates conditions deterministically — no LLM required for dialog flow (LLM is an optional adapter that can generate/embellish dialog text).

## 2. Scope

### In scope
- `DialogDef`: static dialog tree (states, transitions, conditions, actions)
- `DialogState`: runtime conversation state (current_state, history, variables)
- State machine: NPC speaks (state text) → player chooses response (transition) → state changes or dialog ends
- Conditional transitions: GameScript-style trigger conditions (variable checks, stat checks, item checks, reputation checks)
- Actions on transition: set variables, give items, start quests, change reputation, trigger combat
- Journal entries: transitions can add journal notes for quest tracking
- Multi-dialog jump: transitions can jump to another NPC's dialog tree
- CHA/reputation affecting available responses
- Dialog variables: local (per-dialog) and global (per-campaign) variable store

### Out of scope
- Voice acting / audio (UI layer)
- Dialog text generation (LLM adapter concern, not kernel)
- Cinematic/cutscene scripting
- Lip sync

## 3. Functional Requirements (FR)

**FR-01 (DialogDef):** A dialog definition contains: dialog_id, npc_id, states (list of DialogStateNode), and variables (initial local variables). Each state has: state_id, text (template string), trigger_condition (optional, determines if state is valid), transitions (list of DialogTransition).

**FR-02 (DialogTransition):** Each transition has: transition_id, text (player response), condition (trigger expression), action_ids (actions to execute), next_dialog_id (for jumping to another dialog), next_state_id, flags (terminates, journal_entry, hostile).

**FR-03 (Conditions):** Conditions are evaluated expressions. Supported condition types:
- `variable_check(scope, name, operator, value)` — check local/global variable
- `stat_check(actor, stat, operator, value)` — check actor stat (CHA >= 14)
- `skill_check(actor, skill, operator, value)` — check skill level
- `item_check(actor, item_def_id)` — actor has item
- `reputation_check(operator, value)` — party reputation
- `quest_check(quest_id, stage)` — quest at specific stage
- `class_check(actor, class_id)` — actor is specific class
- `alignment_check(actor, alignment)` — actor alignment
- `and(conditions...)` / `or(conditions...)` / `not(condition)` — logical combinators

**FR-04 (Actions):** Actions executed when transition is chosen:
- `set_variable(scope, name, value)` — set local/global variable
- `give_item(actor, item_def_id, quantity)` — add item to inventory
- `take_item(actor, item_def_id, quantity)` — remove item
- `give_xp(actor, amount)` — award XP
- `give_gold(actor, amount)` / `take_gold(actor, amount)`
- `set_reputation(delta)` — change party reputation
- `start_quest(quest_id)` / `advance_quest(quest_id, stage)`
- `set_hostile(npc_id)` — make NPC hostile
- `add_journal(text, quest_id)` — add journal entry
- `spawn_creature(creature_id, position)` — spawn NPC/monster

**FR-05 (Dialog Flow):** `start_dialog(npc, player)` → find first valid state (evaluate state triggers) → present state text + valid transitions (evaluate transition conditions) → player selects transition → execute actions → move to next state or end. If transition has `terminates=True`, dialog ends.

**FR-06 (CHA Gate):** Some transitions have stat_check(player, "CHA", ">=", 16). These options are only visible/available when the player meets the CHA requirement. Same for other stat checks.

**FR-07 (Reaction/Disposition):** NPC reaction: `reaction = (CHA - 10) * 2 + reputation + relationship_score`. High reaction unlocks additional positive dialog paths. Low reaction may lock out options or make NPC hostile.

**FR-08 (Multi-Dialog Jump):** A transition can specify `next_dialog_id` pointing to a different NPC's dialog. This allows chained conversations (e.g., NPC A says "ask my colleague" → jumps to NPC B's dialog).

**FR-09 (Dialog Variables):** Local variables scoped to one dialog (reset each start). Global variables persist across the campaign. Both stored in `DialogState.variables`.

**FR-10 (Serialization):** DialogDef, DialogState, and all sub-structures round-trip via to_dict()/from_dict().

## 4. Data Structures

```python
@dataclass
class DialogCondition:
    condition_type: str      # "variable_check" | "stat_check" | "item_check" | "reputation_check" | "quest_check" | "class_check" | "and" | "or" | "not"
    params: dict[str, Any] = field(default_factory=dict)
    children: list["DialogCondition"] = field(default_factory=list)  # For and/or/not

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogCondition": ...


@dataclass
class DialogAction:
    action_type: str         # "set_variable" | "give_item" | "take_item" | "give_xp" | "give_gold" | "set_reputation" | "start_quest" | "set_hostile" | "add_journal" | "spawn_creature"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogAction": ...


@dataclass
class DialogTransition:
    transition_id: str
    text: str                # Player response text (can be template)
    condition: DialogCondition | None = None
    actions: list[DialogAction] = field(default_factory=list)
    next_dialog_id: str | None = None  # Jump to another dialog
    next_state_id: str | None = None
    terminates: bool = False
    journal_entry: str = ""
    journal_quest_id: str = ""
    hostile: bool = False

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogTransition": ...


@dataclass
class DialogStateNode:
    state_id: str
    text: str                # NPC text (can be template with {variable} refs)
    trigger: DialogCondition | None = None  # Condition for this state to be valid
    transitions: list[DialogTransition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogStateNode": ...


@dataclass
class DialogDef:
    dialog_id: str
    npc_id: str
    states: list[DialogStateNode] = field(default_factory=list)
    initial_variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogDef": ...


@dataclass
class DialogState:
    dialog_id: str
    current_state_id: str
    variables: dict[str, Any] = field(default_factory=dict)  # local + pointer to globals
    history: list[str] = field(default_factory=list)  # state_ids visited
    active: bool = True

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogState": ...
```

## 5. Public API

```python
def start_dialog(
    dialog_def: DialogDef,
    npc: ActorRecord,
    player: ActorRecord,
    global_variables: dict[str, Any],
) -> tuple[DialogState, DialogStateNode, list[DialogTransition]]:
    """Start dialog. Returns state, first valid NPC state, and available transitions."""

def evaluate_condition(
    condition: DialogCondition,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> bool:
    """Evaluate a dialog condition. Deterministic."""

def get_available_transitions(
    state: DialogStateNode,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> list[DialogTransition]:
    """Return transitions whose conditions are met."""

def select_transition(
    dialog_state: DialogState,
    transition: DialogTransition,
    dialog_defs: dict[str, DialogDef],
    player: ActorRecord,
    npc: ActorRecord,
    global_variables: dict[str, Any],
) -> tuple[DialogState, DialogStateNode | None, list[DialogAction]]:
    """Execute transition: run actions, advance to next state. Returns updated state, next NPC state (None if terminated), and actions to execute."""

def execute_dialog_action(
    action: DialogAction,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> dict:
    """Execute a single dialog action. Returns event dict."""

def compute_npc_reaction(player: ActorRecord, npc: ActorRecord, reputation: int) -> int:
    """Compute NPC reaction score: (CHA-10)*2 + reputation + relationship."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-05]: Given a dialog with 3 states, when start_dialog is called, then the first state with valid trigger is returned.

AC-02 [FR-03]: Given transition with condition stat_check(player, "CHA", ">=", 16) and player CHA=14, then transition is NOT in available list.

AC-03 [FR-03]: Given player CHA=18, then the CHA-gated transition IS available.

AC-04 [FR-04]: Given transition with action give_item("healing_potion", 1), when selected, then player gains the item.

AC-05 [FR-04]: Given action set_variable("local", "talked_once", True), when executed, then dialog variables["talked_once"] == True.

AC-06 [FR-05]: Given transition with terminates=True, when selected, then dialog_state.active becomes False.

AC-07 [FR-07]: Given player CHA=18 (reaction +16) and reputation=15, NPC reaction = 16 + 15 = 31.

AC-08 [FR-08]: Given transition with next_dialog_id="npc_b_dialog", when selected, dialog jumps to NPC B's dialog tree.

AC-09 [FR-03]: Given condition and(stat_check("STR", ">=", 14), item_check("magic_key")), with STR=16 and item present, then condition is True.

AC-10 [FR-10]: DialogDef round-trip via to_dict()/from_dict() preserves all states, transitions, conditions, actions.

## 7-10. (Performance, Errors, Integration, Tests)
- evaluate_condition: < 0.05 ms per condition
- Unknown condition_type or action_type: raise ValueError
- Integration: Actor (stats for conditions), Item System (give/take items), Level System (give XP), Colony (reputation), Spell System (quest/variable tracking)
- Tests: all condition types, all action types, multi-state navigation, dialog jump, CHA-gated options, serialization round-trip
