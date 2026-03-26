"""Entity synchronization helpers for GameSession."""
from __future__ import annotations

from typing import Any, Dict, Optional

from engine.world.entity import Entity


class SessionEntityMixin:
    """Entity and spatial synchronization methods."""

    def hold_entity_position(self, entity_id: str, *, turns: int = 1) -> None:
        record = self.entities.get(entity_id)
        if record is None:
            return
        current_turn = self.dm_context.turn if self.dm_context is not None else 0
        hold_until = current_turn + max(0, int(turns))
        record["interaction_lock_until_turn"] = max(int(record.get("interaction_lock_until_turn", 0)), hold_until)

    def entity_position_locked(self, entity_id: str) -> bool:
        record = self.entities.get(entity_id)
        if record is None:
            return False
        current_turn = self.dm_context.turn if self.dm_context is not None else 0
        return int(record.get("interaction_lock_until_turn", 0)) >= current_turn

    def sync_entity_record(self, entity_id: str, entity_ref: Optional[Entity] = None) -> Optional[Dict[str, Any]]:
        record = self.entities.get(entity_id)
        if record is None:
            return None
        live_entity = entity_ref or record.get("entity_ref")
        if live_entity is None:
            return record

        record["entity_ref"] = live_entity
        record["position"] = [live_entity.position[0], live_entity.position[1]]
        record["hp"] = live_entity.hp
        record["max_hp"] = live_entity.max_hp
        record["alive"] = live_entity.alive
        record["blocking"] = live_entity.blocking
        record.setdefault("name", live_entity.name)
        record.setdefault("type", live_entity.entity_type.value)
        if getattr(live_entity, "faction", None) is not None:
            record.setdefault("faction", live_entity.faction)
        if getattr(live_entity, "job", None) is not None:
            record.setdefault("role", live_entity.job)
        if getattr(live_entity, "attitude", None) is not None:
            record["attitude"] = live_entity.attitude
        if getattr(live_entity, "alignment", None) is not None:
            record["alignment"] = live_entity.alignment
        if getattr(live_entity, "alignment_axes", None) is not None:
            record["alignment_axes"] = dict(live_entity.alignment_axes or {})

        live_body = getattr(live_entity, "body", None)
        if live_body is not None:
            record["body"] = live_body
        elif record.get("body") is not None:
            live_entity.body = record["body"]

        live_needs = getattr(live_entity, "needs", None)
        if live_needs is not None:
            record["needs"] = live_needs
        elif record.get("needs") is not None:
            live_entity.needs = record["needs"]

        live_schedule = getattr(live_entity, "schedule", None)
        if live_schedule is not None:
            record["schedule"] = live_schedule
        elif record.get("schedule") is not None:
            live_entity.schedule = record["schedule"]

        return record

    def reattach_entity_refs(self) -> None:
        if not self.entities or self.spatial_index is None:
            return
        live_entities = {entity.id: entity for entity in self.spatial_index.all_entities()}
        for entity_id in list(self.entities.keys()):
            live_entity = live_entities.get(entity_id)
            if live_entity is None:
                continue
            self.sync_entity_record(entity_id, live_entity)
