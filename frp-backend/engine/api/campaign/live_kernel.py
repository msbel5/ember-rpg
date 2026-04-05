from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from engine.api.campaign_kernel import (
    build_canonical_actor_records,
    build_canonical_game_state,
    build_canonical_world_state,
)
from engine.kernel import (
    ActorRecord,
    GameState,
    JobRecord,
    LocalMapState,
    MilitaryState,
    PathAuthorityState,
    ProductionLedger,
    ReactionDef,
    TravelState,
    WorksiteRecord,
    WorldState,
    colony_pressure_from_settlement,
    complete_travel,
    hydrate_local_map,
    local_map_state_from_region,
    military_state_from_settlement,
    path_authority_from_world,
    production_ledger_from_settlement,
    spread_contagion,
)
from engine.npc.npc_memory import NPCMemoryManager
from engine.kernel.scene_types import SceneContext, SceneType
from engine.world.body_parts import ARMOR_COVERAGE

from .runtime_common import active_site_id, saved_list_or, saved_or, stable_seed
from .runtime_effects import effect_events
from .runtime_macro_society import load_stores, macro_society_events
from .world import runtime_region_state
from .runtime_settlement import (
    job_and_farm_events,
    merge_projection_changes_from_settlement,
    rebase_projection_slices,
    refresh_runtime_views,
)
from .runtime_systems import load_systems, systems_events
from .region_projection import sync_combat_projection_state
from engine.kernel.game_state import normalize_party_state


_TRAVEL_STATE_KEYS = {
    "status",
    "origin_region_id",
    "destination_region_id",
    "travel_hours_remaining",
    "travel_hours_total",
    "encounter_roll",
    "encounter_triggered",
    "edge_id",
    "danger_level",
    "encounter_checked",
    "paused_for_encounter",
    "encounter_resolved",
}
_KNOWLEDGE_STATE_KEYS = {
    "discovered_topic_ids",
    "pinned_topic_ids",
}
_EQUIPMENT_CANONICAL_SLOT_ALIASES: dict[str, tuple[str, ...]] = {
    "head": ("helmet",),
    "body": ("armor", "body", "chest"),
    "shield": ("shield",),
    "hands": ("gloves", "gauntlets"),
    "waist": ("belt",),
    "feet": ("boots", "greaves"),
    "cloak": ("cloak", "cover", "over"),
    "neck": ("amulet", "neck"),
    "ring_left": ("left_ring", "ring_left"),
    "ring_right": ("right_ring",),
    "main_hand": ("weapon", "main_hand", "weapon_1"),
    "off_hand": ("off_hand",),
    "weapon_2": ("weapon_2",),
    "weapon_3": ("weapon_3",),
    "weapon_4": ("weapon_4",),
    "quiver_1": ("quiver_1",),
    "quiver_2": ("quiver_2",),
    "quiver_3": ("quiver_3",),
    "quiver_4": ("quiver_4",),
    "quick_item_1": ("quick_item_1",),
    "quick_item_2": ("quick_item_2",),
    "quick_item_3": ("quick_item_3",),
    "underlayer": ("under", "underlayer", "clothes"),
}
_EQUIPMENT_CANONICAL_SLOT_ORDER = tuple(_EQUIPMENT_CANONICAL_SLOT_ALIASES)


def _normalize_runtime_scene_name(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "travel":
        return SceneType.TRANSITION.value
    return normalized or SceneType.EXPLORATION.value


if not getattr(SceneContext, "_travel_scene_alias_installed", False):
    _scene_type_name = SceneContext.scene_type_name

    def _scene_type_name_setter(self: SceneContext, value: str) -> None:
        self.scene_type = SceneType(_normalize_runtime_scene_name(value))

    SceneContext.scene_type_name = property(_scene_type_name.fget, _scene_type_name_setter)
    SceneContext._travel_scene_alias_installed = True


def _normalize_travel_state_payload(raw_state: Any) -> dict[str, Any] | None:
    if isinstance(raw_state, TravelState):
        return raw_state.to_dict()
    if not isinstance(raw_state, dict):
        return None
    payload = dict(raw_state)
    if "route_id" in payload and "edge_id" not in payload:
        payload["edge_id"] = payload.get("route_id")
    normalized = {key: payload[key] for key in _TRAVEL_STATE_KEYS if key in payload}
    try:
        return TravelState.from_dict(normalized).to_dict()
    except Exception:
        return None


def _normalize_topic_id_list(raw_topic_ids: Any) -> list[str]:
    if not isinstance(raw_topic_ids, Sequence) or isinstance(raw_topic_ids, (str, bytes, bytearray)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in raw_topic_ids:
        topic_id = str(entry or "").strip()
        if not topic_id or topic_id in seen:
            continue
        seen.add(topic_id)
        normalized.append(topic_id)
    return normalized


def _normalize_knowledge_state_payload(raw_state: Any) -> dict[str, Any] | None:
    if not isinstance(raw_state, dict):
        return None
    normalized = {
        "discovered_topic_ids": _normalize_topic_id_list(raw_state.get("discovered_topic_ids", [])),
        "pinned_topic_ids": _normalize_topic_id_list(raw_state.get("pinned_topic_ids", [])),
    }
    if not normalized["discovered_topic_ids"] and not normalized["pinned_topic_ids"]:
        return None
    return normalized


def _knowledge_state(runtime: dict[str, Any]) -> dict[str, Any]:
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
    normalized = _normalize_knowledge_state_payload(raw_payload.get("knowledge"))
    if normalized is None:
        return {
            "discovered_topic_ids": [],
            "pinned_topic_ids": [],
        }
    return normalized


def _persist_knowledge_state(runtime: dict[str, Any], knowledge_state: Any) -> None:
    game_state = runtime.get("game_state")
    if game_state is None:
        return
    raw_payload = getattr(game_state, "raw_payload", None)
    if not isinstance(raw_payload, dict):
        raw_payload = {}
        game_state.raw_payload = raw_payload
    normalized = _normalize_knowledge_state_payload(knowledge_state)
    if normalized is None:
        raw_payload.pop("knowledge", None)
        return
    raw_payload["knowledge"] = {key: normalized[key] for key in _KNOWLEDGE_STATE_KEYS}


def _travel_state(runtime: dict[str, Any]) -> TravelState | None:
    runtime_state = _normalize_travel_state_payload(runtime.get("travel_state"))
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
    raw_state = raw_payload.get("travel_state", raw_payload.get("travel"))
    normalized = _normalize_travel_state_payload(raw_state)
    runtime_status = str((runtime_state or {}).get("status", "")).lower().strip() if runtime_state is not None else ""
    if runtime_state is not None and (normalized is None or runtime_status not in {"", "idle", "cancelled"}):
        return TravelState.from_dict(runtime_state)
    if normalized is None:
        return None
    return TravelState.from_dict(normalized)


def _persist_travel_state(runtime: dict[str, Any], travel: TravelState | None) -> None:
    game_state = runtime.get("game_state")
    if game_state is None:
        return
    raw_payload = getattr(game_state, "raw_payload", None)
    if not isinstance(raw_payload, dict):
        raw_payload = {}
        game_state.raw_payload = raw_payload
    raw_payload.pop("travel", None)
    status = str(getattr(travel, "status", "") or "").lower().strip() if travel is not None else ""
    if travel is None or status in {"", "idle", "cancelled"}:
        raw_payload.pop("travel_state", None)
        runtime["travel_state"] = TravelState(status="idle")
        return
    raw_payload["travel_state"] = travel.to_dict()
    runtime["travel_state"] = travel


def _travel_is_active(travel: TravelState | None) -> bool:
    if travel is None:
        return False
    status = str(travel.status or "").lower().strip()
    if status in {"", "idle", "arrived", "completed", "resolved", "cancelled"}:
        return False
    return True


def _travel_projection_region_id(travel: TravelState | None, fallback_region_id: str) -> str:
    if travel is None:
        return str(fallback_region_id)
    status = str(travel.status or "").lower().strip()
    if status in {"arrived", "completed", "resolved"} and str(travel.destination_region_id).strip():
        return str(travel.destination_region_id)
    if str(travel.origin_region_id).strip():
        return str(travel.origin_region_id)
    return str(fallback_region_id)


def _travel_site_id_for_region(world_state: WorldState, region_id: str) -> str:
    for site in world_state.sites.values():
        if str(site.region_id) == str(region_id):
            return str(site.site_id)
    for settlement in world_state.settlements.values():
        if str(settlement.region_id) == str(region_id):
            return str(settlement.settlement_id)
    return str(region_id)


def build_runtime_travel_payload(runtime: dict[str, Any]) -> dict[str, Any] | None:
    travel = _travel_state(runtime)
    if travel is None:
        return None
    if str(travel.status or "").lower().strip() in {"", "idle", "cancelled"}:
        return None
    world_state = runtime.get("world_state")
    route_id = str(getattr(travel, "edge_id", "") or "").strip()
    destination_settlement_id = ""
    destination_name = ""
    if isinstance(world_state, WorldState):
        for edge in world_state.travel_edges:
            if route_id and str(edge.edge_id) != route_id:
                continue
            if not route_id and {
                str(edge.source_region_id),
                str(edge.destination_region_id),
            } != {str(travel.origin_region_id), str(travel.destination_region_id)}:
                continue
            route_id = str(edge.edge_id)
            if str(edge.destination_region_id) == str(travel.destination_region_id):
                destination_settlement_id = str(edge.destination_settlement_id or "")
            elif str(edge.source_region_id) == str(travel.destination_region_id):
                destination_settlement_id = str(edge.source_settlement_id or "")
            break
        if destination_settlement_id:
            settlement = world_state.settlements.get(destination_settlement_id)
            if settlement is not None:
                destination_name = str(settlement.name)
    requires_resolution = bool(travel.paused_for_encounter and not travel.encounter_resolved)
    can_advance = bool(_travel_is_active(travel) and not requires_resolution)
    return {
        "status": str(travel.status),
        "route_id": route_id,
        "origin_region_id": str(travel.origin_region_id),
        "destination_region_id": str(travel.destination_region_id),
        "destination_settlement_id": destination_settlement_id,
        "destination_name": destination_name,
        "travel_hours_total": int(travel.travel_hours_total),
        "travel_hours_remaining": int(travel.travel_hours_remaining),
        "danger_level": int(travel.danger_level),
        "encounter_triggered": bool(travel.encounter_triggered),
        "paused_for_encounter": bool(travel.paused_for_encounter),
        "encounter_resolved": bool(travel.encounter_resolved),
        "can_advance": can_advance,
        "requires_resolution": requires_resolution,
    }


_KNOWLEDGE_CATEGORIES = {"npc", "faction", "region", "settlement", "quest", "rumor", "fact"}


def _normalize_knowledge_ids(values: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        topic_id = str(value or "").strip()
        if not topic_id or topic_id in seen:
            continue
        seen.add(topic_id)
        normalized.append(topic_id)
    return normalized


def _slugify_topic_fragment(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _titleize_topic_fragment(value: Any) -> str:
    text = str(value or "").strip().replace("_", " ").replace(".", " ")
    return text.title().strip() or "Unknown Topic"


def _topic_category(topic_id: str) -> str:
    prefix = str(topic_id).split(".", 1)[0].strip().lower()
    return prefix if prefix in _KNOWLEDGE_CATEGORIES else "fact"


def _knowledge_raw_state(runtime: dict[str, Any]) -> dict[str, list[str]]:
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
    raw_knowledge = raw_payload.get("knowledge", {}) if isinstance(raw_payload, dict) else {}
    if not isinstance(raw_knowledge, dict):
        raw_knowledge = {}
    return {
        "discovered_topic_ids": _normalize_knowledge_ids(raw_knowledge.get("discovered_topic_ids", [])),
        "pinned_topic_ids": _normalize_knowledge_ids(raw_knowledge.get("pinned_topic_ids", [])),
    }


def _world_region_label(world: Any, region_id: str) -> str:
    regions = list(getattr(world, "regions", []) or [])
    for region in regions:
        if str(region.get("id", "")) != str(region_id):
            continue
        label = str(region.get("name", region.get("title", region_id))).strip()
        return label or _titleize_topic_fragment(region_id)
    return _titleize_topic_fragment(region_id)


def _world_settlement_label(world: Any, settlement_id: str) -> str:
    settlements = list(getattr(world, "settlements", []) or [])
    for settlement in settlements:
        if str(getattr(settlement, "id", settlement.get("id", "")) if isinstance(settlement, dict) else getattr(settlement, "id", "")) != str(settlement_id):
            continue
        label = ""
        if isinstance(settlement, dict):
            label = str(settlement.get("center_name", settlement.get("name", settlement_id))).strip()
        else:
            label = str(getattr(settlement, "center_name", getattr(settlement, "name", settlement_id))).strip()
        return label or _titleize_topic_fragment(settlement_id)
    return _titleize_topic_fragment(settlement_id)


def _register_knowledge_topic(
    topics: dict[str, dict[str, Any]],
    topic_id: str,
    *,
    label: str,
    category: str,
    source_type: str,
) -> None:
    normalized_topic_id = str(topic_id).strip()
    if not normalized_topic_id:
        return
    normalized_category = category if category in _KNOWLEDGE_CATEGORIES else _topic_category(normalized_topic_id)
    entry = topics.get(normalized_topic_id)
    if entry is None:
        entry = {
            "topic_id": normalized_topic_id,
            "label": str(label).strip() or _titleize_topic_fragment(normalized_topic_id),
            "category": normalized_category,
            "source_types": [source_type] if source_type else [],
        }
        topics[normalized_topic_id] = entry
        return
    if label and (entry.get("label") in {"", normalized_topic_id} or len(str(label)) > len(str(entry.get("label", "")))) :
        entry["label"] = str(label).strip()
    if normalized_category and entry.get("category") in {"", "fact"}:
        entry["category"] = normalized_category
    if source_type:
        source_types = list(entry.get("source_types", []))
        if source_type not in source_types:
            source_types.append(source_type)
        entry["source_types"] = source_types


def _current_settlement_id(context: "CampaignContext") -> str:
    return str(
        context.settlement_state.get("settlement_id")
        or getattr(getattr(context, "region_snapshot", None), "metadata", {}).get("settlement_id")
        or getattr(getattr(context, "region_snapshot", None), "region_id", "")
    ).strip()


def _current_region_id(context: "CampaignContext") -> str:
    return str(getattr(getattr(context, "region_snapshot", None), "region_id", "")).strip()


def _knowledge_bootstrap_topic_ids(context: "CampaignContext") -> list[str]:
    bootstrap: list[str] = []
    region_id = _current_region_id(context)
    if region_id:
        bootstrap.append(f"region.{region_id}")
    settlement_id = _current_settlement_id(context)
    if settlement_id and settlement_id != region_id:
        bootstrap.append(f"settlement.{settlement_id}")
    active_quests = list((context.campaign_state or {}).get("active_quests", []) or [])
    for quest in active_quests:
        quest_id = str(quest.get("quest_id", quest.get("id", ""))).strip()
        if quest_id:
            bootstrap.append(f"quest.{quest_id}")
    return _normalize_knowledge_ids(bootstrap)


def _knowledge_topic_catalog(context: "CampaignContext", runtime: dict[str, Any]) -> dict[str, dict[str, Any]]:
    topics: dict[str, dict[str, Any]] = {}
    world = getattr(context, "world", None)

    region_id = _current_region_id(context)
    if region_id:
        _register_knowledge_topic(
            topics,
            f"region.{region_id}",
            label=_world_region_label(world, region_id),
            category="region",
            source_type="world",
        )

    settlement_id = _current_settlement_id(context)
    if settlement_id:
        _register_knowledge_topic(
            topics,
            f"settlement.{settlement_id}",
            label=_world_settlement_label(world, settlement_id),
            category="settlement",
            source_type="world",
        )

    if world is not None:
        factions = sorted(list(getattr(world, "factions", []) or []), key=lambda item: str(getattr(item, "id", "") if not isinstance(item, dict) else item.get("id", "")))
        for faction in factions:
            faction_id = str(getattr(faction, "id", faction.get("id", "")) if isinstance(faction, dict) else getattr(faction, "id", "")).strip()
            if not faction_id:
                continue
            label = str(getattr(faction, "id", faction.get("id", "")) if isinstance(faction, dict) else getattr(faction, "id", "")).strip()
            _register_knowledge_topic(
                topics,
                f"faction.{faction_id}",
                label=_titleize_topic_fragment(label),
                category="faction",
                source_type="world",
            )

    active_quests = sorted(
        list((context.campaign_state or {}).get("active_quests", []) or []),
        key=lambda item: str(item.get("quest_id", item.get("id", ""))),
    )
    for quest in active_quests:
        quest_id = str(quest.get("quest_id", quest.get("id", ""))).strip()
        if not quest_id:
            continue
        _register_knowledge_topic(
            topics,
            f"quest.{quest_id}",
            label=str(quest.get("title", quest_id)).strip() or _titleize_topic_fragment(quest_id),
            category="quest",
            source_type="quest",
        )

    actors = runtime.get("actors") or {}
    if isinstance(actors, dict):
        for actor_id in sorted(actors):
            if actor_id == "player":
                continue
            actor = actors.get(actor_id)
            if actor is None:
                continue
            actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip()
            if actor_type not in {"npc", "creature"}:
                continue
            _register_knowledge_topic(
                topics,
                f"npc.{actor_id}",
                label=str(getattr(getattr(actor, "identity", None), "display_name", actor_id)).strip() or _titleize_topic_fragment(actor_id),
                category="npc",
                source_type="npc",
            )
            faction_id = str(getattr(getattr(actor, "identity", None), "faction_id", "")).strip()
            if faction_id:
                _register_knowledge_topic(
                    topics,
                    f"faction.{faction_id}",
                    label=_titleize_topic_fragment(faction_id),
                    category="faction",
                    source_type="npc",
                )

    rumor_network = getattr(context, "rumor_network", None)
    if rumor_network is not None:
        rumors = sorted(list(getattr(rumor_network, "get_all_active", lambda: [])() or []), key=lambda rumor: str(getattr(rumor, "rumor_id", "")))
        for rumor in rumors:
            rumor_id = str(getattr(rumor, "rumor_id", "")).strip()
            if not rumor_id:
                continue
            _register_knowledge_topic(
                topics,
                f"rumor.{rumor_id}",
                label=str(getattr(rumor, "fact", rumor_id)).strip() or _titleize_topic_fragment(rumor_id),
                category="rumor",
                source_type="rumor_network",
            )

    history_seed = getattr(context, "history_seed", None)
    if history_seed is not None:
        history_events = list(getattr(history_seed, "events", []) or [])
        history_events = sorted(
            history_events,
            key=lambda event: (int(getattr(event, "year", 0)), str(getattr(event, "name", ""))),
        )[-5:]
        for event in history_events:
            event_name = str(getattr(event, "name", "")).strip()
            if not event_name:
                continue
            _register_knowledge_topic(
                topics,
                f"fact.{_slugify_topic_fragment(event_name)}",
                label=event_name,
                category="fact",
                source_type="history",
            )

    npc_memory = getattr(context, "npc_memory", None)
    if npc_memory is not None:
        seen_fact_ids: set[str] = set()
        memories = getattr(npc_memory, "memories", {}) or {}
        for memory_id in sorted(memories):
            memory = memories.get(memory_id)
            if memory is None:
                continue
            known_facts = list(getattr(memory, "known_facts", []) or [])
            for fact in sorted({str(fact).strip() for fact in known_facts if str(fact).strip()}):
                fact_topic_id = f"fact.{_slugify_topic_fragment(fact)}"
                if fact_topic_id in seen_fact_ids:
                    continue
                seen_fact_ids.add(fact_topic_id)
                _register_knowledge_topic(
                    topics,
                    fact_topic_id,
                    label=fact,
                    category="fact",
                    source_type="npc_memory",
                )

    return topics


def build_runtime_knowledge_payload(context: "CampaignContext", runtime: dict[str, Any]) -> dict[str, Any]:
    knowledge_state = _knowledge_raw_state(runtime)
    bootstrap_topic_ids = _knowledge_bootstrap_topic_ids(context)
    discovered_topic_ids = _normalize_knowledge_ids(knowledge_state["discovered_topic_ids"] + bootstrap_topic_ids)
    pinned_topic_ids = _normalize_knowledge_ids(knowledge_state["pinned_topic_ids"])
    effective_discovered = set(discovered_topic_ids) | set(pinned_topic_ids)
    topics = _knowledge_topic_catalog(context, runtime)

    for topic_id in sorted(effective_discovered | set(pinned_topic_ids)):
        if topic_id in topics:
            continue
        topics[topic_id] = {
            "topic_id": topic_id,
            "label": _titleize_topic_fragment(topic_id),
            "category": _topic_category(topic_id),
            "source_types": ["persisted"],
        }

    topic_payloads: list[dict[str, Any]] = []
    for topic_id in sorted(topics):
        topic = topics[topic_id]
        topic_payloads.append(
            {
                "topic_id": topic_id,
                "label": str(topic.get("label", topic_id)).strip() or _titleize_topic_fragment(topic_id),
                "category": topic.get("category", _topic_category(topic_id)),
                "discovered": topic_id in effective_discovered,
                "pinned": topic_id in pinned_topic_ids,
                "source_types": sorted({str(item).strip() for item in list(topic.get("source_types", [])) if str(item).strip()}),
            }
        )

    return {
        "discovered_topic_ids": sorted(effective_discovered),
        "pinned_topic_ids": sorted(pinned_topic_ids),
        "topics": topic_payloads,
    }


def _sync_travel_runtime_state(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    travel = _travel_state(runtime)
    _persist_travel_state(runtime, travel)
    if travel is None:
        return
    status = str(travel.status or "").lower().strip()
    if status in {"", "idle", "cancelled"}:
        return
    world_state = runtime.get("world_state")
    if not isinstance(world_state, WorldState):
        return
    projection_region_id = _travel_projection_region_id(travel, str(context.region_snapshot.region_id))
    if projection_region_id:
        world_state.active_region_id = projection_region_id
    if status in {"arrived", "completed", "resolved"}:
        try:
            runtime["path_authority"] = complete_travel(travel, world_state)
        except Exception:
            runtime["path_authority"] = PathAuthorityState(
                active_region_id=projection_region_id,
                active_site_id=_travel_site_id_for_region(world_state, projection_region_id),
                local_map_id=f"region::{projection_region_id}",
                hydrated_from_region=projection_region_id in world_state.regions,
                travel_edge_count=sum(
                    1
                    for edge in world_state.travel_edges
                    if str(edge.source_region_id) == projection_region_id or str(edge.destination_region_id) == projection_region_id
                ),
                reindex_required=False,
                local_map_loaded=projection_region_id in world_state.regions,
                spawn_point=list(getattr(runtime.get("path_authority"), "spawn_point", [10, 7])),
            )
    else:
        runtime["path_authority"] = PathAuthorityState(
            active_region_id=projection_region_id,
            active_site_id=_travel_site_id_for_region(world_state, projection_region_id),
            local_map_id=f"region::{projection_region_id}",
            hydrated_from_region=projection_region_id in world_state.regions,
            travel_edge_count=sum(
                1
                for edge in world_state.travel_edges
                if str(edge.source_region_id) == projection_region_id or str(edge.destination_region_id) == projection_region_id
            ),
            reindex_required=False,
            local_map_loaded=projection_region_id in world_state.regions,
            spawn_point=list(getattr(runtime.get("path_authority"), "spawn_point", [10, 7])),
        )
    hydrated_map = hydrate_local_map(world_state, projection_region_id)
    runtime["local_map_state"] = LocalMapState.from_dict(hydrated_map.to_dict())

if TYPE_CHECKING:
    from .context import CampaignContext

_RUNTIME_MEDICAL_KEYS = (
    "wounds",
    "treatment_records",
    "medical_infections",
    "medical_recoveries",
    "permanent_consequences",
)
_RUNTIME_SOCIAL_KEYS = (
    "recruitable_companion",
    "relationship_score",
    "named_npc_id",
    "identity_source",
    "memory_id",
    "authored_role",
    "authored_location_id",
    "faction_alignment",
    "personality",
    "dialogue_snippets",
    "relationship_modifiers",
)
_RUNTIME_SPELL_KEYS = (
    "spellbooks",
    "spellbook",
    "known_spells",
    "spellcasting_mode",
    "casting_mode",
    "active_cast",
    "active_casting",
    "casting_attempt",
    "concentration",
    "concentration_state",
    "spell_points",
    "max_spell_points",
    "last_cast_tick",
)
_PARTY_CAPABLE_ACTOR_TYPES = {"npc", "creature"}
_SOCIAL_ACTOR_TYPES = {"npc"}
_NON_PARTY_ROLE_HINTS = {"cabinet", "cauldron", "table", "oven", "bench", "chair", "bed", "pew", "sack"}


def _clamp_relationship_score(value: Any) -> int:
    return max(-100, min(100, int(value or 0)))


def _is_party_capable_actor(actor: ActorRecord | None) -> bool:
    if actor is None:
        return False
    actor_id = str(getattr(getattr(actor, "identity", None), "actor_id", "")).strip()
    if not actor_id or actor_id == "player":
        return False
    actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip()
    if actor_type not in _PARTY_CAPABLE_ACTOR_TYPES:
        return False
    role_hint = str(actor.raw_payload.get("role", actor.raw_payload.get("template", ""))).lower().strip()
    if role_hint in _NON_PARTY_ROLE_HINTS:
        return False
    if any(
        bool(actor.raw_payload.get(key))
        for key in ("companion_roster", "party_member", "active_party_member", "reserve_party_member")
    ):
        return True
    return str(actor.raw_payload.get("source", "")).lower().strip() != "campaign_entity"


def _is_social_actor(actor: ActorRecord | None) -> bool:
    if actor is None:
        return False
    actor_id = str(getattr(getattr(actor, "identity", None), "actor_id", "")).strip()
    if not actor_id or actor_id == "player":
        return False
    actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower().strip()
    if actor_type not in _SOCIAL_ACTOR_TYPES:
        return False
    role_hint = str(actor.raw_payload.get("role", actor.raw_payload.get("template", actor.raw_payload.get("legacy_job", "")))).lower().strip()
    if role_hint in _NON_PARTY_ROLE_HINTS:
        return False
    return str(actor.raw_payload.get("legacy_disposition", actor.raw_payload.get("disposition", "friendly"))).lower().strip() != "hostile"


def _relationship_label_from_score(score: int) -> str:
    if score >= 60:
        return "ally"
    if score >= 30:
        return "friend"
    if score >= 10:
        return "acquaintance"
    if score > -20:
        return "stranger"
    if score > -50:
        return "unfriendly"
    return "enemy"


def _optional_identity(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


def _normalize_spellbooks_payload(raw_spellbooks: Any) -> dict[str, dict[str, Any]]:
    from engine.kernel.spells import Spellbook

    if not isinstance(raw_spellbooks, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for book_key, book_value in sorted(raw_spellbooks.items(), key=lambda item: str(item[0])):
        key = str(book_key).strip()
        if not key:
            continue
        if isinstance(book_value, Spellbook):
            normalized[key] = book_value.to_dict()
            continue
        if isinstance(book_value, dict):
            try:
                normalized[key] = Spellbook.from_dict(book_value).to_dict()
            except Exception:
                normalized[key] = copy.deepcopy(book_value)
    return normalized


def _normalize_casting_attempt_payload(raw_attempt: Any) -> dict[str, Any] | None:
    from engine.kernel.spells import CastingAttempt

    if isinstance(raw_attempt, CastingAttempt):
        return raw_attempt.to_dict()
    if isinstance(raw_attempt, dict):
        try:
            return CastingAttempt.from_dict(raw_attempt).to_dict()
        except Exception:
            return copy.deepcopy(raw_attempt)
    return None


def _active_spellbook_payload(raw_payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    spellbooks = _normalize_spellbooks_payload(raw_payload.get("spellbooks", {}))
    if spellbooks:
        preferred_key = str(
            raw_payload.get("spellcasting_mode")
            or raw_payload.get("casting_mode")
            or next(iter(spellbooks))
        ).strip()
        if preferred_key in spellbooks:
            return preferred_key, spellbooks[preferred_key]
        first_key = next(iter(spellbooks))
        return first_key, spellbooks[first_key]
    spellbook = raw_payload.get("spellbook")
    if isinstance(spellbook, dict):
        normalized = _normalize_spellbooks_payload({"primary": spellbook})
        if normalized:
            return "primary", normalized["primary"]
    return None, None


def build_actor_spell_payload(actor: ActorRecord | None) -> dict[str, Any]:
    if actor is None:
        return {
            "spellcasting_mode": "none",
            "spellbooks": {},
            "known_spells": {},
            "slot_state": {"by_level": {}, "books": {}},
            "spell_points": {"current": 0, "max": 0},
            "active_cast": None,
            "concentration": None,
        }
    raw_payload = actor.raw_payload if isinstance(actor.raw_payload, dict) else {}
    spellbooks = _normalize_spellbooks_payload(raw_payload.get("spellbooks", {}))
    active_book_key, active_book = _active_spellbook_payload(raw_payload)
    if active_book_key and active_book is not None:
        spellbooks.setdefault(active_book_key, copy.deepcopy(active_book))
    known_spells: dict[str, list[str]] = {}
    slot_levels: set[int] = set()
    books_payload: dict[str, Any] = {}
    for book_key, book in spellbooks.items():
        known = {
            str(level): sorted({str(spell_id) for spell_id in spell_ids if str(spell_id).strip()})
            for level, spell_ids in sorted(dict(book.get("known_spells", {})).items(), key=lambda item: int(item[0]))
        }
        slots_payload: dict[str, list[dict[str, Any]]] = {}
        slot_summary: dict[str, dict[str, int]] = {}
        max_slots_raw = dict(book.get("max_slots", {}))
        for level, slots in sorted(dict(book.get("slots", {})).items(), key=lambda item: int(item[0])):
            level_key = str(level)
            level_int = int(level)
            slot_levels.add(level_int)
            normalized_slots: list[dict[str, Any]] = []
            memorized_count = 0
            expended_count = 0
            available_count = 0
            for slot in list(slots or []):
                slot_dict = dict(slot) if isinstance(slot, dict) else None
                if slot_dict is None:
                    continue
                normalized_slot = {
                    "spell_level": int(slot_dict.get("spell_level", level_int) or level_int),
                    "spell_id": str(slot_dict.get("spell_id")) if slot_dict.get("spell_id") is not None else None,
                    "memorized": bool(slot_dict.get("memorized", False)),
                    "expended": bool(slot_dict.get("expended", False)),
                }
                if normalized_slot["memorized"]:
                    memorized_count += 1
                if normalized_slot["expended"]:
                    expended_count += 1
                if normalized_slot["memorized"] and not normalized_slot["expended"]:
                    available_count += 1
                normalized_slots.append(normalized_slot)
            slots_payload[level_key] = normalized_slots
            slot_summary[level_key] = {
                "total": len(normalized_slots),
                "memorized": memorized_count,
                "expended": expended_count,
                "available": available_count,
                "max": int(max_slots_raw.get(level_int, max_slots_raw.get(level_key, len(normalized_slots))) or 0),
            }
        books_payload[book_key] = {
            "actor_id": str(book.get("actor_id", actor.identity.actor_id)),
            "spell_type": str(book.get("spell_type", book_key)),
            "known_spells": known,
            "slots": slots_payload,
            "max_slots": {str(level): int(count) for level, count in sorted(max_slots_raw.items(), key=lambda item: int(item[0]))},
            "slot_state": slot_summary,
        }
        for level_key, spells in known.items():
            bucket = known_spells.setdefault(level_key, [])
            for spell_id in spells:
                if spell_id not in bucket:
                    bucket.append(spell_id)
    aggregate_slot_state: dict[str, dict[str, int]] = {}
    for level in sorted(slot_levels):
        level_key = str(level)
        total = memorized = expended = available = max_slots = 0
        for book in books_payload.values():
            summary = dict(book.get("slot_state", {})).get(level_key, {})
            total += int(summary.get("total", 0))
            memorized += int(summary.get("memorized", 0))
            expended += int(summary.get("expended", 0))
            available += int(summary.get("available", 0))
            max_slots += int(summary.get("max", 0))
        aggregate_slot_state[level_key] = {
            "total": total,
            "memorized": memorized,
            "expended": expended,
            "available": available,
            "max": max_slots,
        }
    active_cast = _normalize_casting_attempt_payload(
        raw_payload.get("active_cast")
        or raw_payload.get("active_casting")
        or raw_payload.get("casting_attempt")
    )
    concentration = raw_payload.get("concentration")
    if concentration is None:
        concentration = raw_payload.get("concentration_state")
    concentration_payload = copy.deepcopy(concentration) if isinstance(concentration, dict) else concentration
    spellcasting_mode = str(
        raw_payload.get("spellcasting_mode")
        or raw_payload.get("casting_mode")
        or active_book_key
        or ("spell_points" if int(getattr(actor, "max_spell_points", 0) or 0) > 0 else "none")
    )
    return {
        "spellcasting_mode": spellcasting_mode,
        "active_spellbook": active_book_key,
        "spellbooks": books_payload,
        "known_spells": known_spells,
        "slot_state": {
            "by_level": aggregate_slot_state,
            "books": {key: copy.deepcopy(value.get("slot_state", {})) for key, value in books_payload.items()},
        },
        "spell_points": {
            "current": int(getattr(actor, "spell_points", 0) or 0),
            "max": int(getattr(actor, "max_spell_points", 0) or 0),
        },
        "active_cast": active_cast,
        "concentration": concentration_payload,
        "last_cast_tick": int(raw_payload.get("last_cast_tick", -1) or -1),
    }


def _equipment_canonical_slot(legacy_slot: str) -> str:
    normalized = str(legacy_slot or "").strip().lower()
    for canonical_slot, aliases in _EQUIPMENT_CANONICAL_SLOT_ALIASES.items():
        if normalized == canonical_slot or normalized in aliases:
            return canonical_slot
    return normalized or "unknown"


def _equipment_canonical_slot_index(canonical_slot: str) -> int:
    try:
        return _EQUIPMENT_CANONICAL_SLOT_ORDER.index(canonical_slot)
    except ValueError:
        return len(_EQUIPMENT_CANONICAL_SLOT_ORDER)


def _normalized_equipment_lookup_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _armor_piece_for_item(item_payload: dict[str, Any], legacy_slot: str, canonical_slot: str) -> Any:
    normalized_lookup = {_normalized_equipment_lookup_key(key): piece for key, piece in ARMOR_COVERAGE.items()}
    for candidate in (
        item_payload.get("armor_piece"),
        item_payload.get("armor_profile"),
        item_payload.get("item_def_id"),
        item_payload.get("id"),
        item_payload.get("name"),
        legacy_slot,
        canonical_slot,
    ):
        piece = normalized_lookup.get(_normalized_equipment_lookup_key(candidate))
        if piece is not None:
            return piece
    return None


def _equipment_coverage_zones(item_payload: dict[str, Any], legacy_slot: str, canonical_slot: str) -> list[str]:
    explicit = item_payload.get("coverage") or item_payload.get("covers") or item_payload.get("coverage_zones") or []
    zones = sorted({str(zone).strip() for zone in list(explicit or []) if str(zone).strip()})
    if zones:
        return zones
    piece = _armor_piece_for_item(item_payload, legacy_slot, canonical_slot)
    if piece is not None:
        return sorted({str(zone).strip() for zone in getattr(piece, "covers", ()) if str(zone).strip()})
    fallback_by_slot = {
        "head": ["head"],
        "body": ["chest", "torso"],
        "shield": ["left_arm"],
        "hands": ["left_arm", "right_arm"],
        "feet": ["left_leg", "right_leg"],
    }
    return list(fallback_by_slot.get(canonical_slot, []))


def _equipment_armor_weight_class(item_payload: dict[str, Any], legacy_slot: str, canonical_slot: str) -> str:
    explicit = str(
        item_payload.get("armor_weight_class")
        or item_payload.get("weight_class")
        or item_payload.get("armor_class")
        or ""
    ).strip().lower()
    if explicit in {"none", "light", "medium", "heavy"}:
        return explicit
    item_type = str(item_payload.get("type", "")).strip().lower()
    if canonical_slot not in {"body", "shield", "hands", "feet", "head", "cloak", "underlayer"} and item_type not in {"armor", "shield"}:
        return "none"
    material = str(item_payload.get("material") or item_payload.get("material_id") or "").strip().lower()
    item_name = " ".join(
        str(part).strip().lower()
        for part in (
            item_payload.get("item_def_id"),
            item_payload.get("id"),
            item_payload.get("name"),
            legacy_slot,
        )
        if str(part or "").strip()
    )
    if canonical_slot == "shield":
        return "medium"
    if any(token in item_name for token in ("plate", "breastplate", "full_plate")) or material in {"steel"}:
        return "heavy"
    if any(token in item_name for token in ("chain", "mail", "greaves")) or material in {"iron"}:
        return "medium"
    if any(token in item_name for token in ("leather", "hide", "cloak", "robe", "cap", "gloves", "boots")) or material in {"cloth", "linen", "leather", "hide", "silk"}:
        return "light"
    return "none"


def _equipment_modifier_int(item_payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key not in item_payload:
            continue
        try:
            return int(item_payload.get(key, 0) or 0)
        except Exception:
            return 0
    return None


def _equipment_default_modifiers(canonical_slot: str, armor_weight_class: str) -> tuple[int, int, int]:
    if canonical_slot == "shield":
        return (1, 1, 0)
    if armor_weight_class == "light":
        return (0, 1, 0)
    if armor_weight_class == "medium":
        return (1, 2, 1)
    if armor_weight_class == "heavy":
        return (2, 3, 2)
    return (0, 0, 0)


def _equipment_attunement_required(item_payload: dict[str, Any]) -> bool:
    if any(bool(item_payload.get(key, False)) for key in ("attunement_required", "requires_attunement", "requires_attune")):
        return True
    tags = {str(tag).strip().lower() for tag in list(item_payload.get("tags", []) or []) if str(tag).strip()}
    return "attunement_required" in tags or "requires_attunement" in tags


def _equipment_item_is_attuned(item_payload: dict[str, Any]) -> bool:
    return any(bool(item_payload.get(key, False)) for key in ("attuned", "is_attuned"))


def _equipment_item_payload(stack: Any, legacy_slot: str) -> dict[str, Any]:
    item_payload = copy.deepcopy(stack.to_dict() if hasattr(stack, "to_dict") else dict(stack))
    source_payload = dict(item_payload.get("payload", {}))
    source_payload.setdefault("item_def_id", item_payload.get("item_def_id"))
    source_payload.setdefault("id", source_payload.get("id", item_payload.get("item_def_id")))
    canonical_slot = _equipment_canonical_slot(legacy_slot)
    coverage_zones = _equipment_coverage_zones(source_payload, legacy_slot, canonical_slot)
    armor_weight_class = _equipment_armor_weight_class(source_payload, legacy_slot, canonical_slot)
    movement_penalty = _equipment_modifier_int(source_payload, "movement_penalty")
    stealth_noise = _equipment_modifier_int(source_payload, "stealth_noise")
    spell_interference = _equipment_modifier_int(source_payload, "spell_interference")
    if movement_penalty is None or stealth_noise is None or spell_interference is None:
        defaults = _equipment_default_modifiers(canonical_slot, armor_weight_class)
        movement_penalty = defaults[0] if movement_penalty is None else movement_penalty
        stealth_noise = defaults[1] if stealth_noise is None else stealth_noise
        spell_interference = defaults[2] if spell_interference is None else spell_interference
    item_payload["canonical_slot"] = canonical_slot
    if canonical_slot != str(legacy_slot or "").strip().lower():
        item_payload["legacy_slot"] = str(legacy_slot)
    item_payload["coverage_zones"] = coverage_zones
    item_payload["armor_weight_class"] = armor_weight_class
    item_payload["movement_penalty"] = int(movement_penalty)
    item_payload["stealth_noise"] = int(stealth_noise)
    item_payload["spell_interference"] = int(spell_interference)
    item_payload["attunement_required"] = _equipment_attunement_required(source_payload)
    return item_payload


def build_actor_equipment_payload(actor: ActorRecord | None) -> dict[str, Any]:
    base_slots = {canonical_slot: None for canonical_slot in _EQUIPMENT_CANONICAL_SLOT_ORDER}
    if actor is None or getattr(actor, "equipment", None) is None:
        return {
            "equipment": {"slots": {}},
            "equipment_topology": {
                "slots": base_slots,
                "legacy_slot_aliases": {key: list(value) for key, value in _EQUIPMENT_CANONICAL_SLOT_ALIASES.items()},
                "coverage_summary": {},
            },
            "equipment_modifiers": {
                "total_movement_penalty": 0,
                "total_stealth_noise": 0,
                "total_spell_interference": 0,
            },
            "attunement": {
                "slot_count": 3,
                "attuned_item_ids": [],
                "available_slots": 3,
            },
        }

    raw_slots = dict(getattr(actor.equipment, "slots", {}) or {})
    equipment_slots_payload: dict[str, list[dict[str, Any]]] = {}
    topology_slots = dict(base_slots)
    coverage_summary: dict[str, list[str]] = {}
    attuned_item_ids: list[str] = []
    total_movement_penalty = 0
    total_stealth_noise = 0
    total_spell_interference = 0

    sorted_slots = sorted(
        raw_slots.items(),
        key=lambda item: (
            _equipment_canonical_slot_index(_equipment_canonical_slot(item[0])),
            str(item[0]),
        ),
    )
    for legacy_slot, stacks in sorted_slots:
        enriched_items = [_equipment_item_payload(stack, str(legacy_slot)) for stack in list(stacks or [])]
        if not enriched_items:
            continue
        equipment_slots_payload[str(legacy_slot)] = enriched_items
        for item in enriched_items:
            canonical_slot = str(item.get("canonical_slot", _equipment_canonical_slot(legacy_slot)))
            if canonical_slot not in topology_slots:
                topology_slots[canonical_slot] = None
            if topology_slots[canonical_slot] is None:
                topology_slots[canonical_slot] = copy.deepcopy(item)
            total_movement_penalty += int(item.get("movement_penalty", 0) or 0)
            total_stealth_noise += int(item.get("stealth_noise", 0) or 0)
            total_spell_interference += int(item.get("spell_interference", 0) or 0)
            instance_id = str(item.get("instance_id", item.get("item_def_id", ""))).strip()
            if bool(item.get("attunement_required", False)) and _equipment_item_is_attuned(dict(item.get("payload", {}))):
                if instance_id and instance_id not in attuned_item_ids:
                    attuned_item_ids.append(instance_id)
            for zone in list(item.get("coverage_zones", []) or []):
                zone_key = str(zone).strip()
                if not zone_key:
                    continue
                coverage_summary.setdefault(zone_key, [])
                if instance_id and instance_id not in coverage_summary[zone_key]:
                    coverage_summary[zone_key].append(instance_id)

    for zone in sorted(coverage_summary):
        coverage_summary[zone] = sorted(coverage_summary[zone])

    return {
        "equipment": {"slots": equipment_slots_payload},
        "equipment_topology": {
            "slots": topology_slots,
            "legacy_slot_aliases": {key: list(value) for key, value in _EQUIPMENT_CANONICAL_SLOT_ALIASES.items()},
            "coverage_summary": coverage_summary,
        },
        "equipment_modifiers": {
            "total_movement_penalty": total_movement_penalty,
            "total_stealth_noise": total_stealth_noise,
            "total_spell_interference": total_spell_interference,
        },
        "attunement": {
            "slot_count": 3,
            "attuned_item_ids": sorted(attuned_item_ids),
            "available_slots": max(0, 3 - len(attuned_item_ids)),
        },
    }


def build_travel_state_payload(
    travel_state: TravelState | dict[str, Any] | None,
    *,
    world: Any = None,
) -> dict[str, Any] | None:
    if isinstance(travel_state, TravelState):
        payload = travel_state.to_dict()
    elif isinstance(travel_state, dict):
        payload = dict(travel_state)
    else:
        return None

    destination_region_id = str(payload.get("destination_region_id", "")).strip()
    destination_settlement_id = str(payload.get("destination_settlement_id", "")).strip()
    destination_name = ""
    route_id = str(payload.get("edge_id", payload.get("route_id", ""))).strip()
    if world is not None:
        settlement_nodes = list(getattr(world, "settlement_nodes", []) or [])
        if destination_settlement_id:
            node = next((item for item in settlement_nodes if str(item.get("id", "")) == destination_settlement_id), None)
            if node is not None:
                destination_name = str(node.get("name", "")).strip()
                destination_region_id = destination_region_id or str(node.get("region_id", "")).strip()
        if not destination_name and destination_region_id:
            node = next((item for item in settlement_nodes if str(item.get("region_id", "")) == destination_region_id), None)
            if node is not None:
                destination_name = str(node.get("name", "")).strip()
                destination_settlement_id = destination_settlement_id or str(node.get("id", "")).strip()
        if not route_id:
            edges = list(getattr(world, "travel_edges", []) or [])
            edge = next(
                (
                    item
                    for item in edges
                    if (
                        str(item.get("from_region_id", "")) == str(payload.get("origin_region_id", ""))
                        and str(item.get("to_region_id", "")) == destination_region_id
                    )
                    or (
                        str(item.get("to_region_id", "")) == str(payload.get("origin_region_id", ""))
                        and str(item.get("from_region_id", "")) == destination_region_id
                    )
                ),
                None,
            )
            if edge is not None:
                route_id = str(edge.get("id", "")).strip()

    paused = bool(payload.get("paused_for_encounter", False))
    resolved = bool(payload.get("encounter_resolved", False))
    remaining = int(payload.get("travel_hours_remaining", 0) or 0)
    return {
        "status": str(payload.get("status", "idle")),
        "route_id": route_id,
        "origin_region_id": str(payload.get("origin_region_id", "")).strip(),
        "destination_region_id": destination_region_id,
        "destination_settlement_id": destination_settlement_id,
        "destination_name": destination_name,
        "travel_hours_total": int(payload.get("travel_hours_total", 0) or 0),
        "travel_hours_remaining": remaining,
        "danger_level": int(payload.get("danger_level", 0) or 0),
        "encounter_triggered": bool(payload.get("encounter_triggered", False)),
        "paused_for_encounter": paused,
        "encounter_resolved": resolved,
        "can_advance": remaining > 0 and (not paused or resolved),
        "requires_resolution": paused and not resolved,
    }


def _normalize_actor_spell_state(actor: ActorRecord) -> None:
    spellbooks = _normalize_spellbooks_payload(actor.raw_payload.get("spellbooks", {}))
    if spellbooks:
        actor.raw_payload["spellbooks"] = spellbooks
    active_cast = _normalize_casting_attempt_payload(
        actor.raw_payload.get("active_cast")
        or actor.raw_payload.get("active_casting")
        or actor.raw_payload.get("casting_attempt")
    )
    if active_cast is not None:
        if "active_cast" in actor.raw_payload or "active_casting" not in actor.raw_payload:
            actor.raw_payload["active_cast"] = active_cast
        if "active_casting" in actor.raw_payload:
            actor.raw_payload["active_casting"] = active_cast
        if "casting_attempt" in actor.raw_payload:
            actor.raw_payload["casting_attempt"] = active_cast
    actor.raw_payload["spell_points"] = int(actor.raw_payload.get("spell_points", getattr(actor, "spell_points", 0)) or 0)
    actor.raw_payload["max_spell_points"] = int(actor.raw_payload.get("max_spell_points", getattr(actor, "max_spell_points", 0)) or 0)


def _active_combat_payload(runtime: dict[str, Any]) -> dict[str, Any] | None:
    game_state = runtime.get("game_state")
    raw_payload = getattr(game_state, "raw_payload", {}) if game_state is not None else {}
    combat = raw_payload.get("combat")
    if not isinstance(combat, dict) or not combat.get("combatants"):
        return None
    if str(combat.get("phase", "active")).lower().strip() == "resolved":
        return None
    return combat


def _coerce_combat_turn_resources(payload: Any) -> dict[str, int | bool]:
    if not isinstance(payload, dict):
        return {
            "action": True,
            "bonus_action": True,
            "reaction": True,
            "movement": 0,
            "max_movement": 0,
        }
    return {
        "action": bool(payload.get("action", True)),
        "bonus_action": bool(payload.get("bonus_action", True)),
        "reaction": bool(payload.get("reaction", True)),
        "movement": int(payload.get("movement", 0) or 0),
        "max_movement": int(payload.get("max_movement", payload.get("movement", 0)) or 0),
    }


def _sync_combat_runtime_state(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    combat = _active_combat_payload(runtime)
    if combat is None:
        return
    if context.dm_context is not None:
        context.dm_context.scene_type_name = "combat"
    actors = runtime.get("actors") or {}
    for entry in combat.get("combatants", []):
        actor_id = str(entry.get("actor_id", "")).strip()
        if not actor_id:
            continue
        actor = actors.get(actor_id)
        if actor is None:
            continue
        actor.turn_resources = _coerce_combat_turn_resources(entry.get("turn_resources", {}))
    _annotate_live_combat_payload(context, runtime)


def _combat_blocking_state(context: "CampaignContext", actor_id: str) -> bool | None:
    record = context.entities.get(actor_id) if isinstance(getattr(context, "entities", None), dict) else None
    if not isinstance(record, dict):
        return None
    blocking = record.get("blocking")
    if blocking is not None:
        return bool(blocking)
    entity_ref = record.get("entity_ref")
    if entity_ref is None:
        return None
    return bool(getattr(entity_ref, "blocking", True))


def _combat_move_options(context: "CampaignContext", actor: ActorRecord | None) -> list[dict[str, Any]]:
    from engine.map import TileType

    spatial_index = getattr(context, "spatial_index", None)
    map_data = getattr(context, "map_data", None)
    if actor is None or spatial_index is None:
        return []
    position = getattr(actor, "position", None)
    if position is None:
        return []
    current_x = int(getattr(position, "x", 0))
    current_y = int(getattr(position, "y", 0))
    directions = {
        "north": (0, -1),
        "south": (0, 1),
        "west": (-1, 0),
        "east": (1, 0),
    }
    options: list[dict[str, Any]] = []
    for direction, (dx, dy) in directions.items():
        x = current_x + dx
        y = current_y + dy
        available = True
        blocked_reason: str | None = None
        if map_data is not None:
            width = int(getattr(map_data, "width", 0))
            height = int(getattr(map_data, "height", 0))
            if x < 0 or y < 0 or x >= width or y >= height:
                available = False
                blocked_reason = "out_of_bounds"
            else:
                tile = map_data.tiles[y][x]
                if tile in {TileType.WALL, TileType.WATER, TileType.TREE}:
                    available = False
                    blocked_reason = "blocked_terrain"
        if available and spatial_index.blocking_at(x, y):
            occupant = spatial_index.at(x, y)
            occupant_ids = {str(getattr(item, "id", "")).strip() for item in list(occupant or [])}
            if actor.identity.actor_id not in occupant_ids:
                available = False
                blocked_reason = "occupied"
        options.append(
            {
                "direction": direction,
                "x": x,
                "y": y,
                "position": [x, y],
                "available": available,
                "blocked_reason": blocked_reason,
            }
        )
    return options


def _annotate_live_combat_payload(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    combat = _active_combat_payload(runtime)
    if combat is None:
        return
    actors = runtime.get("actors") or {}
    combatants = [entry for entry in list(combat.get("combatants", [])) if isinstance(entry, dict)]
    current_turn_index = int(combat.get("current_turn_index", 0) or 0)
    if combatants and 0 <= current_turn_index < len(combatants):
        combat["turn_actor_id"] = str(combatants[current_turn_index].get("actor_id", "")).strip()
    targets: list[dict[str, Any]] = []
    for entry in combatants:
        actor_id = str(entry.get("actor_id", "")).strip()
        actor = actors.get(actor_id)
        if actor is None:
            continue
        position = getattr(actor, "position", None)
        if position is not None:
            entry["position"] = [int(getattr(position, "x", 0)), int(getattr(position, "y", 0))]
            entry["projected_position"] = list(entry["position"])
        blocking = _combat_blocking_state(context, actor_id)
        if blocking is not None:
            entry["blocking"] = blocking
        if not bool(entry.get("is_player", False)):
            target_payload = {
                "actor_id": actor_id,
                "name": actor.name,
                "alive": bool(actor.alive),
                "hp": int(actor.stats.get("hp", 0)),
                "max_hp": int(actor.stats.get("max_hp", 1)),
            }
            if "position" in entry:
                target_payload["position"] = list(entry["position"])
            targets.append(target_payload)
    combat["combatants"] = combatants
    combat["targets"] = targets
    active_actor_id = str(combat.get("turn_actor_id", "")).strip()
    combat["move_options"] = _combat_move_options(context, actors.get(active_actor_id)) if active_actor_id else []


def ensure_kernel_runtime(context: "CampaignContext", *, rebuild_projection: bool = False) -> dict[str, Any]:
    if context.kernel_runtime and not rebuild_projection:
        _sync_runtime_from_context(context, context.kernel_runtime)
        context.player = context.kernel_runtime.get("actors", {}).get("player", context.player)
        _sync_social_identity(context, context.kernel_runtime)
        sync_combat_projection_state(context)
        return context.kernel_runtime
    meta = dict(context.campaign_state.get("campaign") or {})
    existing_runtime = context.kernel_runtime or {}
    if rebuild_projection and existing_runtime:
        existing_runtime_travel_payload = _normalize_travel_state_payload(existing_runtime.get("travel_state"))
        existing_travel = (
            TravelState.from_dict(existing_runtime_travel_payload)
            if existing_runtime_travel_payload is not None
            else _travel_state(existing_runtime)
        )
        existing_game_state = existing_runtime.get("game_state")
        game_state_meta = dict(meta.get("game_state") or {})
        raw_payload_meta = dict(game_state_meta.get("raw_payload") or {})
        if existing_game_state is not None and isinstance(getattr(existing_game_state, "raw_payload", None), dict):
            raw_payload_meta.update(copy.deepcopy(existing_game_state.raw_payload))
        if existing_travel is not None:
            status = str(existing_travel.status or "").lower().strip()
            if status in {"", "idle", "cancelled"}:
                raw_payload_meta.pop("travel_state", None)
            else:
                raw_payload_meta["travel_state"] = existing_travel.to_dict()
            meta["travel_state"] = existing_travel.to_dict()
        if raw_payload_meta:
            normalized_knowledge = _normalize_knowledge_state_payload(raw_payload_meta.get("knowledge"))
            if normalized_knowledge is None:
                raw_payload_meta.pop("knowledge", None)
            else:
                raw_payload_meta["knowledge"] = normalized_knowledge
            game_state_meta["raw_payload"] = raw_payload_meta
            meta["game_state"] = game_state_meta
        for key in ("world_state", "path_authority", "local_map_state"):
            value = existing_runtime.get(key)
            if value is not None and hasattr(value, "to_dict"):
                meta[key] = value.to_dict()
    runtime = {
        "world_state": saved_or(
            meta.get("world_state"),
            WorldState,
            lambda: WorldState.from_dict(build_canonical_world_state(context.world)),
        ),
        "game_state": saved_or(
            meta.get("game_state"),
            GameState,
            lambda: build_canonical_game_state(
                context,
                campaign_id=context.campaign_id,
                seed=context.seed,
                active_region_id=context.region_snapshot.region_id,
                active_site_id=active_site_id(context),
            ),
        ),
        "actors": _load_actors(meta.get("actors"), context),
        "jobs": saved_list_or(meta.get("jobs"), JobRecord, lambda: []),
        "reactions": saved_list_or(meta.get("reactions"), ReactionDef, lambda: []),
        "worksites": saved_list_or(meta.get("worksites"), WorksiteRecord, lambda: []),
        "colony_pressure": saved_or(
            meta.get("colony_pressure"),
            type(colony_pressure_from_settlement(context.settlement_state)),
            lambda: colony_pressure_from_settlement(context.settlement_state),
        ),
        "production_ledger": saved_or(
            meta.get("production_ledger"),
            ProductionLedger,
            lambda: production_ledger_from_settlement(context.settlement_state),
        ),
        "path_authority": saved_or(
            meta.get("path_authority"),
            PathAuthorityState,
            lambda: path_authority_from_world(context.world, context.region_snapshot),
        ),
        "local_map_state": saved_or(
            meta.get("local_map_state"),
            type(local_map_state_from_region(context.region_snapshot)),
            lambda: local_map_state_from_region(context.region_snapshot),
        ),
        "travel_state": saved_or(
            meta.get("travel_state"),
            TravelState,
            lambda: TravelState(status="idle"),
        ),
        "military": saved_or(
            meta.get("military"),
            MilitaryState,
            lambda: military_state_from_settlement(context.settlement_state),
        ),
        "systems": load_systems(meta.get("systems"), context),
        "stores": load_stores(meta.get("stores"), context),
    }
    context.kernel_runtime = runtime
    rebase_projection_slices(context, runtime, force=True)
    _persist_knowledge_state(runtime, _knowledge_state(runtime))
    _sync_travel_runtime_state(context, runtime)
    _sync_combat_runtime_state(context, runtime)
    _sync_runtime_from_context(context, runtime)
    context.player = runtime.get("actors", {}).get("player", context.player)
    _sync_social_identity(context, runtime)
    sync_combat_projection_state(context)
    return runtime


def serialize_kernel_runtime(context: "CampaignContext") -> dict[str, Any]:
    runtime = ensure_kernel_runtime(context)
    _persist_knowledge_state(runtime, _knowledge_state(runtime))
    return {
        "world_state": runtime["world_state"].to_dict(),
        "game_state": runtime["game_state"].to_dict(),
        "actors": [actor.to_dict() for actor in runtime["actors"].values()],
        "jobs": [job.to_dict() for job in runtime["jobs"]],
        "reactions": [reaction.to_dict() for reaction in runtime["reactions"]],
        "worksites": [worksite.to_dict() for worksite in runtime["worksites"]],
        "colony_pressure": runtime["colony_pressure"].to_dict(),
        "production_ledger": runtime["production_ledger"].to_dict(),
        "path_authority": runtime["path_authority"].to_dict(),
        "local_map_state": runtime["local_map_state"].to_dict(),
        "travel_state": runtime["travel_state"].to_dict(),
        "military": runtime["military"].to_dict(),
        "systems": {
            "syndrome_registry": [item.to_dict() for item in runtime["systems"]["syndrome_registry"]],
            "power_network": runtime["systems"]["power_network"].to_dict(),
            "traps": [item.to_dict() for item in runtime["systems"]["traps"]],
            "fluid_state": runtime["systems"]["fluid_state"].to_dict(),
            "temperature_state": runtime["systems"]["temperature_state"].to_dict(),
            "strange_mood_incident": runtime["systems"]["strange_mood_incident"].to_dict()
            if runtime["systems"]["strange_mood_incident"] is not None
            else None,
        },
        "stores": [store.to_dict() for store in runtime["stores"]],
    }


def advance_kernel_runtime(
    context: "CampaignContext",
    *,
    hours_advanced: int,
    command_type: str,
    command_text: str,
) -> list[dict[str, Any]]:
    runtime = ensure_kernel_runtime(context, rebuild_projection=command_type == "travel")
    merge_projection_changes_from_settlement(context, runtime)
    _sync_runtime_from_context(context, runtime)
    game_state: GameState = runtime["game_state"]
    actors = list(runtime["actors"].values())
    step_count = max(0, int(hours_advanced))
    seed = stable_seed(
        context.seed,
        context.campaign_id,
        command_type,
        command_text,
        context.world.simulation_snapshot.current_hour,
    )
    events: list[dict[str, Any]] = []
    if step_count > 0:
        game_state.world_time.advance(step_count * max(1, int(game_state.world_time.ticks_per_hour)))
    for step in range(step_count):
        current_tick = int(game_state.world_time.game_tick) + step
        for actor in actors:
            events.extend(effect_events(actor, current_tick))
        infections = spread_contagion(actors, {})
        events.extend(
            {
                "event_type": "syndrome_spread",
                "summary": f"{source_id} infected {target_id}.",
                "source_id": source_id,
                "target_id": target_id,
            }
            for source_id, target_id in infections
        )
        events.extend(_medical_tick_events(actors, current_tick))
        events.extend(job_and_farm_events(context, runtime, seed + step))
        events.extend(macro_society_events(context, runtime))
        events.extend(systems_events(context, runtime, seed + step))
    # ── Post-tick: promote conditions, check level-up ──────────
    for actor in actors:
        # Promote raw string conditions to ConditionRecord objects.
        _ = actor.condition_names  # noqa: property triggers in-place promotion
    player = runtime["actors"].get("player")
    if player is not None:
        events.extend(_check_level_up(player))
    refresh_runtime_views(context, runtime)
    context.player = runtime.get("actors", {}).get("player", context.player)
    return events


def _check_level_up(player: ActorRecord) -> list[dict[str, Any]]:
    """Advance the shared progression adapter for an ActorRecord.

    Campaign runtime still uses a shared XP table from progression.json
    instead of per-class AD&D tables. This helper formalizes that as a
    narrow adapter over kernel/progression.py so level-up behavior stays
    data-driven and testable without reviving legacy progression code.
    """
    from engine.kernel.progression import execute_level_up

    events: list[dict[str, Any]] = []
    progression_state, primary_class_id, class_defs = _progression_adapter(player)
    if progression_state is None or not class_defs:
        return events

    end_mod = (int(player.stats.get("END", 10)) - 10) // 2
    preferred_class = primary_class_id

    while True:
        class_id = _next_level_up_class_id(progression_state, class_defs, preferred_class)
        if class_id is None:
            break
        class_def = class_defs[class_id]
        hit_die_roll = _deterministic_hit_die_roll(player, class_id)
        result = execute_level_up(
            progression_state,
            class_id,
            class_def,
            hit_die_roll=hit_die_roll,
            end_modifier=end_mod,
            class_defs=class_defs,
        )
        _apply_progression_state(player, progression_state, result.hp_gained)
        events.append({
            "event_type": "level_up",
            "summary": (
                f"{player.identity.display_name} reached {class_def.label} {result.new_level} "
                f"(total level {progression_state.level})! "
                f"(+{result.hp_gained} HP, max HP now {int(player.stats.get('max_hp', 1))})"
            ),
            "actor_id": player.identity.actor_id,
            "new_level": progression_state.level,
            "leveled_class": class_id,
            "new_class_level": result.new_level,
            "hp_gained": result.hp_gained,
            "new_max_hp": int(player.stats.get("max_hp", 1)),
        })
        preferred_class = class_id

    return events


def _progression_adapter(player: ActorRecord):
    from engine.data.classes import get_class
    from engine.data.runtime import get_xp_thresholds
    from engine.kernel.progression import ClassDef, ProgressionState

    primary_class_id = str(player.raw_payload.get("class_name", "warrior")).strip().lower() or "warrior"
    thresholds = get_xp_thresholds()
    if not thresholds:
        return None, None, None

    raw_progression = player.raw_payload.get("progression")
    if isinstance(raw_progression, dict):
        try:
            progression_state = ProgressionState.from_dict(raw_progression)
        except Exception:  # pragma: no cover - malformed saves should fall back safely
            progression_state = ProgressionState(actor_id=player.identity.actor_id)
    else:
        progression_state = ProgressionState(actor_id=player.identity.actor_id)
    progression_state.actor_id = player.identity.actor_id
    progression_state.xp = int(player.raw_payload.get("xp", progression_state.xp))
    progression_state.bab = int(player.raw_payload.get("bab", progression_state.bab))
    progression_state.saves = {
        str(key): int(value)
        for key, value in dict(player.raw_payload.get("saves", progression_state.saves)).items()
    }
    fallback_level = max(1, int(player.raw_payload.get("level", progression_state.level or 1)))
    normalized_levels = {
        str(key).strip().lower(): int(value)
        for key, value in dict(progression_state.class_levels).items()
        if str(key).strip()
    }
    class_order: list[str] = []
    for candidate in [primary_class_id, *progression_state.classes, *normalized_levels.keys()]:
        normalized = str(candidate).strip().lower()
        if normalized and normalized not in class_order:
            class_order.append(normalized)
    if not class_order:
        class_order = [primary_class_id]
    if not normalized_levels:
        normalized_levels = {class_order[0]: fallback_level}
    elif class_order[0] not in normalized_levels:
        remaining_levels = max(1, fallback_level - sum(normalized_levels.values()))
        normalized_levels[class_order[0]] = remaining_levels
    for class_id in normalized_levels:
        if class_id not in class_order:
            class_order.append(class_id)
    progression_state.class_levels = normalized_levels
    progression_state.classes = class_order
    progression_state.level = max(1, sum(normalized_levels.values()))

    class_defs = {
        class_id: _runtime_class_def(player, class_id, thresholds)
        for class_id in class_order
    }
    return progression_state, primary_class_id, class_defs


def _runtime_class_def(player: ActorRecord, class_id: str, thresholds: list[int]):
    from engine.data.classes import get_class
    from engine.kernel.progression import ClassDef

    class_data = get_class(class_id)
    return ClassDef(
        class_id=class_id,
        label=str(class_data.get("name", class_id.title())),
        hit_die=int(class_data.get("hit_die_size", player.raw_payload.get("hit_die_size", 8) or 8)),
        bab_rate=_adapter_bab_rate(player, class_data),
        good_saves=[],
        proficiency_rate=4,
        skill_points_per_level=int(class_data.get("skill_pick_count", 0) or 0),
        spell_type="",
        hp_after_cap=_deterministic_hit_die_roll(player, class_id),
        hit_die_cap_level=len(thresholds),
        xp_table=list(thresholds),
    )


def _next_level_up_class_id(progression_state: Any, class_defs: dict[str, Any], preferred_class_id: str | None = None) -> str | None:
    shared_xp = int(progression_state.xp) // max(1, len(class_defs))
    ordered_classes: list[str] = []
    for candidate in [preferred_class_id, *progression_state.classes, *class_defs.keys()]:
        normalized = str(candidate or "").strip().lower()
        if normalized and normalized not in ordered_classes:
            ordered_classes.append(normalized)
    for class_id in ordered_classes:
        class_def = class_defs.get(class_id)
        if class_def is None:
            continue
        current_level = int(progression_state.class_levels.get(class_id, 0))
        if current_level >= len(class_def.xp_table):
            continue
        if shared_xp >= int(class_def.xp_table[current_level]):
            return class_id
    return None


def _adapter_bab_rate(player: ActorRecord, class_data: dict[str, Any]) -> str:
    raw_rate = player.raw_payload.get("bab_rate")
    if isinstance(raw_rate, str):
        return raw_rate
    if raw_rate is not None:
        rate = float(raw_rate)
        if rate >= 1.0:
            return "full"
        if rate >= 0.75:
            return "three_quarter"
        return "half"
    hit_die = int(class_data.get("hit_die_size", player.raw_payload.get("hit_die_size", 8) or 8))
    if hit_die >= 10:
        return "full"
    if hit_die >= 8:
        return "three_quarter"
    return "half"


def _deterministic_hit_die_roll(player: ActorRecord, class_id: str) -> int:
    from engine.data.runtime import get_hp_per_level

    hp_per_level = get_hp_per_level()
    return max(
        1,
        int(
            hp_per_level.get(
                class_id,
                player.raw_payload.get("hit_die_size", 8) or 8,
            )
        ),
    )


def _apply_progression_state(player: ActorRecord, progression_state: Any, hp_gained: int) -> None:
    new_max_hp = int(player.stats.get("max_hp", 1)) + int(hp_gained)
    player.stats["max_hp"] = new_max_hp
    player.stats["hp"] = new_max_hp
    if getattr(progression_state, "class_levels", None):
        progression_state.level = max(1, sum(int(value) for value in progression_state.class_levels.values()))
    player.raw_payload["level"] = int(progression_state.level)
    player.raw_payload["xp"] = int(progression_state.xp)
    player.raw_payload["bab"] = int(progression_state.bab)
    player.raw_payload["saves"] = dict(progression_state.saves)
    class_order = [str(item).strip().lower() for item in list(getattr(progression_state, "classes", [])) if str(item).strip()]
    primary_class = str(player.raw_payload.get("class_name", "warrior")).strip().lower() or "warrior"
    if primary_class and primary_class not in class_order:
        class_order.insert(0, primary_class)
    for class_id in class_order:
        if int(getattr(progression_state, "class_levels", {}).get(class_id, 0)) > int(getattr(progression_state, "class_levels", {}).get(primary_class, 0)):
            primary_class = class_id
    player.raw_payload["class_name"] = primary_class
    player.raw_payload["progression"] = progression_state.to_dict()


def _load_actors(saved_payload: Any, context: "CampaignContext") -> dict[str, ActorRecord]:
    if isinstance(saved_payload, list):
        actors = {actor.identity.actor_id: actor for actor in [ActorRecord.from_dict(dict(item)) for item in saved_payload]}
        for actor in actors.values():
            _normalize_actor_spell_state(actor)
            normalize_actor_social_state(actor)
            normalize_actor_medical_state(actor, sync_derived=True)
        return actors
    actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }
    for actor in actors.values():
        _normalize_actor_spell_state(actor)
        normalize_actor_social_state(actor)
        normalize_actor_medical_state(actor, sync_derived=True)
    return actors


def _sync_runtime_from_context(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    combat_payload = _active_combat_payload(runtime)
    combat_turn_resources = {
        str(entry.get("actor_id", "")).strip(): _coerce_combat_turn_resources(entry.get("turn_resources", {}))
        for entry in list(combat_payload.get("combatants", []))
        if isinstance(entry, dict) and str(entry.get("actor_id", "")).strip()
    } if combat_payload is not None else {}
    fresh_actors = {
        actor.identity.actor_id: actor
        for actor in build_canonical_actor_records(
            context,
            active_region_id=context.region_snapshot.region_id,
            active_site_id=active_site_id(context),
        )
    }
    # Preserve runtime-owned actors that are not part of the authored region
    # projection yet, such as recruited companions and runtime-only NPCs.
    merged: dict[str, ActorRecord] = {
        actor_id: actor
        for actor_id, actor in dict(runtime.get("actors", {})).items()
    }
    for actor_id, fresh_actor in fresh_actors.items():
        existing = merged.get(actor_id)
        if existing is None:
            _normalize_actor_spell_state(fresh_actor)
            normalize_actor_social_state(fresh_actor)
            normalize_actor_medical_state(fresh_actor, sync_derived=True)
            merged[actor_id] = fresh_actor
            continue
        _merge_actor(existing, fresh_actor, combat_turn_resources=combat_turn_resources.get(actor_id))
        _normalize_actor_spell_state(existing)
        normalize_actor_social_state(existing)
        normalize_actor_medical_state(existing, sync_derived=True)
        merged[actor_id] = existing
    for actor_id, actor in merged.items():
        if actor_id not in fresh_actors:
            _normalize_actor_spell_state(actor)
            normalize_actor_social_state(actor)
            normalize_actor_medical_state(actor, sync_derived=True)
    runtime["actors"] = merged
    _sync_social_identity(context, runtime)
    _persist_knowledge_state(runtime, _knowledge_state(runtime))
    _sync_travel_runtime_state(context, runtime)
    _sync_combat_runtime_state(context, runtime)
    runtime["game_state"].actors = dict(merged)
    normalize_party_state(runtime["game_state"])
    existing_party = [str(actor_id) for actor_id in list(getattr(runtime["game_state"], "party", [])) if str(actor_id)]
    requested_party = [str(actor_id) for actor_id in list(context.campaign_state.get("party", [])) if str(actor_id)]
    party: list[str] = []
    for actor_id in existing_party + requested_party:
        if actor_id == "player":
            if actor_id in merged and actor_id not in party:
                party.append(actor_id)
            continue
        if actor_id in merged and _is_party_capable_actor(merged.get(actor_id)) and actor_id not in party:
            party.append(actor_id)
    if "player" in merged and "player" not in party:
        party.insert(0, "player")
    runtime["game_state"].party = party
    existing_reserves = [
        str(actor_id)
        for actor_id in list(getattr(runtime["game_state"], "inactive_npcs", []))
        if str(actor_id)
        and str(actor_id) in merged
        and str(actor_id) not in party
        and _is_party_capable_actor(merged.get(str(actor_id)))
    ]
    requested_reserves = [
        str(actor_id)
        for actor_id in list(context.campaign_state.get("reserve_party_members", []))
        if str(actor_id)
        and str(actor_id) in merged
        and str(actor_id) not in party
        and _is_party_capable_actor(merged.get(str(actor_id)))
    ]
    roster_reserves = [
        actor_id
        for actor_id, actor in merged.items()
        if actor_id not in party
        and actor_id != "player"
        and _is_party_capable_actor(actor)
        and bool(actor.raw_payload.get("companion_roster"))
    ]
    inactive: list[str] = []
    for actor_id in existing_reserves + requested_reserves + roster_reserves:
        if actor_id not in inactive:
            inactive.append(actor_id)
    runtime["game_state"].inactive_npcs = inactive
    normalize_party_state(runtime["game_state"])
    context.campaign_state["party_tactics"] = dict(getattr(runtime["game_state"], "party_tactics", {}))
    context.campaign_state["party"] = list(getattr(runtime["game_state"], "party", []))
    context.campaign_state["reserve_party_members"] = list(getattr(runtime["game_state"], "inactive_npcs", []))
    for actor_id, actor in merged.items():
        eligible = _is_party_capable_actor(actor)
        grandfathered_recruitable = actor_id != "player" and (
            actor_id in context.campaign_state["party"] or actor_id in context.campaign_state["reserve_party_members"]
        )
        if actor_id != "player" and (
            eligible
            or grandfathered_recruitable
            or "relationship_score" in actor.raw_payload
            or "recruitable_companion" in actor.raw_payload
        ):
            actor.raw_payload["relationship_score"] = _clamp_relationship_score(actor.raw_payload.get("relationship_score", 0))
            actor.raw_payload["recruitable_companion"] = bool(
                actor.raw_payload.get("recruitable_companion", False) or grandfathered_recruitable
            )
        preserve_roster_flag = bool(actor.raw_payload.get("companion_roster")) and eligible
        is_active = eligible and actor_id in context.campaign_state["party"] and actor_id != "player"
        is_reserve = eligible and actor_id in context.campaign_state["reserve_party_members"]
        if actor_id != "player":
            actor.raw_payload["companion_roster"] = bool(is_active or is_reserve or preserve_roster_flag)
            actor.raw_payload["party_member"] = is_active
            actor.raw_payload["active_party_member"] = is_active
            actor.raw_payload["reserve_party_member"] = is_reserve
            actor.raw_payload["recruitable_companion"] = bool(
                actor.raw_payload.get("recruitable_companion")
                or is_active
                or is_reserve
                or preserve_roster_flag
            )
        if eligible and (is_active or is_reserve or preserve_roster_flag):
            actor.raw_payload["party_tactic_mode"] = str(
                getattr(runtime["game_state"], "party_tactics", {}).get(actor_id, "balanced")
            )
        elif actor_id != "player":
            actor.raw_payload.pop("party_tactic_mode", None)
        normalize_actor_social_state(actor)
    context.player = merged.get("player", context.player)
    sync_combat_projection_state(context)


def _merge_actor(
    target: ActorRecord,
    fresh: ActorRecord,
    *,
    combat_turn_resources: dict[str, int | bool] | None = None,
) -> None:
    target.action_points = fresh.action_points
    target.max_action_points = fresh.max_action_points
    target.turn_resources = (
        dict(combat_turn_resources)
        if combat_turn_resources is not None
        else dict(fresh.turn_resources)
    )
    # Runtime actors own their live coordinates. Region projection can rebuild
    # fresh shells each tick, but we must not snap actors back to authored spawn
    # points here or hazards/traps/combat movement will silently desync.
    if target.position is None:
        target.position = fresh.position
    target.alive = target.alive and fresh.alive
    for key, value in fresh.stats.items():
        if key in {"hp", "max_hp"} or key not in target.stats:
            target.stats[key] = value
    for key, value in fresh.skills.items():
        target.skills.setdefault(key, value)
    target.inventory = fresh.inventory
    target.equipment = fresh.equipment
    # Preserve progression fields (xp, level) that the kernel owns.
    preserved_xp = target.raw_payload.get("xp")
    preserved_level = target.raw_payload.get("level")
    preserved_recruitable = target.raw_payload.get("recruitable_companion") if "recruitable_companion" in target.raw_payload else None
    preserved_relationship = target.raw_payload.get("relationship_score") if "relationship_score" in target.raw_payload else None
    preserved_named_npc_id = target.raw_payload.get("named_npc_id") if "named_npc_id" in target.raw_payload else None
    preserved_identity_source = target.raw_payload.get("identity_source") if "identity_source" in target.raw_payload else None
    preserved_memory_id = target.raw_payload.get("memory_id") if "memory_id" in target.raw_payload else None
    preserved_spell = {
        key: copy.deepcopy(target.raw_payload.get(key))
        for key in _RUNTIME_SPELL_KEYS
        if key in target.raw_payload
    }
    preserved_medical = {
        key: target.raw_payload.get(key)
        for key in _RUNTIME_MEDICAL_KEYS
        if key in target.raw_payload
    }
    preserved_social = {
        key: target.raw_payload.get(key)
        for key in _RUNTIME_SOCIAL_KEYS
        if key in target.raw_payload
    }
    target.raw_payload.update(fresh.raw_payload)
    if preserved_xp is not None:
        target.raw_payload["xp"] = max(int(preserved_xp), int(target.raw_payload.get("xp", 0)))
    if preserved_level is not None:
        target.raw_payload["level"] = max(int(preserved_level), int(target.raw_payload.get("level", 1)))
    if preserved_recruitable is not None:
        target.raw_payload["recruitable_companion"] = bool(preserved_recruitable)
    if preserved_relationship is not None:
        target.raw_payload["relationship_score"] = _clamp_relationship_score(preserved_relationship)
    if preserved_named_npc_id is not None:
        target.raw_payload["named_npc_id"] = preserved_named_npc_id
    if preserved_identity_source is not None:
        target.raw_payload["identity_source"] = preserved_identity_source
    if preserved_memory_id is not None:
        target.raw_payload["memory_id"] = preserved_memory_id
    for key, value in preserved_spell.items():
        target.raw_payload[key] = copy.deepcopy(value)
    for key, value in preserved_medical.items():
        target.raw_payload[key] = value
    for key, value in preserved_social.items():
        target.raw_payload[key] = value
    _normalize_actor_spell_state(target)
    if target.body_state is None:
        target.body_state = fresh.body_state
    elif target.body_state is not None and fresh.body_state is not None:
        for part_id, part in fresh.body_state.parts.items():
            existing_part = target.body_state.parts.get(part_id)
            if existing_part is None:
                target.body_state.parts[part_id] = part
                continue
            existing_part.max_hp = max(existing_part.max_hp, part.max_hp)
            existing_part.current_hp = min(existing_part.current_hp, part.current_hp)
    if target.schedule.owner_id == "" and fresh.schedule.owner_id:
        target.schedule = fresh.schedule


def normalize_actor_social_state(actor: ActorRecord) -> None:
    actor.raw_payload["recruitable_companion"] = bool(actor.raw_payload.get("recruitable_companion", False))
    relationship_score = int(actor.raw_payload.get("relationship_score", 0) or 0)
    actor.raw_payload["relationship_score"] = max(-100, min(100, relationship_score))


def _sync_social_identity(context: "CampaignContext", runtime: dict[str, Any]) -> None:
    manager = context.npc_memory
    if manager is None:
        manager = NPCMemoryManager(session_id=context.campaign_id)
        context.npc_memory = manager

    region_state = runtime_region_state(context.world, context.region_snapshot.region_id)
    runtime_npcs = {
        str(entry.get("id", "")): dict(entry)
        for entry in list(region_state.get("npcs", []))
        if isinstance(entry, dict) and str(entry.get("id", "")).strip()
    }
    used_authored_ids = {
        str(_optional_identity(entry.get("named_npc_id")))
        for entry in runtime_npcs.values()
        if str(entry.get("identity_source", "")).lower().strip() == "authored" and _optional_identity(entry.get("named_npc_id"))
    }
    for actor_id, actor in sorted(runtime.get("actors", {}).items(), key=lambda item: item[0]):
        if not _is_social_actor(actor):
            continue
        actor_id = str(actor_id)
        runtime_npc = runtime_npcs.get(actor_id, {})
        metadata_keys = (
            "authored_role",
            "authored_location_id",
            "faction_alignment",
            "personality",
            "dialogue_snippets",
            "relationship_modifiers",
        )
        for key in metadata_keys:
            if key in runtime_npc:
                actor.raw_payload[key] = copy.deepcopy(runtime_npc[key])

        named_npc_id = _optional_identity(runtime_npc.get("named_npc_id", actor.raw_payload.get("named_npc_id")))
        identity_source = _optional_identity(runtime_npc.get("identity_source", actor.raw_payload.get("identity_source")))
        identity_source = str(identity_source).lower() if identity_source is not None else None
        memory_id = _optional_identity(runtime_npc.get("memory_id", actor.raw_payload.get("memory_id")))

        if identity_source is None:
            identity_source = "generated"
        if memory_id is None:
            memory_id = named_npc_id or actor_id

        if identity_source == "authored" and named_npc_id:
            used_authored_ids.add(named_npc_id)

        actor.raw_payload["named_npc_id"] = named_npc_id
        actor.raw_payload["identity_source"] = identity_source
        actor.raw_payload["memory_id"] = memory_id

        score = _clamp_relationship_score(actor.raw_payload.get("relationship_score", 0))
        actor.raw_payload["relationship_score"] = score
        actor.raw_payload["recruitable_companion"] = bool(actor.raw_payload.get("recruitable_companion", False))

        if memory_id != actor_id and actor_id in manager.memories and memory_id not in manager.memories:
            manager.memories[memory_id] = manager.memories.pop(actor_id)
            manager.memories[memory_id].npc_id = memory_id
        memory = manager.get_memory(memory_id, npc_name=str(getattr(getattr(actor, "identity", None), "display_name", memory_id)))
        memory.name = str(getattr(getattr(actor, "identity", None), "display_name", memory_id))
        memory.relationship_score = score
        memory.relationship_label = _relationship_label_from_score(score)


def normalize_actor_medical_state(actor: ActorRecord, *, sync_derived: bool = False) -> None:
    """Normalize an actor's medical raw payload into typed kernel objects."""
    from engine.kernel.medical import InfectionState, PermanentConsequence, RecoveryState, TreatmentRecord

    body_wounds = list(getattr(getattr(actor, "body_state", None), "wounds", []) or [])
    raw_wounds = actor.raw_payload.get("wounds", [])
    wounds = _merge_wounds(raw_wounds, body_wounds)
    actor.raw_payload["wounds"] = wounds
    if actor.body_state is not None:
        actor.body_state.wounds = wounds

    actor.raw_payload["treatment_records"] = _normalize_records(
        actor.raw_payload.get("treatment_records", []),
        TreatmentRecord,
    )
    actor.raw_payload["medical_infections"] = _normalize_records(
        actor.raw_payload.get("medical_infections", []),
        InfectionState,
    )
    actor.raw_payload["medical_recoveries"] = _normalize_records(
        actor.raw_payload.get("medical_recoveries", []),
        RecoveryState,
    )
    actor.raw_payload["permanent_consequences"] = _normalize_records(
        actor.raw_payload.get("permanent_consequences", []),
        PermanentConsequence,
    )

    if sync_derived:
        sync_actor_medical_runtime_state(actor)


def sync_actor_medical_runtime_state(actor: ActorRecord) -> None:
    """Refresh treatment, infection, and recovery state for an actor."""
    from engine.kernel.medical import InfectionState, RecoveryState

    normalize_actor_medical_state(actor, sync_derived=False)
    wounds: list = list(actor.raw_payload.get("wounds", []))
    current_tick = int(actor.raw_payload.get("game_tick", 0))
    record_map = {record.wound_id: record for record in actor.raw_payload.get("treatment_records", [])}
    refreshed_records = []
    for wound in wounds:
        record = record_map.get(wound.wound_id)
        if record is None:
            continue
        refreshed_records.append(_refresh_treatment_record(record, wound, current_tick))
    actor.raw_payload["treatment_records"] = refreshed_records

    existing_infections = {
        state.wound_id: state
        for state in actor.raw_payload.get("medical_infections", [])
        if isinstance(state, InfectionState)
    }
    infections = []
    wound_ids = {wound.wound_id for wound in wounds}
    for wound in wounds:
        record = next((item for item in refreshed_records if item.wound_id == wound.wound_id), None)
        state = _sync_infection_state(wound, record, existing_infections.get(wound.wound_id))
        if state is not None:
            infections.append(state)
    for wound_id, state in existing_infections.items():
        if wound_id not in wound_ids:
            infections.append(state)
    actor.raw_payload["medical_infections"] = infections

    existing_recoveries = {
        state.body_part_id: state
        for state in actor.raw_payload.get("medical_recoveries", [])
        if isinstance(state, RecoveryState)
    }
    recoveries = []
    body_state = getattr(actor, "body_state", None)
    if body_state is not None:
        treatment_by_part: dict[str, float] = {}
        for wound in wounds:
            record = next((item for item in refreshed_records if item.wound_id == wound.wound_id), None)
            if record is None:
                continue
            treatment_by_part[wound.body_part_id] = max(
                float(treatment_by_part.get(wound.body_part_id, 0.0)),
                float(record.treatment_quality),
            )
        for part_id, part in body_state.parts.items():
            existing = existing_recoveries.get(part_id)
            if int(part.current_hp) >= int(part.max_hp) and existing is None:
                continue
            recovery = existing or RecoveryState(
                body_part_id=part_id,
                current_hp=int(part.current_hp),
                max_hp=int(part.max_hp),
            )
            recovery.current_hp = int(part.current_hp)
            recovery.max_hp = int(part.max_hp)
            recovery.recuperation_bonus = max(float(recovery.recuperation_bonus), _recuperation_bonus(actor))
            recovery.treatment_quality = max(
                float(recovery.treatment_quality),
                float(treatment_by_part.get(part_id, 0.5)),
            )
            if int(recovery.current_hp) < int(recovery.max_hp):
                recoveries.append(recovery)
        for part_id, recovery in existing_recoveries.items():
            if part_id not in body_state.parts:
                recoveries.append(recovery)
    actor.raw_payload["medical_recoveries"] = recoveries


def build_medical_payload(actor: ActorRecord) -> dict[str, Any]:
    """Project structured medical state for campaign payloads."""
    from engine.kernel.medical import InfectionState, PermanentConsequence, RecoveryState, TreatmentRecord

    normalize_actor_medical_state(actor, sync_derived=True)
    wounds: list = list(actor.raw_payload.get("wounds", []))
    records: list[TreatmentRecord] = list(actor.raw_payload.get("treatment_records", []))
    infections: list[InfectionState] = list(actor.raw_payload.get("medical_infections", []))
    recoveries: list[RecoveryState] = list(actor.raw_payload.get("medical_recoveries", []))
    consequences: list[PermanentConsequence] = list(actor.raw_payload.get("permanent_consequences", []))

    from engine.kernel.medical import check_lethal_conditions

    lethal, reason = check_lethal_conditions(actor)
    active_infections = [
        state
        for state in infections
        if float(state.infection_level) > 0.0 or state.fever or state.organ_damage or state.lethal
    ]
    recovering_parts = [state.body_part_id for state in recoveries if int(state.current_hp) < int(state.max_hp)]
    aftercare: list[str] = []
    for state in recoveries:
        if int(state.current_hp) < int(state.max_hp):
            aftercare.append(f"{state.body_part_id} recovering ({int(state.current_hp)}/{int(state.max_hp)} hp).")
    for infection in active_infections:
        aftercare.append(
            f"Monitor {infection.body_part_id} for infection ({float(infection.infection_level):.2f}).",
        )
    if consequences:
        aftercare.extend(f"{entry.body_part_id}: {entry.description}" for entry in consequences)

    if lethal:
        status = f"critical:{reason}"
    elif active_infections:
        status = "infected"
    elif wounds or records or recoveries:
        status = "recovering"
    else:
        status = "stable"

    return {
        "summary": {
            "status": status,
            "active_wound_count": len(wounds),
            "pending_treatment_steps": sum(len(record.steps_remaining) for record in records),
            "infection_count": len(active_infections),
            "recovering_parts": recovering_parts,
            "aftercare": aftercare,
        },
        "wounds": [
            {
                "wound_id": wound.wound_id,
                "body_part_id": wound.body_part_id,
                "damage_type": wound.damage_type,
                "damage_amount": int(wound.damage_amount),
                "bleeding": int(wound.bleeding),
                "pain": int(wound.pain),
                "open_wound": bool(wound.open_wound),
                "fracture": bool(wound.fracture),
                "infected": bool(getattr(wound, "infected", False)),
                "untreated": bool(wound.untreated),
                "destroyed": bool(wound.destroyed),
                "crippled": bool(wound.crippled),
                "infection_risk": float(getattr(wound, "infection_risk", 0.0)),
            }
            for wound in wounds
        ],
        "treatment_records": [
            {
                "wound_id": record.wound_id,
                "patient_id": record.patient_id,
                "doctor_id": record.doctor_id,
                "diagnosed": bool(record.diagnosed),
                "steps_completed": [step.name.lower() for step in record.steps_completed],
                "steps_remaining": [step.name.lower() for step in record.steps_remaining],
                "infection_level": float(record.infection_level),
                "infection_rate": float(record.infection_rate),
                "treatment_quality": float(record.treatment_quality),
                "tick_started": int(record.tick_started),
                "tick_completed": record.tick_completed,
            }
            for record in records
        ],
        "infections": [
            {
                "wound_id": infection.wound_id,
                "body_part_id": infection.body_part_id,
                "infection_level": float(infection.infection_level),
                "cleaned": bool(infection.cleaned),
                "fever": bool(infection.fever),
                "organ_damage": bool(infection.organ_damage),
                "lethal": bool(infection.lethal),
            }
            for infection in infections
        ],
        "recoveries": [
            {
                "body_part_id": recovery.body_part_id,
                "current_hp": int(recovery.current_hp),
                "max_hp": int(recovery.max_hp),
                "treatment_quality": float(recovery.treatment_quality),
                "recuperation_bonus": float(recovery.recuperation_bonus),
                "ticks_since_last_heal": int(recovery.ticks_since_last_heal),
            }
            for recovery in recoveries
        ],
        "permanent_consequences": [
            {
                "consequence_id": consequence.consequence_id,
                "kind": consequence.kind,
                "body_part_id": consequence.body_part_id,
                "description": consequence.description,
                "mobility_penalty": int(consequence.mobility_penalty),
                "stress_per_tick": float(consequence.stress_per_tick),
                "stat_modifiers": dict(consequence.stat_modifiers),
            }
            for consequence in consequences
        ],
    }


def _merge_wounds(raw_entries: list[Any], body_entries: list[Any]) -> list[Any]:
    from engine.kernel.medical import WoundRecord

    merged: list[Any] = []
    seen: set[str] = set()
    for entry in list(raw_entries or []) + list(body_entries or []):
        wound = entry if isinstance(entry, WoundRecord) else WoundRecord.from_dict(dict(entry)) if isinstance(entry, dict) else None
        if wound is None or wound.wound_id in seen:
            continue
        seen.add(wound.wound_id)
        merged.append(wound)
    return merged


def _normalize_records(entries: list[Any], cls: type) -> list[Any]:
    key_name = "body_part_id" if cls.__name__ == "RecoveryState" else "consequence_id" if cls.__name__ == "PermanentConsequence" else "wound_id"
    normalized: list[Any] = []
    seen: set[str] = set()
    for entry in entries or []:
        item = entry if isinstance(entry, cls) else cls.from_dict(dict(entry)) if isinstance(entry, dict) else None
        if item is None:
            continue
        key = str(getattr(item, key_name, ""))
        if not key or key in seen:
            continue
        if cls.__name__ == "TreatmentRecord":
            item.steps_completed = _dedupe_steps(item.steps_completed)
            item.steps_remaining = _dedupe_steps(
                [step for step in item.steps_remaining if step not in item.steps_completed],
            )
        if cls.__name__ == "InfectionState":
            from engine.kernel.medical import tick_infection

            tick_infection(item, 0)
        seen.add(key)
        normalized.append(item)
    return normalized


def _dedupe_steps(steps: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[Any] = set()
    for step in steps:
        if step in seen:
            continue
        seen.add(step)
        deduped.append(step)
    return deduped


def _refresh_treatment_record(record: Any, wound: Any, current_tick: int) -> Any:
    from engine.kernel.medical import TreatmentStep, determine_treatment_plan

    plan = determine_treatment_plan(wound)
    diagnosed = bool(record.diagnosed or getattr(wound, "diagnosed", False))
    completed = _dedupe_steps(record.steps_completed)
    if diagnosed and TreatmentStep.DIAGNOSIS not in completed:
        completed.insert(0, TreatmentStep.DIAGNOSIS)
    remaining = [step for step in plan if step not in completed]

    record.diagnosed = diagnosed
    record.steps_completed = completed
    record.steps_remaining = remaining
    record.infection_level = max(float(record.infection_level), float(getattr(wound, "infection_level", 0.0)))
    record.infection_rate = float(getattr(wound, "infection_risk", record.infection_rate))
    record.treatment_quality = max(float(record.treatment_quality), 0.5)
    if int(record.tick_started) <= 0:
        record.tick_started = int(current_tick)
    record.tick_completed = int(current_tick) if not remaining else None

    setattr(wound, "diagnosed", record.diagnosed)
    setattr(wound, "infection_risk", record.infection_rate)
    setattr(wound, "infection_level", record.infection_level)
    return record


def _sync_infection_state(wound: Any, record: Any, existing: Any) -> Any:
    from engine.kernel.medical import InfectionState, TreatmentStep, tick_infection

    infection_level = float(getattr(wound, "infection_level", 0.0))
    infection_risk = float(getattr(wound, "infection_risk", 0.0))
    if record is not None:
        infection_level = max(infection_level, float(record.infection_level))
        infection_risk = max(infection_risk, float(record.infection_rate))
    should_track = bool(existing) or bool(wound.open_wound) or bool(wound.infected) or infection_level > 0.0 or infection_risk > 0.0
    if not should_track:
        return None
    state = existing or InfectionState(wound_id=wound.wound_id, body_part_id=wound.body_part_id)
    state.body_part_id = wound.body_part_id
    state.infection_level = max(float(state.infection_level), infection_level)
    cleaned = bool(state.cleaned)
    if record is not None and TreatmentStep.CLEAN in record.steps_completed:
        cleaned = True
    if infection_risk <= 0.1 and infection_risk > 0.0:
        cleaned = True
    state.cleaned = cleaned
    tick_infection(state, 0)
    wound.infected = state.infection_level > 0.0 or state.fever or state.organ_damage or state.lethal
    setattr(wound, "infection_level", state.infection_level)
    setattr(wound, "infection_risk", infection_risk)
    if record is not None:
        record.infection_level = max(float(record.infection_level), float(state.infection_level))
        record.infection_rate = infection_risk
    return state


def _recuperation_bonus(actor: ActorRecord) -> float:
    return max(0.0, float(actor.stats.get("recuperation", 0)) / 100.0)


def _medical_tick_events(actors: list, current_tick: int) -> list[dict[str, Any]]:
    """Advance infection and recovery states for all actors."""
    from engine.kernel.medical import InfectionState, RecoveryState, tick_infection, tick_recovery

    events: list[dict[str, Any]] = []
    for actor in actors:
        normalize_actor_medical_state(actor, sync_derived=True)
        wounds_by_id = {
            wound.wound_id: wound
            for wound in actor.raw_payload.get("wounds", [])
        }
        for infection in actor.raw_payload.get("medical_infections", []):
            if isinstance(infection, InfectionState):
                prev = infection.infection_level
                tick_infection(infection, 1)
                wound = wounds_by_id.get(infection.wound_id)
                if wound is not None:
                    wound.infected = infection.infection_level > 0.0 or infection.fever or infection.organ_damage or infection.lethal
                    setattr(wound, "infection_level", infection.infection_level)
                if infection.infection_level > prev:
                    events.append({
                        "event_type": "infection_progress",
                        "summary": f"{actor.identity.display_name}: infection advanced to {infection.infection_level:.0%}.",
                        "actor_id": actor.identity.actor_id,
                    })
        for recovery in actor.raw_payload.get("medical_recoveries", []):
            if isinstance(recovery, RecoveryState):
                healed = tick_recovery(recovery, 1)
                if actor.body_state is not None and recovery.body_part_id in actor.body_state.parts:
                    part = actor.body_state.parts[recovery.body_part_id]
                    part.current_hp = min(int(part.max_hp), int(part.current_hp) + int(healed))
                    recovery.current_hp = int(part.current_hp)
                if healed > 0:
                    actor.stats["hp"] = min(
                        int(actor.stats.get("max_hp", actor.stats.get("hp", 0))),
                        int(actor.stats.get("hp", 0)) + int(healed),
                    )
                if healed > 0:
                    events.append({
                        "event_type": "medical_recovery",
                        "summary": f"{actor.identity.display_name}: recovered {healed} hp.",
                        "actor_id": actor.identity.actor_id,
                    })
    return events


__all__ = [
    "_check_level_up",
    "advance_kernel_runtime",
    "build_actor_equipment_payload",
    "build_actor_spell_payload",
    "build_runtime_knowledge_payload",
    "build_travel_state_payload",
    "ensure_kernel_runtime",
    "serialize_kernel_runtime",
]
