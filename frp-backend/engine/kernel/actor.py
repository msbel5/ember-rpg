from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine.kernel.common import serialize_value
from engine.world.body_parts import BodyPartTracker, DEFAULT_PART_HP
from engine.world.entity import Entity

if TYPE_CHECKING:
    from engine.kernel.effects import EffectQueue

VITAL_PART_IDS = {"head", "neck", "chest", "torso"}
_BODY_PART_LABELS = {
    "head": "Head",
    "neck": "Neck",
    "chest": "Chest",
    "torso": "Torso",
    "left_arm": "Left Arm",
    "right_arm": "Right Arm",
    "left_leg": "Left Leg",
    "right_leg": "Right Leg",
}
_BODY_PART_LAYER_BLUEPRINTS = {
    "head": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
        {"layer_id": "bone", "material_id": "bone", "relative_thickness": 3, "structural": True},
        {"layer_id": "brain", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
    "neck": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 1, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
        {"layer_id": "spine", "material_id": "bone", "relative_thickness": 2, "structural": True},
        {"layer_id": "artery", "material_id": "organ", "relative_thickness": 1, "under_pressure": True, "vital": True},
    ),
    "chest": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 3},
        {"layer_id": "ribcage", "material_id": "bone", "relative_thickness": 3, "structural": True},
        {"layer_id": "lungs", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
    "torso": (
        {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
        {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 3},
        {"layer_id": "spine", "material_id": "bone", "relative_thickness": 2, "structural": True},
        {"layer_id": "organs", "material_id": "organ", "relative_thickness": 2, "vital": True},
    ),
}
_DEFAULT_LAYER_BLUEPRINT = (
    {"layer_id": "skin", "material_id": "skin", "relative_thickness": 2, "under_pressure": True},
    {"layer_id": "muscle", "material_id": "muscle", "relative_thickness": 2},
    {"layer_id": "bone", "material_id": "bone", "relative_thickness": 2, "structural": True},
)
_DEFAULT_NEED_VALUES = {
    "eat": 100.0,
    "drink": 100.0,
    "sleep": 100.0,
    "pray": 100.0,
    "socialize": 100.0,
    "craft": 100.0,
    "train": 100.0,
    "admire_art": 100.0,
}


@dataclass
class ActorIdentity:
    actor_id: str
    display_name: str
    actor_type: str
    faction_id: str | None = None
    site_id: str | None = None
    species_id: str | None = None
    culture_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorIdentity":
        return cls(**data)


@dataclass
class ActorPosition:
    x: int
    y: int
    z: int = 0
    region_id: str | None = None
    site_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorPosition":
        return cls(**data)


@dataclass
class NeedState:
    values: dict[str, float] = field(default_factory=dict)
    mood: str = "steady"
    modifiers: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = {key: float(value) for key, value in self.values.items()}
        for need_id, default_value in _DEFAULT_NEED_VALUES.items():
            normalized.setdefault(need_id, default_value)
        self.values = normalized

    @classmethod
    def from_legacy(cls, legacy: Any) -> "NeedState":
        if legacy is None:
            return cls()
        if hasattr(legacy, "to_dict"):
            values = {str(key): float(value) for key, value in legacy.to_dict().items()}
            mood = str(legacy.emotional_state()) if hasattr(legacy, "emotional_state") else "steady"
            modifiers = (
                dict(legacy.behavior_modifiers())
                if hasattr(legacy, "behavior_modifiers")
                else {}
            )
            return cls(values=values, mood=mood, modifiers=modifiers)
            return cls(values={str(key): float(value) for key, value in dict(legacy).items()})

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeedState":
        return cls(
            values={str(key): float(value) for key, value in data.get("values", {}).items()},
            mood=str(data.get("mood", "steady")),
            modifiers=dict(data.get("modifiers", {})),
        )


@dataclass
class ScheduleEntry:
    period: str
    location_id: str | None = None
    position: list[int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleEntry":
        payload = dict(data)
        position = payload.get("position")
        metadata = dict(payload)
        period = str(
            payload.get("period")
            or payload.get("time_period")
            or payload.get("hour")
            or payload.get("activity")
            or "unscheduled"
        )
        location_id = payload.get("location_id") or payload.get("building_kind") or payload.get("activity")
        return cls(
            period=period,
            location_id=str(location_id) if location_id is not None else None,
            position=list(position) if position is not None else None,
            metadata=metadata,
        )


@dataclass
class ScheduleState:
    owner_id: str = ""
    owner_name: str = ""
    entries: list[ScheduleEntry] = field(default_factory=list)
    patrol_route: list[list[int]] = field(default_factory=list)

    @classmethod
    def from_legacy(cls, legacy: Any) -> "ScheduleState":
        if legacy is None:
            return cls()
        if hasattr(legacy, "to_dict"):
            data = legacy.to_dict()
        else:
            data = dict(legacy)
        entries: list[ScheduleEntry] = []
        locations = dict(data.get("locations", {}))
        positions = dict(data.get("positions", {}))
        if not entries:
            for period, location_id in locations.items():
                entries.append(
                    ScheduleEntry(
                        period=str(period),
                        location_id=str(location_id),
                        position=list(positions.get(period)) if positions.get(period) is not None else None,
                    )
                )
        for entry in data.get("entries", []):
            if isinstance(entry, dict):
                entries.append(ScheduleEntry.from_dict(entry))
        patrol_route = [list(point) for point in (data.get("patrol_route") or [])]
        return cls(
            owner_id=str(data.get("npc_id", data.get("owner_id", ""))),
            owner_name=str(data.get("npc_name", data.get("owner_name", ""))),
            entries=entries,
            patrol_route=patrol_route,
        )

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleState":
        return cls(
            owner_id=str(data.get("owner_id", "")),
            owner_name=str(data.get("owner_name", "")),
            entries=[ScheduleEntry.from_dict(item) for item in data.get("entries", [])],
            patrol_route=[list(point) for point in data.get("patrol_route", [])],
        )


@dataclass
class TissueLayerDef:
    layer_id: str
    material_id: str
    relative_thickness: int = 1
    structural: bool = False
    under_pressure: bool = False
    cosmetic: bool = False
    vital: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TissueLayerDef":
        return cls(**data)


@dataclass
class BodyPartDef:
    part_id: str
    label: str
    max_hp: int
    vital: bool = False
    parent_id: str | None = None
    relative_size: int = 1
    layers: list[TissueLayerDef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyPartDef":
        payload = dict(data)
        payload["layers"] = [TissueLayerDef.from_dict(item) for item in payload.get("layers", [])]
        return cls(**payload)


@dataclass
class BodyPlanDef:
    plan_id: str
    label: str
    parts: list[BodyPartDef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyPlanDef":
        payload = dict(data)
        payload["parts"] = [BodyPartDef.from_dict(item) for item in payload.get("parts", [])]
        return cls(**payload)


@dataclass
class BodyPartState:
    part_id: str
    current_hp: int
    max_hp: int
    status: str = "healthy"
    bleed_rate: int = 0
    pain: int = 0
    mobility_penalty: int = 0

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyPartState":
        return cls(**data)


@dataclass
class WoundRecord:
    wound_id: str
    body_part_id: str
    damage_type: str
    damage_amount: int
    bleeding: int = 0
    pain: int = 0
    destroyed: bool = False
    open_wound: bool = False
    infected: bool = False
    untreated: bool = True
    fracture: bool = False
    crippled: bool = False
    vital: bool = False
    armor_absorbed: int = 0
    attack_force: int = 0
    source_item_id: str | None = None
    layer_hits: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WoundRecord":
        payload = dict(data)
        payload["layer_hits"] = [str(item) for item in payload.get("layer_hits", [])]
        payload["tags"] = [str(item) for item in payload.get("tags", [])]
        return cls(**payload)


@dataclass
class ConditionRecord:
    condition_id: str
    name: str
    duration_ticks: int | None = None
    severity: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionRecord":
        return cls(**data)


@dataclass
class BodyState:
    plan: BodyPlanDef
    parts: dict[str, BodyPartState] = field(default_factory=dict)
    wounds: list[WoundRecord] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)

    @classmethod
    def from_tracker(
        cls,
        tracker: BodyPartTracker,
        *,
        plan_id: str = "legacy_humanoid",
        label: str = "Legacy Humanoid",
    ) -> "BodyState":
        part_defs: list[BodyPartDef] = []
        part_states: dict[str, BodyPartState] = {}
        injury_effects = tracker.get_injury_effects()
        for part_id, max_hp in tracker.max_hp.items():
            current_hp = int(tracker.current_hp.get(part_id, max_hp))
            vital = part_id in VITAL_PART_IDS
            status = injury_effects.get(part_id, "healthy")
            layers = [
                TissueLayerDef(**layer)
                for layer in _BODY_PART_LAYER_BLUEPRINTS.get(part_id, _DEFAULT_LAYER_BLUEPRINT)
            ]
            part_defs.append(
                BodyPartDef(
                    part_id=part_id,
                    label=_BODY_PART_LABELS.get(part_id, part_id.replace("_", " ").title()),
                    max_hp=int(max_hp),
                    vital=vital,
                    relative_size=int(max_hp),
                    layers=layers,
                )
            )
            part_states[part_id] = BodyPartState(
                part_id=part_id,
                current_hp=current_hp,
                max_hp=int(max_hp),
                status=status,
                mobility_penalty=2 if status in {"crippled", "destroyed"} and "leg" in part_id else 0,
            )
        return cls(plan=BodyPlanDef(plan_id=plan_id, label=label, parts=part_defs), parts=part_states)

    def part_def(self, part_id: str) -> BodyPartDef:
        for part in self.plan.parts:
            if part.part_id == part_id:
                return part
        raise ValueError(f"Unknown body part `{part_id}`")

    def apply_wound(self, wound: WoundRecord) -> None:
        if wound.body_part_id not in self.parts:
            raise ValueError(f"Unknown body part `{wound.body_part_id}`")
        part_state = self.parts[wound.body_part_id]
        part_def = self.part_def(wound.body_part_id)
        part_state.current_hp = max(0, part_state.current_hp - max(wound.damage_amount, 0))
        part_state.status = _status_for_ratio(part_state.current_hp, part_state.max_hp)
        part_state.bleed_rate = max(part_state.bleed_rate, int(wound.bleeding))
        part_state.pain += max(0, int(wound.pain))
        if wound.fracture or part_state.status in {"crippled", "destroyed"}:
            part_state.mobility_penalty = max(part_state.mobility_penalty, 2 if "leg" in wound.body_part_id else 1)
        wound.destroyed = part_state.current_hp == 0 or wound.destroyed
        wound.crippled = wound.crippled or part_state.status in {"crippled", "destroyed"}
        wound.vital = wound.vital or part_def.vital
        if wound.open_wound and wound.untreated:
            self._upsert_condition(
                ConditionRecord(
                    condition_id=f"bleeding_{wound.body_part_id}",
                    name="bleeding",
                    severity=max(1, int(wound.bleeding)),
                    tags=[wound.body_part_id],
                )
            )
        if wound.infected:
            self._upsert_condition(
                ConditionRecord(
                    condition_id=f"infection_{wound.body_part_id}",
                    name="infection",
                    severity=max(1, int(wound.damage_amount)),
                    tags=[wound.body_part_id],
                )
            )
        self.wounds.append(wound)

    def blood_loss_rate(self) -> int:
        return sum(max(0, part.bleed_rate) for part in self.parts.values())

    def total_pain(self) -> int:
        return sum(max(0, part.pain) for part in self.parts.values())

    def is_viable(self) -> bool:
        vital_parts = {part.part_id for part in self.plan.parts if part.vital}
        if not all(self.parts.get(part_id, BodyPartState(part_id, 0, 1)).current_hp > 0 for part_id in vital_parts):
            return False
        return self.blood_loss_rate() < max(1, sum(part.max_hp for part in self.parts.values()) // 2)

    def to_tracker(self) -> BodyPartTracker:
        tracker = BodyPartTracker(
            max_hp={part.part_id: part.max_hp for part in self.plan.parts},
            current_hp={
                part.part_id: self.parts.get(part.part_id, BodyPartState(part.part_id, part.max_hp, part.max_hp)).current_hp
                for part in self.plan.parts
            },
        )
        return tracker

    def _upsert_condition(self, condition: ConditionRecord) -> None:
        existing = next((item for item in self.conditions if item.condition_id == condition.condition_id), None)
        if existing is None:
            self.conditions.append(condition)
            return
        existing.severity = max(existing.severity, condition.severity)
        existing.tags = sorted(set(existing.tags) | set(condition.tags))

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyState":
        payload = dict(data)
        payload["plan"] = BodyPlanDef.from_dict(payload["plan"])
        payload["parts"] = {
            key: BodyPartState.from_dict(value) for key, value in payload.get("parts", {}).items()
        }
        payload["wounds"] = [WoundRecord.from_dict(item) for item in payload.get("wounds", [])]
        payload["conditions"] = [
            ConditionRecord.from_dict(item) for item in payload.get("conditions", [])
        ]
        return cls(**payload)


@dataclass
class MaterialDef:
    material_id: str
    label: str
    category: str
    density: int = 0
    impact_yield: int = 0
    impact_fracture: int = 0
    shear_yield: int = 0
    shear_fracture: int = 0
    max_edge: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialDef":
        return cls(**data)


@dataclass
class ItemDef:
    item_id: str
    label: str
    category: str
    slot: str | None = None
    coverage: list[str] = field(default_factory=list)
    default_material_id: str | None = None
    attack_profile: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemDef":
        return cls(**data)


@dataclass
class ItemStack:
    instance_id: str
    item_def_id: str
    quantity: int = 1
    material_id: str | None = None
    quality: int = 0
    wear: int = 0
    sharpness: int = 100
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemStack":
        return cls(**data)


@dataclass
class EquipmentLoadout:
    slots: dict[str, list[ItemStack]] = field(default_factory=dict)

    def add_item(self, slot: str, item: ItemStack) -> None:
        self.slots.setdefault(slot, []).append(item)

    def covered_parts(self) -> set[str]:
        covered: set[str] = set()
        for items in self.slots.values():
            for item in items:
                coverage = item.payload.get("coverage", [])
                if not coverage:
                    coverage = item.payload.get("covers", [])
                for part_id in coverage:
                    covered.add(str(part_id))
        return covered

    def covering_items(self, part_id: str) -> list[tuple[str, ItemStack]]:
        matches: list[tuple[str, ItemStack]] = []
        for slot, items in self.slots.items():
            for item in items:
                coverage = set(str(entry) for entry in item.payload.get("coverage", []))
                coverage.update(str(entry) for entry in item.payload.get("covers", []))
                if part_id in coverage:
                    matches.append((slot, item))
        matches.sort(key=lambda pair: _equipment_layer_order(pair[0]))
        return matches

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EquipmentLoadout":
        payload = dict(data)
        payload["slots"] = {
            key: [ItemStack.from_dict(item) for item in items]
            for key, items in payload.get("slots", {}).items()
        }
        return cls(**payload)


@dataclass
class ActorRecord:
    identity: ActorIdentity
    position: ActorPosition
    action_points: int
    max_action_points: int
    alive: bool
    stats: dict[str, int | float] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    needs: NeedState = field(default_factory=NeedState)
    schedule: ScheduleState = field(default_factory=ScheduleState)
    body_state: BodyState | None = None
    inventory: list[ItemStack] = field(default_factory=list)
    equipment: EquipmentLoadout = field(default_factory=EquipmentLoadout)
    conditions: list[ConditionRecord] = field(default_factory=list)
    effect_queue: "EffectQueue | None" = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorRecord":
        payload = dict(data)
        payload["identity"] = ActorIdentity.from_dict(payload["identity"])
        payload["position"] = ActorPosition.from_dict(payload["position"])
        needs = payload.get("needs")
        payload["needs"] = NeedState.from_dict(needs) if isinstance(needs, dict) else NeedState()
        schedule = payload.get("schedule")
        payload["schedule"] = ScheduleState.from_dict(schedule) if isinstance(schedule, dict) else ScheduleState()
        body_state = payload.get("body_state")
        payload["body_state"] = BodyState.from_dict(body_state) if body_state else None
        payload["inventory"] = [ItemStack.from_dict(item) for item in payload.get("inventory", [])]
        payload["equipment"] = EquipmentLoadout.from_dict(payload.get("equipment", {}))
        payload["conditions"] = [
            ConditionRecord.from_dict(item) for item in payload.get("conditions", [])
        ]
        effect_queue = payload.get("effect_queue")
        if isinstance(effect_queue, dict):
            from engine.kernel.effects import EffectQueue

            payload["effect_queue"] = EffectQueue.from_dict(effect_queue)
        return cls(**payload)


def item_stack_from_legacy_payload(payload: dict[str, Any], *, index: int = 0) -> ItemStack:
    item_name = str(payload.get("name", payload.get("id", f"item_{index}"))).strip() or f"item_{index}"
    instance_id = str(payload.get("instance_id", payload.get("id", f"legacy_item_{index}")))
    item_def_id = str(payload.get("item_def_id", item_name.lower().replace(" ", "_")))
    quantity = max(1, int(payload.get("quantity", payload.get("count", 1))))
    material_id = payload.get("material_id") or payload.get("material") or payload.get("weapon_material")
    sharpness = int(payload.get("sharpness", 100))
    return ItemStack(
        instance_id=instance_id,
        item_def_id=item_def_id,
        quantity=quantity,
        material_id=str(material_id) if material_id else None,
        quality=int(payload.get("quality", 0)),
        wear=int(payload.get("wear", 0)),
        sharpness=sharpness,
        tags=[str(tag) for tag in payload.get("tags", [])],
        payload=dict(payload),
    )


def actor_record_from_entity(
    entity: Entity,
    *,
    site_id: str | None = None,
    species_id: str | None = None,
    culture_id: str | None = None,
    region_id: str | None = None,
) -> ActorRecord:
    identity = ActorIdentity(
        actor_id=entity.id,
        display_name=entity.name,
        actor_type=entity.entity_type.value,
        faction_id=entity.faction,
        site_id=site_id,
        species_id=species_id,
        culture_id=culture_id,
    )
    position = ActorPosition(
        x=int(entity.position[0]),
        y=int(entity.position[1]),
        region_id=region_id,
        site_id=site_id,
    )
    inventory_entries = list(entity.inventory or [])
    inventory = [item_stack_from_legacy_payload(entry, index=index) for index, entry in enumerate(inventory_entries)]
    equipment = EquipmentLoadout()
    for item in inventory:
        slot = str(item.payload.get("slot", item.payload.get("equip_slot", ""))).strip()
        if slot:
            equipment.add_item(slot, item)
    stats = {
        "hp": entity.hp,
        "max_hp": entity.max_hp,
    }
    return ActorRecord(
        identity=identity,
        position=position,
        action_points=entity.ap,
        max_action_points=entity.max_ap,
        alive=entity.alive,
        stats=stats,
        skills=dict(entity.skills or {}),
        needs=NeedState.from_legacy(entity.needs),
        schedule=ScheduleState.from_legacy(entity.schedule),
        body_state=BodyState.from_tracker(entity.body or BodyPartTracker()),
        inventory=inventory,
        equipment=equipment,
        raw_payload={
            "legacy_alignment": entity.alignment,
            "legacy_alignment_axes": dict(entity.alignment_axes or {}),
            "legacy_disposition": entity.disposition,
            "legacy_attitude": entity.attitude,
            "legacy_blocking": entity.blocking,
            "legacy_color": entity.color,
            "legacy_glyph": entity.glyph,
            "legacy_job": entity.job,
        },
    )


def actor_record_from_character(
    character: Any,
    *,
    actor_id: str,
    actor_type: str = "player",
    faction_id: str | None = None,
    site_id: str | None = None,
    region_id: str | None = None,
    position: tuple[int, int] = (0, 0),
    equipment_payloads: dict[str, dict[str, Any] | None] | None = None,
) -> ActorRecord:
    equipment = EquipmentLoadout()
    inventory: list[ItemStack] = []
    for index, (slot, payload) in enumerate((equipment_payloads or {}).items()):
        if not payload:
            continue
        item_payload = dict(payload)
        item_payload.setdefault("slot", slot)
        stack = item_stack_from_legacy_payload(item_payload, index=index)
        equipment.add_item(slot, stack)
        inventory.append(stack)
    return ActorRecord(
        identity=ActorIdentity(
            actor_id=actor_id,
            display_name=str(getattr(character, "name", actor_id)),
            actor_type=actor_type,
            faction_id=faction_id,
            site_id=site_id,
        ),
        position=ActorPosition(x=int(position[0]), y=int(position[1]), region_id=region_id, site_id=site_id),
        action_points=int(getattr(character, "ap", 0) or 0),
        max_action_points=int(getattr(character, "max_ap", getattr(character, "ap", 0) or 0) or 0),
        alive=int(getattr(character, "hp", 0)) > 0,
        stats=dict(getattr(character, "stats", {}) or {}),
        skills=dict(getattr(character, "skills", {}) or {}),
        needs=NeedState(),
        schedule=ScheduleState(),
        body_state=BodyState.from_tracker(BodyPartTracker()),
        inventory=inventory,
        equipment=equipment,
        raw_payload={
            "ac": int(getattr(character, "ac", 10)),
            "alignment": str(getattr(character, "alignment", "TN")),
        },
    )


def sync_body_state_to_tracker(body_state: BodyState, tracker: BodyPartTracker) -> None:
    for part_id, default_hp in DEFAULT_PART_HP.items():
        tracker.max_hp.setdefault(part_id, default_hp)
        tracker.current_hp.setdefault(part_id, default_hp)
    for part_id, state in body_state.parts.items():
        tracker.max_hp[part_id] = int(state.max_hp)
        tracker.current_hp[part_id] = max(0, int(state.current_hp))


def _equipment_layer_order(slot: str) -> int:
    order = {
        "under": 0,
        "underlayer": 0,
        "clothes": 1,
        "over": 1,
        "armor": 2,
        "cover": 3,
        "main_hand": 4,
        "off_hand": 4,
        "weapon": 4,
    }
    return order.get(str(slot).lower(), 5)


def _status_for_ratio(current_hp: int, max_hp: int) -> str:
    if max_hp <= 0:
        return "destroyed"
    ratio = current_hp / max_hp
    if ratio <= 0.0:
        return "destroyed"
    if ratio <= 0.25:
        return "crippled"
    if ratio <= 0.5:
        return "wounded"
    if ratio <= 0.75:
        return "bruised"
    return "healthy"
