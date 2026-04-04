"""Quest state preservation helpers for campaign projection rebuilds."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext


def snapshot_quest_state(context: "CampaignContext") -> dict[str, Any]:
    return {
        "active_quests": copy.deepcopy(context.campaign_state.get("active_quests", [])),
        "completed_quest_ids": list(context.campaign_state.get("completed_quest_ids", [])),
        "failed_quest_ids": list(context.campaign_state.get("failed_quest_ids", [])),
        "quest_offers": copy.deepcopy(context.campaign_state.get("quest_offers", [])),
        "context_quest_offers": copy.deepcopy(getattr(context, "quest_offers", [])),
        "authored_campaigns": copy.deepcopy(context.campaign_state.get("authored_campaigns", {})),
        "authored_quest_offers": copy.deepcopy(context.campaign_state.get("authored_quest_offers", [])),
    }


def restore_quest_state(
    context: "CampaignContext",
    snapshot: dict[str, Any],
    *,
    preserve_offers: bool,
) -> None:
    if not snapshot:
        return
    context.campaign_state["active_quests"] = copy.deepcopy(snapshot.get("active_quests", []))
    context.campaign_state["completed_quest_ids"] = sorted(
        {str(item) for item in snapshot.get("completed_quest_ids", []) if str(item)}
    )
    context.campaign_state["failed_quest_ids"] = sorted(
        {str(item) for item in snapshot.get("failed_quest_ids", []) if str(item)}
    )
    context.campaign_state["authored_campaigns"] = copy.deepcopy(snapshot.get("authored_campaigns", {}))
    context.campaign_state["authored_quest_offers"] = copy.deepcopy(snapshot.get("authored_quest_offers", []))
    if preserve_offers:
        offers = copy.deepcopy(snapshot.get("context_quest_offers") or snapshot.get("quest_offers", []))
        context.quest_offers = offers
        context.campaign_state["quest_offers"] = copy.deepcopy(offers)


__all__ = ["restore_quest_state", "snapshot_quest_state"]
