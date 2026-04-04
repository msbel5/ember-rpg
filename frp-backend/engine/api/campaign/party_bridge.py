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
        return _recruit(context, match.group(1).strip())

    match = _DISMISS_RE.match(text)
    if match:
        return _dismiss(context, match.group(1).strip())

    return None


def party_member_ids(context: "CampaignContext") -> list[str]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is None:
        return ["player"]
    seen: set[str] = set()
    party: list[str] = []
    for actor_id in [str(item) for item in list(getattr(game_state, "party", [])) if str(item)]:
        if actor_id in seen:
            continue
        seen.add(actor_id)
        party.append(actor_id)
    if "player" not in party and (runtime.get("actors") or {}).get("player") is not None:
        party.insert(0, "player")
    if getattr(game_state, "party", None) != party:
        game_state.party = list(party)
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
    game_state = runtime.get("game_state")
    if game_state is None:
        return ("Party state is unavailable.", "party", 0)
    actor = _find_actor_by_query(context, query)
    if actor is None:
        return (f"No recruitable companion matched '{query}'.", "party", 0)
    if actor.identity.actor_id == "player":
        return ("The player is already the party leader.", "party", 0)
    if actor.identity.actor_id in allied_actor_ids(context):
        return (f"{actor.identity.display_name} is already in the party.", "party", 0)
    actor_type = str(getattr(actor.identity, "actor_type", ""))
    if actor_type not in {"npc", "creature"}:
        return (f"{actor.identity.display_name} cannot join the party.", "party", 0)
    if bool(actor.raw_payload.get("hostile")):
        return (f"{actor.identity.display_name} is hostile and refuses to join.", "party", 0)
    success, message = add_to_party(game_state, actor.identity.actor_id)
    if not success:
        return (f"Could not recruit {actor.identity.display_name}: {message}.", "party", 0)
    _mark_party_membership(context, actor, is_party_member=True)
    context.campaign_state["party"] = party_member_ids(context)
    logger.info("Recruited %s into party", actor.identity.actor_id)
    return (f"{actor.identity.display_name} joins the party.", "party", 0)


def _mark_party_membership(context: "CampaignContext", actor: "ActorRecord", *, is_party_member: bool) -> None:
    actor.raw_payload["party_member"] = bool(is_party_member)
    actor.raw_payload["legacy_attitude"] = "ally" if is_party_member else "friendly"
    actor.raw_payload["legacy_disposition"] = "ally" if is_party_member else "friendly"
    record = context.entities.get(actor.identity.actor_id)
    if isinstance(record, dict):
        record["attitude"] = "ally" if is_party_member else "friendly"
        record["disposition"] = "ally" if is_party_member else "friendly"
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            entity_ref.attitude = record["attitude"]
            entity_ref.disposition = record["disposition"]
            entity_ref.faction = getattr(actor.identity, "faction_id", None)
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
            disposition="ally" if is_party_member else "friendly",
            attitude="ally" if is_party_member else "friendly",
            faction=getattr(actor.identity, "faction_id", None),
            job=str(actor.raw_payload.get("role", "companion")),
        )
        context.entities[actor.identity.actor_id] = {
            "name": actor.identity.display_name,
            "type": "npc",
            "position": [int(actor.position.x), int(actor.position.y)],
            "faction": getattr(actor.identity, "faction_id", None),
            "role": str(actor.raw_payload.get("role", "companion")),
            "attitude": "ally" if is_party_member else "friendly",
            "disposition": "ally" if is_party_member else "friendly",
            "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", "companion"))),
            "context_actions": ["examine"],
            "entity_ref": live_entity,
        }
        if getattr(context, "spatial_index", None) is not None and context.spatial_index.get_position(actor.identity.actor_id) is None:
            context.spatial_index.add(live_entity)


def _dismiss(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    game_state = runtime.get("game_state")
    if game_state is None:
        return ("Party state is unavailable.", "party", 0)
    actor = _find_actor_by_query(context, query)
    if actor is None:
        return (f"No party member matched '{query}'.", "party", 0)
    actor_id = actor.identity.actor_id
    if actor_id == "player":
        return ("You cannot dismiss the player from the party.", "party", 0)
    if actor_id not in allied_actor_ids(context):
        return (f"{actor.identity.display_name} is not in the party.", "party", 0)
    remove_from_party(game_state, actor_id)
    if actors.get(actor_id) is not None:
        _mark_party_membership(context, actors[actor_id], is_party_member=False)
    context.campaign_state["party"] = party_member_ids(context)
    logger.info("Dismissed %s from party", actor_id)
    return (f"{actor.identity.display_name} leaves the party.", "party", 0)


def _find_actor_by_query(context: "CampaignContext", query: str) -> "ActorRecord | None":
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    query_lower = query.lower().strip()
    for actor_id, actor in actors.items():
        display_name = str(actor.identity.display_name).lower()
        if query_lower in display_name or query_lower.replace(" ", "_") == actor_id.lower():
            return actor
    return None


def _find_recruitable_actor(context: "CampaignContext", query: str) -> "ActorRecord | None":
    actor = _find_actor_by_query(context, query)
    if actor is None:
        return None
    if actor.identity.actor_id == "player" or actor.identity.actor_id in allied_actor_ids(context):
        return None
    actor_type = str(getattr(actor.identity, "actor_type", ""))
    if actor_type not in {"npc", "creature"}:
        return None
    if bool(actor.raw_payload.get("hostile")):
        return None
    return actor


__all__ = ["allied_actor_ids", "maybe_handle_party_command", "party_member_ids", "party_summary"]
