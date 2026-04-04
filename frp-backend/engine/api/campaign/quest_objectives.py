"""Objective normalization and runtime sync for campaign quests."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext

_SUPPORTED_OBJECTIVE_TYPES = {"kill", "collect", "talk", "visit"}


def sync_runtime_objectives(context: "CampaignContext") -> bool:
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors") or {}
    player = actors.get("player")
    changed = False

    if player is not None:
        changed = _sync_collect_objectives(context, player.inventory) or changed
        changed = _sync_kill_objectives(context, actors) or changed

    changed = _sync_visit_objectives(context) or changed

    conversation = dict(context.conversation_state or {})
    if str(conversation.get("target_type", "")).strip() == "npc":
        changed = _sync_talk_objectives(
            context,
            npc_id=str(conversation.get("npc_id", "")).strip(),
            npc_name=str(conversation.get("npc_name", "")).strip(),
        ) or changed

    return changed


def normalize_objectives(raw_objectives: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_objective in list(raw_objectives or []):
        if not isinstance(raw_objective, dict):
            continue
        objective = copy.deepcopy(raw_objective)
        objective_type = str(
            objective.get("type")
            or objective.get("category")
            or objective.get("objective_type")
            or objective.get("kind")
            or ""
        ).strip().lower()
        required = max(1, int(objective.get("required", objective.get("target_count", objective.get("count", 1))) or 1))
        progress = max(0, int(objective.get("progress", 0)))
        matched_ids = [str(item) for item in list(objective.get("matched_ids", objective.get("seen_ids", [])) or []) if str(item)]
        objective["type"] = objective_type
        objective["required"] = required
        objective["progress"] = min(progress, required)
        objective["matched_ids"] = matched_ids
        objective["supported"] = objective_type in _SUPPORTED_OBJECTIVE_TYPES
        objective["completed"] = bool(objective.get("completed", False)) or objective["progress"] >= required
        normalized.append(objective)
    return normalized


def refresh_quest_progress(quest: dict[str, Any]) -> None:
    objectives = normalize_objectives(quest.get("objectives", []))
    quest["objectives"] = objectives
    if not objectives:
        quest["objectives_complete"] = True
        quest["report_ready"] = True
        return
    all_completed = all(bool(objective.get("completed")) for objective in objectives)
    quest["objectives_complete"] = all_completed
    quest["report_ready"] = all_completed


def quest_ready_to_report(quest: dict[str, Any]) -> bool:
    refresh_quest_progress(quest)
    return bool(quest.get("report_ready", False))


def objective_status_text(quest: dict[str, Any]) -> str:
    objectives = normalize_objectives(quest.get("objectives", []))
    if not objectives:
        return ""
    parts: list[str] = []
    for objective in objectives:
        label = str(objective.get("label") or objective.get("text") or objective.get("target") or objective.get("type") or "objective")
        parts.append(f"{label}: {int(objective.get('progress', 0))}/{int(objective.get('required', 1))}")
    return "Objectives: " + ", ".join(parts)


def _sync_collect_objectives(context: "CampaignContext", inventory: Iterable[Any]) -> bool:
    changed = False
    inventory_counts: dict[str, int] = {}
    for item in inventory:
        item_def_id = str(getattr(item, "item_def_id", "")).strip().lower()
        if not item_def_id:
            continue
        inventory_counts[item_def_id] = inventory_counts.get(item_def_id, 0) + max(1, int(getattr(item, "quantity", 1)))
    for quest in context.campaign_state.get("active_quests", []):
        objectives = normalize_objectives(quest.get("objectives", []))
        for objective in objectives:
            if objective.get("type") != "collect" or not objective.get("supported", False):
                continue
            target = _objective_target_key(objective)
            if not target:
                continue
            quantity = inventory_counts.get(target, 0)
            changed = _set_objective_progress(objective, quantity) or changed
        quest["objectives"] = objectives
        refresh_quest_progress(quest)
    return changed


def _sync_kill_objectives(context: "CampaignContext", actors: dict[str, Any]) -> bool:
    changed = False
    for quest in context.campaign_state.get("active_quests", []):
        objectives = normalize_objectives(quest.get("objectives", []))
        for objective in objectives:
            if objective.get("type") != "kill" or not objective.get("supported", False):
                continue
            matched_ids = set(objective.get("matched_ids", []))
            for actor_id, actor in actors.items():
                if actor_id == "player" or bool(getattr(actor, "alive", True)):
                    continue
                if actor_id in matched_ids:
                    continue
                if not _objective_matches_actor(objective, actor_id, actor):
                    continue
                matched_ids.add(actor_id)
                changed = True
            objective["matched_ids"] = sorted(matched_ids)
            changed = _set_objective_progress(objective, len(matched_ids)) or changed
        quest["objectives"] = objectives
        refresh_quest_progress(quest)
    return changed


def _sync_talk_objectives(context: "CampaignContext", *, npc_id: str, npc_name: str) -> bool:
    if not npc_id and not npc_name:
        return False
    changed = False
    target_key = npc_id or _normalized_name(npc_name)
    for quest in context.campaign_state.get("active_quests", []):
        objectives = normalize_objectives(quest.get("objectives", []))
        for objective in objectives:
            if objective.get("type") != "talk" or not objective.get("supported", False):
                continue
            if not _objective_matches_name(objective, npc_id, npc_name):
                continue
            matched_ids = set(objective.get("matched_ids", []))
            if target_key not in matched_ids:
                matched_ids.add(target_key)
                objective["matched_ids"] = sorted(matched_ids)
                changed = True
            changed = _set_objective_progress(objective, len(matched_ids)) or changed
        quest["objectives"] = objectives
        refresh_quest_progress(quest)
    return changed


def _sync_visit_objectives(context: "CampaignContext") -> bool:
    region_id = str(getattr(context.region_snapshot, "region_id", "")).strip()
    settlement_id = str(context.settlement_state.get("settlement_id", "")).strip()
    settlement_name = str(context.settlement_state.get("name", "")).strip()
    location = str(getattr(getattr(context, "dm_context", None), "location", "")).strip()
    if not any((region_id, settlement_id, settlement_name, location)):
        return False
    changed = False
    visit_targets = {key for key in {region_id, settlement_id, _normalized_name(settlement_name), _normalized_name(location)} if key}
    for quest in context.campaign_state.get("active_quests", []):
        objectives = normalize_objectives(quest.get("objectives", []))
        for objective in objectives:
            if objective.get("type") != "visit" or not objective.get("supported", False):
                continue
            target = _objective_target_key(objective)
            if target not in visit_targets:
                continue
            matched_ids = set(objective.get("matched_ids", []))
            if target not in matched_ids:
                matched_ids.add(target)
                objective["matched_ids"] = sorted(matched_ids)
                changed = True
            changed = _set_objective_progress(objective, 1) or changed
        quest["objectives"] = objectives
        refresh_quest_progress(quest)
    return changed


def _objective_target_key(objective: dict[str, Any]) -> str:
    for key in ("item_def_id", "item_id", "target_id", "npc_id", "actor_id", "region_id", "site_id", "settlement_id", "target"):
        value = str(objective.get(key, "")).strip().lower()
        if value:
            return value
    name = str(objective.get("name") or objective.get("location") or objective.get("label") or "").strip()
    return _normalized_name(name)


def _normalized_name(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _objective_matches_name(objective: dict[str, Any], npc_id: str, npc_name: str) -> bool:
    targets = {
        _objective_target_key(objective),
        _normalized_name(str(objective.get("npc_name", ""))),
        _normalized_name(str(objective.get("name", ""))),
    }
    candidate_ids = {_normalized_name(npc_id), _normalized_name(npc_name)}
    return bool({target for target in targets if target} & {candidate for candidate in candidate_ids if candidate})


def _objective_matches_actor(objective: dict[str, Any], actor_id: str, actor: Any) -> bool:
    objective_targets = {
        _objective_target_key(objective),
        _normalized_name(str(getattr(getattr(actor, "identity", None), "display_name", ""))),
    }
    actor_targets = {
        _normalized_name(actor_id),
        _normalized_name(str(getattr(getattr(actor, "identity", None), "display_name", ""))),
        _normalized_name(str(getattr(actor, "raw_payload", {}).get("role", ""))),
        _normalized_name(str(getattr(actor, "raw_payload", {}).get("template", ""))),
    }
    return bool({target for target in objective_targets if target} & {candidate for candidate in actor_targets if candidate})


def _set_objective_progress(objective: dict[str, Any], progress: int) -> bool:
    required = max(1, int(objective.get("required", 1)))
    next_progress = min(max(0, int(progress)), required)
    changed = next_progress != int(objective.get("progress", 0))
    objective["progress"] = next_progress
    objective["completed"] = next_progress >= required
    return changed

