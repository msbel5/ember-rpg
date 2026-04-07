from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Any

from engine.api.campaign.knowledge import (
    build_campaign_knowledge_payload,
    related_discovered_topic_ids_for_actor,
)
from engine.api.campaign.live_kernel import build_runtime_travel_payload
from engine.api.campaign.settlement import current_player_turn_resources
from engine.api.campaign.world import build_travel_options

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


_ASK_DM_RE = re.compile(r"^ask\s+dm(?:\s+(?P<query>.+))?$", re.IGNORECASE)
_OBJECTIVE_KEYWORDS = (
    "objective",
    "quest",
    "mission",
    "goal",
    "next step",
    "what should i do",
    "what now",
    "journal",
)
_NAVIGATION_KEYWORDS = (
    "where",
    "go",
    "travel",
    "route",
    "path",
    "road",
    "map",
    "direction",
    "destination",
    "navigate",
)
_COMBAT_KEYWORDS = (
    "combat",
    "fight",
    "attack",
    "enemy",
    "target",
    "turn",
    "range",
    "line of sight",
    "los",
    "defend",
    "flee",
)
_RESOURCE_KEYWORDS = (
    "hp",
    "health",
    "resource",
    "inventory",
    "item",
    "potion",
    "rest",
    "heal",
    "spell point",
    "spell points",
    "supplies",
    "gear",
)
_SOCIAL_KEYWORDS = (
    "talk",
    "speak",
    "conversation",
    "dialog",
    "npc",
    "rumor",
    "topic",
    "ask",
    "pin",
    "social",
)


def maybe_handle_advisor_command(
    context: "CampaignContext",
    command_text: str,
) -> tuple[str, str, int] | None:
    match = _ASK_DM_RE.match(str(command_text or "").strip())
    if match is None:
        return None
    return _advisor_command(context, str(match.group("query") or "").strip())


def maybe_handle_structured_advisor_command(
    context: "CampaignContext",
    args: dict[str, Any],
) -> tuple[str, str, int] | None:
    action_id = str(args.get("action_id", "")).strip().lower()
    if not action_id:
        return None
    if action_id != "ask_dm":
        return (f"Unsupported advisor action '{action_id}'.", "advisor", 0)
    return _advisor_command(context, str(args.get("query", "")).strip())


def _advisor_command(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    advisor_view = build_advisor_view(context, query)
    _queue_advisor_view(context, advisor_view)
    narrative = " ".join(line for line in advisor_view.get("answer_lines", []) if str(line).strip()).strip()
    if not narrative:
        narrative = "Ask DM could not ground an answer from the current campaign state."
    return narrative, "advisor", 0


def _queue_advisor_view(context: "CampaignContext", payload: dict[str, Any]) -> None:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    runtime["_pending_advisor_payload"] = {"advisor_view": payload}


def build_advisor_view(context: "CampaignContext", query: str) -> dict[str, Any]:
    stripped_query = str(query or "").strip()
    if not stripped_query:
        return _finalize_view(
            context,
            {
                "intent": "unknown",
                "answer_lines": ["Ask DM requires a question."],
                "related_topic_ids": [],
                "suggested_commands": ["quests", "topics"],
                "blockers": ["missing_query"],
            },
        )

    intent = _classify_intent(context, stripped_query)
    if intent == "objective":
        view = _build_objective_view(context)
    elif intent == "navigation":
        view = _build_navigation_view(context)
    elif intent == "combat":
        view = _build_combat_view(context)
    elif intent == "resources":
        view = _build_resources_view(context)
    elif intent == "social":
        view = _build_social_view(context)
    else:
        view = {
            "intent": "unknown",
            "answer_lines": [
                "I can only answer grounded questions about objectives, travel, combat, resources, and social leads."
            ],
            "related_topic_ids": [],
            "suggested_commands": ["quests", "topics", "look around"],
            "blockers": ["unclassified_query"],
        }
    return _finalize_view(context, view)


def _classify_intent(context: "CampaignContext", query: str) -> str:
    normalized = _normalize_text(query)
    if any(keyword in normalized for keyword in _OBJECTIVE_KEYWORDS):
        return "objective"
    if any(keyword in normalized for keyword in _NAVIGATION_KEYWORDS):
        return "navigation"
    if any(keyword in normalized for keyword in _COMBAT_KEYWORDS):
        return "combat"
    if any(keyword in normalized for keyword in _RESOURCE_KEYWORDS):
        return "resources"
    if any(keyword in normalized for keyword in _SOCIAL_KEYWORDS):
        return "social"
    if _combat_is_active(context):
        return "combat"
    if _dialog_is_active(context):
        return "social"
    if _travel_is_active(context):
        return "navigation"
    return "unknown"


def _build_objective_view(context: "CampaignContext") -> dict[str, Any]:
    active_quests = [
        dict(item)
        for item in list((context.campaign_state or {}).get("active_quests", []) or [])
        if isinstance(item, dict)
    ]
    if not active_quests:
        return {
            "intent": "objective",
            "answer_lines": ["No active objective is tracked right now."],
            "related_topic_ids": [],
            "suggested_commands": ["quests", "topics"],
            "blockers": ["no_active_objective"],
        }

    quest = active_quests[0]
    quest_id = str(quest.get("quest_id") or quest.get("id") or "").strip()
    title = str(quest.get("title", "")).strip() or quest_id.replace("_", " ").title() or "Active objective"
    stage = str(quest.get("stage", "")).strip()
    objectives = list(quest.get("objectives", []) or [])
    related = [f"quest.{quest_id}"] if quest_id else []
    answer_lines = [f"Active objective: {title}."]
    if stage:
        answer_lines.append(f"Current stage: {stage.replace('_', ' ')}.")
    if objectives:
        answer_lines.append(f"Tracked objectives: {len(objectives)}.")
    suggested = ["quests"]
    if quest_id:
        suggested.append(f"think quest.{quest_id}")
    return {
        "intent": "objective",
        "answer_lines": answer_lines,
        "related_topic_ids": related,
        "suggested_commands": suggested,
        "blockers": [],
    }


def _build_navigation_view(context: "CampaignContext") -> dict[str, Any]:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    travel_state = build_runtime_travel_payload(runtime)
    region_id = _current_region_id(context)
    settlement_id = _current_settlement_id(context)
    settlement_name = _current_settlement_name(context)
    related: list[str] = []
    if region_id:
        related.append(f"region.{region_id}")
    if settlement_id:
        related.append(f"settlement.{settlement_id}")

    if _travel_payload_is_active(travel_state):
        destination_name = str(travel_state.get("destination_name", "")).strip() or "the destination"
        answer_lines = [
            f"You are traveling to {destination_name}.",
            f"Travel hours remaining: {int(travel_state.get('travel_hours_remaining', 0) or 0)}.",
        ]
        blockers: list[str] = []
        suggested = ["continue travel"]
        if bool(travel_state.get("paused_for_encounter")) and not bool(travel_state.get("encounter_resolved")):
            answer_lines.append("Travel is paused until the encounter is resolved.")
            blockers.append("travel_paused_for_encounter")
            suggested = ["resolve travel encounter", "continue travel"]
        destination_region_id = str(travel_state.get("destination_region_id", "")).strip()
        destination_settlement_id = str(travel_state.get("destination_settlement_id", "")).strip()
        if destination_region_id:
            related.append(f"region.{destination_region_id}")
        if destination_settlement_id:
            related.append(f"settlement.{destination_settlement_id}")
        return {
            "intent": "navigation",
            "answer_lines": answer_lines,
            "related_topic_ids": related,
            "suggested_commands": suggested,
            "blockers": blockers,
        }

    travel_options = [
        dict(item)
        for item in list(build_travel_options(context.world, context=context) or [])
        if isinstance(item, dict) and not item.get("is_current")
    ]
    answer_lines = [
        f"You are in {settlement_name}." if settlement_name else f"You are in {region_id.replace('_', ' ')}.",
        f"Reachable routes: {len(travel_options)}.",
    ]
    suggested = ["look around"]
    if travel_options:
        option = travel_options[0]
        destination_region_id = str(option.get("destination_region_id", "")).strip()
        destination_settlement_id = str(option.get("destination_settlement_id", "")).strip()
        destination_name = str(option.get("destination_name", "")).strip() or destination_region_id or "the next region"
        answer_lines.append(f"Nearest route points toward {destination_name}.")
        if destination_region_id:
            suggested.append(f"travel {destination_region_id}")
            related.append(f"region.{destination_region_id}")
        elif destination_settlement_id:
            suggested.append(f"travel {destination_settlement_id}")
            related.append(f"settlement.{destination_settlement_id}")
    else:
        answer_lines.append("No outbound route is currently available.")
    if region_id:
        suggested.append(f"think region.{region_id}")
    return {
        "intent": "navigation",
        "answer_lines": answer_lines,
        "related_topic_ids": related,
        "suggested_commands": suggested,
        "blockers": [],
    }


def _build_combat_view(context: "CampaignContext") -> dict[str, Any]:
    if not _combat_is_active(context):
        return {
            "intent": "combat",
            "answer_lines": ["You are not in combat right now."],
            "related_topic_ids": [],
            "suggested_commands": ["look around", "topics"],
            "blockers": ["not_in_combat"],
        }

    from engine.api.combat_bridge import build_combat_payload

    combat = build_combat_payload(context) or {}
    turn_actor_id = str(combat.get("turn_actor_id", "")).strip()
    combatants = {
        str(entry.get("actor_id", "")).strip(): dict(entry)
        for entry in list(combat.get("combatants", []) or [])
        if isinstance(entry, dict)
    }
    turn_name = str(combatants.get(turn_actor_id, {}).get("name", turn_actor_id or "unknown")).strip()
    available_actions = [str(item).strip() for item in list(combat.get("available_actions", []) or []) if str(item).strip()]
    targets = [
        dict(item)
        for item in list(combat.get("targets", []) or [])
        if isinstance(item, dict) and bool(item.get("alive", True))
    ]

    answer_lines = [
        "It is your turn." if turn_actor_id == "player" else f"It is {turn_name}'s turn.",
        "Available actions: %s." % (", ".join(available_actions) if available_actions else "none"),
    ]
    if targets:
        answer_lines.append("Visible targets: %s." % ", ".join(str(item.get("name", "")).strip() for item in targets[:3]))
    else:
        answer_lines.append("No live targets are exposed.")

    suggested: list[str] = []
    if turn_actor_id == "player":
        first_target_name = str(targets[0].get("name", "")).strip() if targets else ""
        if "attack" in available_actions and first_target_name:
            suggested.append(f"attack {first_target_name}")
        if "use_item" in available_actions:
            usable_items = _usable_item_ids(_player(context))
            if usable_items:
                suggested.append(f"use {usable_items[0]}")
        if "defend" in available_actions:
            suggested.append("defend")
        if "flee" in available_actions:
            suggested.append("flee")
        if "end_turn" in available_actions:
            suggested.append("end turn")

    return {
        "intent": "combat",
        "answer_lines": answer_lines,
        "related_topic_ids": [],
        "suggested_commands": suggested,
        "blockers": [],
    }


def _build_resources_view(context: "CampaignContext") -> dict[str, Any]:
    player = _player(context)
    if player is None:
        return {
            "intent": "resources",
            "answer_lines": ["No active player state is available."],
            "related_topic_ids": [],
            "suggested_commands": [],
            "blockers": ["unclassified_query"],
        }

    hp = int(player.stats.get("hp", 0))
    max_hp = int(player.stats.get("max_hp", max(1, hp)) or max(1, hp))
    spell_points = int(getattr(player, "spell_points", player.raw_payload.get("spell_points", 0)) or 0)
    max_spell_points = int(getattr(player, "max_spell_points", player.raw_payload.get("max_spell_points", 0)) or 0)
    turn_resources = current_player_turn_resources(context)
    inventory_ids = [str(getattr(item, "item_def_id", "")).strip() for item in list(getattr(player, "inventory", []) or []) if str(getattr(item, "item_def_id", "")).strip()]
    usable_items = _usable_item_ids(player)

    answer_lines = [
        f"HP {hp}/{max_hp}. Spell points {spell_points}/{max_spell_points}.",
        f"Inventory entries: {len(inventory_ids)}. Movement remaining: {int(turn_resources.get('movement_remaining', 0) or 0)}.",
    ]
    if usable_items:
        answer_lines.append("Usable items: %s." % ", ".join(usable_items[:3]))
    else:
        answer_lines.append("No usable consumables are ready.")

    suggested = ["inventory"]
    if usable_items:
        suggested.append(f"use {usable_items[0]}")
    if not _combat_is_active(context) and not _travel_is_active(context):
        suggested.append("rest")
    return {
        "intent": "resources",
        "answer_lines": answer_lines,
        "related_topic_ids": [],
        "suggested_commands": suggested,
        "blockers": [],
    }


def _build_social_view(context: "CampaignContext") -> dict[str, Any]:
    knowledge_payload = build_campaign_knowledge_payload(context)
    pinned = list(knowledge_payload.get("pinned_topic_ids", []) or [])
    npc_actor = _dialog_actor(context)
    if npc_actor is not None:
        actor_id = str(getattr(getattr(npc_actor, "identity", None), "actor_id", "")).strip()
        npc_name = str(getattr(getattr(npc_actor, "identity", None), "display_name", actor_id)).strip() or actor_id
        faction_id = str(
            getattr(getattr(npc_actor, "identity", None), "faction_id", "")
            or getattr(npc_actor, "raw_payload", {}).get("faction_id", "")
            or ""
        ).strip()
        related = related_discovered_topic_ids_for_actor(context, actor_id, faction_id)
        suggested = ["topics"]
        ask_topic = next((topic_id for topic_id in related if topic_id != f"npc.{actor_id}"), "")
        if ask_topic:
            suggested.append(f"ask about {ask_topic}")
        elif pinned:
            suggested.append(f"ask about {pinned[0]}")
        return {
            "intent": "social",
            "answer_lines": [
                f"You are speaking with {npc_name}.",
                "Use ask about on a discovered topic they plausibly know.",
                f"Pinned topics available: {len(pinned)}.",
            ],
            "related_topic_ids": related + pinned,
            "suggested_commands": suggested,
            "blockers": [],
        }

    talkables = _talkable_npc_names(context)
    if not talkables:
        return {
            "intent": "social",
            "answer_lines": ["No talkable social target is currently projected."],
            "related_topic_ids": pinned,
            "suggested_commands": ["topics", "look around"],
            "blockers": ["no_social_target"],
        }
    return {
        "intent": "social",
        "answer_lines": [
            f"Talkable contacts nearby: {len(talkables)}.",
            f"The clearest lead is {talkables[0]}.",
        ],
        "related_topic_ids": pinned,
        "suggested_commands": [f"talk {talkables[0]}", "topics"],
        "blockers": [],
    }


def _finalize_view(context: "CampaignContext", payload: dict[str, Any]) -> dict[str, Any]:
    discovered = set(build_campaign_knowledge_payload(context).get("discovered_topic_ids", []) or [])
    return {
        "intent": str(payload.get("intent", "unknown")).strip().lower() or "unknown",
        "answer_lines": _limit_strings(payload.get("answer_lines", []), max_items=3),
        "related_topic_ids": _limit_topic_ids(payload.get("related_topic_ids", []), discovered, max_items=3),
        "suggested_commands": _limit_strings(payload.get("suggested_commands", []), max_items=4),
        "blockers": _limit_strings(payload.get("blockers", []), max_items=4),
        "spoiler_safe": True,
    }


def _player(context: "CampaignContext") -> Any:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    return (runtime.get("actors") or {}).get("player", getattr(context, "player", None))


def _combat_is_active(context: "CampaignContext") -> bool:
    return bool(getattr(context, "in_combat", lambda: False)())


def _dialog_is_active(context: "CampaignContext") -> bool:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    dialog_state = runtime.get("dialog_state")
    return bool(getattr(dialog_state, "active", False))


def _travel_is_active(context: "CampaignContext") -> bool:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    return _travel_payload_is_active(build_runtime_travel_payload(runtime))


def _travel_payload_is_active(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).strip().lower()
    return status not in {"", "idle", "arrived", "completed", "resolved", "cancelled"}


def _dialog_actor(context: "CampaignContext") -> Any:
    if not _dialog_is_active(context):
        return None
    runtime = getattr(context, "kernel_runtime", {}) or {}
    conversation = dict(getattr(context, "conversation_state", {}) or {})
    npc_id = str(runtime.get("dialog_npc_id") or conversation.get("npc_id") or "").strip()
    if not npc_id:
        return None
    return (runtime.get("actors") or {}).get(npc_id)


def _talkable_npc_names(context: "CampaignContext") -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for record in list((getattr(context, "entities", {}) or {}).values()):
        if not isinstance(record, dict):
            continue
        if str(record.get("type", "")).strip().lower() != "npc":
            continue
        actions = {str(item).strip().lower() for item in list(record.get("context_actions", []) or [])}
        if "talk" not in actions:
            continue
        name = str(record.get("name", "")).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _usable_item_ids(player: Any) -> list[str]:
    if player is None:
        return []
    from engine.api.gameplay_bridge import _runtime_item_is_usable_now, _runtime_item_source

    item_ids: list[str] = []
    seen: set[str] = set()
    for item in list(getattr(player, "inventory", []) or []):
        source = _runtime_item_source(item)
        if not _runtime_item_is_usable_now(item, source):
            continue
        item_id = str(getattr(item, "item_def_id", "") or source.get("item_def_id") or source.get("id") or "").strip()
        if item_id and item_id not in seen:
            seen.add(item_id)
            item_ids.append(item_id)
    return item_ids


def _current_region_id(context: "CampaignContext") -> str:
    if getattr(context, "region_snapshot", None) is not None:
        return str(context.region_snapshot.region_id)
    return ""


def _current_settlement_id(context: "CampaignContext") -> str:
    settlement_state = getattr(context, "settlement_state", {}) or {}
    return str(
        settlement_state.get("settlement_id")
        or settlement_state.get("site_id")
        or getattr(getattr(context, "region_snapshot", None), "metadata", {}).get("settlement_id", "")
        or ""
    ).strip()


def _current_settlement_name(context: "CampaignContext") -> str:
    settlement_state = getattr(context, "settlement_state", {}) or {}
    return str(
        settlement_state.get("name")
        or settlement_state.get("settlement_name")
        or settlement_state.get("center_name")
        or _current_settlement_id(context).replace("_", " ").title()
        or _current_region_id(context).replace("_", " ").title()
    ).strip()


def _normalize_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).strip()
    return re.sub(r"\s+", " ", collapsed)


def _limit_strings(values: Any, *, max_items: int) -> list[str]:
    limited: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        limited.append(normalized)
        if len(limited) >= max_items:
            break
    return limited


def _limit_topic_ids(values: Any, discovered: set[str], *, max_items: int) -> list[str]:
    limited: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        topic_id = str(value or "").strip()
        if not topic_id or topic_id in seen or topic_id not in discovered:
            continue
        seen.add(topic_id)
        limited.append(topic_id)
        if len(limited) >= max_items:
            break
    return limited


__all__ = [
    "build_advisor_view",
    "maybe_handle_advisor_command",
    "maybe_handle_structured_advisor_command",
]
