from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from random import Random
from typing import Any

from engine.kernel.actor import ActorRecord, ConditionRecord, ItemStack, WoundRecord
from engine.kernel.colony import ColonyPressureState
from engine.kernel.common import serialize_value
from engine.worldgen.models import RegionSnapshot


@dataclass
class SyndromeEffect:
    effect_id: str
    effect_type: str
    severity: int
    target: str | None = None
    start_tick: int = 0
    end_tick: int = -1
    tick_counter: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class SyndromeDef:
    syndrome_id: str
    name: str
    delivery: str
    resistance_dc: int = 10
    contagious: bool = False
    contagion_probability: float = 0.05
    effects: list[SyndromeEffect] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


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


@dataclass
class PowerNetworkState:
    nodes: list[PowerNodeState] = field(default_factory=list)
    total_available: int = 0
    total_required: int = 0
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class TrapComponent:
    component_id: str
    component_type: str
    material_id: str = "iron"
    quality: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


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


@dataclass
class FluidCell:
    x: int
    y: int
    fluid_type: str
    level: int

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class FluidState:
    cells: list[FluidCell] = field(default_factory=list)
    fluid_counts: dict[str, int] = field(default_factory=dict)
    pressure_enabled: bool = False
    muddy_floor_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class TemperatureState:
    ambient_band: str
    ambient_value: int = 10015
    hazardous: bool = False
    heat_sources: list[dict[str, Any]] = field(default_factory=list)
    cold_threshold: int = 10000
    heat_threshold: int = 10500
    tags: list[str] = field(default_factory=list)
    tile_states: dict[tuple[int, int], str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ambient_band": self.ambient_band,
            "ambient_value": self.ambient_value,
            "hazardous": self.hazardous,
            "heat_sources": serialize_value(self.heat_sources),
            "cold_threshold": self.cold_threshold,
            "heat_threshold": self.heat_threshold,
            "tags": list(self.tags),
            "tile_states": {f"{x},{y}": value for (x, y), value in self.tile_states.items()},
        }


@dataclass
class MaterialDemand:
    material_tag: str
    satisfied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class StrangeMoodIncident:
    incident_id: str
    state: str
    trigger_reason: str
    mood_type: str = ""
    actor_id: str = ""
    claimed_worksite_id: str = ""
    material_demands: list[MaterialDemand] = field(default_factory=list)
    timeout_ticks: int = 500
    elapsed_ticks: int = 0
    artifact_item_id: str | None = None
    candidate_actor_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


def syndrome_registry_from_actors(actors: list[ActorRecord]) -> list[SyndromeDef]:
    registry: list[SyndromeDef] = []
    seen: set[str] = set()
    for actor in actors:
        for condition in actor.conditions:
            syndrome_id = f"condition::{condition.condition_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=condition.name,
                    delivery="contact",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{condition.condition_id}::severity",
                            effect_type=condition.name,
                            severity=int(condition.severity),
                            target="actor",
                        )
                    ],
                )
            )
        if actor.body_state is None:
            continue
        for condition in actor.body_state.conditions:
            syndrome_id = f"body_condition::{condition.condition_id}"
            if syndrome_id in seen:
                continue
            seen.add(syndrome_id)
            registry.append(
                SyndromeDef(
                    syndrome_id=syndrome_id,
                    name=condition.name,
                    delivery="body_state",
                    effects=[
                        SyndromeEffect(
                            effect_id=f"{condition.condition_id}::severity",
                            effect_type=condition.name,
                            severity=int(condition.severity),
                            target="body",
                        )
                    ],
                )
            )
    return registry


def apply_syndrome(actor: ActorRecord, syndrome: SyndromeDef, seed: int) -> bool:
    disease_resistance = int(actor.stats.get("disease_resistance", actor.stats.get("DISEASE_RESISTANCE", 0)))
    toughness = int(actor.stats.get("TOUGHNESS", actor.stats.get("END", actor.stats.get("CON", 10))))
    d20 = _resolve_d20(seed)
    resistance_total = d20 + disease_resistance + (toughness // 2)
    if resistance_total >= int(syndrome.resistance_dc):
        return False
    actor.raw_payload.setdefault("active_syndromes", []).append(
        {
            "syndrome_id": syndrome.syndrome_id,
            "name": syndrome.name,
            "delivery": syndrome.delivery,
            "contagious": syndrome.contagious,
            "contagion_probability": syndrome.contagion_probability,
            "effects": [effect.to_dict() for effect in syndrome.effects],
        }
    )
    return True


def tick_syndromes(actor: ActorRecord) -> list[str]:
    active = list(actor.raw_payload.get("active_syndromes", []))
    kept: list[dict[str, Any]] = []
    events: list[str] = []
    for syndrome in active:
        effects = list(syndrome.get("effects", []))
        kept_effects: list[dict[str, Any]] = []
        for effect in effects:
            tick_counter = int(effect.get("tick_counter", 0))
            start_tick = int(effect.get("start_tick", 0))
            end_tick = int(effect.get("end_tick", -1))
            if tick_counter >= start_tick and (end_tick == -1 or tick_counter <= end_tick):
                _apply_syndrome_effect(actor, effect)
                events.append(str(effect.get("effect_type", "unknown")))
            tick_counter += 1
            effect["tick_counter"] = tick_counter
            if end_tick == -1 or tick_counter <= end_tick:
                kept_effects.append(effect)
        if kept_effects:
            syndrome["effects"] = kept_effects
            kept.append(syndrome)
    actor.raw_payload["active_syndromes"] = kept
    return events


def spread_contagion(actors: list[ActorRecord], region_tiles: dict) -> list[tuple[str, str]]:
    del region_tiles
    infections: list[tuple[str, str]] = []
    for source in actors:
        for syndrome in source.raw_payload.get("active_syndromes", []):
            if not bool(syndrome.get("contagious", False)):
                continue
            probability = float(syndrome.get("contagion_probability", 0.0))
            for target in actors:
                if target.identity.actor_id == source.identity.actor_id:
                    continue
                if abs(target.position.x - source.position.x) + abs(target.position.y - source.position.y) > 1:
                    continue
                if _has_active_syndrome(target, str(syndrome.get("syndrome_id", ""))):
                    continue
                if _deterministic_probability(source.identity.actor_id, target.identity.actor_id) <= probability:
                    target.raw_payload.setdefault("active_syndromes", []).append(
                        {
                            "syndrome_id": syndrome["syndrome_id"],
                            "name": syndrome["name"],
                            "delivery": syndrome["delivery"],
                            "contagious": syndrome.get("contagious", False),
                            "contagion_probability": syndrome.get("contagion_probability", 0.0),
                            "effects": [dict(effect) for effect in syndrome.get("effects", [])],
                        }
                    )
                    infections.append((source.identity.actor_id, target.identity.actor_id))
    return infections


def compute_power_network(settlement_state: dict) -> PowerNetworkState:
    nodes_payload = settlement_state.get("power_nodes")
    if nodes_payload:
        nodes = [_node_from_payload(payload) for payload in nodes_payload]
        return _recompute_power_network(PowerNetworkState(nodes=nodes))
    return power_network_from_settlement(settlement_state)


def toggle_gear(network: PowerNetworkState, gear_id: str) -> PowerNetworkState:
    for node in network.nodes:
        if node.node_id == gear_id and node.kind == "gear_assembly":
            node.disengaged = not node.disengaged
            break
    return _recompute_power_network(network)


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
            wounds.append(_make_wound(f"{trap.trap_id}_{index}", "piercing", 8 + rng.randint(0, 4)))
    elif trap.trap_type == "stone_fall":
        wounds.append(_make_wound(trap.trap_id, "blunt", 20 + (5 * len(trap.components))))
    elif trap.trap_type == "upright_spike":
        wounds.append(_make_wound(trap.trap_id, "piercing", 12))
    for wound in wounds:
        if target.body_state is not None:
            target.body_state.apply_wound(wound)
    return wounds


def tick_fluids(fluid_state: FluidState, terrain: list[list[dict]]) -> FluidState:
    cells = [FluidCell(cell.x, cell.y, cell.fluid_type, max(0, min(7, int(cell.level)))) for cell in fluid_state.cells]
    by_coord: dict[tuple[int, int], list[FluidCell]] = {}
    for cell in cells:
        by_coord.setdefault((cell.x, cell.y), []).append(cell)

    consumed: set[tuple[int, int]] = set()
    for coord, group in by_coord.items():
        kinds = {cell.fluid_type for cell in group if cell.level > 0}
        if {"water", "magma"} <= kinds:
            x, y = coord
            terrain[y][x]["terrain"] = "obsidian"
            consumed.add(coord)

    if consumed:
        cells = [cell for cell in cells if (cell.x, cell.y) not in consumed]
        by_coord = {}
        for cell in cells:
            by_coord.setdefault((cell.x, cell.y), []).append(cell)

    transfers: list[tuple[FluidCell, tuple[int, int]]] = []
    for cell in cells:
        if cell.level <= 1:
            continue
        for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1)):
            nx, ny = cell.x + dx, cell.y + dy
            if ny < 0 or ny >= len(terrain) or nx < 0 or nx >= len(terrain[0]):
                continue
            neighbor = next((other for other in cells if other.x == nx and other.y == ny and other.fluid_type == cell.fluid_type), None)
            neighbor_level = neighbor.level if neighbor is not None else 0
            if neighbor_level < cell.level:
                transfers.append((cell, (nx, ny)))
                break

    for cell, target in transfers:
        if cell.level <= 0:
            continue
        cell.level -= 1
        neighbor = next((other for other in cells if other.x == target[0] and other.y == target[1] and other.fluid_type == cell.fluid_type), None)
        if neighbor is None:
            cells.append(FluidCell(x=target[0], y=target[1], fluid_type=cell.fluid_type, level=1))
        else:
            neighbor.level = min(7, neighbor.level + 1)

    counts = {"water": 0, "magma": 0}
    for cell in cells:
        counts[cell.fluid_type] = counts.get(cell.fluid_type, 0) + max(0, int(cell.level))
    return FluidState(
        cells=[cell for cell in cells if cell.level > 0],
        fluid_counts=counts,
        pressure_enabled=counts.get("water", 0) > 8,
        muddy_floor_risk=any(cell.fluid_type == "water" and terrain[cell.y][cell.x].get("terrain") == "soil" for cell in cells),
    )


def check_drowning(actor: ActorRecord, fluid_state: FluidState) -> bool:
    cell = next((cell for cell in fluid_state.cells if cell.x == actor.position.x and cell.y == actor.position.y and cell.fluid_type == "water"), None)
    if cell is None or cell.level < 7:
        actor.raw_payload["suffocation_ticks"] = 0
        return False
    actor.raw_payload["suffocation_ticks"] = int(actor.raw_payload.get("suffocation_ticks", 0)) + 1
    if actor.raw_payload["suffocation_ticks"] >= 10:
        actor.alive = False
        return True
    return False


def check_magma_damage(actor: ActorRecord, fluid_state: FluidState) -> WoundRecord | None:
    cell = next((cell for cell in fluid_state.cells if cell.x == actor.position.x and cell.y == actor.position.y and cell.fluid_type == "magma" and cell.level > 0), None)
    if cell is None:
        return None
    wound = _make_wound("magma", "fire", 25)
    if actor.body_state is not None:
        actor.body_state.apply_wound(wound)
    actor.conditions.append(ConditionRecord(condition_id="ignition", name="burning", severity=20))
    return wound


def tick_temperature(temp_state: TemperatureState, actors: list[ActorRecord]) -> list[dict]:
    events: list[dict] = []
    for actor in actors:
        if temp_state.ambient_value < temp_state.cold_threshold:
            actor.raw_payload["cold_ticks"] = int(actor.raw_payload.get("cold_ticks", 0)) + 1
            if actor.raw_payload["cold_ticks"] >= 3:
                events.append({"type": "frostbite", "actor_id": actor.identity.actor_id})
        else:
            actor.raw_payload["cold_ticks"] = 0
        if temp_state.ambient_value > temp_state.heat_threshold:
            actor.raw_payload["heat_ticks"] = int(actor.raw_payload.get("heat_ticks", 0)) + 1
            events.append({"type": "heat", "actor_id": actor.identity.actor_id})
            ignite_point = actor.raw_payload.get("organic_item_ignite_point")
            if ignite_point is not None and temp_state.ambient_value >= int(ignite_point):
                events.append({"type": "item_ignited", "actor_id": actor.identity.actor_id})
        else:
            actor.raw_payload["heat_ticks"] = 0

    updated_tile_states: dict[tuple[int, int], str] = {}
    for coord, state in temp_state.tile_states.items():
        if state == "water" and temp_state.ambient_value < temp_state.cold_threshold:
            updated_tile_states[coord] = "ice"
            events.append({"type": "freeze", "tile": coord})
        elif state == "ice" and temp_state.ambient_value >= temp_state.cold_threshold:
            updated_tile_states[coord] = "water"
            events.append({"type": "melt", "tile": coord})
        else:
            updated_tile_states[coord] = state
    temp_state.tile_states = updated_tile_states
    return events


def tick_strange_mood(
    incident: StrangeMoodIncident,
    settlement: dict,
    actors: list[ActorRecord],
    seed: int,
) -> StrangeMoodIncident:
    actor_map = {actor.identity.actor_id: actor for actor in actors}
    if incident.state == "triggered":
        chosen = next(
            (actor for actor in actors if actor.identity.actor_id in incident.candidate_actor_ids and _moodable(actor)),
            None,
        )
        if chosen is None:
            return incident
        incident.actor_id = chosen.identity.actor_id
        incident.mood_type = _choose_mood_type(chosen)
        worksites = settlement.get("worksites", [])
        incident.claimed_worksite_id = str(worksites[0]["id"]) if worksites else ""
        if not incident.material_demands:
            incident.material_demands = [MaterialDemand("metal_bar")]
        incident.state = "demanding_materials"
        return incident

    if incident.state == "demanding_materials":
        incident.elapsed_ticks += 1
        available = {str(item) for item in settlement.get("available_materials", [])}
        all_satisfied = True
        for demand in incident.material_demands:
            if demand.material_tag in available:
                demand.satisfied = True
            all_satisfied = all_satisfied and demand.satisfied
        if all_satisfied:
            incident.state = "working"
            return incident
        if incident.elapsed_ticks >= incident.timeout_ticks:
            incident.state = "failed"
            _apply_mood_failure(actor_map.get(incident.actor_id), incident.mood_type)
        return incident

    if incident.state == "working" and incident.artifact_item_id is None:
        actor = actor_map.get(incident.actor_id)
        if actor is None:
            return incident
        artifact = create_artifact(incident, actor, seed)
        incident.artifact_item_id = artifact.instance_id
        incident.state = "completed"
        return incident

    if incident.state == "failed":
        _apply_mood_failure(actor_map.get(incident.actor_id), incident.mood_type)
    return incident


def create_artifact(incident: StrangeMoodIncident, actor: ActorRecord, seed: int) -> ItemStack:
    suffix = abs(int(seed)) % 100000
    actor.skills["crafting"] = 20
    actor.raw_payload["morale_bonus"] = int(actor.raw_payload.get("morale_bonus", 0)) + 25
    return ItemStack(
        instance_id=f"artifact_{incident.incident_id}_{suffix}",
        item_def_id="artifact_item",
        quantity=1,
        quality=6,
        tags=["artifact"],
        payload={"value_multiplier": 120, "combat_multiplier": 3},
    )


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
    network = PowerNetworkState(nodes=nodes)
    return _recompute_power_network(network)


def trap_state_from_settlement(settlement_state: dict[str, Any]) -> list[TrapState]:
    defense_posture = str(settlement_state.get("defense_posture", "normal"))
    if defense_posture != "fortified":
        return []
    return [
        TrapState(trap_id="gate_spikes", trap_type="upright_spike", armed=True, trigger="pressure_plate", reusable=True),
        TrapState(trap_id="courtyard_alarm", trap_type="lever_alarm", armed=True, trigger="lever"),
    ]


def fluid_state_from_region(region_snapshot: RegionSnapshot) -> FluidState:
    cells: list[FluidCell] = []
    counts: dict[str, int] = {"water": 0, "magma": 0}
    for y, row in enumerate(region_snapshot.typed_tiles):
        for x, tile in enumerate(row):
            terrain = str(tile.get("terrain", ""))
            if terrain == "water":
                cells.append(FluidCell(x=x, y=y, fluid_type="water", level=7))
                counts["water"] += 7
            if terrain in {"lava", "magma"}:
                cells.append(FluidCell(x=x, y=y, fluid_type="magma", level=7))
                counts["magma"] += 7
    return FluidState(
        cells=cells,
        fluid_counts=counts,
        pressure_enabled=counts["water"] > 8,
        muddy_floor_risk=counts["water"] > 0 and any(str(tile.get("terrain", "")) == "floor" for row in region_snapshot.typed_tiles for tile in row),
    )


def temperature_state_from_region(region_snapshot: RegionSnapshot) -> TemperatureState:
    biome = str(region_snapshot.biome_id).lower()
    if "arctic" in biome or "ice" in biome or "tundra" in biome:
        return TemperatureState(ambient_band="cold", ambient_value=9990, hazardous=False, tags=["freezing_risk"])
    if "desert" in biome or "volcanic" in biome or "lava" in biome:
        return TemperatureState(ambient_band="hot", ambient_value=10600, hazardous=True, tags=["burn_risk"])
    return TemperatureState(ambient_band="temperate", ambient_value=10015, hazardous=False, tags=[])


def strange_mood_incident_from_settlement(
    settlement_state: dict[str, Any],
    colony_pressure: ColonyPressureState,
) -> StrangeMoodIncident | None:
    if not settlement_state.get("jobs"):
        return None
    if colony_pressure.morale > 75 and colony_pressure.unrest < 35:
        return None
    candidates = [
        str(resident.get("id"))
        for resident in settlement_state.get("residents", [])
        if str(resident.get("role")) not in {"commander", "guard"}
    ]
    return StrangeMoodIncident(
        incident_id="creative_pressure_event",
        state="triggered",
        trigger_reason="morale_pressure" if colony_pressure.morale < 70 else "unrest_pressure",
        candidate_actor_ids=candidates[:3],
    )


def _apply_syndrome_effect(actor: ActorRecord, effect: dict[str, Any]) -> None:
    effect_type = str(effect.get("effect_type", ""))
    severity = int(effect.get("severity", 0))
    if effect_type == "CE_PAIN":
        actor.raw_payload["pain"] = int(actor.raw_payload.get("pain", 0)) + severity
    elif effect_type == "CE_BLEEDING":
        actor.stats["blood_loss"] = int(actor.stats.get("blood_loss", 0)) + severity
    elif effect_type == "CE_PARALYSIS":
        actor.conditions.append(ConditionRecord(condition_id="paralysis", name="paralyzed", severity=severity))
    elif effect_type == "CE_NAUSEA":
        actor.conditions.append(ConditionRecord(condition_id="nausea", name="nausea", severity=severity))
    elif effect_type == "CE_FEVER":
        actor.raw_payload["fever"] = int(actor.raw_payload.get("fever", 0)) + severity
    elif effect_type == "CE_NUMBNESS":
        actor.raw_payload["numbness"] = int(actor.raw_payload.get("numbness", 0)) + severity
    elif effect_type == "CE_UNCONSCIOUSNESS":
        actor.conditions.append(ConditionRecord(condition_id="unconscious", name="unconscious", severity=severity))
    elif effect_type == "CE_NECROSIS":
        actor.conditions.append(ConditionRecord(condition_id="necrosis", name="necrosis", severity=severity))
    elif effect_type == "CE_PERSONALITY_CHANGE":
        actor.raw_payload["personality_shift"] = int(actor.raw_payload.get("personality_shift", 0)) + severity
    elif effect_type == "CE_SPEED_CHANGE":
        actor.raw_payload["speed_penalty"] = int(actor.raw_payload.get("speed_penalty", 0)) + severity
    elif effect_type == "CE_STAT_CHANGE":
        actor.stats["syndrome_stat_delta"] = int(actor.stats.get("syndrome_stat_delta", 0)) + severity


def _has_active_syndrome(actor: ActorRecord, syndrome_id: str) -> bool:
    return any(entry.get("syndrome_id") == syndrome_id for entry in actor.raw_payload.get("active_syndromes", []))


def _deterministic_probability(source_id: str, target_id: str) -> float:
    digest = hashlib.sha256(f"{source_id}->{target_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


def _resolve_d20(seed: int) -> int:
    if 1 <= int(seed) <= 20:
        return int(seed)
    return Random(int(seed)).randint(1, 20)


def _recompute_power_network(network: PowerNetworkState) -> PowerNetworkState:
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


def _node_from_payload(payload: dict[str, Any]) -> PowerNodeState:
    return PowerNodeState(
        node_id=str(payload["node_id"]),
        kind=str(payload.get("kind", "gear_assembly")),
        role=str(payload.get("role", "transmitter")),
        power_delta=int(payload.get("power_delta", 0)),
        connected_to=[str(item) for item in payload.get("connected_to", [])],
        disengaged=bool(payload.get("disengaged", False)),
    )


def _make_wound(wound_id: str, damage_type: str, damage_amount: int) -> WoundRecord:
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


def _moodable(actor: ActorRecord) -> bool:
    return any(int(value) > 0 for value in actor.skills.values())


def _choose_mood_type(actor: ActorRecord) -> str:
    personality = str(actor.raw_payload.get("personality", "calm")).lower()
    if personality in {"violent", "cruel"}:
        return "fell"
    if personality in {"grim", "dark"}:
        return "macabre"
    if personality in {"obsessive", "secretive"}:
        return "secretive"
    if personality in {"creative", "artistic"}:
        return "fey_crafter"
    return "possessed"


def _apply_mood_failure(actor: ActorRecord | None, mood_type: str) -> None:
    if actor is None:
        return
    outcome = "melancholy" if mood_type in {"fey_crafter", "secretive"} else "insane"
    if outcome == "insane" and mood_type == "fell":
        outcome = "insane"
    actor.conditions.append(ConditionRecord(condition_id=f"mood_{outcome}", name=outcome, severity=10))
