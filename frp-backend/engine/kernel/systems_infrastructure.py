from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord, WoundRecord
from engine.kernel.common import serialize_value


@dataclass
class PowerNodeState:
    node_id: str
    kind: str
    role: str
    power_delta: int
    connected_to: list[str] = field(default_factory=list)
    disengaged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PowerNodeState":
        payload = dict(data)
        payload["connected_to"] = [str(item) for item in payload.get("connected_to", [])]
        return cls(**payload)


@dataclass
class PowerNetworkState:
    nodes: list[PowerNodeState] = field(default_factory=list)
    total_available: int = 0
    total_required: int = 0
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PowerNetworkState":
        payload = dict(data)
        payload["nodes"] = [
            node if isinstance(node, PowerNodeState) else PowerNodeState.from_dict(dict(node))
            for node in payload.get("nodes", [])
        ]
        return cls(**payload)


@dataclass
class TrapComponent:
    component_id: str
    component_type: str
    material_id: str = "iron"
    quality: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrapComponent":
        return cls(**data)


@dataclass
class TrapState:
    trap_id: str
    trap_type: str
    armed: bool
    trigger: str
    components: list[TrapComponent] = field(default_factory=list)
    reusable: bool = False
    linked_lever_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrapState":
        payload = dict(data)
        payload["components"] = [
            item if isinstance(item, TrapComponent) else TrapComponent.from_dict(dict(item))
            for item in payload.get("components", [])
        ]
        return cls(**payload)


def compute_power_network(settlement_state: dict) -> PowerNetworkState:
    nodes_payload = settlement_state.get("power_nodes")
    if nodes_payload:
        nodes = [node_from_payload(payload) for payload in nodes_payload]
        return recompute_power_network(PowerNetworkState(nodes=nodes))
    return power_network_from_settlement(settlement_state)


def toggle_gear(network: PowerNetworkState, gear_id: str) -> PowerNetworkState:
    for node in network.nodes:
        if node.node_id == gear_id and node.kind == "gear_assembly":
            node.disengaged = not node.disengaged
            break
    return recompute_power_network(network)


def check_trap_triggers(
    traps: list[TrapState],
    unit_positions: dict[str, Any],
    trap_positions: dict[str, tuple[int, int]],
) -> list[dict]:
    events: list[dict] = []
    for trap in traps:
        if not trap.armed:
            continue
        trap_position = trap_positions.get(trap.trap_id)
        if trap_position is None:
            continue
        for actor_id, payload in unit_positions.items():
            if isinstance(payload, dict):
                position = tuple(payload.get("position", (0, 0)))
                tags = {str(tag) for tag in payload.get("tags", [])}
            else:
                position = tuple(payload)
                tags = set()
            if tuple(position) != tuple(trap_position):
                continue
            if "trap_avoid" in tags and trap.trap_type == "cage_trap":
                continue
            event = {
                "trap_id": trap.trap_id,
                "target_actor_id": actor_id,
                "damage_type": "blunt",
                "damage_amount": 0,
                "damage_count": 0,
                "captured": False,
            }
            if trap.trap_type == "weapon_trap":
                event["damage_type"] = "weapon"
                event["damage_count"] = sum(1 for component in trap.components if component.component_type == "weapon")
                event["damage_amount"] = event["damage_count"] * 10
            elif trap.trap_type == "cage_trap":
                event["captured"] = True
                trap.armed = False
            elif trap.trap_type == "stone_fall":
                event["damage_amount"] = 20 * max(1, len(trap.components))
                trap.armed = False
            elif trap.trap_type == "upright_spike":
                event["damage_type"] = "piercing"
                event["damage_count"] = max(1, len(trap.components))
                event["damage_amount"] = event["damage_count"] * 8
                if not trap.reusable:
                    trap.armed = False
            if not trap.reusable and trap.trap_type not in {"weapon_trap", "upright_spike"}:
                trap.armed = False
            events.append(event)
    return events


def resolve_trap_damage(trap: TrapState, target: ActorRecord, seed: int) -> list[WoundRecord]:
    rng = Random(int(seed))
    wounds: list[WoundRecord] = []
    if trap.trap_type == "weapon_trap":
        count = sum(1 for component in trap.components if component.component_type == "weapon")
        for index in range(count):
            wounds.append(make_wound(f"{trap.trap_id}_{index}", "piercing", 8 + rng.randint(0, 4)))
    elif trap.trap_type == "stone_fall":
        wounds.append(make_wound(trap.trap_id, "blunt", 20 + (5 * len(trap.components))))
    elif trap.trap_type == "upright_spike":
        wounds.append(make_wound(trap.trap_id, "piercing", 12))
    for wound in wounds:
        if target.body_state is not None:
            target.body_state.apply_wound(wound)
    return wounds


def power_network_from_settlement(settlement_state: dict[str, Any]) -> PowerNetworkState:
    if settlement_state.get("power_nodes"):
        return compute_power_network(settlement_state)
    nodes: list[PowerNodeState] = []
    for room in settlement_state.get("rooms", []):
        for workstation in room.get("workstations", []):
            workstation_id = f"{room.get('id', 'room')}::{workstation}"
            if workstation in {"well", "waterwheel", "water_wheel"}:
                nodes.append(PowerNodeState(node_id=workstation_id, kind=str(workstation), role="source", power_delta=20))
            elif workstation == "windmill":
                nodes.append(PowerNodeState(node_id=workstation_id, kind="windmill", role="source", power_delta=40))
            elif workstation in {"forge", "mill", "pump", "roller", "loom", "press", "bar_counter"}:
                nodes.append(PowerNodeState(node_id=workstation_id, kind=str(workstation), role="consumer", power_delta=-10))
    return recompute_power_network(PowerNetworkState(nodes=nodes))


def trap_state_from_settlement(settlement_state: dict[str, Any]) -> list[TrapState]:
    if str(settlement_state.get("defense_posture", "normal")) != "fortified":
        return []
    return [
        TrapState(trap_id="gate_spikes", trap_type="upright_spike", armed=True, trigger="pressure_plate", reusable=True),
        TrapState(trap_id="courtyard_alarm", trap_type="lever_alarm", armed=True, trigger="lever"),
    ]


def recompute_power_network(network: PowerNetworkState) -> PowerNetworkState:
    node_map = {node.node_id: node for node in network.nodes}
    sources = [node for node in network.nodes if node.role == "source"]
    if any(node.connected_to for node in network.nodes):
        reachable: set[str] = set()
        stack = [node.node_id for node in sources]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            node = node_map.get(node_id)
            if node is None:
                continue
            reachable.add(node_id)
            if node.kind == "gear_assembly" and node.disengaged:
                continue
            for neighbor_id in node.connected_to:
                neighbor = node_map.get(neighbor_id)
                if neighbor is None:
                    continue
                if neighbor.kind == "gear_assembly" and neighbor.disengaged:
                    continue
                stack.append(neighbor_id)
        considered = [node_map[node_id] for node_id in reachable]
    else:
        considered = [node for node in network.nodes if not (node.kind == "gear_assembly" and node.disengaged)]
    network.total_available = sum(node.power_delta for node in considered if node.power_delta > 0)
    network.total_required = abs(sum(node.power_delta for node in considered if node.power_delta < 0))
    network.active = network.total_available >= network.total_required if network.total_required > 0 else network.total_available > 0
    return network


def node_from_payload(payload: dict[str, Any]) -> PowerNodeState:
    return PowerNodeState(
        node_id=str(payload["node_id"]),
        kind=str(payload.get("kind", "gear_assembly")),
        role=str(payload.get("role", "transmitter")),
        power_delta=int(payload.get("power_delta", 0)),
        connected_to=[str(item) for item in payload.get("connected_to", [])],
        disengaged=bool(payload.get("disengaged", False)),
    )


def make_wound(wound_id: str, damage_type: str, damage_amount: int) -> WoundRecord:
    return WoundRecord(
        wound_id=str(wound_id),
        body_part_id="torso",
        damage_type=damage_type,
        damage_amount=int(damage_amount),
        bleeding=max(0, int(damage_amount // 4)) if damage_type in {"piercing", "slashing", "fire"} else 0,
        pain=max(1, int(damage_amount)),
        open_wound=True,
        untreated=True,
        vital=True,
    )


__all__ = [
    "PowerNetworkState",
    "PowerNodeState",
    "TrapComponent",
    "TrapState",
    "check_trap_triggers",
    "compute_power_network",
    "power_network_from_settlement",
    "resolve_trap_damage",
    "toggle_gear",
    "trap_state_from_settlement",
]
