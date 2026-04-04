"""Authored campaign loading and offer progression for campaign runtime."""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.data._shared import load_json_path

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


_CAMPAIGN_FILES = (
    "tutorial_campaign.json",
    "side_quest_campaign.json",
    "main_quest_campaign.json",
)
_AUTHORED_SOURCE = "authored_campaign"


@lru_cache(maxsize=1)
def load_authored_campaign_registry() -> dict[str, dict[str, Any]]:
    base_dir = Path(__file__).resolve().parents[3] / "data" / "campaigns"
    campaigns: dict[str, dict[str, Any]] = {}
    for filename in _CAMPAIGN_FILES:
        raw = load_json_path(base_dir / filename)
        if not isinstance(raw, dict):
            continue
        campaign = copy.deepcopy(raw)
        campaign_id = str(campaign.get("id") or Path(filename).stem).strip()
        if not campaign_id:
            continue
        campaign["id"] = campaign_id
        campaign["acts"] = [copy.deepcopy(act) for act in list(campaign.get("acts", [])) if isinstance(act, dict)]
        campaigns[campaign_id] = campaign
    return campaigns


def ensure_authored_campaign_state(context: "CampaignContext") -> dict[str, dict[str, Any]]:
    campaigns = load_authored_campaign_registry()
    state_root = context.campaign_state.setdefault("authored_campaigns", {})
    completed_quest_ids = {
        str(item)
        for item in list(context.campaign_state.get("completed_quest_ids", []))
        if str(item)
    }

    for campaign_id, campaign in campaigns.items():
        progress = dict(state_root.get(campaign_id, {})) if isinstance(state_root.get(campaign_id), dict) else {}
        completed_act_ids = {str(item) for item in list(progress.get("completed_act_ids", [])) if str(item)}
        for act in campaign.get("acts", []):
            if _quest_id(act) in completed_quest_ids:
                completed_act_ids.add(str(act.get("id", "")))
        ordered_ids = _ordered_act_ids(campaign, completed_act_ids)
        progress["campaign_id"] = campaign_id
        progress["completed_act_ids"] = ordered_ids
        progress["completed"] = bool(progress.get("completed")) or len(ordered_ids) >= len(list(campaign.get("acts", [])))
        state_root[campaign_id] = progress

    offers = []
    for offer in list(context.campaign_state.get("authored_quest_offers", []) or []):
        if not isinstance(offer, dict):
            continue
        canonical = resolve_authored_offer(str(offer.get("quest_id") or offer.get("id") or ""))
        if canonical is not None:
            offers.append(canonical)
    context.campaign_state["authored_quest_offers"] = _dedupe_offers(offers)
    return state_root


def refresh_authored_campaign_offers(context: "CampaignContext") -> list[dict[str, Any]]:
    campaigns = load_authored_campaign_registry()
    state_root = ensure_authored_campaign_state(context)
    claimed_ids = _claimed_quest_ids(context)
    offers_by_id: dict[str, dict[str, Any]] = {}

    for offer in list(context.campaign_state.get("authored_quest_offers", []) or []):
        quest_id = str(offer.get("quest_id") or offer.get("id") or "")
        if not quest_id or quest_id in claimed_ids:
            continue
        canonical = resolve_authored_offer(quest_id)
        if canonical is not None:
            offers_by_id[quest_id] = canonical

    player_level = _player_level(context)
    for campaign_id, campaign in campaigns.items():
        progress = state_root[campaign_id]
        if progress.get("completed"):
            continue
        candidate = _next_unlocked_offer(campaign, progress, claimed_ids, player_level)
        if candidate is None:
            progress["completed"] = len(progress.get("completed_act_ids", [])) >= len(list(campaign.get("acts", [])))
            continue
        candidate_id = str(candidate.get("quest_id", candidate.get("id", "")))
        if candidate_id and candidate_id not in offers_by_id and candidate_id not in claimed_ids:
            offers_by_id[candidate_id] = candidate

    offers = sorted(offers_by_id.values(), key=_offer_sort_key)
    context.campaign_state["authored_quest_offers"] = copy.deepcopy(offers)
    return copy.deepcopy(offers)


def resolve_authored_offer(quest_id: str) -> dict[str, Any] | None:
    normalized = str(quest_id).strip()
    if not normalized:
        return None
    for campaign in load_authored_campaign_registry().values():
        for act in campaign.get("acts", []):
            if _quest_id(act) != normalized:
                continue
            return _offer_from_act(campaign, act)
    return None


def remove_authored_offer(context: "CampaignContext", quest_id: str) -> None:
    normalized = str(quest_id).strip()
    offers = [
        copy.deepcopy(offer)
        for offer in list(context.campaign_state.get("authored_quest_offers", []) or [])
        if str(offer.get("quest_id") or offer.get("id") or "") != normalized
    ]
    context.campaign_state["authored_quest_offers"] = offers


def mark_authored_act_completed(context: "CampaignContext", quest: dict[str, Any]) -> None:
    campaign_id = str(quest.get("campaign_id") or "").strip()
    act_id = str(quest.get("act_id") or "").strip()
    if not campaign_id or not act_id:
        resolved = _resolve_act_for_quest_id(str(quest.get("quest_id", quest.get("id", ""))))
        if resolved is None:
            return
        campaign_id, act = resolved
        act_id = str(act.get("id", "")).strip()
    campaign = load_authored_campaign_registry().get(campaign_id)
    if campaign is None or not act_id:
        return

    state_root = ensure_authored_campaign_state(context)
    progress = state_root.setdefault(campaign_id, {"campaign_id": campaign_id, "completed_act_ids": [], "completed": False})
    completed_ids = {str(item) for item in list(progress.get("completed_act_ids", [])) if str(item)}
    completed_ids.add(act_id)
    progress["completed_act_ids"] = _ordered_act_ids(campaign, completed_ids)
    progress["completed"] = len(progress["completed_act_ids"]) >= len(list(campaign.get("acts", [])))
    remove_authored_offer(context, str(quest.get("quest_id", quest.get("id", ""))))
    refresh_authored_campaign_offers(context)


def is_authored_quest(offer_or_quest: dict[str, Any]) -> bool:
    return str(offer_or_quest.get("source", "")).strip().lower() == _AUTHORED_SOURCE


def _resolve_act_for_quest_id(quest_id: str) -> tuple[str, dict[str, Any]] | None:
    normalized = str(quest_id).strip()
    if not normalized:
        return None
    for campaign_id, campaign in load_authored_campaign_registry().items():
        for act in campaign.get("acts", []):
            if _quest_id(act) == normalized:
                return campaign_id, copy.deepcopy(act)
    return None


def _offer_from_act(campaign: dict[str, Any], act: dict[str, Any]) -> dict[str, Any]:
    quest_id = _quest_id(act)
    return {
        "id": quest_id,
        "quest_id": quest_id,
        "title": str(act.get("name", quest_id.replace("_", " ").title())),
        "description": str(act.get("description", campaign.get("description", ""))),
        "objectives": copy.deepcopy(act.get("objectives", [])),
        "rewards": copy.deepcopy(act.get("rewards", [])),
        "reward_gold": int(act.get("reward_gold", 0) or 0),
        "reward_xp": int(act.get("reward_xp", 0) or 0),
        "deadline": act.get("deadline"),
        "status": "available",
        "source": _AUTHORED_SOURCE,
        "campaign_id": str(campaign.get("id", "")),
        "act_id": str(act.get("id", "")),
        "recommended_level": int(campaign.get("recommended_level", 1) or 1),
    }


def _quest_id(act: dict[str, Any]) -> str:
    return str(act.get("quest_id") or act.get("id") or "").strip()


def _ordered_act_ids(campaign: dict[str, Any], act_ids: set[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for act in campaign.get("acts", []):
        act_id = str(act.get("id", "")).strip()
        if not act_id or act_id not in act_ids or act_id in seen:
            continue
        seen.add(act_id)
        ordered.append(act_id)
    return ordered


def _next_unlocked_offer(
    campaign: dict[str, Any],
    progress: dict[str, Any],
    claimed_ids: set[str],
    player_level: int,
) -> dict[str, Any] | None:
    acts = list(campaign.get("acts", []))
    if not acts:
        return None
    completed_act_ids = {str(item) for item in list(progress.get("completed_act_ids", [])) if str(item)}
    candidate: dict[str, Any] | None = None
    if not completed_act_ids:
        recommended_level = int(campaign.get("recommended_level", 1) or 1)
        if recommended_level <= player_level + 1:
            candidate = acts[0]
    else:
        for act in acts:
            if str(act.get("id", "")) not in completed_act_ids:
                candidate = act
                break
    if candidate is None:
        return None
    quest_id = _quest_id(candidate)
    if not quest_id or quest_id in claimed_ids:
        return None
    return _offer_from_act(campaign, candidate)


def _player_level(context: "CampaignContext") -> int:
    level = 1
    if getattr(context, "player", None) is not None:
        level = int(getattr(context.player, "level", 1) or context.player.raw_payload.get("level", 1) or 1)
        level = max(level, int(context.player.raw_payload.get("level", level) or level))
    return max(1, level)


def _claimed_quest_ids(context: "CampaignContext") -> set[str]:
    return {
        *{str(item.get("quest_id", item.get("id", ""))) for item in context.campaign_state.get("active_quests", [])},
        *{str(item) for item in context.campaign_state.get("completed_quest_ids", [])},
        *{str(item) for item in context.campaign_state.get("failed_quest_ids", [])},
    }


def _dedupe_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for offer in offers:
        quest_id = str(offer.get("quest_id") or offer.get("id") or "")
        if quest_id:
            unique[quest_id] = copy.deepcopy(offer)
    return sorted(unique.values(), key=_offer_sort_key)


def _offer_sort_key(offer: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(offer.get("recommended_level", 0) or 0),
        str(offer.get("campaign_id", "")),
        str(offer.get("act_id", "")),
    )


__all__ = [
    "ensure_authored_campaign_state",
    "is_authored_quest",
    "load_authored_campaign_registry",
    "mark_authored_act_completed",
    "refresh_authored_campaign_offers",
    "remove_authored_offer",
    "resolve_authored_offer",
]
