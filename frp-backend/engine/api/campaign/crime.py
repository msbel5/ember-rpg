from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

import engine.world.consequence as consequence_runtime
from engine.api.campaign.runtime_common import active_site_id
from engine.world import WorldState as ConsequenceWorldState
from engine.world.ethics import evaluate_action_full
from engine.world.institutions import InstitutionManager, TOWN_INSTITUTIONS

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


_PROTECTED_ACTOR_TYPES = {"npc", "creature", "monster", "animal"}
_GUARD_ROLE_HINTS = {"guard", "captain", "magistrate", "watch", "warden", "jailer", "marshal"}
_AUTHORITY_ROLE_HINTS = _GUARD_ROLE_HINTS | {"mayor", "thane", "commander", "constable"}
_LOCKED_TRESPASS_TARGETS = {"door", "gate", "cell_door"}
_MURDER_CRITICAL_ROLE_HINTS = {"guard", "captain", "magistrate", "watch", "warden"}


def default_crime_state() -> dict[str, Any]:
    return {
        "wanted": False,
        "active_bounty": 0,
        "witness_count": 0,
        "last_incident": None,
    }


def current_crime_state(context: "CampaignContext") -> dict[str, Any]:
    raw_payload = _raw_payload(context)
    raw_state = raw_payload.get("crime_state")
    if not isinstance(raw_state, dict):
        return default_crime_state()
    last_incident = _normalize_incident(raw_state.get("last_incident"))
    return {
        "wanted": bool(raw_state.get("wanted", False)),
        "active_bounty": int(raw_state.get("active_bounty", raw_state.get("bounty", 0)) or 0),
        "witness_count": int(raw_state.get("witness_count", 0) or 0),
        "last_incident": last_incident,
    }


def record_theft_incident(
    context: "CampaignContext",
    *,
    item_id: str,
    store: Any,
    detected: bool,
) -> dict[str, Any]:
    authority_faction_id = _resolve_authority_faction(context)
    settlement_id = _current_settlement_id(context)
    witness_ids = _detect_witness_ids(context, incident_position=_player_position(context))
    witness_count = len(witness_ids)
    if detected and witness_count == 0:
        witness_count = 1
    witnessed = bool(detected or witness_count)
    reported = bool(witnessed and (_guard_witness_present(context, witness_ids) or authority_faction_id))
    responses: list[str] = []
    if detected:
        _process_cascade_trigger(
            context,
            {
                "type": "item_stolen",
                "detected": True,
                "faction_id": authority_faction_id,
                "settlement_id": settlement_id,
                "store_id": str(getattr(store, "store_id", "") or "").strip(),
                "item_id": item_id,
            },
        )
    responses.extend(
        _apply_authority_reactions(
            context,
            crime_type="theft",
            severity="medium" if detected else "low",
            authority_faction_id=authority_faction_id,
        ),
    )
    return _store_incident(
        context,
        crime_type="theft",
        severity="medium" if detected else "low",
        target_id=str(getattr(store, "store_id", "") or "").strip() or None,
        target_name=str(getattr(store, "label", item_id) or item_id).strip() or item_id,
        faction_id=authority_faction_id or None,
        settlement_id=settlement_id or None,
        witnessed=witnessed,
        reported=reported,
        witness_count=witness_count,
        responses=responses,
        bounty_floor=50 if detected else 0,
        summary=f"Theft recorded against {str(getattr(store, 'label', 'the market') or 'the market')}.",
    )


def record_assault_incident(
    context: "CampaignContext",
    *,
    target_actor: Any,
) -> dict[str, Any]:
    record = _entity_record(context, str(target_actor.identity.actor_id))
    authority_faction_id = _resolve_authority_faction(
        context,
        target_faction_id=str(getattr(target_actor.identity, "faction_id", "") or "").strip(),
    )
    settlement_id = _current_settlement_id(context)
    target_position = _actor_position(target_actor, record)
    witness_ids = _detect_witness_ids(
        context,
        incident_position=target_position,
        victim_actor_id=str(target_actor.identity.actor_id),
        include_victim_if_alive=bool(getattr(target_actor, "alive", True)),
    )
    responses = _apply_authority_reactions(
        context,
        crime_type="assault",
        severity="low",
        authority_faction_id=authority_faction_id,
    )
    return _store_incident(
        context,
        crime_type="assault",
        severity="low",
        target_id=str(target_actor.identity.actor_id),
        target_name=str(getattr(target_actor.identity, "display_name", target_actor.identity.actor_id)),
        faction_id=authority_faction_id or None,
        settlement_id=settlement_id or None,
        witnessed=bool(witness_ids),
        reported=bool(witness_ids and (_guard_witness_present(context, witness_ids) or authority_faction_id)),
        witness_count=len(witness_ids),
        responses=responses,
        summary=f"Assault recorded against {str(getattr(target_actor.identity, 'display_name', target_actor.identity.actor_id))}.",
    )


def record_murder_incident(
    context: "CampaignContext",
    *,
    target_actor: Any,
) -> dict[str, Any]:
    target_id = str(target_actor.identity.actor_id)
    record = _entity_record(context, target_id)
    target_role = _actor_role(target_actor, record)
    severity = "critical" if any(hint in target_role for hint in _MURDER_CRITICAL_ROLE_HINTS) else "high"
    authority_faction_id = _resolve_authority_faction(
        context,
        target_faction_id=str(getattr(target_actor.identity, "faction_id", "") or "").strip(),
    )
    settlement_id = _current_settlement_id(context)
    target_position = _actor_position(target_actor, record)
    witness_ids = _detect_witness_ids(
        context,
        incident_position=target_position,
        victim_actor_id=target_id,
        include_victim_if_alive=False,
    )
    _consequence_world_state(context).update_npc_killed(target_id, witnessed=bool(witness_ids))
    _process_cascade_trigger(
        context,
        {
            "type": "npc_killed",
            "npc_id": target_id,
            "npc_role": target_role,
            "witnessed": bool(witness_ids),
            "faction_id": authority_faction_id,
            "settlement_id": settlement_id,
        },
    )
    responses = _apply_authority_reactions(
        context,
        crime_type="murder",
        severity=severity,
        authority_faction_id=authority_faction_id,
    )
    return _store_incident(
        context,
        crime_type="murder",
        severity=severity,
        target_id=target_id,
        target_name=str(getattr(target_actor.identity, "display_name", target_id)),
        faction_id=authority_faction_id or None,
        settlement_id=settlement_id or None,
        witnessed=bool(witness_ids),
        reported=bool(witness_ids and (_guard_witness_present(context, witness_ids) or authority_faction_id)),
        witness_count=len(witness_ids),
        responses=responses,
        bounty_floor=100,
        summary=f"Murder recorded for {str(getattr(target_actor.identity, 'display_name', target_id))}.",
    )


def maybe_record_trespass(
    context: "CampaignContext",
    *,
    verb: str,
    target_query: str,
    success: bool,
) -> dict[str, Any] | None:
    if not success or str(verb).strip().lower() not in {"open", "lockpick"}:
        return None
    if not _current_settlement_id(context):
        return None
    target_id, record = _resolve_trespass_target(context, target_query)
    if target_id is None or not isinstance(record, dict):
        return None
    authority_faction_id = _resolve_authority_faction(
        context,
        target_faction_id=str(record.get("faction", "") or "").strip(),
    )
    settlement_id = _current_settlement_id(context)
    position = _record_position(record)
    witness_ids = _detect_witness_ids(context, incident_position=position)
    return _store_incident(
        context,
        crime_type="trespass",
        severity="low",
        target_id=target_id,
        target_name=str(record.get("name", target_id) or target_id),
        faction_id=authority_faction_id or None,
        settlement_id=settlement_id or None,
        witnessed=bool(witness_ids),
        reported=bool(witness_ids and (_guard_witness_present(context, witness_ids) or authority_faction_id)),
        witness_count=len(witness_ids),
        responses=["You entered a controlled locked space without permission."],
        summary=f"Trespass recorded at {str(record.get('name', target_id) or target_id)}.",
    )


def is_protected_crime_target(context: "CampaignContext", actor: Any) -> bool:
    actor_id = str(getattr(getattr(actor, "identity", None), "actor_id", "") or "").strip()
    if not actor_id or actor_id == "player":
        return False
    actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "") or "").strip().lower()
    if actor_type not in _PROTECTED_ACTOR_TYPES:
        return False
    if actor_id in _party_ids(context):
        return False
    if _actor_is_hostile(context, actor_id, actor):
        return False
    return True


def _store_incident(
    context: "CampaignContext",
    *,
    crime_type: str,
    severity: str,
    target_id: str | None,
    target_name: str | None,
    faction_id: str | None,
    settlement_id: str | None,
    witnessed: bool,
    reported: bool,
    witness_count: int,
    responses: list[str],
    summary: str,
    bounty_floor: int = 0,
) -> dict[str, Any]:
    crime_state = current_crime_state(context)
    world_state = _consequence_world_state(context)
    relevant_flags = getattr(world_state, "flags", {}) if world_state is not None else {}
    response_texts = _dedup_strings(responses)
    active_bounty = max(
        int(crime_state.get("active_bounty", 0) or 0),
        int(getattr(relevant_flags, "get", lambda *_args, **_kwargs: 0)("bounty_active", 0) or 0),
        int(bounty_floor),
    )
    if bool(getattr(relevant_flags, "get", lambda *_args, **_kwargs: False)("player_has_bounty")) and active_bounty <= 0:
        active_bounty = int(bounty_floor or 25)
    incident = {
        "crime_type": str(crime_type).strip().lower(),
        "severity": str(severity).strip().lower(),
        "target_id": str(target_id or "").strip() or None,
        "target_name": str(target_name or "").strip() or None,
        "faction_id": str(faction_id or "").strip() or None,
        "settlement_id": str(settlement_id or "").strip() or None,
        "witnessed": bool(witnessed),
        "reported": bool(reported),
        "responses": response_texts,
        "tick": _current_tick(context),
    }
    if active_bounty > 0:
        relevant_flags["bounty_active"] = int(active_bounty)
    wanted = bool(
        crime_state.get("wanted")
        or active_bounty > 0
        or relevant_flags.get("guards_alerted")
        or any(response_type in " ".join(response_texts).lower() for response_type in ("guard", "arrest", "curfew", "investigation"))
    )
    relevant_flags["witness_count"] = int(witness_count)
    if wanted:
        relevant_flags["wanted"] = True
    _raw_payload(context)["crime_state"] = {
        "wanted": wanted,
        "active_bounty": int(active_bounty),
        "witness_count": int(witness_count),
        "last_incident": incident,
    }
    if world_state is not None:
        world_state.log_event(f"crime_{crime_type}", summary, [item for item in [target_id] if item])
    _append_recent_event(
        context,
        event_type=f"crime_{crime_type}",
        summary=summary,
        crime_type=crime_type,
        target_id=target_id,
        settlement_id=settlement_id,
    )
    return copy.deepcopy(_raw_payload(context)["crime_state"])


def _apply_authority_reactions(
    context: "CampaignContext",
    *,
    crime_type: str,
    severity: str,
    authority_faction_id: str,
) -> list[str]:
    responses: list[str] = []
    if crime_type in {"theft", "assault", "murder"} and authority_faction_id:
        action_type = {
            "theft": "THEFT",
            "assault": "ASSAULT",
            "murder": "KILL_CITIZEN",
        }[crime_type]
        try:
            evaluation = evaluate_action_full(authority_faction_id, action_type)
        except KeyError:
            evaluation = None
        if evaluation is not None:
            world_state = _consequence_world_state(context)
            faction_state = getattr(world_state, "factions", {}).get(authority_faction_id) if world_state is not None else None
            if faction_state is not None and hasattr(faction_state, "reputation"):
                faction_state.reputation += int(evaluation.rep_change)
            if evaluation.consequence:
                responses.append(str(evaluation.consequence))
    if crime_type not in {"theft", "murder"}:
        return responses
    town_id = _institution_town_id(context)
    if not town_id:
        return responses
    manager = InstitutionManager()
    for response in manager.handle_event(crime_type, severity, town_id):
        responses.append(str(response.description))
        response_type = str(response.response_type or "").strip().lower()
        if response_type == "bounty":
            bounty_gold = int(response.parameters.get("bounty_gold", 0) or 0)
            world_state = _consequence_world_state(context)
            if world_state is not None:
                world_state.flags["bounty_active"] = max(int(world_state.flags.get("bounty_active", 0) or 0), bounty_gold)
                world_state.flags["player_has_bounty"] = True
        elif response_type in {"investigation", "arrest", "curfew", "martial_law"}:
            world_state = _consequence_world_state(context)
            if world_state is not None:
                world_state.flags["guards_alerted"] = True
    return responses


def _process_cascade_trigger(context: "CampaignContext", trigger: dict[str, Any]) -> list[Any]:
    cascade_engine = getattr(context, "cascade_engine", None)
    world_state = _consequence_world_state(context)
    if cascade_engine is None or world_state is None:
        return []
    original_random = consequence_runtime.random.random
    consequence_runtime.random.random = lambda: 0.0
    try:
        return list(cascade_engine.process_trigger(trigger, world_state) or [])
    finally:
        consequence_runtime.random.random = original_random


def _resolve_authority_faction(context: "CampaignContext", *, target_faction_id: str = "") -> str:
    target_faction_id = str(target_faction_id or "").strip()
    if target_faction_id:
        return target_faction_id
    settlement_faction_id = _current_settlement_faction_id(context)
    if settlement_faction_id:
        return settlement_faction_id
    return _current_region_controller_faction_id(context)


def _current_settlement_id(context: "CampaignContext") -> str:
    return str(active_site_id(context) or "").strip()


def _current_settlement_faction_id(context: "CampaignContext") -> str:
    settlement_state = getattr(context, "settlement_state", {}) or {}
    faction_id = str(settlement_state.get("faction_id", "") or "").strip()
    if faction_id:
        return faction_id
    settlement_id = _current_settlement_id(context)
    world_state = _kernel_world_state(context)
    settlements = getattr(world_state, "settlements", {}) if world_state is not None else {}
    if settlement_id and isinstance(settlements, dict):
        settlement = settlements.get(settlement_id)
        faction_id = str(getattr(settlement, "faction_id", "") or "").strip() if settlement is not None else ""
        if faction_id:
            return faction_id
    return ""


def _current_region_controller_faction_id(context: "CampaignContext") -> str:
    region_id = str(getattr(getattr(context, "region_snapshot", None), "region_id", "") or "").strip()
    world_state = _kernel_world_state(context)
    regions = getattr(world_state, "regions", {}) if world_state is not None else {}
    if region_id and isinstance(regions, dict):
        region = regions.get(region_id)
        faction_id = str(getattr(region, "controller_faction_id", "") or "").strip() if region is not None else ""
        if faction_id:
            return faction_id
    for region in list(getattr(getattr(context, "world", None), "regions", []) or []):
        if str(region.get("id", "")).strip() != region_id:
            continue
        return str(region.get("controller_faction_id", "") or "").strip()
    return ""


def _institution_town_id(context: "CampaignContext") -> str:
    settlement_state = getattr(context, "settlement_state", {}) or {}
    candidates = [
        settlement_state.get("institution_town_id"),
        settlement_state.get("town_id"),
        settlement_state.get("settlement_id"),
        active_site_id(context),
        _slugify(settlement_state.get("name")),
    ]
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if normalized in TOWN_INSTITUTIONS:
            return normalized
    return ""


def _detect_witness_ids(
    context: "CampaignContext",
    *,
    incident_position: tuple[int, int] | None,
    victim_actor_id: str = "",
    include_victim_if_alive: bool = False,
) -> list[str]:
    actors = (context.kernel_runtime or {}).get("actors", {})
    position = incident_position or _player_position(context)
    witness_ids: list[str] = []
    for actor_id, actor in actors.items():
        normalized_id = str(actor_id).strip()
        if not normalized_id or normalized_id == "player" or normalized_id == victim_actor_id:
            continue
        if not getattr(actor, "alive", True):
            continue
        if normalized_id in _party_ids(context):
            continue
        if _actor_is_hostile(context, normalized_id, actor):
            continue
        actor_position = _actor_position(actor, _entity_record(context, normalized_id))
        if actor_position is None:
            continue
        if _chebyshev_distance(position, actor_position) <= 6:
            witness_ids.append(normalized_id)
    if include_victim_if_alive and victim_actor_id:
        victim = actors.get(victim_actor_id)
        if victim is not None and getattr(victim, "alive", True) and victim_actor_id not in _party_ids(context):
            witness_ids.insert(0, victim_actor_id)
    return _dedup_strings(witness_ids)


def _guard_witness_present(context: "CampaignContext", witness_ids: list[str]) -> bool:
    actors = (context.kernel_runtime or {}).get("actors", {})
    for witness_id in witness_ids:
        actor = actors.get(witness_id)
        if actor is None:
            continue
        role = _actor_role(actor, _entity_record(context, witness_id))
        if any(hint in role for hint in _GUARD_ROLE_HINTS):
            return True
    return False


def _resolve_trespass_target(context: "CampaignContext", target_query: str) -> tuple[str | None, dict[str, Any] | None]:
    normalized_query = _slugify(target_query)
    if not normalized_query:
        return (None, None)
    for entity_id, record in getattr(context, "entities", {}).items():
        if not isinstance(record, dict):
            continue
        role = str(record.get("role", record.get("template", "")) or "").strip().lower()
        template = str(record.get("template", role) or "").strip().lower()
        if role not in _LOCKED_TRESPASS_TARGETS and template not in _LOCKED_TRESPASS_TARGETS:
            continue
        if not bool(record.get("locked")):
            continue
        name = str(record.get("name", entity_id) or entity_id)
        candidates = {
            _slugify(entity_id),
            _slugify(name),
            _slugify(role),
            _slugify(template),
        }
        if normalized_query in candidates or any(normalized_query in candidate for candidate in candidates if candidate):
            return (str(entity_id), record)
    return (None, None)


def _actor_is_hostile(context: "CampaignContext", actor_id: str, actor: Any) -> bool:
    if bool(getattr(actor, "raw_payload", {}).get("hostile")):
        return True
    record = _entity_record(context, actor_id)
    if isinstance(record, dict):
        attitude = str(record.get("attitude", "") or "").strip().lower()
        disposition = str(record.get("disposition", "") or "").strip().lower()
        if attitude == "hostile" or disposition == "hostile":
            return True
    return str(getattr(actor, "raw_payload", {}).get("disposition", "") or "").strip().lower() == "hostile"


def _actor_role(actor: Any, record: dict[str, Any] | None) -> str:
    if isinstance(record, dict):
        role = str(record.get("role", record.get("template", "")) or "").strip().lower()
        if role:
            return role
    return str(getattr(actor, "raw_payload", {}).get("role", getattr(actor, "raw_payload", {}).get("template", "")) or "").strip().lower()


def _party_ids(context: "CampaignContext") -> set[str]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is not None:
        return {str(actor_id) for actor_id in list(getattr(game_state, "party", [])) if str(actor_id)}
    return {str(actor_id) for actor_id in list((getattr(context, "campaign_state", {}) or {}).get("party", [])) if str(actor_id)}


def _entity_record(context: "CampaignContext", actor_id: str) -> dict[str, Any] | None:
    record = getattr(context, "entities", {}).get(actor_id)
    return record if isinstance(record, dict) else None


def _player_position(context: "CampaignContext") -> tuple[int, int]:
    position = getattr(context, "position", None)
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        return (int(position[0]), int(position[1]))
    runtime = context.kernel_runtime or {}
    player = (runtime.get("actors") or {}).get("player")
    if player is not None:
        return (int(player.position.x), int(player.position.y))
    return (0, 0)


def _actor_position(actor: Any, record: dict[str, Any] | None) -> tuple[int, int] | None:
    position = getattr(actor, "position", None)
    if position is not None:
        return (int(position.x), int(position.y))
    return _record_position(record)


def _record_position(record: dict[str, Any] | None) -> tuple[int, int] | None:
    if not isinstance(record, dict):
        return None
    position = record.get("position")
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        return (int(position[0]), int(position[1]))
    return None


def _chebyshev_distance(a: tuple[int, int], b: tuple[int, int] | None) -> int:
    if b is None:
        return 999
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1])))


def _dedup_strings(values: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = str(value)
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(value)
    return normalized


def _append_recent_event(context: "CampaignContext", **payload: Any) -> None:
    context.recent_event_log.append(copy.deepcopy(payload))
    context.recent_event_log = context.recent_event_log[-20:]


def _current_tick(context: "CampaignContext") -> int:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None) if game_state is not None else None
    return int(getattr(world_time, "game_tick", 0) or 0)


def _kernel_world_state(context: "CampaignContext") -> Any:
    runtime = context.kernel_runtime or {}
    return runtime.get("world_state")


def _consequence_world_state(context: "CampaignContext") -> ConsequenceWorldState:
    world_state = getattr(context, "world_state", None)
    if world_state is None:
        world_state = ConsequenceWorldState(game_id=context.campaign_id)
        context.world_state = world_state
    return world_state


def _raw_payload(context: "CampaignContext") -> dict[str, Any]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", None) if game_state is not None else None
    if not isinstance(raw_payload, dict):
        raw_payload = {}
        if game_state is not None:
            game_state.raw_payload = raw_payload
    return raw_payload


def _normalize_incident(raw_incident: Any) -> dict[str, Any] | None:
    if not isinstance(raw_incident, dict):
        crime_type = str(raw_incident or "").strip()
        if not crime_type:
            return None
        raw_incident = {"crime_type": crime_type}
    crime_type = str(raw_incident.get("crime_type") or raw_incident.get("type") or "").strip().lower()
    if not crime_type:
        return None
    responses = raw_incident.get("responses", [])
    normalized_responses = [
        str(entry).strip()
        for entry in list(responses or [])
        if str(entry).strip()
    ] if isinstance(responses, (list, tuple)) else []
    return {
        "crime_type": crime_type,
        "severity": str(raw_incident.get("severity", "low") or "low").strip().lower(),
        "target_id": str(raw_incident.get("target_id", "") or "").strip() or None,
        "target_name": str(raw_incident.get("target_name", "") or "").strip() or None,
        "faction_id": str(raw_incident.get("faction_id", "") or "").strip() or None,
        "settlement_id": str(raw_incident.get("settlement_id", "") or "").strip() or None,
        "witnessed": bool(raw_incident.get("witnessed")),
        "reported": bool(raw_incident.get("reported")),
        "responses": _dedup_strings(normalized_responses),
        "tick": int(raw_incident.get("tick", 0) or 0),
    }


def _slugify(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return slug.strip("_")


__all__ = [
    "current_crime_state",
    "default_crime_state",
    "is_protected_crime_target",
    "maybe_record_trespass",
    "record_assault_incident",
    "record_murder_incident",
    "record_theft_incident",
]
