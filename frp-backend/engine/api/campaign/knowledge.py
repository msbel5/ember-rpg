from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Any, Iterable

from engine.api.campaign.live_kernel import build_runtime_knowledge_payload
from engine.world.rumors import NPCInfo

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


_TOPIC_RE = re.compile(r"^(?P<category>[a-z_]+)\.(?P<identifier>.+)$")
_TOPICS_RE = re.compile(r"^topics$", re.IGNORECASE)
_THINK_RE = re.compile(r"^think\s+(.+)$", re.IGNORECASE)
_PIN_RE = re.compile(r"^pin\s+(.+)$", re.IGNORECASE)
_ASK_ABOUT_RE = re.compile(r"^ask\s+about\s+(.+)$", re.IGNORECASE)
_VALID_CATEGORIES = {"npc", "faction", "region", "settlement", "quest", "rumor", "fact"}


def _game_state(context: "CampaignContext") -> Any:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    return runtime.get("game_state")


def _normalize_topic_id_list(values: Any, *, allowed_ids: Iterable[str] | None = None) -> list[str]:
    allowed = None if allowed_ids is None else {str(item).strip() for item in allowed_ids if str(item).strip()}
    normalized: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        topic_id = str(value or "").strip()
        if not topic_id or topic_id in seen:
            continue
        if allowed is not None and topic_id not in allowed:
            continue
        seen.add(topic_id)
        normalized.append(topic_id)
    return normalized


def _knowledge_state(context: "CampaignContext") -> dict[str, list[str]]:
    game_state = _game_state(context)
    if game_state is None:
        raise ValueError("Knowledge authority requires kernel game state.")
    raw_payload = getattr(game_state, "raw_payload", None)
    if not isinstance(raw_payload, dict):
        raw_payload = {}
        game_state.raw_payload = raw_payload
    knowledge = raw_payload.get("knowledge")
    if not isinstance(knowledge, dict):
        knowledge = {}
    discovered = _normalize_topic_id_list(knowledge.get("discovered_topic_ids", []))
    pinned = _normalize_topic_id_list(knowledge.get("pinned_topic_ids", []), allowed_ids=discovered)
    knowledge = {
        "discovered_topic_ids": discovered,
        "pinned_topic_ids": pinned,
    }
    raw_payload["knowledge"] = knowledge
    return knowledge


def _normalize_alias(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()
    return re.sub(r"\s+", " ", collapsed)


def _label_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _fallback_label(topic_id: str) -> str:
    match = _TOPIC_RE.match(str(topic_id))
    if not match:
        return topic_id.replace("_", " ").title()
    return match.group("identifier").replace("_", " ").replace(".", " ").title()


def _fallback_category(topic_id: str) -> str:
    match = _TOPIC_RE.match(str(topic_id))
    if not match:
        return "fact"
    category = str(match.group("category")).strip().lower()
    return category if category in _VALID_CATEGORIES else "fact"


def _append_topic(
    catalog: dict[str, dict[str, Any]],
    *,
    topic_id: str,
    label: str,
    category: str,
    source_types: Iterable[str],
    aliases: Iterable[str] = (),
) -> None:
    normalized_id = str(topic_id).strip()
    normalized_category = str(category).strip().lower()
    if not normalized_id or normalized_category not in _VALID_CATEGORIES:
        return
    entry = catalog.setdefault(
        normalized_id,
        {
            "topic_id": normalized_id,
            "label": str(label).strip() or _fallback_label(normalized_id),
            "category": normalized_category,
            "source_types": set(),
            "_aliases": set(),
            "_label_key": _label_key(label),
        },
    )
    entry["label"] = entry["label"] or _fallback_label(normalized_id)
    entry["category"] = normalized_category
    entry["_label_key"] = _label_key(entry["label"])
    entry["source_types"].update(str(item).strip() for item in source_types if str(item).strip())
    entry["_aliases"].add(_normalize_alias(normalized_id))
    identifier = normalized_id.split(".", 1)[-1]
    entry["_aliases"].add(_normalize_alias(identifier))
    entry["_aliases"].add(_normalize_alias(entry["label"]))
    for alias in aliases:
        normalized_alias = _normalize_alias(alias)
        if normalized_alias:
            entry["_aliases"].add(normalized_alias)


def _current_region_id(context: "CampaignContext") -> str:
    if getattr(context, "region_snapshot", None) is not None:
        return str(context.region_snapshot.region_id)
    world = getattr(context, "world", None)
    snapshot = getattr(world, "simulation_snapshot", None)
    return str(getattr(snapshot, "active_region_id", "") or "")


def _current_settlement_id(context: "CampaignContext") -> str:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    world_state = runtime.get("world_state")
    active_region_id = _current_region_id(context)
    if world_state is None:
        return ""
    for settlement_id, settlement in getattr(world_state, "settlements", {}).items():
        if str(getattr(settlement, "region_id", "")) == active_region_id:
            return str(settlement_id)
    return ""


def _quest_entries(context: "CampaignContext") -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for collection_name in ("active_quests", "quest_offers"):
        for item in list((context.campaign_state or {}).get(collection_name, []) or []):
            if not isinstance(item, dict):
                continue
            quest_id = str(item.get("quest_id") or item.get("id") or "").strip()
            if quest_id:
                entries.setdefault(quest_id, dict(item))
    for quest_id in list((context.campaign_state or {}).get("completed_quest_ids", []) or []):
        normalized = str(quest_id).strip()
        if normalized:
            entries.setdefault(normalized, {"quest_id": normalized, "title": _fallback_label(normalized)})
    for quest_id in list((context.campaign_state or {}).get("failed_quest_ids", []) or []):
        normalized = str(quest_id).strip()
        if normalized:
            entries.setdefault(normalized, {"quest_id": normalized, "title": _fallback_label(normalized)})
    return entries


def _active_quest_ids(context: "CampaignContext") -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in list((context.campaign_state or {}).get("active_quests", []) or []):
        if not isinstance(item, dict):
            continue
        quest_id = str(item.get("quest_id") or item.get("id") or "").strip()
        if quest_id and quest_id not in seen:
            seen.add(quest_id)
            result.append(quest_id)
    return result


def ensure_bootstrap_topics(context: "CampaignContext") -> dict[str, list[str]]:
    _knowledge_state(context)
    bootstrap_ids: list[str] = []
    region_id = _current_region_id(context)
    if region_id:
        bootstrap_ids.append(f"region.{region_id}")
    settlement_id = _current_settlement_id(context)
    if settlement_id:
        bootstrap_ids.append(f"settlement.{settlement_id}")
    bootstrap_ids.extend(f"quest.{quest_id}" for quest_id in _active_quest_ids(context))
    discover_topics(context, bootstrap_ids)
    return _knowledge_state(context)


def build_topic_catalog(context: "CampaignContext") -> dict[str, dict[str, Any]]:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    world_state = runtime.get("world_state")
    catalog: dict[str, dict[str, Any]] = {}

    payload = build_runtime_knowledge_payload(context, runtime)
    for topic in list(payload.get("topics", [])):
        if not isinstance(topic, dict):
            continue
        topic_id = str(topic.get("topic_id", "")).strip()
        if not topic_id:
            continue
        label = str(topic.get("label", "")).strip() or _fallback_label(topic_id)
        category = str(topic.get("category", "")).strip().lower() or _fallback_category(topic_id)
        _append_topic(
            catalog,
            topic_id=topic_id,
            label=label,
            category=category,
            source_types=list(topic.get("source_types", [])),
            aliases=[topic_id, topic_id.split(".", 1)[-1], label],
        )

    if world_state is not None:
        for region_id, region in getattr(world_state, "regions", {}).items():
            settlement_labels = [
                str(getattr(world_state.settlements.get(settlement_id), "name", ""))
                for settlement_id in getattr(region, "settlement_ids", [])
                if settlement_id in getattr(world_state, "settlements", {})
            ]
            label = next((name for name in settlement_labels if name), "") or _fallback_label(f"region.{region_id}")
            _append_topic(
                catalog,
                topic_id=f"region.{region_id}",
                label=label,
                category="region",
                source_types=("world_state", "history"),
                aliases=[region_id, *settlement_labels],
            )

        for settlement_id, settlement in getattr(world_state, "settlements", {}).items():
            _append_topic(
                catalog,
                topic_id=f"settlement.{settlement_id}",
                label=str(getattr(settlement, "name", settlement_id)),
                category="settlement",
                source_types=("world_state",),
                aliases=[settlement_id],
            )

        for faction_id, faction in getattr(world_state, "factions", {}).items():
            _append_topic(
                catalog,
                topic_id=f"faction.{faction_id}",
                label=_fallback_label(faction_id),
                category="faction",
                source_types=("world_state", "history"),
                aliases=[faction_id, getattr(faction, "culture_id", ""), getattr(faction, "species_id", "")],
            )

    for quest_id, quest in _quest_entries(context).items():
        _append_topic(
            catalog,
            topic_id=f"quest.{quest_id}",
            label=str(quest.get("title", _fallback_label(quest_id))).strip() or _fallback_label(quest_id),
            category="quest",
            source_types=("quest_state",),
            aliases=[quest_id],
        )

    actors = runtime.get("actors", {}) or {}
    for actor_id, actor in actors.items():
        if str(actor_id) == "player":
            continue
        identity = getattr(actor, "identity", None)
        actor_type = str(getattr(identity, "actor_type", "")).strip().lower()
        if actor_type != "npc":
            continue
        raw_payload = getattr(actor, "raw_payload", {}) or {}
        _append_topic(
            catalog,
            topic_id=f"npc.{actor_id}",
            label=str(getattr(identity, "display_name", actor_id)),
            category="npc",
            source_types=("actor", "npc_memory", "rumor_network"),
            aliases=[
                actor_id,
                raw_payload.get("memory_id", ""),
                raw_payload.get("named_npc_id", ""),
                raw_payload.get("role", ""),
                raw_payload.get("template", ""),
            ],
        )

    memory_manager = getattr(context, "npc_memory", None)
    for memory_id, memory in getattr(memory_manager, "memories", {}).items():
        topic_id = f"npc.{memory_id}"
        if topic_id in catalog:
            continue
        _append_topic(
            catalog,
            topic_id=topic_id,
            label=str(getattr(memory, "name", memory_id)),
            category="npc",
            source_types=("npc_memory",),
            aliases=[memory_id],
        )

    for topic_id, entry in catalog.items():
        entry["aliases"] = sorted(alias for alias in entry.pop("_aliases", set()) if alias)
        entry["_label_key"] = str(entry.pop("_label_key", "") or "")
        entry["source_types"] = sorted(set(entry["source_types"]))
        entry.setdefault("label", _fallback_label(topic_id))

    return catalog


def _resolved_entry(catalog: dict[str, dict[str, Any]], topic_id: str) -> dict[str, Any]:
    entry = catalog.get(topic_id)
    if entry is not None:
        return entry
    return {
        "topic_id": topic_id,
        "label": _fallback_label(topic_id),
        "category": _fallback_category(topic_id),
        "aliases": [],
        "source_types": [],
    }


def build_campaign_knowledge_payload(context: "CampaignContext") -> dict[str, Any]:
    return build_runtime_knowledge_payload(context, getattr(context, "kernel_runtime", {}) or {})


def discover_topics(context: "CampaignContext", topic_ids: Iterable[str]) -> list[str]:
    state = _knowledge_state(context)
    discovered = list(state.get("discovered_topic_ids", []))
    seen = set(discovered)
    new_ids: list[str] = []
    for topic_id in topic_ids:
        normalized = str(topic_id).strip()
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            discovered.append(normalized)
            new_ids.append(normalized)
    state["discovered_topic_ids"] = discovered
    state["pinned_topic_ids"] = _normalize_topic_id_list(state.get("pinned_topic_ids", []), allowed_ids=discovered)
    return new_ids


def discover_npc_topics(context: "CampaignContext", actor: Any) -> list[str]:
    identity = getattr(actor, "identity", None)
    actor_id = str(getattr(identity, "actor_id", "")).strip()
    raw_payload = getattr(actor, "raw_payload", {}) or {}
    faction_id = str(getattr(identity, "faction_id", "") or raw_payload.get("faction_id", "") or "").strip()
    topic_ids = [
        f"npc.{actor_id}" if actor_id else "",
        f"faction.{faction_id}" if faction_id else "",
        f"region.{_current_region_id(context)}" if _current_region_id(context) else "",
        f"settlement.{_current_settlement_id(context)}" if _current_settlement_id(context) else "",
    ]
    return discover_topics(context, topic_ids)


def discover_travel_topics(
    context: "CampaignContext",
    *,
    destination_region_id: str | None = None,
    destination_settlement_id: str | None = None,
) -> list[str]:
    topic_ids = [
        f"region.{str(destination_region_id).strip()}" if str(destination_region_id or "").strip() else "",
        f"settlement.{str(destination_settlement_id).strip()}" if str(destination_settlement_id or "").strip() else "",
    ]
    return discover_topics(context, topic_ids)


def related_discovered_topic_ids_for_actor(context: "CampaignContext", actor_id: str, faction_id: str = "") -> list[str]:
    payload = build_campaign_knowledge_payload(context)
    discovered = set(payload["discovered_topic_ids"])
    related = {
        item
        for item in (
            f"npc.{str(actor_id).strip()}",
            f"faction.{str(faction_id).strip()}" if str(faction_id).strip() else "",
            f"region.{_current_region_id(context)}" if _current_region_id(context) else "",
            f"settlement.{_current_settlement_id(context)}" if _current_settlement_id(context) else "",
        )
        if item
    }
    return sorted(related & discovered)


def _topic_query_matches(catalog: dict[str, dict[str, Any]], query: str) -> tuple[str, list[str]]:
    stripped = str(query or "").strip()
    if not stripped:
        return "empty", []
    if stripped in catalog:
        return "exact_topic_id", [stripped]
    normalized_query = _normalize_alias(stripped)
    if normalized_query:
        alias_matches = sorted(
            topic_id
            for topic_id, entry in catalog.items()
            if normalized_query in set(entry.get("aliases", []))
        )
        if alias_matches:
            return "exact_alias", alias_matches
    label_query = _label_key(stripped)
    label_matches = sorted(
        topic_id
        for topic_id, entry in catalog.items()
        if label_query and label_query == str(entry.get("_label_key", ""))
    )
    if label_matches:
        return "exact_label", label_matches
    return "unknown", []


def _region_rumors(context: "CampaignContext", region_id: str) -> list[str]:
    network = getattr(context, "rumor_network", None)
    if network is None:
        return []
    runtime = getattr(context, "kernel_runtime", {}) or {}
    world_state = runtime.get("world_state")
    region = getattr(world_state, "regions", {}).get(region_id) if world_state is not None else None
    location_ids = {region_id}
    for settlement_id in getattr(region, "settlement_ids", []) if region is not None else []:
        location_ids.add(str(settlement_id))
    lines = []
    for rumor in network.get_all_active():
        if location_ids & {str(item) for item in getattr(rumor, "locations", set())}:
            lines.append(str(rumor.fact))
    return sorted(dict.fromkeys(line for line in lines if line))


def _memory_entry_for_actor(context: "CampaignContext", *, actor_id: str, memory_id: str) -> Any:
    manager = getattr(context, "npc_memory", None)
    memories = getattr(manager, "memories", {}) or {}
    normalized_memory_id = str(memory_id or "").strip()
    normalized_actor_id = str(actor_id or "").strip()
    if normalized_memory_id and normalized_memory_id in memories:
        return memories[normalized_memory_id]
    if normalized_actor_id and normalized_actor_id in memories:
        return memories[normalized_actor_id]
    return None


def _topic_slug_fragment(value: Any) -> str:
    normalized = _normalize_alias(value).replace(" ", "_")
    return normalized.strip("_") or "topic"


def _settlement_rumors(context: "CampaignContext", settlement_id: str) -> list[str]:
    network = getattr(context, "rumor_network", None)
    if network is None:
        return []
    lines = []
    for rumor in network.get_all_active():
        if str(settlement_id) in {str(item) for item in getattr(rumor, "locations", set())}:
            lines.append(str(rumor.fact))
    return sorted(dict.fromkeys(line for line in lines if line))


def _npc_rumors(context: "CampaignContext", actor: Any) -> list[str]:
    network = getattr(context, "rumor_network", None)
    if network is None:
        return []
    identity = getattr(actor, "identity", None)
    raw_payload = getattr(actor, "raw_payload", {}) or {}
    info = NPCInfo(
        npc_id=str(getattr(identity, "actor_id", "") or raw_payload.get("memory_id", "") or ""),
        location=_current_settlement_id(context) or _current_region_id(context),
        faction=str(getattr(identity, "faction_id", "") or raw_payload.get("faction_id", "") or "") or None,
    )
    return sorted(dict.fromkeys(str(rumor.fact) for rumor in network.get_rumors_for_npc(info) if str(rumor.fact).strip()))


def _rumor_entry(context: "CampaignContext", rumor_id: str) -> Any:
    normalized_rumor_id = str(rumor_id or "").strip()
    if not normalized_rumor_id:
        return None
    network = getattr(context, "rumor_network", None)
    if network is None:
        return None
    for rumor in network.get_all_active():
        if str(getattr(rumor, "rumor_id", "")).strip() == normalized_rumor_id:
            return rumor
    return None


def _history_facts_for_topic(context: "CampaignContext", *, region_id: str = "", faction_id: str = "") -> list[str]:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    world_state = runtime.get("world_state")
    facts: list[str] = []
    history_events = list(getattr(world_state, "history_events", []) or []) if world_state is not None else []
    for event in history_events:
        matches_region = bool(region_id) and str(region_id) in {str(item) for item in getattr(event, "regions", [])}
        matches_faction = bool(faction_id) and str(faction_id) in {str(item) for item in getattr(event, "factions", [])}
        if matches_region or matches_faction:
            facts.append(str(getattr(event, "summary", "")).strip())
    return [item for item in facts[:2] if item]


def _quest_payload(context: "CampaignContext", quest_id: str) -> dict[str, Any] | None:
    quest_id = str(quest_id).strip()
    if not quest_id:
        return None
    for item in list((context.campaign_state or {}).get("active_quests", []) or []):
        if str(item.get("quest_id") or item.get("id") or "").strip() == quest_id:
            payload = dict(item)
            payload["status"] = "active"
            return payload
    if quest_id in {str(item).strip() for item in list((context.campaign_state or {}).get("completed_quest_ids", []) or [])}:
        return {"quest_id": quest_id, "title": _fallback_label(quest_id), "status": "completed"}
    if quest_id in {str(item).strip() for item in list((context.campaign_state or {}).get("failed_quest_ids", []) or [])}:
        return {"quest_id": quest_id, "title": _fallback_label(quest_id), "status": "failed"}
    for item in list((context.campaign_state or {}).get("quest_offers", []) or []):
        if str(item.get("quest_id") or item.get("id") or "").strip() == quest_id:
            payload = dict(item)
            payload["status"] = "offered"
            return payload
    return None


def _topic_facts_and_rumors(context: "CampaignContext", topic_id: str, entry: dict[str, Any]) -> tuple[list[str], list[str]]:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    world_state = runtime.get("world_state")
    category = str(entry.get("category", _fallback_category(topic_id))).strip().lower()
    identifier = topic_id.split(".", 1)[-1]
    facts: list[str] = []
    rumors: list[str] = []

    if category == "region" and world_state is not None:
        region = getattr(world_state, "regions", {}).get(identifier)
        if region is not None:
            facts.append(
                f"{entry['label']} is a {str(getattr(region, 'biome_id', 'frontier')).replace('_', ' ')} region with "
                f"{len(getattr(region, 'settlement_ids', []))} settlement(s)."
            )
            controller = str(getattr(region, "controller_faction_id", "") or "").strip()
            if controller:
                facts.append(f"It is currently influenced by {controller.replace('_', ' ')}.")
            facts.extend(_history_facts_for_topic(context, region_id=identifier))
            rumors = _region_rumors(context, identifier)
    elif category == "settlement" and world_state is not None:
        settlement = getattr(world_state, "settlements", {}).get(identifier)
        if settlement is not None:
            facts.append(
                f"{entry['label']} is a {str(getattr(settlement, 'settlement_type', 'settlement')).replace('_', ' ')} "
                f"with population {int(getattr(settlement, 'population', 0) or 0)}."
            )
            faction_id = str(getattr(settlement, "faction_id", "") or "").strip()
            if faction_id:
                facts.append(f"It belongs to {faction_id.replace('_', ' ')}.")
            region_id = str(getattr(settlement, "region_id", "") or "").strip()
            if region_id:
                facts.append(f"It is located in {region_id.replace('_', ' ')}.")
            rumors = _settlement_rumors(context, identifier)
    elif category == "faction" and world_state is not None:
        faction = getattr(world_state, "factions", {}).get(identifier)
        if faction is not None:
            facts.append(
                f"{entry['label']} is rooted in {str(getattr(faction, 'origin_region_id', '')).replace('_', ' ')} "
                f"and has presence in {len(getattr(faction, 'region_presence', {}))} region(s)."
            )
            species_id = str(getattr(faction, "species_id", "") or "").strip()
            if species_id:
                facts.append(f"Its dominant species is {species_id.replace('_', ' ')}.")
            facts.extend(_history_facts_for_topic(context, faction_id=identifier))
            network = getattr(context, "rumor_network", None)
            if network is not None:
                rumors = sorted(
                    dict.fromkeys(
                        str(rumor.fact)
                        for rumor in network.get_all_active()
                        if str(getattr(rumor, "faction_filter", "") or "").strip() == identifier
                    )
                )
    elif category == "quest":
        quest = _quest_payload(context, identifier)
        if quest is not None:
            title = str(quest.get("title", entry["label"])).strip() or entry["label"]
            status = str(quest.get("status", "active")).strip().lower() or "active"
            facts.append(f"{title} is currently {status}.")
            stage = str(quest.get("stage", "")).strip()
            if stage:
                facts.append(f"Current stage: {stage.replace('_', ' ')}.")
            objectives = list(quest.get("objectives", []) or [])
            if objectives:
                facts.append(f"It tracks {len(objectives)} objective(s).")
    elif category == "rumor":
        rumor = _rumor_entry(context, identifier)
        if rumor is not None:
            rumor_fact = str(getattr(rumor, "fact", "") or "").strip()
            if rumor_fact:
                rumors.append(rumor_fact)
    elif category == "fact":
        fact_label = str(entry.get("label", "")).strip()
        if fact_label:
            facts.append(fact_label)
    elif category == "npc":
        actor = (runtime.get("actors") or {}).get(identifier)
        memory_manager = getattr(context, "npc_memory", None)
        memory = None
        if memory_manager is not None:
            memory = getattr(memory_manager, "memories", {}).get(identifier)
        if actor is not None:
            raw_payload = getattr(actor, "raw_payload", {}) or {}
            role = str(raw_payload.get("role") or raw_payload.get("template") or "").strip()
            if role:
                facts.append(f"{entry['label']} is a {role.replace('_', ' ')}.")
            faction_id = str(getattr(getattr(actor, "identity", None), "faction_id", "") or raw_payload.get("faction_id", "") or "").strip()
            if faction_id:
                facts.append(f"They are aligned with {faction_id.replace('_', ' ')}.")
            relationship_score = int(raw_payload.get("relationship_score", 0) or 0)
            facts.append(f"Your current relationship score is {relationship_score}.")
            rumors = _npc_rumors(context, actor)
        if memory is not None:
            relationship_label = str(getattr(memory, "relationship_label", "") or "").strip()
            if relationship_label:
                facts.append(f"They currently regard you as {relationship_label}.")
            memory_summary = str(getattr(memory, "long_term_memory", "") or "").strip()
            if memory_summary:
                facts.append(memory_summary)
            for fact in list(getattr(memory, "known_facts", []) or [])[:3]:
                normalized = str(fact).strip()
                if normalized:
                    facts.append(normalized)

    facts = [item for item in dict.fromkeys(item.strip() for item in facts if str(item).strip())]
    rumors = [item for item in dict.fromkeys(item.strip() for item in rumors if str(item).strip())]
    return facts[:6], rumors[:6]


def _queue_knowledge_view(context: "CampaignContext", payload: dict[str, Any]) -> None:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    runtime["_pending_knowledge_payload"] = {"knowledge_view": payload}


def _queue_ask_about_view(context: "CampaignContext", ask_about: dict[str, Any], knowledge_view: dict[str, Any]) -> None:
    queued_view = dict(knowledge_view)
    queued_view["ask_about"] = ask_about
    _queue_knowledge_view(context, queued_view)
    conversation = dict(getattr(context, "conversation_state", {}) or {})
    if conversation:
        conversation["ask_about"] = ask_about
        context.conversation_state = conversation


def build_think_view(context: "CampaignContext", topic_id: str) -> dict[str, Any]:
    payload = build_campaign_knowledge_payload(context)
    catalog = build_topic_catalog(context)
    entry = _resolved_entry(catalog, topic_id)
    facts, rumors = _topic_facts_and_rumors(context, topic_id, entry)
    blockers = [] if facts or rumors else ["no_grounded_facts"]
    return {
        "topic": {
            "topic_id": topic_id,
            "label": entry["label"],
            "category": entry["category"],
            "source_types": list(entry.get("source_types", [])),
        },
        "facts": facts,
        "rumors": rumors,
        "blockers": blockers,
        "pinned": topic_id in set(payload["pinned_topic_ids"]),
    }


def _dialog_npc_actor(context: "CampaignContext") -> Any:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    dialog_state = runtime.get("dialog_state")
    if not bool(getattr(dialog_state, "active", False)):
        return None
    conversation = dict(getattr(context, "conversation_state", {}) or {})
    if str(conversation.get("target_type", "")).strip().lower() != "npc":
        return None
    npc_id = str(runtime.get("dialog_npc_id") or conversation.get("npc_id") or "").strip()
    if not npc_id:
        return None
    return (runtime.get("actors") or {}).get(npc_id)


def _known_topic_ids_for_actor(context: "CampaignContext", actor: Any) -> list[str]:
    identity = getattr(actor, "identity", None)
    actor_id = str(getattr(identity, "actor_id", "")).strip()
    raw_payload = getattr(actor, "raw_payload", {}) or {}
    memory_id = str(raw_payload.get("memory_id", "") or raw_payload.get("named_npc_id", "") or actor_id).strip()
    named_npc_id = str(raw_payload.get("named_npc_id", "") or "").strip()
    candidate_ids = {
        str(value).strip()
        for value in (actor_id, memory_id, named_npc_id)
        if str(value or "").strip()
    }
    if not candidate_ids:
        return []

    known_topic_ids: list[str] = []
    seen: set[str] = set()

    memory = _memory_entry_for_actor(context, actor_id=actor_id, memory_id=memory_id)
    for fact in sorted({str(fact).strip() for fact in list(getattr(memory, "known_facts", []) or []) if str(fact).strip()}):
        topic_id = f"fact.{_topic_slug_fragment(fact)}"
        if topic_id in seen:
            continue
        seen.add(topic_id)
        known_topic_ids.append(topic_id)

    network = getattr(context, "rumor_network", None)
    active_rumors = network.get_all_active() if network is not None else []
    for rumor in sorted(active_rumors, key=lambda item: str(getattr(item, "rumor_id", ""))):
        rumor_id = str(getattr(rumor, "rumor_id", "")).strip()
        if not rumor_id:
            continue
        owner_ids = {
            str(owner_id).strip()
            for owner_id in list(getattr(rumor, "heard_by", set()) or set())
            if str(owner_id).strip()
        }
        source_npc = str(getattr(rumor, "source_npc", "") or "").strip()
        if source_npc:
            owner_ids.add(source_npc)
        if not owner_ids.intersection(candidate_ids):
            continue
        topic_id = f"rumor.{rumor_id}"
        if topic_id in seen:
            continue
        seen.add(topic_id)
        known_topic_ids.append(topic_id)

    return known_topic_ids


def _ask_about_topic_ids_for_actor(context: "CampaignContext", actor: Any) -> list[str]:
    identity = getattr(actor, "identity", None)
    actor_id = str(getattr(identity, "actor_id", "")).strip()
    faction_id = str(getattr(identity, "faction_id", "") or getattr(actor, "raw_payload", {}).get("faction_id", "") or "").strip()
    related_topic_ids = related_discovered_topic_ids_for_actor(context, actor_id, faction_id)
    ask_about_topic_ids: list[str] = []
    seen: set[str] = set()
    for topic_id in list(related_topic_ids) + list(_known_topic_ids_for_actor(context, actor)):
        normalized = str(topic_id).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ask_about_topic_ids.append(normalized)
    return ask_about_topic_ids


def _redirect_topic_ids_for_actor(context: "CampaignContext", actor: Any, *, exclude_topic_id: str = "") -> list[str]:
    related = _ask_about_topic_ids_for_actor(context, actor)
    excluded = str(exclude_topic_id or "").strip()
    catalog = build_topic_catalog(context)
    redirect_ids: list[str] = []
    for topic_id in related:
        normalized = str(topic_id).strip()
        if not normalized or normalized == excluded:
            continue
        entry = _resolved_entry(catalog, normalized)
        facts, rumors = _topic_facts_and_rumors(context, normalized, entry)
        if not facts and not rumors:
            continue
        redirect_ids.append(normalized)
    return redirect_ids[:3]


def _topic_payload_from_entry(topic_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "label": entry["label"],
        "category": entry["category"],
        "source_types": list(entry.get("source_types", [])),
    }


def _ask_about_rejection_payload(
    *,
    topic: dict[str, Any] | None,
    refusal_reason: str,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "response_type": "refusal",
        "facts": [],
        "rumors": [],
        "redirect_topic_ids": [],
        "refusal_reason": refusal_reason,
    }


def _build_ask_about_payload(context: "CampaignContext", actor: Any, topic_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    think_view = build_think_view(context, topic_id)
    facts = list(think_view.get("facts", []))
    rumors = list(think_view.get("rumors", []))
    direct_topic_ids = set(_known_topic_ids_for_actor(context, actor))
    ask_about_topic_ids = set(_ask_about_topic_ids_for_actor(context, actor))

    if topic_id in ask_about_topic_ids:
        if topic_id in direct_topic_ids and facts:
            response_type = "fact"
        elif topic_id in direct_topic_ids and rumors:
            response_type = "rumor"
        elif facts:
            response_type = "fact"
        elif rumors:
            response_type = "rumor"
        else:
            redirect_topic_ids = _redirect_topic_ids_for_actor(context, actor, exclude_topic_id=topic_id)
            if redirect_topic_ids:
                return {
                    "topic": _topic_payload_from_entry(topic_id, entry),
                    "response_type": "redirect",
                    "facts": [],
                    "rumors": [],
                    "redirect_topic_ids": redirect_topic_ids,
                }
            return _ask_about_rejection_payload(
                topic=_topic_payload_from_entry(topic_id, entry),
                refusal_reason="no_grounded_answer",
            )
        return {
            "topic": _topic_payload_from_entry(topic_id, entry),
            "response_type": response_type,
            "facts": facts,
            "rumors": rumors,
            "redirect_topic_ids": [],
        }

    redirect_topic_ids = _redirect_topic_ids_for_actor(context, actor, exclude_topic_id=topic_id)
    if redirect_topic_ids:
        return {
            "topic": _topic_payload_from_entry(topic_id, entry),
            "response_type": "redirect",
            "facts": [],
            "rumors": [],
            "redirect_topic_ids": redirect_topic_ids,
        }
    return _ask_about_rejection_payload(
        topic=_topic_payload_from_entry(topic_id, entry),
        refusal_reason="unknown_to_npc",
    )


def _resolve_for_command(context: "CampaignContext", query: str) -> tuple[str, list[str], dict[str, Any]]:
    catalog = build_topic_catalog(context)
    resolution_kind, topic_ids = _topic_query_matches(catalog, query)
    discovered = set(build_campaign_knowledge_payload(context)["discovered_topic_ids"])
    if not topic_ids:
        return resolution_kind, [], catalog
    if len(topic_ids) > 1:
        return "ambiguous", topic_ids, catalog
    if topic_ids[0] not in discovered:
        return "undiscovered", topic_ids, catalog
    return resolution_kind, topic_ids, catalog


def _topics_command(context: "CampaignContext") -> tuple[str, str, int]:
    payload = build_campaign_knowledge_payload(context)
    _queue_knowledge_view(
        context,
        {
            "topics": list(payload["topics"]),
            "discovered_topic_ids": list(payload["discovered_topic_ids"]),
            "pinned_topic_ids": list(payload["pinned_topic_ids"]),
            "blockers": [],
        },
    )
    count = len(payload["topics"])
    return (f"You review {count} discovered topic{'s' if count != 1 else ''}.", "knowledge", 0)


def _think_command(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    resolution_kind, topic_ids, catalog = _resolve_for_command(context, query)
    if resolution_kind == "unknown":
        _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["unknown_topic"], "pinned": False})
        return (f"No knowledge topic matched '{query.strip()}'.", "knowledge", 0)
    if resolution_kind == "ambiguous":
        _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["ambiguous_topic"], "pinned": False})
        options = ", ".join(topic_ids)
        return (f"That topic is ambiguous. Try one of: {options}.", "knowledge", 0)
    topic_id = topic_ids[0]
    if resolution_kind == "undiscovered":
        entry = _resolved_entry(catalog, topic_id)
        _queue_knowledge_view(
            context,
            {
                "topic": {
                    "topic_id": topic_id,
                    "label": entry["label"],
                    "category": entry["category"],
                    "source_types": list(entry.get("source_types", [])),
                },
                "facts": [],
                "rumors": [],
                "blockers": ["undiscovered_topic"],
                "pinned": False,
            },
        )
        return (f"You have not discovered {entry['label']} yet.", "knowledge", 0)
    view = build_think_view(context, topic_id)
    _queue_knowledge_view(context, view)
    topic_label = view["topic"]["label"]
    if view["blockers"]:
        return (f"You pause to think about {topic_label}, but nothing grounded comes to mind.", "knowledge", 0)
    return (f"You organize what you know about {topic_label}.", "knowledge", 0)


def _ask_about_command(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    actor = _dialog_npc_actor(context)
    if actor is None:
        _queue_knowledge_view(
            context,
            {
                "topic": None,
                "facts": [],
                "rumors": [],
                "blockers": ["no_active_dialog"],
                "pinned": False,
                "ask_about": _ask_about_rejection_payload(topic=None, refusal_reason="no_active_dialog"),
            },
        )
        return ("Ask about only works during an active NPC conversation.", "dialog", 0)

    resolution_kind, topic_ids, catalog = _resolve_for_command(context, query)
    if resolution_kind == "unknown":
        ask_about = _ask_about_rejection_payload(topic=None, refusal_reason="unknown_topic")
        _queue_ask_about_view(
            context,
            ask_about,
            {"topic": None, "facts": [], "rumors": [], "blockers": ["unknown_topic"], "pinned": False},
        )
        return (f"No knowledge topic matched '{query.strip()}'.", "dialog", 0)
    if resolution_kind == "ambiguous":
        ask_about = _ask_about_rejection_payload(topic=None, refusal_reason="ambiguous_topic")
        _queue_ask_about_view(
            context,
            ask_about,
            {"topic": None, "facts": [], "rumors": [], "blockers": ["ambiguous_topic"], "pinned": False},
        )
        options = ", ".join(topic_ids)
        return (f"That topic is ambiguous. Try one of: {options}.", "dialog", 0)

    topic_id = topic_ids[0]
    entry = _resolved_entry(catalog, topic_id)
    if resolution_kind == "undiscovered":
        ask_about = _ask_about_rejection_payload(
            topic=_topic_payload_from_entry(topic_id, entry),
            refusal_reason="undiscovered_topic",
        )
        _queue_ask_about_view(
            context,
            ask_about,
            {
                "topic": _topic_payload_from_entry(topic_id, entry),
                "facts": [],
                "rumors": [],
                "blockers": ["undiscovered_topic"],
                "pinned": False,
            },
        )
        return (f"You have not discovered {entry['label']} yet.", "dialog", 0)

    ask_about = _build_ask_about_payload(context, actor, topic_id, entry)
    knowledge_view = build_think_view(context, topic_id)
    _queue_ask_about_view(context, ask_about, knowledge_view)
    npc_name = str(getattr(getattr(actor, "identity", None), "display_name", "")).strip() or "They"
    label = str(entry["label"]).strip() or _fallback_label(topic_id)
    response_type = str(ask_about.get("response_type", "")).strip().lower()
    if response_type == "fact":
        return (f"{npc_name} shares what they know about {label}.", "dialog", 0)
    if response_type == "rumor":
        return (f"{npc_name} passes along a rumor about {label}.", "dialog", 0)
    if response_type == "redirect":
        redirects = list(ask_about.get("redirect_topic_ids", []))
        if redirects:
            redirect_entry = _resolved_entry(catalog, redirects[0])
            return (
                f"{npc_name} cannot speak on {label}, but points you toward {redirect_entry['label']}.",
                "dialog",
                0,
            )
        return (f"{npc_name} changes the subject instead of answering.", "dialog", 0)
    return (f"{npc_name} refuses to discuss {label}.", "dialog", 0)


def _pin_command(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    resolution_kind, topic_ids, catalog = _resolve_for_command(context, query)
    if resolution_kind == "unknown":
        _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["unknown_topic"], "pinned": False})
        return (f"No knowledge topic matched '{query.strip()}'.", "knowledge", 0)
    if resolution_kind == "ambiguous":
        _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["ambiguous_topic"], "pinned": False})
        options = ", ".join(topic_ids)
        return (f"That topic is ambiguous. Try one of: {options}.", "knowledge", 0)
    topic_id = topic_ids[0]
    if resolution_kind == "undiscovered":
        entry = _resolved_entry(catalog, topic_id)
        _queue_knowledge_view(
            context,
            {
                "topic": {
                    "topic_id": topic_id,
                    "label": entry["label"],
                    "category": entry["category"],
                    "source_types": list(entry.get("source_types", [])),
                },
                "facts": [],
                "rumors": [],
                "blockers": ["undiscovered_topic"],
                "pinned": False,
            },
        )
        return (f"You cannot pin {entry['label']} before discovering it.", "knowledge", 0)
    state = _knowledge_state(context)
    discovered = _normalize_topic_id_list(state.get("discovered_topic_ids", []))
    if topic_id not in set(discovered):
        discovered.append(topic_id)
    state["discovered_topic_ids"] = discovered
    pinned = _normalize_topic_id_list(
        state.get("pinned_topic_ids", []),
        allowed_ids=discovered,
    )
    already_pinned = topic_id in set(pinned)
    if not already_pinned:
        pinned.append(topic_id)
    state["pinned_topic_ids"] = pinned
    view = build_think_view(context, topic_id)
    view["pinned"] = True
    _queue_knowledge_view(context, view)
    label = view["topic"]["label"]
    if already_pinned:
        return (f"{label} is already pinned in your notes.", "knowledge", 0)
    return (f"Pinned {label} in your notes.", "knowledge", 0)


def maybe_handle_knowledge_command(context: "CampaignContext", command_text: str) -> tuple[str, str, int] | None:
    text = command_text.strip()
    if _TOPICS_RE.match(text):
        return _topics_command(context)
    think_match = _THINK_RE.match(text)
    if think_match:
        return _think_command(context, think_match.group(1).strip())
    pin_match = _PIN_RE.match(text)
    if pin_match:
        return _pin_command(context, pin_match.group(1).strip())
    return None


def maybe_handle_ask_about_command(context: "CampaignContext", command_text: str) -> tuple[str, str, int] | None:
    match = _ASK_ABOUT_RE.match(command_text.strip())
    if not match:
        return None
    query = match.group(1).strip()
    if not query:
        _queue_knowledge_view(
            context,
            {
                "topic": None,
                "facts": [],
                "rumors": [],
                "blockers": ["missing_topic_query"],
                "pinned": False,
                "ask_about": _ask_about_rejection_payload(topic=None, refusal_reason="missing_topic_query"),
            },
        )
        return ("Ask about requires a topic.", "dialog", 0)
    return _ask_about_command(context, query)


def maybe_handle_structured_knowledge_command(
    context: "CampaignContext",
    args: dict[str, Any],
) -> tuple[str, str, int] | None:
    action_id = str(args.get("action_id", "")).strip().lower()
    query = str(args.get("topic_id") or args.get("query") or "").strip()
    if action_id == "topics":
        return _topics_command(context)
    if action_id == "think":
        if not query:
            _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["missing_topic_query"], "pinned": False})
            return ("Think requires a topic_id or query.", "knowledge", 0)
        return _think_command(context, query)
    if action_id == "pin":
        if not query:
            _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["missing_topic_query"], "pinned": False})
            return ("Pin requires a topic_id or query.", "knowledge", 0)
        return _pin_command(context, query)
    if action_id:
        _queue_knowledge_view(context, {"topic": None, "facts": [], "rumors": [], "blockers": ["unsupported_action"], "pinned": False})
        return (f"Unsupported knowledge action '{action_id}'.", "knowledge", 0)
    return None


def maybe_handle_structured_ask_about_command(
    context: "CampaignContext",
    args: dict[str, Any],
) -> tuple[str, str, int] | None:
    action_id = str(args.get("action_id", "")).strip().lower()
    if action_id != "ask_about":
        return None
    query = str(args.get("topic_id") or args.get("query") or "").strip()
    if not query:
        _queue_knowledge_view(
            context,
            {
                "topic": None,
                "facts": [],
                "rumors": [],
                "blockers": ["missing_topic_query"],
                "pinned": False,
                "ask_about": _ask_about_rejection_payload(topic=None, refusal_reason="missing_topic_query"),
            },
        )
        return ("Ask about requires a topic_id or query.", "dialog", 0)
    return _ask_about_command(context, query)
