"""Canonical campaign-kernel adapters."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.campaign.campaign_session import CampaignSession
from engine.kernel import (
    ActorRecord,
    AreaState,
    GameState,
    actor_record_from_character,
    actor_record_from_entity,
    create_game_state,
    world_state_from_blueprint,
)
from engine.worldgen.models import WorldBlueprint


def build_canonical_world_state(world: WorldBlueprint) -> dict[str, Any]:
    return world_state_from_blueprint(world).to_dict()


def build_canonical_actor_roster(
    session: CampaignSession,
    *,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        actor.to_dict()
        for actor in build_canonical_actor_records(
            session,
            active_region_id=active_region_id,
            active_site_id=active_site_id,
        )
    ]


def build_canonical_actor_records(
    session: CampaignSession,
    *,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> list[ActorRecord]:
    if hasattr(session, "ensure_consistency"):
        session.ensure_consistency()

    actors: list[ActorRecord] = []
    player_actor = actor_record_from_character(
        session.player,
        actor_id="player",
        position=tuple(session.position),
        region_id=active_region_id,
        site_id=active_site_id,
        equipment_payloads=session.equipment,
    )
    player_actor.raw_payload["source"] = "player_character"
    actors.append(player_actor)

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
        actors.append(actor)
    return actors


def build_canonical_game_state(
    session: CampaignSession,
    *,
    campaign_id: str,
    seed: int,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> GameState:
    actors = build_canonical_actor_records(
        session,
        active_region_id=active_region_id,
        active_site_id=active_site_id,
    )
    state = create_game_state(str(campaign_id), int(seed))
    active_area_id = str(active_region_id or active_site_id or "")
    if active_area_id:
        state.current_area_id = active_area_id
        state.loaded_area_ids = [active_area_id]
        state.loaded_areas[active_area_id] = AreaState(area_id=active_area_id)
    state.actors = {actor.identity.actor_id: actor for actor in actors}
    if "player" in state.actors:
        state.party = ["player"]
    state.inactive_npcs = [
        actor_id for actor_id in state.actors if actor_id not in state.party
    ]
    if session.game_time is not None:
        state.world_time.hour = int(getattr(session.game_time, "hour", state.world_time.hour))
    state.raw_payload.update(
        {
            "active_site_id": str(active_site_id or ""),
            "session_id": str(getattr(session, "session_id", "")),
            "adapter_id": str(session.campaign_state.get("adapter_id", "")),
            "profile_id": str(session.campaign_state.get("profile_id", "")),
            "world_seed": int(session.campaign_state.get("world_seed", seed)),
        }
    )
    if getattr(session, "position", None):
        state.raw_payload["current_area_position"] = [int(session.position[0]), int(session.position[1])]
    return state
