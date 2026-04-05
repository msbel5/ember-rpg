"""Command dispatch and world-tick advancement for campaign runtime.

Extracted from runtime.py to keep files under 450 lines.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Optional

from engine.api.campaign.debug_trace import snapshot_hash, trace_event
from engine.api.campaign.dialog import build_dialog_payload
from engine.api.campaign.live_kernel import advance_kernel_runtime
from engine.api.campaign.persistence import campaign_payload, persist_campaign_state
from engine.api.campaign.quest_bridge import (
    maybe_handle_quest_command,
    sync_quest_state,
    sync_runtime_objectives,
    tick_quest_tracker,
)
from engine.api.campaign.quest_state import restore_quest_state, snapshot_quest_state
from engine.api.campaign.party_bridge import maybe_handle_party_command
from engine.api.campaign.state_sync import sync_context_clock
from engine.api.campaign.region_projection import apply_region_to_context, persist_projected_npc_state
from engine.api.campaign.settlement import build_settlement_state
from engine.api.campaign.controls import merge_settlement_controls
from engine.api.campaign.world import alerts_from_events
from engine.api.campaign_commands import (
    handle_travel,
    maybe_handle_commander_command,
    maybe_handle_commerce_command,
    maybe_handle_dialog_command,
    maybe_handle_medical_command,
    maybe_handle_talk_command,
    resolve_command_text,
)
from engine.api.exploration_bridge import (
    maybe_handle_look_command,
    maybe_handle_examine_command,
    maybe_handle_move_command,
    maybe_handle_scene_verb_command,
)
from engine.worldgen import realize_region, tick_global

from .context import CampaignContext

logger = logging.getLogger(__name__)


def run_command(
    context: CampaignContext,
    input_text: str,
    shortcut: Optional[str] = None,
    args: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Dispatch a player command, tick the world, and return the result."""
    command_args = dict(args or {})
    issued = resolve_command_text(input_text=input_text, shortcut=shortcut, args=command_args)
    pre_hash = snapshot_hash(campaign_payload(context))
    trace_event(
        "campaign_command_input",
        campaign_id=context.campaign_id,
        command_text=issued,
        shortcut=str(shortcut or ""),
        pre_snapshot_hash=pre_hash,
    )
    narrative, command_type, hours_advanced = _dispatch(context, issued, command_args)
    pending_dialog_payload = (context.kernel_runtime or {}).pop("_pending_dialog_payload", None)
    _advance_world(context, command_type, hours_advanced, issued)
    # Dialog payload: use pre-built payload from talk handler if available, otherwise build fresh.
    runtime = context.kernel_runtime or {}
    dialog_payload = pending_dialog_payload or runtime.pop("_pending_dialog_payload", None) or (
        build_dialog_payload(context, narrative) if command_type == "dialog" else {}
    )
    final_payload = campaign_payload(context)
    trace_event(
        "campaign_command_output",
        campaign_id=context.campaign_id,
        command_text=issued,
        command_type=command_type,
        pre_snapshot_hash=pre_hash,
        post_snapshot_hash=snapshot_hash(final_payload),
    )
    return {
        "campaign_id": context.campaign_id,
        "narrative": narrative,
        "command_type": command_type,
        "hours_advanced": hours_advanced,
        "generated_events": list(context.recent_event_log[-20:]),
        "campaign": final_payload,
        **dialog_payload,
    }


def advance_world_tick(context: CampaignContext, hours: int = 1) -> list[dict[str, Any]]:
    """Run a world tick without a player command (idle tick)."""
    return _advance_world(context, command_type="idle", hours_advanced=hours, command_text="")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dispatch(
    context: CampaignContext,
    issued: str,
    command_args: dict[str, Any],
) -> tuple[str, str, int]:
    """Route command text to the correct handler. Returns (narrative, type, hours)."""
    lower = issued.lower().strip()
    from engine.api.combat_bridge import maybe_handle_combat_command  # noqa: E402

    if context.in_combat():
        combat = maybe_handle_combat_command(context, issued)
        if combat is not None:
            return combat
        return ("You are in combat. Use attack, defend, or flee before doing anything else.", "combat", 0)

    dialog = maybe_handle_dialog_command(context, issued)
    if dialog is not None:
        return dialog

    talk = maybe_handle_talk_command(context, issued)
    if talk is not None:
        return talk

    combat = maybe_handle_combat_command(context, issued)
    if combat is not None:
        return combat

    quest = maybe_handle_quest_command(context, issued)
    if quest is not None:
        return quest

    party = maybe_handle_party_command(context, issued)
    if party is not None:
        return party

    commerce = maybe_handle_commerce_command(context, issued)
    if commerce is not None:
        return commerce

    medical = maybe_handle_medical_command(context, issued)
    if medical is not None:
        return medical

    from engine.api.gameplay_bridge import (  # noqa: E402
        maybe_handle_craft_command,
        maybe_handle_equipment_command,
        maybe_handle_inventory_command,
        maybe_handle_item_use_command,
        maybe_handle_progression_command,
        maybe_handle_rest_command,
        maybe_handle_spell_command,
    )

    progression = maybe_handle_progression_command(context, issued)
    if progression is not None:
        return progression
    equipment = maybe_handle_equipment_command(context, issued)
    if equipment is not None:
        return equipment
    inventory = maybe_handle_inventory_command(context, issued)
    if inventory is not None:
        return inventory
    item_use = maybe_handle_item_use_command(context, issued)
    if item_use is not None:
        return item_use
    craft = maybe_handle_craft_command(context, issued)
    if craft is not None:
        return craft
    rest = maybe_handle_rest_command(context, issued)
    if rest is not None:
        return rest
    spell = maybe_handle_spell_command(context, issued)
    if spell is not None:
        return spell

    look = maybe_handle_look_command(context, issued)
    if look is not None:
        return look
    examine = maybe_handle_examine_command(context, issued)
    if examine is not None:
        return examine
    move_result = maybe_handle_move_command(context, issued)
    if move_result is not None:
        return move_result
    scene = maybe_handle_scene_verb_command(context, issued)
    if scene is not None:
        return scene

    handled = maybe_handle_commander_command(context, issued)
    if handled is not None:
        return handled

    if lower.startswith("travel"):
        narrative = handle_travel(context, issued, command_args)
        hours = int(context.campaign_state.get("last_travel_hours", 4))
        return narrative, "travel", hours

    logger.warning("Unknown command rejected: %s", issued[:80])
    return (
        f"Unknown command: '{issued}'. Try: attack, cast, use, equip, craft, rest, "
        f"travel, train, proficiency, raise, buy, sell, diagnose, dialog, recruit, quests, or world interaction controls.",
        "unknown",
        0,
    )


def _advance_world(
    context: CampaignContext,
    command_type: str,
    hours_advanced: int,
    command_text: str = "",
) -> list[dict[str, Any]]:
    """Tick world, realize region, advance kernel runtime, persist state."""
    previous_settlement = copy.deepcopy(context.settlement_state)
    preserved_quest_state = snapshot_quest_state(context)
    persist_projected_npc_state(context)
    tick_result = tick_global(context.world, hours_advanced)
    generated_events = list(tick_result.generated_events)
    active_region_id = str(context.world.simulation_snapshot.active_region_id)
    context.region_snapshot = realize_region(context.world, active_region_id)
    context.settlement_state = build_settlement_state(
        context.world, context.region_snapshot,
        context.adapter_id, context.player.name,
    )
    if command_type != "travel":
        context.settlement_state = merge_settlement_controls(
            context.settlement_state, previous_settlement,
        )
    apply_region_to_context(
        context=context, world=context.world,
        region_snapshot=context.region_snapshot,
        settlement_state=context.settlement_state,
        campaign_id=context.campaign_id, adapter_id=context.adapter_id,
        profile_id=context.profile_id, seed=context.seed,
        preserve_position=command_type != "travel",
    )
    restore_quest_state(context, preserved_quest_state, preserve_offers=command_type != "travel")
    sync_context_clock(context)
    live_events = advance_kernel_runtime(
        context, hours_advanced=hours_advanced,
        command_type=command_type, command_text=command_text,
    )
    generated_events.extend(live_events)
    sync_runtime_objectives(context)
    generated_events.extend(tick_quest_tracker(context))
    sync_quest_state(context)
    context.recent_event_log.extend(generated_events)
    context.recent_event_log = context.recent_event_log[-20:]
    if generated_events:
        context.settlement_state["alerts"] = alerts_from_events(generated_events)
    sim = context.world.simulation_snapshot
    context.settlement_state["current_hour"] = sim.current_hour
    context.settlement_state["current_day"] = sim.current_day
    context.settlement_state["season"] = sim.season
    sync_context_clock(context)
    persist_campaign_state(context)
    return generated_events


__all__ = ["advance_world_tick", "run_command"]
