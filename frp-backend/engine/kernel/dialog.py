from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord, ItemStack
from engine.kernel.common import serialize_value


@dataclass
class DialogCondition:
    condition_type: str
    params: dict[str, Any] = field(default_factory=dict)
    children: list["DialogCondition"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogCondition":
        payload = dict(data)
        payload["params"] = dict(payload.get("params", {}))
        payload["children"] = [
            item if isinstance(item, DialogCondition) else DialogCondition.from_dict(dict(item))
            for item in payload.get("children", [])
        ]
        return cls(**payload)


@dataclass
class DialogAction:
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogAction":
        payload = dict(data)
        payload["params"] = dict(payload.get("params", {}))
        return cls(**payload)


@dataclass
class DialogTransition:
    transition_id: str
    text: str
    condition: DialogCondition | None = None
    actions: list[DialogAction] = field(default_factory=list)
    next_dialog_id: str | None = None
    next_state_id: str | None = None
    terminates: bool = False
    journal_entry: str = ""
    journal_quest_id: str = ""
    hostile: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogTransition":
        payload = dict(data)
        condition = payload.get("condition")
        payload["condition"] = (
            condition if isinstance(condition, DialogCondition) else DialogCondition.from_dict(dict(condition))
        ) if condition else None
        payload["actions"] = [
            item if isinstance(item, DialogAction) else DialogAction.from_dict(dict(item))
            for item in payload.get("actions", [])
        ]
        return cls(**payload)


@dataclass
class DialogStateNode:
    state_id: str
    text: str
    trigger: DialogCondition | None = None
    transitions: list[DialogTransition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogStateNode":
        payload = dict(data)
        trigger = payload.get("trigger")
        payload["trigger"] = (
            trigger if isinstance(trigger, DialogCondition) else DialogCondition.from_dict(dict(trigger))
        ) if trigger else None
        payload["transitions"] = [
            item if isinstance(item, DialogTransition) else DialogTransition.from_dict(dict(item))
            for item in payload.get("transitions", [])
        ]
        return cls(**payload)


@dataclass
class DialogDef:
    dialog_id: str
    npc_id: str
    states: list[DialogStateNode] = field(default_factory=list)
    initial_variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogDef":
        payload = dict(data)
        payload["states"] = [
            item if isinstance(item, DialogStateNode) else DialogStateNode.from_dict(dict(item))
            for item in payload.get("states", [])
        ]
        payload["initial_variables"] = dict(payload.get("initial_variables", {}))
        return cls(**payload)


@dataclass
class DialogState:
    dialog_id: str
    current_state_id: str
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogState":
        payload = dict(data)
        payload["variables"] = dict(payload.get("variables", {}))
        payload["history"] = [str(item) for item in payload.get("history", [])]
        return cls(**payload)


def start_dialog(
    dialog_def: DialogDef,
    npc: ActorRecord,
    player: ActorRecord,
    global_variables: dict[str, Any],
) -> tuple[DialogState, DialogStateNode, list[DialogTransition]]:
    state_node = _first_valid_state(dialog_def, player, npc, dialog_def.initial_variables, global_variables)
    if state_node is None:
        raise ValueError(f"No valid dialog state found for {dialog_def.dialog_id}")
    dialog_state = DialogState(
        dialog_id=dialog_def.dialog_id,
        current_state_id=state_node.state_id,
        variables=dict(dialog_def.initial_variables),
        history=[state_node.state_id],
        active=True,
    )
    transitions = get_available_transitions(state_node, player, npc, dialog_state.variables, global_variables)
    return dialog_state, state_node, transitions


def evaluate_condition(
    condition: DialogCondition,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> bool:
    if condition.condition_type == "and":
        return all(evaluate_condition(child, player, npc, variables, global_variables) for child in condition.children)
    if condition.condition_type == "or":
        return any(evaluate_condition(child, player, npc, variables, global_variables) for child in condition.children)
    if condition.condition_type == "not":
        if not condition.children:
            raise ValueError("not condition requires a child")
        return not evaluate_condition(condition.children[0], player, npc, variables, global_variables)

    params = condition.params
    if condition.condition_type == "variable_check":
        scope = str(params.get("scope", "local"))
        store = global_variables if scope == "global" else variables
        return _compare(store.get(str(params.get("name", ""))), str(params.get("operator", "==")), params.get("value"))
    if condition.condition_type == "stat_check":
        actor = _resolve_actor(str(params.get("actor", "player")), player, npc)
        return _compare(actor.stats.get(str(params.get("stat", "")), 0), str(params.get("operator", "==")), params.get("value"))
    if condition.condition_type == "skill_check":
        actor = _resolve_actor(str(params.get("actor", "player")), player, npc)
        return _compare(actor.skills.get(str(params.get("skill", "")), 0), str(params.get("operator", "==")), params.get("value"))
    if condition.condition_type == "item_check":
        actor = _resolve_actor(str(params.get("actor", "player")), player, npc)
        item_def_id = str(params.get("item_def_id", ""))
        return any(item.item_def_id == item_def_id for item in actor.inventory)
    if condition.condition_type == "reputation_check":
        return _compare(global_variables.get("reputation", 0), str(params.get("operator", "==")), params.get("value"))
    if condition.condition_type == "quest_check":
        quest_id = str(params.get("quest_id", ""))
        stage = params.get("stage")
        return player.raw_payload.get("quests", {}).get(quest_id) == stage
    if condition.condition_type == "class_check":
        actor = _resolve_actor(str(params.get("actor", "player")), player, npc)
        return actor.raw_payload.get("class_id") == params.get("class_id")
    if condition.condition_type == "alignment_check":
        actor = _resolve_actor(str(params.get("actor", "player")), player, npc)
        return actor.raw_payload.get("alignment") == params.get("alignment")
    raise ValueError(f"Unknown condition_type: {condition.condition_type}")


def get_available_transitions(
    state: DialogStateNode,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> list[DialogTransition]:
    available: list[DialogTransition] = []
    for transition in state.transitions:
        if transition.condition is None or evaluate_condition(transition.condition, player, npc, variables, global_variables):
            available.append(transition)
    return available


def select_transition(
    dialog_state: DialogState,
    transition: DialogTransition,
    dialog_defs: dict[str, DialogDef],
    player: ActorRecord,
    npc: ActorRecord,
    global_variables: dict[str, Any],
) -> tuple[DialogState, DialogStateNode | None, list[dict[str, Any]]]:
    events = [
        execute_dialog_action(action, player, npc, dialog_state.variables, global_variables)
        for action in transition.actions
    ]
    if transition.hostile:
        npc.raw_payload["hostile"] = True
    if transition.journal_entry:
        journal_event = execute_dialog_action(
            DialogAction("add_journal", {"text": transition.journal_entry, "quest_id": transition.journal_quest_id}),
            player,
            npc,
            dialog_state.variables,
            global_variables,
        )
        events.append(journal_event)
    if transition.terminates:
        dialog_state.active = False
        return dialog_state, None, events

    target_dialog_id = transition.next_dialog_id or dialog_state.dialog_id
    dialog_def = dialog_defs[target_dialog_id]
    if transition.next_dialog_id:
        dialog_state.dialog_id = transition.next_dialog_id
        dialog_state.variables = dict(dialog_def.initial_variables)
    if transition.next_state_id:
        next_state = _state_by_id(dialog_def, transition.next_state_id)
    else:
        next_state = _first_valid_state(dialog_def, player, npc, dialog_state.variables, global_variables)
    if next_state is None:
        dialog_state.active = False
        return dialog_state, None, events
    dialog_state.current_state_id = next_state.state_id
    dialog_state.history.append(next_state.state_id)
    dialog_state.active = True
    return dialog_state, next_state, events


def execute_dialog_action(
    action: DialogAction,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> dict[str, Any]:
    params = action.params
    if action.action_type == "set_variable":
        scope = str(params.get("scope", "local"))
        target = global_variables if scope == "global" else variables
        target[str(params.get("name", ""))] = params.get("value")
        return {"type": "set_variable", "scope": scope, "name": params.get("name"), "value": params.get("value")}
    if action.action_type == "give_item":
        item_def_id = str(params.get("item_def_id", ""))
        quantity = int(params.get("quantity", 1))
        player.inventory.append(ItemStack(instance_id=f"{item_def_id}_{len(player.inventory)}", item_def_id=item_def_id, quantity=quantity))
        return {"type": "give_item", "item_def_id": item_def_id, "quantity": quantity}
    if action.action_type == "take_item":
        item_def_id = str(params.get("item_def_id", ""))
        quantity = int(params.get("quantity", 1))
        remaining = quantity
        kept: list[ItemStack] = []
        for item in player.inventory:
            if item.item_def_id != item_def_id or remaining <= 0:
                kept.append(item)
                continue
            if item.quantity > remaining:
                item.quantity -= remaining
                remaining = 0
                kept.append(item)
            else:
                remaining -= item.quantity
        player.inventory = kept
        return {"type": "take_item", "item_def_id": item_def_id, "quantity": quantity - remaining}
    if action.action_type == "give_xp":
        amount = int(params.get("amount", 0))
        player.raw_payload["xp"] = int(player.raw_payload.get("xp", 0)) + amount
        return {"type": "give_xp", "amount": amount}
    if action.action_type == "give_gold":
        amount = int(params.get("amount", 0))
        player.raw_payload["gold"] = int(player.raw_payload.get("gold", 0)) + amount
        return {"type": "give_gold", "amount": amount}
    if action.action_type == "take_gold":
        amount = int(params.get("amount", 0))
        player.raw_payload["gold"] = max(0, int(player.raw_payload.get("gold", 0)) - amount)
        return {"type": "take_gold", "amount": amount}
    if action.action_type == "set_reputation":
        delta = int(params.get("delta", 0))
        global_variables["reputation"] = int(global_variables.get("reputation", 0)) + delta
        return {"type": "set_reputation", "delta": delta}
    if action.action_type == "start_quest":
        quest_id = str(params.get("quest_id", ""))
        player.raw_payload.setdefault("quests", {})[quest_id] = "started"
        return {"type": "start_quest", "quest_id": quest_id}
    if action.action_type == "advance_quest":
        quest_id = str(params.get("quest_id", ""))
        stage = params.get("stage")
        player.raw_payload.setdefault("quests", {})[quest_id] = stage
        return {"type": "advance_quest", "quest_id": quest_id, "stage": stage}
    if action.action_type == "set_hostile":
        npc.raw_payload["hostile"] = True
        return {"type": "set_hostile", "npc_id": params.get("npc_id", npc.identity.actor_id)}
    if action.action_type == "add_journal":
        entry = {"text": str(params.get("text", "")), "quest_id": str(params.get("quest_id", ""))}
        player.raw_payload.setdefault("journal", []).append(entry)
        return {"type": "add_journal", **entry}
    if action.action_type == "spawn_creature":
        spawn = {"creature_id": str(params.get("creature_id", "")), "position": params.get("position")}
        player.raw_payload.setdefault("spawned_creatures", []).append(spawn)
        return {"type": "spawn_creature", **spawn}
    raise ValueError(f"Unknown action_type: {action.action_type}")


def compute_npc_reaction(player: ActorRecord, npc: ActorRecord, reputation: int) -> int:
    cha = int(player.stats.get("CHA", player.stats.get("cha", 10)))
    relationship_score = int(npc.raw_payload.get("relationship_score", 0))
    return ((cha - 10) * 2) + int(reputation) + relationship_score


def _first_valid_state(
    dialog_def: DialogDef,
    player: ActorRecord,
    npc: ActorRecord,
    variables: dict[str, Any],
    global_variables: dict[str, Any],
) -> DialogStateNode | None:
    for state in dialog_def.states:
        if state.trigger is None or evaluate_condition(state.trigger, player, npc, variables, global_variables):
            return state
    return None


def _state_by_id(dialog_def: DialogDef, state_id: str) -> DialogStateNode:
    for state in dialog_def.states:
        if state.state_id == state_id:
            return state
    raise KeyError(state_id)


def _resolve_actor(actor_name: str, player: ActorRecord, npc: ActorRecord) -> ActorRecord:
    return player if actor_name == "player" else npc


def _compare(left: Any, operator: str, right: Any) -> bool:
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    raise ValueError(f"Unknown operator: {operator}")
