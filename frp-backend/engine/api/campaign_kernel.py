"""Canonical campaign-kernel adapters."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.game_session import GameSession
from engine.kernel import actor_record_from_character, actor_record_from_entity, world_state_from_blueprint
from engine.worldgen.models import WorldBlueprint


def build_canonical_world_state(world: WorldBlueprint) -> dict[str, Any]:
    return world_state_from_blueprint(world).to_dict()


def build_canonical_actor_roster(
    session: GameSession,
    *,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> list[dict[str, Any]]:
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()

    actors: list[dict[str, Any]] = []
    player_actor = actor_record_from_character(
        session.player,
        actor_id="player",
        position=tuple(session.position),
        region_id=active_region_id,
        site_id=active_site_id,
        equipment_payloads=session.equipment,
    )
    player_actor.raw_payload["source"] = "player_character"
    actors.append(player_actor.to_dict())

    for entity_id in sorted(session.entities):
        record = session.entities[entity_id]
        entity_ref = record.get("entity_ref")
        if entity_ref is None:
            continue
        actor = actor_record_from_entity(
            entity_ref,
            region_id=active_region_id,
            site_id=active_site_id,
        )
        actor.raw_payload["source"] = "session_entity"
        actor.raw_payload["template"] = record.get("template")
        actor.raw_payload["context_actions"] = copy.deepcopy(record.get("context_actions", []))
        actors.append(actor.to_dict())
    return actors
