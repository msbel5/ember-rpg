from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.world.body_parts import BodyPartTracker, DEFAULT_PART_HP
from engine.world.entity import Entity

from .actor_body import BodyState, ConditionRecord
from .actor_foundation import ActorIdentity, ActorPosition, NeedState, ScheduleState
from .actor_items import EquipmentLoadout, ItemStack, item_stack_from_legacy_payload


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
        payload["conditions"] = [ConditionRecord.from_dict(item) for item in payload.get("conditions", [])]
        effect_queue = payload.get("effect_queue")
        if isinstance(effect_queue, dict):
            from engine.kernel.effects import EffectQueue

            payload["effect_queue"] = EffectQueue.from_dict(effect_queue)
        return cls(**payload)


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
    position = ActorPosition(x=int(entity.position[0]), y=int(entity.position[1]), region_id=region_id, site_id=site_id)
    inventory_entries = list(entity.inventory or [])
    inventory = [item_stack_from_legacy_payload(entry, index=index) for index, entry in enumerate(inventory_entries)]
    equipment = EquipmentLoadout()
    for item in inventory:
        slot = str(item.payload.get("slot", item.payload.get("equip_slot", ""))).strip()
        if slot:
            equipment.add_item(slot, item)
    return ActorRecord(
        identity=identity,
        position=position,
        action_points=entity.ap,
        max_action_points=entity.max_ap,
        alive=entity.alive,
        stats={"hp": entity.hp, "max_hp": entity.max_hp},
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


__all__ = [
    "ActorRecord",
    "actor_record_from_character",
    "actor_record_from_entity",
    "sync_body_state_to_tracker",
]
