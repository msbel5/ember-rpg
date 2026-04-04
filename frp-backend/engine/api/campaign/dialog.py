"""Dialog payload bridge: authored kernel dialog authority for campaigns."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from engine.kernel.dialog import (
    DialogCondition,
    DialogDef,
    DialogState,
    DialogTransition,
    start_dialog,
)

if TYPE_CHECKING:
    from engine.kernel.actor import ActorRecord
    from .context import CampaignContext

logger = logging.getLogger(__name__)


def build_dialog_payload(context: "CampaignContext", narrative: str) -> dict[str, Any]:
    """Build dialog payload using kernel dialog authority."""
    conversation = dict(context.conversation_state or {})
    if str(conversation.get("target_type", "")).strip() != "npc":
        return {}
    if context.in_combat():
        return {}

    npc_id = str(conversation.get("npc_id", "")).strip()
    npc_name = str(conversation.get("npc_name", "")).strip() or "NPC"

    player_actor = _get_player_actor(context)
    npc_actor = _get_npc_actor(context, npc_id, npc_name)
    if player_actor is None or npc_actor is None:
        logger.debug("Dialog skipped: kernel actors unavailable for %s", npc_id)
        return {}

    dialog_def = _resolve_dialog_def(context, npc_id, npc_name, npc_actor)
    if dialog_def is None:
        logger.debug("Dialog skipped: no authored dialog for %s", npc_id or npc_name)
        return {}
    global_vars = _global_variables(context)

    try:
        dialog_state, state_node, transitions = start_dialog(
            dialog_def, npc_actor, player_actor, global_vars,
        )
    except (ValueError, KeyError) as exc:
        logger.debug("Dialog start failed for %s: %s — no fallback", npc_id, exc)
        return {}

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
        display_name = str(getattr(getattr(actor, "identity", None), "display_name", "")).strip()
        if display_name and display_name.lower() == npc_name.lower():
            return actor
    return None


# ---------------------------------------------------------------------------
# Dialog definition resolution
# ---------------------------------------------------------------------------

def _resolve_dialog_def(
    context: "CampaignContext",
    npc_id: str,
    npc_name: str,
    npc_actor: "ActorRecord",
) -> Optional[DialogDef]:
    """Look up an authored dialog def by NPC id or authored role."""
    from engine.data._shared import dialog_defs_registry
    registry = dialog_defs_registry()
    if npc_id and npc_id in registry:
        return _dialog_def_from_data(registry[npc_id])
    role = _extract_npc_role(context, npc_id, npc_name, npc_actor)
    if role:
        for def_data in registry.values():
            if str(def_data.get("role", "")).lower() == role.lower():
                logger.debug("Dialog: role-based match '%s' for NPC '%s'", role, npc_id)
                return _dialog_def_from_data(def_data)
    return None


def _dialog_def_from_data(raw: dict) -> DialogDef:
    """Build DialogDef from registry data, stripping non-schema fields like 'role'."""
    clean = {k: v for k, v in raw.items() if k in DialogDef.__dataclass_fields__}
    return DialogDef.from_dict(clean)


def _extract_npc_role(
    context: "CampaignContext",
    npc_id: str,
    npc_name: str,
    npc_actor: "ActorRecord",
) -> str:
    """Get the role string for an NPC from kernel runtime.

    Checks raw_payload keys: role, template, legacy_job (worldgen NPCs
    often use 'template' instead of 'role').
    """
    rp = getattr(npc_actor, "raw_payload", {})
    for key in ("role", "template", "legacy_job"):
        value = str(rp.get(key, "")).strip()
        if value:
            return value
    return ""


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
