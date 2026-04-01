from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord, ItemStack
from engine.kernel.common import serialize_value


logger = logging.getLogger(__name__)
_SCRIPT_SLOT_ORDER = ("override", "class", "race", "general", "default")


@dataclass
class Trigger:
    trigger_type: str
    params: dict[str, Any] = field(default_factory=dict)
    negated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trigger":
        payload = dict(data)
        payload["params"] = dict(payload.get("params", {}))
        return cls(**payload)


@dataclass
class Action:
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        payload = dict(data)
        payload["params"] = dict(payload.get("params", {}))
        return cls(**payload)


@dataclass
class ScriptBlock:
    triggers: list[Trigger] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptBlock":
        payload = dict(data)
        payload["triggers"] = [
            item if isinstance(item, Trigger) else Trigger.from_dict(dict(item))
            for item in payload.get("triggers", [])
        ]
        payload["actions"] = [
            item if isinstance(item, Action) else Action.from_dict(dict(item))
            for item in payload.get("actions", [])
        ]
        return cls(**payload)


@dataclass
class ScriptDef:
    script_id: str
    label: str
    blocks: list[ScriptBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptDef":
        payload = dict(data)
        payload["blocks"] = [
            item if isinstance(item, ScriptBlock) else ScriptBlock.from_dict(dict(item))
            for item in payload.get("blocks", [])
        ]
        return cls(**payload)


@dataclass
class ScriptState:
    actor_id: str
    scripts: dict[str, str] = field(default_factory=dict)
    wait_counter: int = 0
    last_action_tick: int = 0
    variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptState":
        payload = dict(data)
        payload["scripts"] = {str(key): str(value) for key, value in payload.get("scripts", {}).items()}
        payload["variables"] = dict(payload.get("variables", {}))
        return cls(**payload)


def evaluate_trigger(
    trigger: Trigger,
    actor: ActorRecord,
    script_state: ScriptState,
    world_context: dict,
    global_variables: dict[str, Any],
) -> bool:
    result = _evaluate_trigger_impl(trigger, actor, script_state, world_context, global_variables)
    return not result if trigger.negated else result


def evaluate_script_block(
    block: ScriptBlock,
    actor: ActorRecord,
    script_state: ScriptState,
    world_context: dict,
    global_variables: dict[str, Any],
) -> bool:
    return all(evaluate_trigger(trigger, actor, script_state, world_context, global_variables) for trigger in block.triggers)


def tick_script(
    actor: ActorRecord,
    script_state: ScriptState,
    script_registry: dict[str, ScriptDef],
    world_context: dict,
    global_variables: dict[str, Any],
) -> list[Action]:
    if script_state.wait_counter > 0:
        script_state.wait_counter -= 1
        return []
    for slot in _SCRIPT_SLOT_ORDER:
        script_id = script_state.scripts.get(slot)
        if not script_id:
            continue
        script = script_registry.get(script_id)
        if script is None:
            continue
        for block in script.blocks:
            if evaluate_script_block(block, actor, script_state, world_context, global_variables):
                script_state.last_action_tick = int(world_context.get("current_tick", script_state.last_action_tick))
                return list(block.actions)
    return []


def execute_action(
    action: Action,
    actor: ActorRecord,
    world_context: dict,
    global_variables: dict[str, Any],
) -> dict:
    script_states: dict[str, ScriptState] = world_context.get("script_states", {})
    script_state = script_states.get(actor.identity.actor_id)
    if action.action_type == "attack":
        target = resolve_target(action.params.get("target", "nearest_enemy"), actor, world_context)
        return {"type": "attack", "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    if action.action_type == "move_to":
        target = resolve_target(action.params.get("target", "nearest_enemy"), actor, world_context)
        if isinstance(target, ActorRecord):
            return {"type": "move_to", "target_id": target.identity.actor_id}
        return {"type": "move_to", "position": target}
    if action.action_type == "run_away":
        target = resolve_target(action.params.get("target", "nearest_enemy"), actor, world_context)
        return {"type": "run_away", "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    if action.action_type == "dialogue":
        target = resolve_target(action.params.get("target", "nearest_ally"), actor, world_context)
        return {"type": "dialogue", "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    if action.action_type == "force_spell":
        return {"type": "force_spell", "spell_id": action.params.get("spell_id"), "target": action.params.get("target")}
    if action.action_type == "use_item":
        item_id = str(action.params.get("item_id", ""))
        target = resolve_target(action.params.get("target", "myself"), actor, world_context)
        return {"type": "use_item", "item_id": item_id, "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    if action.action_type == "set_global":
        scope = str(action.params.get("scope", "global"))
        name = str(action.params.get("name", ""))
        value = action.params.get("value")
        if scope == "local" and script_state is not None:
            script_state.variables[name] = value
        else:
            global_variables[name] = value
        return {"type": "set_global", "scope": scope, "name": name, "value": value}
    if action.action_type == "give_item":
        target = resolve_target(action.params.get("target", "myself"), actor, world_context)
        if isinstance(target, ActorRecord):
            target.inventory.append(ItemStack(instance_id=f"{action.params.get('item_id', 'item')}_{len(target.inventory)}", item_def_id=str(action.params.get("item_id", ""))))
            return {"type": "give_item", "item_id": action.params.get("item_id"), "target_id": target.identity.actor_id}
        return {"type": "give_item", "item_id": action.params.get("item_id"), "target_id": None}
    if action.action_type == "create_creature":
        spawn = {"creature_id": action.params.get("creature_id"), "position": action.params.get("position")}
        world_context.setdefault("spawned_creatures", []).append(spawn)
        return {"type": "create_creature", **spawn}
    if action.action_type == "change_script":
        if script_state is not None:
            script_state.scripts[str(action.params.get("slot", "general"))] = str(action.params.get("script_id", ""))
        return {"type": "change_script", "script_id": action.params.get("script_id"), "slot": action.params.get("slot")}
    if action.action_type == "shout":
        message_id = str(action.params.get("message_id", ""))
        hearing_range = int(world_context.get("hearing_range", 8))
        for other in world_context.get("actors", []):
            if other.identity.actor_id == actor.identity.actor_id:
                continue
            if other.identity.faction_id != actor.identity.faction_id:
                continue
            if _distance(actor, other) <= hearing_range:
                other_state = script_states.get(other.identity.actor_id)
                if other_state is not None:
                    other_state.variables[f"heard_shout_{message_id}"] = True
        return {"type": "shout", "message_id": message_id}
    if action.action_type == "wait":
        if script_state is not None:
            script_state.wait_counter = int(action.params.get("ticks", 1))
        return {"type": "wait", "ticks": int(action.params.get("ticks", 1))}
    if action.action_type == "flee":
        actor.raw_payload["fleeing"] = True
        return {"type": "flee"}
    if action.action_type == "protect":
        target = resolve_target(action.params.get("target", "nearest_ally"), actor, world_context)
        return {"type": "protect", "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    if action.action_type == "heal":
        target = resolve_target(action.params.get("target", "nearest_ally"), actor, world_context)
        return {"type": "heal", "target_id": target.identity.actor_id if isinstance(target, ActorRecord) else None}
    logger.warning("Unknown action_type: %s", action.action_type)
    return {"type": "noop", "action_type": action.action_type}


def resolve_target(
    target_spec: str | dict,
    actor: ActorRecord,
    world_context: dict,
) -> ActorRecord | tuple[int, int] | None:
    actors = list(world_context.get("actors", []))
    if isinstance(target_spec, dict):
        if "position" in target_spec:
            position = target_spec["position"]
            return int(position[0]), int(position[1])
        filtered = actors
        if target_spec.get("faction") is not None:
            filtered = [candidate for candidate in filtered if candidate.identity.faction_id == target_spec["faction"]]
        if target_spec.get("class") is not None:
            filtered = [candidate for candidate in filtered if candidate.raw_payload.get("class_id") == target_spec["class"]]
        if target_spec.get("race") is not None:
            filtered = [candidate for candidate in filtered if candidate.identity.species_id == target_spec["race"]]
        if target_spec.get("alignment") is not None:
            filtered = [candidate for candidate in filtered if candidate.raw_payload.get("alignment") == target_spec["alignment"]]
        return _nearest_actor(actor, filtered)
    target_name = str(target_spec)
    if target_name == "myself":
        return actor
    if target_name == "nearest_enemy":
        return _nearest_actor(actor, _visible_enemies(actor, actors, world_context))
    if target_name == "last_attacker":
        attacker_id = world_context.get("last_attacker_id") or actor.raw_payload.get("last_attacker_id")
        return next((candidate for candidate in actors if candidate.identity.actor_id == attacker_id), None)
    if target_name == "last_seen":
        last_seen_id = world_context.get("last_seen_id") or actor.raw_payload.get("last_seen_id")
        return next((candidate for candidate in actors if candidate.identity.actor_id == last_seen_id), None)
    if target_name.startswith("player_"):
        index = int(target_name.split("_", 1)[1]) - 1
        party_ids = list(world_context.get("party_ids", []))
        if 0 <= index < len(party_ids):
            return next((candidate for candidate in actors if candidate.identity.actor_id == party_ids[index]), None)
        return None
    if target_name == "nearest_ally":
        allies = [
            candidate
            for candidate in actors
            if candidate.identity.actor_id != actor.identity.actor_id
            and candidate.identity.faction_id == actor.identity.faction_id
        ]
        return _nearest_actor(actor, allies)
    return None


def _evaluate_trigger_impl(
    trigger: Trigger,
    actor: ActorRecord,
    script_state: ScriptState,
    world_context: dict,
    global_variables: dict[str, Any],
) -> bool:
    params = trigger.params
    if trigger.trigger_type == "see":
        target = resolve_target(str(params.get("target_filter", "nearest_enemy")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return _distance(actor, target) <= int(actor.raw_payload.get("visual_range", 10))
    if trigger.trigger_type == "hp_percent_lt":
        target = resolve_target(str(params.get("target", "myself")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return _hp_percent(target) < float(params.get("percent", 100))
    if trigger.trigger_type == "hp_percent_gt":
        target = resolve_target(str(params.get("target", "myself")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return _hp_percent(target) > float(params.get("percent", 0))
    if trigger.trigger_type == "attacked_by":
        attacker_id = world_context.get("last_attacker_id") or actor.raw_payload.get("last_attacker_id")
        return attacker_id is not None
    if trigger.trigger_type == "state_check":
        state = str(params.get("state", ""))
        return any(condition.name == state for condition in actor.conditions)
    if trigger.trigger_type == "has_item":
        target = resolve_target(str(params.get("target", "myself")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        item_id = str(params.get("item_id", ""))
        return any(item.item_def_id == item_id for item in target.inventory)
    if trigger.trigger_type == "global_eq":
        scope = str(params.get("scope", "global"))
        name = str(params.get("name", ""))
        value = params.get("value")
        store = script_state.variables if scope == "local" else global_variables
        return store.get(name) == value
    if trigger.trigger_type == "global_gt":
        scope = str(params.get("scope", "global"))
        name = str(params.get("name", ""))
        value = params.get("value", 0)
        store = script_state.variables if scope == "local" else global_variables
        return store.get(name, 0) > value
    if trigger.trigger_type == "global_lt":
        scope = str(params.get("scope", "global"))
        name = str(params.get("name", ""))
        value = params.get("value", 0)
        store = script_state.variables if scope == "local" else global_variables
        return store.get(name, 0) < value
    if trigger.trigger_type == "in_party":
        return str(params.get("actor_id", "")) in set(world_context.get("party_ids", []))
    if trigger.trigger_type == "level_gt":
        target = resolve_target(str(params.get("target", "myself")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return int(target.raw_payload.get("level", 0)) > int(params.get("level", 0))
    if trigger.trigger_type == "alignment":
        target = resolve_target(str(params.get("target", "myself")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return target.raw_payload.get("alignment") == params.get("alignment")
    if trigger.trigger_type == "range":
        target = resolve_target(str(params.get("target", "nearest_enemy")), actor, world_context)
        if not isinstance(target, ActorRecord):
            return False
        return _distance(actor, target) <= float(params.get("distance", 0))
    if trigger.trigger_type == "time_of_day":
        hour = float(world_context.get("hour", 0))
        return float(params.get("hour_start", 0)) <= hour <= float(params.get("hour_end", 24))
    if trigger.trigger_type == "num_enemies_gt":
        return len(_visible_enemies(actor, list(world_context.get("actors", [])), world_context)) > int(params.get("count", 0))
    if trigger.trigger_type == "num_allies_lt":
        allies = [
            candidate
            for candidate in world_context.get("actors", [])
            if candidate.identity.actor_id != actor.identity.actor_id
            and candidate.identity.faction_id == actor.identity.faction_id
            and _distance(actor, candidate) <= int(actor.raw_payload.get("visual_range", 10))
        ]
        return len(allies) < int(params.get("count", 0))
    if trigger.trigger_type == "heard_shout":
        message_id = str(params.get("message_id", ""))
        return bool(script_state.variables.get(f"heard_shout_{message_id}", False))
    logger.warning("Unknown trigger_type: %s", trigger.trigger_type)
    return False


def _visible_enemies(actor: ActorRecord, actors: list[ActorRecord], world_context: dict) -> list[ActorRecord]:
    visual_range = int(actor.raw_payload.get("visual_range", 10))
    return [
        candidate
        for candidate in actors
        if candidate.identity.actor_id != actor.identity.actor_id
        and candidate.identity.faction_id != actor.identity.faction_id
        and _distance(actor, candidate) <= visual_range
    ]


def _nearest_actor(actor: ActorRecord, candidates: list[ActorRecord]) -> ActorRecord | None:
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: (_distance(actor, candidate), candidate.identity.actor_id))


def _distance(a: ActorRecord, b: ActorRecord) -> float:
    return abs(a.position.x - b.position.x) + abs(a.position.y - b.position.y)


def _hp_percent(actor: ActorRecord) -> float:
    max_hp = max(1.0, float(actor.stats.get("max_hp", 1)))
    return (float(actor.stats.get("hp", 0)) / max_hp) * 100.0
