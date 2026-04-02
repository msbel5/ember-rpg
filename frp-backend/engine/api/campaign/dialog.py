"""Dialog payload helpers for campaign-first responses."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .context import CampaignContext


def build_dialog_payload(context: "CampaignContext", narrative: str) -> dict[str, Any]:
    session = context.session
    conversation = dict(session.conversation_state or {})
    if str(conversation.get("target_type", "")).strip() != "npc":
        return {}
    if session.in_combat():
        return {}

    npc_name = str(conversation.get("npc_name", "")).strip() or "NPC"
    player_stats = dict(getattr(session.player, "stats", {}) or {})
    pre = int(player_stats.get("PRE", 10))
    ins = int(player_stats.get("INS", 10))
    mig = int(player_stats.get("MIG", 10))

    opener = "Ask about available work" if session.quest_offers else "Ask about the local situation"
    options: list[dict[str, Any]] = [
        {
            "text": opener,
            "command": "ask about work",
            "available": True,
            "enabled": True,
            "disabled_reason": "",
            "skill_check": {},
        },
        {
            "text": "Probe for rumors",
            "command": "ask about rumors",
            "check": "INS 12",
            "available": ins >= 12,
            "enabled": ins >= 12,
            "disabled_reason": "" if ins >= 12 else "Requires INS 12",
            "skill_check": {"ability": "INS", "required": 12, "current": ins, "label": "INS 12"},
        },
        {
            "text": "Appeal for help",
            "command": f"persuade {npc_name}",
            "check": "PRE 12",
            "available": pre >= 12,
            "enabled": pre >= 12,
            "disabled_reason": "" if pre >= 12 else "Requires PRE 12",
            "skill_check": {"ability": "PRE", "required": 12, "current": pre, "label": "PRE 12"},
        },
        {
            "text": "Threaten for answers",
            "command": f"intimidate {npc_name}",
            "check": "MIG 11",
            "available": mig >= 11,
            "enabled": mig >= 11,
            "disabled_reason": "" if mig >= 11 else "Requires MIG 11",
            "skill_check": {"ability": "MIG", "required": 11, "current": mig, "label": "MIG 11"},
        },
    ]

    dialog_text = narrative.strip() or f"{npc_name} studies you in silence."
    return {
        "dialog_npc": npc_name,
        "dialog_text": dialog_text,
        "dialog_options": options,
    }


__all__ = ["build_dialog_payload"]
