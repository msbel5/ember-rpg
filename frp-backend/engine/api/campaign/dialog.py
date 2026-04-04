"""Dialog payload bridge: authored kernel dialog authority for campaigns."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from engine.kernel.dialog import (
    DialogCondition,
    DialogDef,
    DialogState,
    DialogTransition,
    evaluate_condition,
    get_available_transitions,
    start_dialog,
)

if TYPE_CHECKING:
    from engine.kernel.actor import ActorRecord
    from .context import CampaignContext

logger = logging.getLogger(__name__)

_ROLE_ALIASES: dict[str, str] = {
    "alchemist": "healer",
    "apothecary": "healer",
    "bard": "commoner",
    "baker": "merchant",
    "jailer": "guard",
    "mayor": "quest_giver",
    "priest": "healer",
    "quartermaster": "merchant",
    "researcher": "quest_giver",
    "sage": "quest_giver",
    "scholar": "quest_giver",
    "scribe": "quest_giver",
    "stablehand": "merchant",
    "warden": "guard",
    "witch": "healer",
}


def build_dialog_payload(context: "CampaignContext", narrative: str) -> dict[str, Any]:
    """Build dialog payload using kernel dialog authority.

    When a dialog is already active with the same NPC, reuse the current kernel
    state instead of restarting from the greeting node.
    """
    conversation = dict(context.conversation_state or {})
    if str(conversation.get("target_type", "")).strip() != "npc":
        return {}
    if context.in_combat():
        return {}

    npc_id = str(conversation.get("npc_id", "")).strip()
    npc_name = str(conversation.get("npc_name", "")).strip() or "NPC"
    from engine.api.campaign.party_bridge import allied_actor_ids

    if npc_id and npc_id in allied_actor_ids(context) and npc_id != "player":
        return {}

    player_actor = _get_player_actor(context)
    npc_actor = _get_npc_actor(context, npc_id, npc_name)
    if player_actor is None or npc_actor is None:
        logger.debug("Dialog skipped: kernel actors unavailable for %s", npc_id)
        return {}

    dialog_def = _resolve_dialog_def(context, npc_id, npc_name, npc_actor)
    if dialog_def is None:
        logger.debug("Dialog skipped: no authored dialog for %s", npc_id or npc_name)
        return {}
    runtime = context.kernel_runtime or {}
    global_vars = _global_variables(context)
    dialog_state, state_node, transitions = _current_or_start_state(
        context=context,
        dialog_def=dialog_def,
        player_actor=player_actor,
        npc_actor=npc_actor,
        npc_id=npc_id,
        global_vars=global_vars,
    )
    if dialog_state is None or state_node is None:
        return {}

    store_dialog_state(context, dialog_state, dialog_def, npc_actor)
    dialog_text = str(state_node.text or narrative or f"{npc_name} studies you in silence.").strip()
    options = _transitions_to_options(state_node.transitions, player_actor, npc_actor, dialog_state.variables, global_vars)
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
        normalized_roles = [role.lower()]
        alias = _ROLE_ALIASES.get(role.lower())
        if alias and alias not in normalized_roles:
            normalized_roles.append(alias)
        for candidate_role in normalized_roles:
            for def_data in registry.values():
                if str(def_data.get("role", "")).lower() == candidate_role:
                    logger.debug("Dialog: role-based match '%s' for NPC '%s'", candidate_role, npc_id)
                    return _dialog_def_from_data(def_data)
    return None


def _dialog_def_from_data(raw: dict) -> DialogDef:
    """Build DialogDef from registry data, stripping non-schema fields like role."""
    clean = {k: v for k, v in raw.items() if k in DialogDef.__dataclass_fields__}
    return DialogDef.from_dict(clean)


def _extract_npc_role(
    context: "CampaignContext",
    npc_id: str,
    npc_name: str,
    npc_actor: "ActorRecord",
) -> str:
    """Get the role string for an NPC from kernel runtime."""
    del context, npc_id, npc_name
    raw_payload = getattr(npc_actor, "raw_payload", {})
    for key in ("role", "template", "legacy_job"):
        value = str(raw_payload.get(key, "")).strip()
        if value:
            return value
    return ""


def _current_or_start_state(
    *,
    context: "CampaignContext",
    dialog_def: DialogDef,
    player_actor: "ActorRecord",
    npc_actor: "ActorRecord",
    npc_id: str,
    global_vars: dict[str, Any],
) -> tuple[DialogState | None, Any, list[DialogTransition]]:
    runtime = context.kernel_runtime or {}
    existing_state = runtime.get("dialog_state")
    existing_npc_id = str(runtime.get("dialog_npc_id", "")).strip()
    if (
        isinstance(existing_state, DialogState)
        and existing_state.active
        and existing_state.dialog_id == dialog_def.dialog_id
        and existing_npc_id == (npc_id or getattr(npc_actor.identity, "actor_id", ""))
    ):
        state_node = _state_by_id(dialog_def, existing_state.current_state_id)
        if state_node is not None:
            transitions = get_available_transitions(
                state_node,
                player_actor,
                npc_actor,
                existing_state.variables,
                global_vars,
            )
            return existing_state, state_node, transitions
        clear_dialog_state(context)

    try:
        dialog_state, state_node, transitions = start_dialog(
            dialog_def,
            npc_actor,
            player_actor,
            global_vars,
        )
    except (ValueError, KeyError) as exc:
        logger.debug("Dialog start failed for %s: %s — no fallback", npc_id, exc)
        return None, None, []
    return dialog_state, state_node, transitions


def _state_by_id(dialog_def: DialogDef, state_id: str) -> Any:
    for state in dialog_def.states:
        if state.state_id == state_id:
            return state
    return None


# ---------------------------------------------------------------------------
# Transition → client option conversion
# ---------------------------------------------------------------------------

def _transitions_to_options(
    transitions: list[DialogTransition],
    player: "ActorRecord",
    npc: "ActorRecord",
    variables: dict[str, Any],
    global_vars: dict[str, Any],
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for transition in transitions:
        enabled = True
        disabled_reason = ""
        if transition.condition is not None:
            enabled = evaluate_condition(transition.condition, player, npc, variables, global_vars)
            if not enabled:
                disabled_reason = _condition_reason(transition.condition, player, variables, global_vars)
        options.append(
            {
                "text": transition.text,
                "command": f"dialog {transition.transition_id}",
                "transition_id": transition.transition_id,
                "available": enabled,
                "enabled": enabled,
                "disabled_reason": disabled_reason,
                "skill_check": _extract_skill_check(transition.condition, player) if transition.condition else {},
                "hostile": transition.hostile,
            }
        )
    return options


def _extract_skill_check(condition: DialogCondition, player: "ActorRecord") -> dict[str, Any]:
    if condition.condition_type == "stat_check":
        stat = str(condition.params.get("stat", ""))
        required = int(condition.params.get("value", 0))
        current = int(player.stats.get(stat, 0))
        return {"ability": stat, "required": required, "current": current, "label": f"{stat} {required}"}
    if condition.condition_type == "skill_check":
        skill = str(condition.params.get("skill", ""))
        required = int(condition.params.get("value", 0))
        current = int(player.skills.get(skill, 0))
        return {"skill": skill, "required": required, "current": current, "label": f"{skill} {required}"}
    return {}


def _condition_reason(
    condition: DialogCondition,
    player: "ActorRecord",
    variables: dict[str, Any],
    global_vars: dict[str, Any],
) -> str:
    if condition.condition_type == "stat_check":
        stat = str(condition.params.get("stat", ""))
        required = int(condition.params.get("value", 0))
        current = int(player.stats.get(stat, 0))
        if current < required:
            return f"Requires {stat} {required} (current {current})."
    if condition.condition_type == "skill_check":
        skill = str(condition.params.get("skill", ""))
        required = int(condition.params.get("value", 0))
        current = int(player.skills.get(skill, 0))
        if current < required:
            return f"Requires {skill} {required} (current {current})."
    if condition.condition_type == "variable_check":
        scope = str(condition.params.get("scope", "local")).lower()
        name = str(condition.params.get("name", "state"))
        store = global_vars if scope == "global" else variables
        return f"Requires {scope} variable {name} to match the branch condition." if name not in store else "Condition not met."
    return "Condition not met."


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
    """Remove dialog state from kernel runtime and clear conversation targeting."""
    runtime = context.kernel_runtime
    if runtime is not None:
        runtime.pop("dialog_state", None)
        runtime.pop("dialog_npc_id", None)
    context.conversation_state = {
        "target_type": None,
        "npc_id": "",
        "npc_name": "",
    }


__all__ = ["build_dialog_payload", "clear_dialog_state", "store_dialog_state"]
