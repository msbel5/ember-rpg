"""Dialog payload bridge: kernel dialog authority for campaign responses.

Replaces the old synthetic overlay with the kernel dialog state machine.
If an NPC has a DialogDef, we use it. Otherwise we generate a default
dialog tree driven by actual kernel conditions (stat checks, quest state).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from engine.kernel.dialog import (
    DialogAction,
    DialogCondition,
    DialogDef,
    DialogState,
    DialogStateNode,
    DialogTransition,
    get_available_transitions,
    start_dialog,
)

if TYPE_CHECKING:
    from engine.kernel.actor import ActorRecord
    from .context import CampaignContext

logger = logging.getLogger(__name__)


def build_dialog_payload(context: "CampaignContext", narrative: str) -> dict[str, Any]:
    """Build dialog payload using kernel dialog authority."""
    session = context.session
    conversation = dict(session.conversation_state or {})
    if str(conversation.get("target_type", "")).strip() != "npc":
        return {}
    if session.in_combat():
        return {}

    npc_id = str(conversation.get("npc_id", "")).strip()
    npc_name = str(conversation.get("npc_name", "")).strip() or "NPC"

    player_actor = _get_player_actor(context)
    npc_actor = _get_npc_actor(context, npc_id, npc_name)
    if player_actor is None or npc_actor is None:
        return _fallback_payload(npc_name, narrative)

    dialog_def = _resolve_dialog_def(context, npc_id, npc_name)
    global_vars = _global_variables(context)

    try:
        dialog_state, state_node, transitions = start_dialog(
            dialog_def, npc_actor, player_actor, global_vars,
        )
    except (ValueError, KeyError) as exc:
        logger.debug("Dialog start failed for %s: %s", npc_id, exc)
        return _fallback_payload(npc_name, narrative)

    store_dialog_state(context, dialog_state, dialog_def, npc_actor)
    options = _transitions_to_options(transitions, player_actor, npc_actor, global_vars)
    dialog_text = narrative.strip() or state_node.text or f"{npc_name} studies you in silence."
    return {
        "dialog_npc": npc_name,
        "dialog_text": dialog_text,
        "dialog_options": options,
        "dialog_state": dialog_state.to_dict(),
    }


# ---------------------------------------------------------------------------
# Actor resolution
# ---------------------------------------------------------------------------

def _get_player_actor(context: "CampaignContext") -> "ActorRecord | None":
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    return actors.get("player")


def _get_npc_actor(context: "CampaignContext", npc_id: str, npc_name: str) -> "ActorRecord | None":
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    if npc_id and npc_id in actors:
        return actors[npc_id]
    for actor in actors.values():
        if getattr(actor.identity, "name", "") == npc_name:
            return actor
    return None


# ---------------------------------------------------------------------------
# Dialog definition resolution
# ---------------------------------------------------------------------------

def _resolve_dialog_def(context: "CampaignContext", npc_id: str, npc_name: str) -> DialogDef:
    """Look up NPC's dialog def from data, falling back to generated default."""
    from engine.data._shared import dialog_defs_registry
    registry = dialog_defs_registry()
    # Exact NPC ID match.
    if npc_id and npc_id in registry:
        return DialogDef.from_dict(registry[npc_id])
    # Role-based match: extract NPC role from kernel runtime.
    role = _extract_npc_role(context, npc_id)
    if role:
        for def_data in registry.values():
            if str(def_data.get("role", "")).lower() == role.lower():
                logger.debug("Dialog: role-based match '%s' for NPC '%s'", role, npc_id)
                return DialogDef.from_dict(def_data)
    return _default_dialog_def(npc_id or npc_name, npc_name, context)


def _extract_npc_role(context: "CampaignContext", npc_id: str) -> str:
    """Get the role string for an NPC from kernel runtime."""
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    actor = actors.get(npc_id)
    if actor is not None:
        return str(getattr(actor, "raw_payload", {}).get("role", ""))
    return ""


def _default_dialog_def(npc_id: str, npc_name: str, context: "CampaignContext") -> DialogDef:
    """Generate a kernel-authoritative default dialog tree for generic NPCs."""
    has_quests = bool(context.session.quest_offers)
    opener = "Ask about available work" if has_quests else "Ask about the local situation"
    return DialogDef(
        dialog_id=f"default_{npc_id}",
        npc_id=npc_id,
        states=[DialogStateNode(
            state_id="greeting",
            text=f"{npc_name} regards you.",
            transitions=[
                DialogTransition(
                    transition_id="ask_work", text=opener,
                    next_state_id="farewell",
                    actions=[DialogAction("set_variable", {"name": "asked_work", "value": True})],
                ),
                DialogTransition(
                    transition_id="probe_rumors", text="Probe for rumors",
                    condition=DialogCondition("stat_check", {"stat": "INS", "operator": ">=", "value": 12}),
                    next_state_id="farewell",
                ),
                DialogTransition(
                    transition_id="persuade", text="Appeal for help",
                    condition=DialogCondition("stat_check", {"stat": "PRE", "operator": ">=", "value": 12}),
                    next_state_id="farewell",
                ),
                DialogTransition(
                    transition_id="intimidate", text="Threaten for answers",
                    condition=DialogCondition("stat_check", {"stat": "MIG", "operator": ">=", "value": 11}),
                    next_state_id="farewell",
                ),
                DialogTransition(
                    transition_id="leave", text="Leave", terminates=True,
                ),
            ],
        ), DialogStateNode(
            state_id="farewell",
            text=f"{npc_name} nods.",
            transitions=[DialogTransition(transition_id="done", text="Farewell", terminates=True)],
        )],
    )


# ---------------------------------------------------------------------------
# Transition → client option conversion
# ---------------------------------------------------------------------------

def _transitions_to_options(
    transitions: list[DialogTransition],
    player: "ActorRecord",
    npc: "ActorRecord",
    global_vars: dict[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for t in transitions:
        skill_check = _extract_skill_check(t.condition, player) if t.condition else {}
        options.append({
            "text": t.text,
            "command": f"dialog {t.transition_id}",
            "transition_id": t.transition_id,
            "available": True,
            "enabled": True,
            "disabled_reason": "",
            "skill_check": skill_check,
            "hostile": t.hostile,
        })
    return options


def _extract_skill_check(condition: DialogCondition, player: "ActorRecord") -> dict[str, Any]:
    if condition.condition_type == "stat_check":
        stat = str(condition.params.get("stat", ""))
        required = int(condition.params.get("value", 0))
        current = int(player.stats.get(stat, 0))
        return {"ability": stat, "required": required, "current": current, "label": f"{stat} {required}"}
    return {}


def _global_variables(context: "CampaignContext") -> dict[str, Any]:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    if game_state is not None:
        return dict(getattr(game_state, "global_variables", {}))
    return {}


def _fallback_payload(npc_name: str, narrative: str) -> dict[str, Any]:
    return {
        "dialog_npc": npc_name,
        "dialog_text": narrative.strip() or f"{npc_name} studies you in silence.",
        "dialog_options": [
            {"text": "Ask about the local situation", "command": "ask about work",
             "available": True, "enabled": True, "disabled_reason": "", "skill_check": {}},
            {"text": "Leave", "command": "leave", "available": True, "enabled": True,
             "disabled_reason": "", "skill_check": {}},
        ],
    }


def store_dialog_state(
    context: "CampaignContext",
    dialog_state: DialogState,
    dialog_def: DialogDef,
    npc_actor: "ActorRecord",
) -> None:
    """Persist dialog state into kernel runtime for later transition selection."""
    runtime = context.kernel_runtime
    if runtime is None:
        return
    runtime["dialog_state"] = dialog_state
    runtime.setdefault("dialog_defs", {})[dialog_def.dialog_id] = dialog_def
    runtime["dialog_npc_id"] = getattr(npc_actor.identity, "actor_id", "")


def clear_dialog_state(context: "CampaignContext") -> None:
    """Remove dialog state from kernel runtime."""
    runtime = context.kernel_runtime
    if runtime is None:
        return
    runtime.pop("dialog_state", None)
    runtime.pop("dialog_npc_id", None)


__all__ = ["build_dialog_payload", "store_dialog_state", "clear_dialog_state"]
