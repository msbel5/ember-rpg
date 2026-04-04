"""Quest and journal integration for the campaign runtime."""
from __future__ import annotations

import copy
import logging
import re
from typing import TYPE_CHECKING, Any, Iterable, Optional

from engine.api.campaign.quest_objectives import (
    normalize_objectives,
    objective_status_text,
    quest_ready_to_report,
    refresh_quest_progress,
    sync_runtime_objectives as sync_objectives,
)
from engine.kernel.game_state import add_journal_entry, modify_reputation

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext

logger = logging.getLogger(__name__)

_ACCEPT_RE = re.compile(r"^(?:accept(?:\s+quest)?|take\s+quest)\s+(.+)$", re.IGNORECASE)
_REPORT_RE = re.compile(r"^(?:report|complete|turn\s+in)(?:\s+quest)?\s+(.+)$", re.IGNORECASE)
_QUESTS_RE = re.compile(r"^(?:quests|journal)$", re.IGNORECASE)


def maybe_handle_quest_command(context: "CampaignContext", command_text: str) -> Optional[tuple[str, str, int]]:
    text = command_text.strip()
    match = _ACCEPT_RE.match(text)
    if match:
        return _accept_quest(context, match.group(1).strip())
    match = _REPORT_RE.match(text)
    if match:
        return _report_quest(context, match.group(1).strip())
    if _QUESTS_RE.match(text):
        return (_journal_summary(context), "quest", 0)
    return None


def apply_dialog_events(context: "CampaignContext", events: Iterable[dict[str, Any]]) -> list[str]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    player = (runtime.get("actors") or {}).get("player")
    if game_state is None or player is None:
        return []

    summaries: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "")).strip().lower()
        if event_type == "set_reputation":
            delta = int(event.get("delta", 0))
            new_rep = modify_reputation(game_state, delta)
            game_state.global_variables["reputation"] = new_rep
            summaries.append(f"Reputation {'increased' if delta >= 0 else 'decreased'} to {new_rep}.")
            continue
        if event_type == "add_journal":
            text = str(event.get("text", "")).strip()
            quest_id = str(event.get("quest_id", "")).strip()
            if text:
                add_journal_entry(game_state, text, quest_id=quest_id)
                summaries.append(text)
            continue
        if event_type == "start_quest":
            quest_id = str(event.get("quest_id", "")).strip()
            quest = start_quest(context, quest_id)
            if quest is not None:
                summaries.append(f"Quest started: {quest.get('title', quest_id)}.")
            continue
        if event_type == "advance_quest":
            quest_id = str(event.get("quest_id", "")).strip()
            stage = str(event.get("stage", "")).strip() or "updated"
            quest = advance_quest(context, quest_id, stage)
            if quest is not None:
                add_journal_entry(game_state, f"{quest.get('title', quest_id)} advanced to {stage}.", quest_id=quest_id)
                summaries.append(f"Quest updated: {quest.get('title', quest_id)} ({stage}).")
            continue
        if event_type == "set_hostile":
            npc_id = str(event.get("npc_id", "")).strip()
            hostile_name = _mark_hostile(context, npc_id)
            if hostile_name:
                summaries.append(f"{hostile_name} turns hostile.")
            continue
        if event_type in {"give_item", "take_item"}:
            qty = int(event.get("quantity", 1))
            item_id = str(event.get("item_def_id", "item")).replace("_", " ")
            verb = "Received" if event_type == "give_item" else "Handed over"
            summaries.append(f"{verb} {qty}x {item_id}.")
            continue
        if event_type in {"give_gold", "take_gold", "give_xp"}:
            amount = int(event.get("amount", 0))
            label = {
                "give_gold": f"Received {amount} gold.",
                "take_gold": f"Spent {amount} gold.",
                "give_xp": f"Gained {amount} XP.",
            }[event_type]
            summaries.append(label)
            continue
        if event_type == "set_variable":
            if str(event.get("scope", "local")).lower() == "global":
                game_state.global_variables[str(event.get("name", ""))] = event.get("value")
            summaries.append(f"{event.get('name', 'State')} updated.")

    sync_quest_state(context)
    return summaries


def sync_runtime_objectives(context: "CampaignContext") -> None:
    if sync_objectives(context):
        sync_quest_state(context)


def start_quest(context: "CampaignContext", quest_id: str) -> Optional[dict[str, Any]]:
    if not quest_id:
        return None
    tracker = _ensure_tracker(context)
    existing = tracker.get_quest(quest_id)
    if existing is not None:
        sync_quest_state(context)
        return _active_quest_payload(context, existing.quest_id, existing.title, "active", existing.deadline_hour, "started")

    offer = _find_offer(context, quest_id) or {
        "id": quest_id,
        "quest_id": quest_id,
        "title": quest_id.replace("_", " ").title(),
        "description": "Authored quest accepted through dialog.",
        "reward_gold": 0,
        "reward_xp": 0,
        "deadline": None,
    }
    current_hour = _current_hour(context)
    tracker.add_quest(
        quest_id=str(offer.get("quest_id") or offer.get("id") or quest_id),
        title=str(offer.get("title", quest_id.replace("_", " ").title())),
        current_hour=current_hour,
        deadline_hour=_optional_float(offer.get("deadline")),
    )
    active_entry = copy.deepcopy(offer)
    active_entry.update(
        {
            "status": "active",
            "stage": "started",
            "accepted_hour": current_hour,
            "objectives": normalize_objectives(offer.get("objectives", [])),
        }
    )
    refresh_quest_progress(active_entry)
    _remove_offer(context, quest_id)
    context.campaign_state.setdefault("active_quests", []).append(active_entry)

    runtime = context.kernel_runtime or {}
    player = (runtime.get("actors") or {}).get("player")
    if player is not None:
        player.raw_payload.setdefault("quests", {})[quest_id] = "started"
    game_state = runtime.get("game_state")
    if game_state is not None:
        add_journal_entry(game_state, f"Accepted quest: {active_entry['title']}", quest_id=quest_id)

    sync_quest_state(context)
    return active_entry


def advance_quest(context: "CampaignContext", quest_id: str, stage: str) -> Optional[dict[str, Any]]:
    quest = _find_active_quest(context, quest_id) or start_quest(context, quest_id)
    if quest is None:
        return None
    quest["stage"] = stage
    refresh_quest_progress(quest)
    runtime = context.kernel_runtime or {}
    player = (runtime.get("actors") or {}).get("player")
    if player is not None:
        player.raw_payload.setdefault("quests", {})[str(quest.get("quest_id", quest.get("id", "")))] = stage
    sync_quest_state(context)
    return quest


def sync_quest_state(context: "CampaignContext") -> None:
    tracker = _ensure_tracker(context)
    stored_active = list(context.campaign_state.get("active_quests", []))
    active_entries: list[dict[str, Any]] = []

    for entry in tracker.get_active_quests():
        stored = next((item for item in stored_active if str(item.get("quest_id", item.get("id", ""))) == entry.quest_id), None)
        payload = _active_quest_payload(
            context,
            entry.quest_id,
            str(stored.get("title") if stored else entry.title),
            "active",
            (stored or {}).get("deadline", entry.deadline_hour),
            str((stored or {}).get("stage", "started")),
        )
        if stored:
            payload.update(
                {
                    "description": str(stored.get("description", payload.get("description", ""))),
                    "giver_name": str(stored.get("giver_name", "")),
                    "reward_gold": int(stored.get("reward_gold", 0)),
                    "reward_xp": int(stored.get("reward_xp", 0)),
                    "objectives": normalize_objectives(stored.get("objectives", [])),
                }
            )
        refresh_quest_progress(payload)
        active_entries.append(payload)

    context.campaign_state["active_quests"] = active_entries
    context.campaign_state["completed_quest_ids"] = sorted(set(context.campaign_state.get("completed_quest_ids", [])))
    context.campaign_state["failed_quest_ids"] = sorted(set(context.campaign_state.get("failed_quest_ids", [])))
    context.quest_offers = current_quest_offers(context)
    context.campaign_state["quest_offers"] = copy.deepcopy(context.quest_offers)


def current_quest_offers(context: "CampaignContext") -> list[dict[str, Any]]:
    region_offers = list((context.campaign_state or {}).get("quest_offers", []) or [])
    if not region_offers:
        region_offers = list(getattr(context, "quest_offers", []) or [])
    claimed_ids = {
        *{str(item.get("quest_id", item.get("id", ""))) for item in context.campaign_state.get("active_quests", [])},
        *{str(item) for item in context.campaign_state.get("completed_quest_ids", [])},
        *{str(item) for item in context.campaign_state.get("failed_quest_ids", [])},
    }
    return [copy.deepcopy(offer) for offer in region_offers if str(offer.get("quest_id", offer.get("id", ""))) not in claimed_ids]


def tick_quest_tracker(context: "CampaignContext") -> list[dict[str, Any]]:
    tracker = _ensure_tracker(context)
    result = tracker.tick(_current_hour(context))
    events: list[dict[str, Any]] = []

    for reminder in result.get("reminders", []):
        title = str(reminder.get("title", reminder.get("quest_id", "Quest")))
        events.append(
            {
                "event_type": "quest_reminder",
                "summary": f"Quest reminder: {title} has {int(float(reminder.get('hours_remaining', 0)))}h remaining.",
                "quest_id": str(reminder.get("quest_id", "")),
                "hours_remaining": float(reminder.get("hours_remaining", 0)),
            }
        )

    for expired in result.get("expired", []):
        quest_id = str(expired.get("quest_id", ""))
        title = str(expired.get("title", quest_id or "Quest"))
        context.campaign_state.setdefault("failed_quest_ids", [])
        if quest_id and quest_id not in context.campaign_state["failed_quest_ids"]:
            context.campaign_state["failed_quest_ids"].append(quest_id)

        runtime = context.kernel_runtime or {}
        player = (runtime.get("actors") or {}).get("player")
        if player is not None and quest_id:
            player.raw_payload.setdefault("quests", {})[quest_id] = "failed"
        context.campaign_state["active_quests"] = [
            quest for quest in context.campaign_state.get("active_quests", [])
            if str(quest.get("quest_id", quest.get("id", ""))) != quest_id
        ]
        events.append({"event_type": "quest_expired", "summary": f"Quest failed: {title} expired.", "quest_id": quest_id})

    if events:
        sync_quest_state(context)
    return events


def _accept_quest(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    offer = _find_offer(context, query)
    if offer is None:
        return (f"No available quest matched '{query}'.", "quest", 0)
    quest = start_quest(context, str(offer.get("quest_id") or offer.get("id") or query))
    if quest is None:
        return (f"Could not accept '{query}'.", "quest", 0)
    return (f"Accepted quest: {quest.get('title', query)}.", "quest", 0)


def _report_quest(context: "CampaignContext", query: str) -> tuple[str, str, int]:
    quest = _find_active_quest(context, query)
    if quest is None:
        completed_match = _match_completed_quest_id(context, query)
        if completed_match is not None:
            return (f"Quest '{completed_match}' has already been reported.", "quest", 0)
        return (f"No active quest matched '{query}'.", "quest", 0)
    if not quest_ready_to_report(quest):
        return (f"{quest.get('title', query)} is not ready to report yet. {objective_status_text(quest)}", "quest", 0)

    quest_id = str(quest.get("quest_id", quest.get("id", "")))
    tracker = _ensure_tracker(context)
    if tracker.get_quest(quest_id) is not None:
        tracker.complete_quest(quest_id, _current_hour(context))
    context.campaign_state.setdefault("completed_quest_ids", [])
    if quest_id and quest_id not in context.campaign_state["completed_quest_ids"]:
        context.campaign_state["completed_quest_ids"].append(quest_id)
    context.campaign_state["active_quests"] = [
        candidate for candidate in context.campaign_state.get("active_quests", [])
        if str(candidate.get("quest_id", candidate.get("id", ""))) != quest_id
    ]

    runtime = context.kernel_runtime or {}
    player = (runtime.get("actors") or {}).get("player")
    game_state = runtime.get("game_state")
    reward_gold = int(quest.get("reward_gold", 0))
    reward_xp = int(quest.get("reward_xp", 0))
    if player is not None:
        player.raw_payload["gold"] = int(player.raw_payload.get("gold", 0)) + reward_gold
        player.raw_payload["xp"] = int(player.raw_payload.get("xp", 0)) + reward_xp
        player.raw_payload.setdefault("quests", {})[quest_id] = "completed"
    if game_state is not None:
        add_journal_entry(game_state, f"Completed quest: {quest.get('title', quest_id)}", quest_id=quest_id, quest_stage=999)

    sync_quest_state(context)
    return (f"Completed quest: {quest.get('title', quest_id)}. Reward: {reward_gold} gold, {reward_xp} XP.", "quest", 0)


def _journal_summary(context: "CampaignContext") -> str:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    journal = getattr(game_state, "journal", []) if game_state is not None else []
    active = context.campaign_state.get("active_quests", [])
    lines: list[str] = []
    if active:
        lines.append("Active quests:")
        for quest in active[:8]:
            title = str(quest.get("title", quest.get("quest_id", quest.get("id", "Quest"))))
            lines.append(f"- {title} [{str(quest.get('stage', 'started'))}]")
    else:
        lines.append("No active quests.")
    if journal:
        lines.append("Recent journal:")
        for entry in journal[-5:]:
            lines.append(f"- {entry.text}")
    return "\n".join(lines)


def _find_offer(context: "CampaignContext", query: str) -> Optional[dict[str, Any]]:
    query_lower = query.lower().strip().replace("_", " ")
    for offer in current_quest_offers(context):
        quest_id = str(offer.get("quest_id", offer.get("id", ""))).lower().replace("_", " ")
        title = str(offer.get("title", "")).lower()
        if query_lower in {quest_id, title} or query_lower in title or query_lower in quest_id:
            return offer
    return None


def _find_active_quest(context: "CampaignContext", query: str) -> Optional[dict[str, Any]]:
    query_lower = query.lower().strip().replace("_", " ")
    for quest in context.campaign_state.get("active_quests", []):
        quest_id = str(quest.get("quest_id", quest.get("id", ""))).lower().replace("_", " ")
        title = str(quest.get("title", "")).lower()
        if query_lower in {quest_id, title} or query_lower in title or query_lower in quest_id:
            return quest
    return None


def _active_quest_payload(
    context: "CampaignContext",
    quest_id: str,
    title: str,
    status: str,
    deadline: Any,
    stage: str,
) -> dict[str, Any]:
    deadline_value = _optional_float(deadline)
    remaining = None if deadline_value is None else max(0, int(deadline_value - _current_hour(context)))
    return {
        "id": quest_id,
        "quest_id": quest_id,
        "title": title,
        "status": status,
        "stage": stage,
        "deadline": deadline_value,
        "hours_remaining": remaining,
        "objectives": [],
        "objectives_complete": False,
        "report_ready": False,
    }


def _match_completed_quest_id(context: "CampaignContext", query: str) -> str | None:
    query_lower = query.lower().strip().replace("_", " ")
    for quest_id in context.campaign_state.get("completed_quest_ids", []):
        normalized_id = str(quest_id).lower().replace("_", " ")
        if query_lower == normalized_id or query_lower in normalized_id:
            return str(quest_id)
    return None


def _remove_offer(context: "CampaignContext", quest_id: str) -> None:
    quest_id = str(quest_id)
    context.quest_offers = [offer for offer in context.quest_offers if str(offer.get("quest_id", offer.get("id", ""))) != quest_id]
    context.campaign_state["quest_offers"] = copy.deepcopy(context.quest_offers)


def _ensure_tracker(context: "CampaignContext"):
    if context.quest_tracker is None:
        from engine.world.quest_timeout import QuestTracker

        context.quest_tracker = QuestTracker()
    return context.quest_tracker


def _mark_hostile(context: "CampaignContext", npc_id: str) -> str:
    runtime = context.kernel_runtime or {}
    actor = (runtime.get("actors") or {}).get(npc_id)
    if actor is not None:
        actor.raw_payload["hostile"] = True
        actor.raw_payload["legacy_disposition"] = "hostile"
        actor.raw_payload["legacy_attitude"] = "hostile"
    record = context.entities.get(npc_id)
    if isinstance(record, dict):
        record["attitude"] = "hostile"
        entity_ref = record.get("entity_ref")
        if entity_ref is not None:
            entity_ref.disposition = "hostile"
            entity_ref.attitude = "hostile"
        return str(record.get("name", npc_id))
    return actor.identity.display_name if actor is not None else ""


def _current_hour(context: "CampaignContext") -> float:
    snapshot = getattr(getattr(context, "world", None), "simulation_snapshot", None)
    if snapshot is not None:
        return float(getattr(snapshot, "current_hour", 0))
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is not None:
        ticks_per_hour = max(1, getattr(game_state.world_time, "ticks_per_hour", 100))
        return float(getattr(game_state.world_time, "game_tick", 0) / ticks_per_hour)
    return 0.0


def _optional_float(value: Any) -> float | None:
    return None if value in (None, "", False) else float(value)


__all__ = [
    "apply_dialog_events",
    "current_quest_offers",
    "maybe_handle_quest_command",
    "start_quest",
    "sync_quest_state",
    "sync_runtime_objectives",
    "tick_quest_tracker",
]
