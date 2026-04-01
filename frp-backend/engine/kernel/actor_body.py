from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.world.body_parts import BodyPartTracker

from .actor_foundation import (
    BODY_PART_LABELS,
    BODY_PART_LAYER_BLUEPRINTS,
    DEFAULT_LAYER_BLUEPRINT,
    VITAL_PART_IDS,
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
            layers = [TissueLayerDef(**layer) for layer in BODY_PART_LAYER_BLUEPRINTS.get(part_id, DEFAULT_LAYER_BLUEPRINT)]
            part_defs.append(
                BodyPartDef(
                    part_id=part_id,
                    label=BODY_PART_LABELS.get(part_id, part_id.replace("_", " ").title()),
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
        part_state.status = status_for_ratio(part_state.current_hp, part_state.max_hp)
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
        return BodyPartTracker(
            max_hp={part.part_id: part.max_hp for part in self.plan.parts},
            current_hp={
                part.part_id: self.parts.get(part.part_id, BodyPartState(part.part_id, part.max_hp, part.max_hp)).current_hp
                for part in self.plan.parts
            },
        )

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
        payload["parts"] = {key: BodyPartState.from_dict(value) for key, value in payload.get("parts", {}).items()}
        payload["wounds"] = [WoundRecord.from_dict(item) for item in payload.get("wounds", [])]
        payload["conditions"] = [ConditionRecord.from_dict(item) for item in payload.get("conditions", [])]
        return cls(**payload)


def status_for_ratio(current_hp: int, max_hp: int) -> str:
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


__all__ = [
    "BodyPartDef",
    "BodyPartState",
    "BodyPlanDef",
    "BodyState",
    "ConditionRecord",
    "TissueLayerDef",
    "WoundRecord",
    "status_for_ratio",
]
