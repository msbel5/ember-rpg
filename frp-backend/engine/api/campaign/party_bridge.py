"""Party and companion commands for the campaign runtime."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

from engine.kernel.game_state import add_to_party, remove_from_party
from engine.world.entity import Entity, EntityType

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext
    from engine.kernel.actor_records import ActorRecord

logger = logging.getLogger(__name__)

_PARTY_RE = re.compile(r"^party$", re.IGNORECASE)
_RECRUIT_RE = re.compile(r"^(?:recruit|invite)\s+(.+)$", re.IGNORECASE)
_DISMISS_RE = re.compile(r"^(?:dismiss|remove\s+from\s+party)\s+(.+)$", re.IGNORECASE)


def maybe_handle_party_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle recruit/dismiss/party commands."""
    text = command_text.strip()
    if _PARTY_RE.match(text):
        return (party_summary(context), "party", 0)

    match = _RECRUIT_RE.match(text)
    if match:
        query = match.group(1).strip()
        if _find_recruitable_actor(context, query) is None:
            return None
        return _recruit(context, query)

    match = _DISMISS_RE.match(text)
    if match:
        return _dismiss(context, match.group(1).strip())

    return None


def party_member_ids(context: "CampaignContext") -> list[str]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return ["player"]
    party = [str(actor_id) for actor_id in list(getattr(game_state, "party", [])) if str(actor_id)]
    if "player" not in party and (runtime.get("actors") or {}).get("player") is not None:
        party.insert(0, "player")
    return party or ["player"]


def party_summary(context: "CampaignContext") -> str:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    members = []
    for actor_id in party_member_ids(context):
        actor = actors.get(actor_id)
        if actor is None:
            continue
        status = "player" if actor_id == "player" else str(getattr(actor.identity, "actor_type", "ally"))
        members.append(f"- {actor.identity.display_name} ({status}) HP {int(actor.stats.get('hp', 0))}/{int(actor.stats.get('max_hp', 1))}")
    if not members:
        return "Party is empty."
    return "Party members:\n" + "\n".join(members)


def allied_actor_ids(context: "CampaignContext") -> set[str]:
    return set(party_member_ids(context))


def _recruit(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    game_state = runtime.get("game_state")
    if game_state is None:
        return ("Party state is unavailable.", "party", 0)
    actor = _find_recruitable_actor(context, query)
    if actor is None:
        return (f"No recruitable companion matched '{query}'.", "party", 0)
    success, message = add_to_party(game_state, actor.identity.actor_id)
    if not success:
        return (f"Could not recruit {actor.identity.display_name}: {message}.", "party", 0)
    actor.raw_payload["party_member"] = True
    actor.raw_payload["legacy_attitude"] = "ally"
    actor.raw_payload["legacy_disposition"] = "ally"
    record = context.entities.get(actor.identity.actor_id)
    if isinstance(record, dict):
        record["attitude"] = "ally"
        record["disposition"] = "ally"
    else:
        live_entity = Entity(
            id=actor.identity.actor_id,
            entity_type=EntityType.NPC,
            name=actor.identity.display_name,
            position=(int(actor.position.x), int(actor.position.y)),
            glyph="A",
            color="light_blue",
            blocking=True,
            hp=int(actor.stats.get("hp", 0)),
            max_hp=int(actor.stats.get("max_hp", 1)),
            disposition="friendly",
            attitude="ally",
            faction=getattr(actor.identity, "faction_id", None),
            job=str(actor.raw_payload.get("role", "companion")),
        )
        context.entities[actor.identity.actor_id] = {
            "name": actor.identity.display_name,
            "type": "npc",
            "position": [int(actor.position.x), int(actor.position.y)],
            "faction": getattr(actor.identity, "faction_id", None),
            "role": str(actor.raw_payload.get("role", "companion")),
            "attitude": "ally",
            "disposition": "ally",
            "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", "companion"))),
            "context_actions": ["examine"],
            "entity_ref": live_entity,
        }
        if getattr(context, "spatial_index", None) is not None and context.spatial_index.get_position(actor.identity.actor_id) is None:
            context.spatial_index.add(live_entity)
    context.campaign_state["party"] = party_member_ids(context)
    logger.info("Recruited %s into party", actor.identity.actor_id)
    return (f"{actor.identity.display_name} joins the party.", "party", 0)


def _dismiss(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    game_state = runtime.get("game_state")
    if game_state is None:
        return ("Party state is unavailable.", "party", 0)
    actor_id = None
    for candidate_id in party_member_ids(context):
        if candidate_id == "player":
            continue
        actor = actors.get(candidate_id)
        if actor is None:
            continue
        if query.lower() in actor.identity.display_name.lower() or query.lower().replace(" ", "_") == candidate_id.lower():
            actor_id = candidate_id
            break
    if actor_id is None:
        return (f"No party member matched '{query}'.", "party", 0)
    remove_from_party(game_state, actor_id)
    if actors.get(actor_id) is not None:
        actors[actor_id].raw_payload["party_member"] = False
        actors[actor_id].raw_payload["legacy_attitude"] = "friendly"
        actors[actor_id].raw_payload["legacy_disposition"] = "friendly"
    record = context.entities.get(actor_id)
    if isinstance(record, dict):
        record["attitude"] = "friendly"
        record["disposition"] = "friendly"
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            entity_ref.attitude = "friendly"
            entity_ref.disposition = "friendly"
    context.campaign_state["party"] = party_member_ids(context)
    logger.info("Dismissed %s from party", actor_id)
    return (f"{actors[actor_id].identity.display_name} leaves the party.", "party", 0)


def _find_recruitable_actor(context: "CampaignContext", query: str) -> "ActorRecord | None":
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    query_lower = query.lower().strip()
    party_ids = allied_actor_ids(context)
    for actor_id, actor in actors.items():
        if actor_id == "player" or actor_id in party_ids:
            continue
        actor_type = str(getattr(actor.identity, "actor_type", ""))
        if actor_type not in {"npc", "creature"}:
            continue
        if bool(actor.raw_payload.get("hostile")):
            continue
        if query_lower in actor.identity.display_name.lower() or query_lower.replace(" ", "_") == actor_id.lower():
            return actor
    return None


__all__ = ["allied_actor_ids", "maybe_handle_party_command", "party_member_ids", "party_summary"]
