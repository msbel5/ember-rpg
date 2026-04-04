"""Canonical campaign-kernel adapters."""
from __future__ import annotations

import copy
from typing import Any

from engine.api.campaign.context import CampaignContext
from engine.kernel import (
    ActorRecord,
    AreaState,
    GameState,
    actor_record_from_entity,
    create_game_state,
    world_state_from_blueprint,
)
from engine.worldgen.models import WorldBlueprint


def build_canonical_world_state(world: WorldBlueprint) -> dict[str, Any]:
    return world_state_from_blueprint(world).to_dict()


def build_canonical_actor_roster(
    context: CampaignContext,
    *,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        actor.to_dict()
        for actor in build_canonical_actor_records(
            context,
            active_region_id=active_region_id,
            active_site_id=active_site_id,
        )
    ]


def build_canonical_actor_records(
    context: CampaignContext,
    *,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> list[ActorRecord]:
    if hasattr(context, "ensure_consistency"):
        context.ensure_consistency()

    actors: list[ActorRecord] = []
    player_actor = ActorRecord.from_dict(context.player.to_dict())
    player_actor.identity.actor_id = "player"
    player_actor.identity.site_id = active_site_id
    player_actor.position.x = int(context.position[0])
    player_actor.position.y = int(context.position[1])
    player_actor.position.region_id = active_region_id
    player_actor.position.site_id = active_site_id
    player_actor.raw_payload["source"] = "player_runtime"
    actors.append(player_actor)

    for entity_id in sorted(context.entities):
        record = context.entities[entity_id]
        entity_ref = record.get("entity_ref")
        if entity_ref is None:
            continue
        actor = actor_record_from_entity(
            entity_ref,
            region_id=active_region_id,
            site_id=active_site_id,
        )
        actor.raw_payload["source"] = "campaign_entity"
        actor.raw_payload["template"] = record.get("template")
        actor.raw_payload["context_actions"] = copy.deepcopy(record.get("context_actions", []))
        actors.append(actor)
    return actors


def build_canonical_game_state(
    context: CampaignContext,
    *,
    campaign_id: str,
    seed: int,
    active_region_id: str | None = None,
    active_site_id: str | None = None,
) -> GameState:
    actors = build_canonical_actor_records(
        context,
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
    if context.game_time is not None:
        state.world_time.hour = int(getattr(context.game_time, "hour", state.world_time.hour))
    state.raw_payload.update(
        {
            "active_site_id": str(active_site_id or ""),
            "adapter_id": str(context.campaign_state.get("adapter_id", "")),
            "profile_id": str(context.campaign_state.get("profile_id", "")),
            "world_seed": int(context.campaign_state.get("world_seed", seed)),
        }
    )
    if getattr(context, "position", None):
        state.raw_payload["current_area_position"] = [int(context.position[0]), int(context.position[1])]
    return state
