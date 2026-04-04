"""Command parsing helpers for campaign-first runtime.

Handles text resolution, commander commands, travel, and kernel-delegated
commands for commerce (buy/sell), medical (diagnose/treat), and spells.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

from engine.worldgen import realize_region
from engine.api.campaign.dialog import build_dialog_payload, clear_dialog_state, store_dialog_state
from engine.api.campaign.party_bridge import allied_actor_ids
from engine.api.campaign.quest_bridge import apply_dialog_events
from engine.api.campaign.region_projection import apply_region_to_context
from engine.api.campaign.settlement import build_settlement_state

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext

logger = logging.getLogger(__name__)


def resolve_command_text(*, input_text: str, shortcut: Optional[str], args: dict[str, Any]) -> str:
    text = input_text.strip()
    if text:
        return text
    shortcut_value = str(shortcut or "").strip().lower()
    if shortcut_value == "assign":
        return "assign %s to %s" % (args.get("resident", "resident"), args.get("job", "duty"))
    if shortcut_value == "travel":
        if args.get("destination_region_id"):
            return "travel %s" % args.get("destination_region_id")
        if args.get("destination"):
            return "travel %s" % args.get("destination")
        return "travel next outpost"
    if shortcut_value == "build":
        return "build %s" % args.get("kind", "house")
    return "look around"


def maybe_handle_commander_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    lower = command_text.lower().strip()
    settlement = context.settlement_state
    if lower.startswith("assign ") and " to " in lower:
        left, right = command_text[7:].split(" to ", 1)
        resident_name = left.strip()
        assignment = right.strip()
        for resident in settlement["residents"]:
            if resident["name"].lower() == resident_name.lower():
                resident["assignment"] = assignment
                settlement["jobs"].append(
                    {
                        "id": f"job_{resident['id']}_{len(settlement['jobs'])}",
                        "kind": assignment,
                        "priority": 3,
                        "status": "queued",
                        "assignee_id": resident["id"],
                    }
                )
                return (f"{resident['name']} is now assigned to {assignment}.", "commander", 1)
        return ("No resident matched that assignment order.", "commander", 1)
    if lower.startswith("prioritize "):
        target = command_text[len("prioritize "):].strip()
        for room in settlement["rooms"]:
            if target.lower() in room["kind"].lower() or target.lower() in room["label"].lower():
                room["priority"] = min(5, int(room.get("priority", 3)) + 1)
                return (f"{room['label']} priority increased to {room['priority']}.", "commander", 1)
        settlement["alerts"] = [f"No room matched '{target}'."]
        return ("No room matched that priority order.", "commander", 1)
    if lower.startswith("set stockpile"):
        resource = command_text.replace("set stockpile", "", 1).strip() or "general"
        settlement["stockpiles"].append(
            {
                "id": f"stockpile_{len(settlement['stockpiles'])}",
                "label": f"{resource.title()} Stockpile",
                "resource_tags": [resource.lower()],
                "room_id": settlement["rooms"][0]["id"] if settlement["rooms"] else None,
            }
        )
        return (f"Established a {resource} stockpile.", "commander", 1)
    if lower.startswith("draft "):
        target = command_text[len("draft "):].strip()
        for resident in settlement["residents"]:
            if resident["name"].lower() == target.lower():
                resident["drafted"] = True
                settlement["defense_posture"] = "alert"
                return (f"{resident['name']} is now drafted.", "commander", 1)
        return ("No resident matched that draft order.", "commander", 1)
    if lower.startswith("recruit "):
        target = command_text[len("recruit "):].strip()
        for resident in settlement["residents"]:
            if resident["name"].lower() == target.lower():
                resident["squad_role"] = "escort"
                return (f"{resident['name']} joined the command squad.", "commander", 1)
        return ("No resident matched that recruit order.", "commander", 1)
    if lower.startswith("build "):
        target = command_text[len("build "):].strip() or "house"
        settlement["construction_queue"].append(
            {"id": f"build_{len(settlement['construction_queue'])}", "kind": target, "status": "planned"}
        )
        return (f"{target.title()} added to the construction queue.", "commander", 2)
    if lower.startswith("defend"):
        settlement["defense_posture"] = "fortified"
        return ("Settlement defense posture set to fortified.", "commander", 1)
    if lower.startswith("designate harvest"):
        settlement["jobs"].append(
            {
                "id": f"job_harvest_{len(settlement['jobs'])}",
                "kind": "harvest",
                "priority": 3,
                "status": "queued",
                "assignee_id": None,
            }
        )
        return ("Harvest jobs added to the settlement queue.", "commander", 1)
    return None


def handle_travel(context: "CampaignContext", command_text: str, args: Optional[dict[str, Any]] = None) -> str:
    payload = dict(args or {})
    target = command_text[len("travel"):].strip().lower()
    destination_region_id = str(payload.get("destination_region_id", "")).strip()
    destination_settlement_id = str(payload.get("destination_settlement_id", "")).strip()
    destinations = list(context.world.settlement_nodes)
    current_region_id = context.world.simulation_snapshot.active_region_id
    reachable_options = []
    for edge in context.world.travel_edges:
        if edge["from_region_id"] == current_region_id:
            reachable_options.append((edge["to_region_id"], edge["to_settlement_id"], edge))
        elif edge["to_region_id"] == current_region_id:
            reachable_options.append((edge["from_region_id"], edge["from_settlement_id"], edge))
    chosen = None
    chosen_edge = None
    if destination_region_id:
        chosen = next(
            (
                settlement
                for settlement in destinations
                if settlement["region_id"] == destination_region_id
                and (not destination_settlement_id or settlement["id"] == destination_settlement_id)
            ),
            None,
        )
        if chosen is not None:
            chosen_edge = next(
                (
                    edge
                    for _, settlement_id, edge in reachable_options
                    if settlement_id == chosen["id"]
                ),
                None,
            )
    if chosen is None and target:
        for settlement in destinations:
            if target in str(settlement["name"]).lower() or target in str(settlement["region_id"]).lower():
                chosen = settlement
                chosen_edge = next(
                    (
                        edge
                        for _, settlement_id, edge in reachable_options
                        if settlement_id == settlement["id"]
                    ),
                    None,
                )
                break
    if chosen is None:
        if reachable_options:
            destination_region_id, destination_settlement_id, chosen_edge = reachable_options[0]
            chosen = next(
                settlement
                for settlement in destinations
                if settlement["region_id"] == destination_region_id
                and settlement["id"] == destination_settlement_id
            )
        else:
            current_index = next(
                (
                    index
                    for index, settlement in enumerate(destinations)
                    if settlement["region_id"] == current_region_id
                ),
                0,
            )
            chosen = destinations[(current_index + 1) % len(destinations)]
    if chosen_edge is None and current_region_id != chosen["region_id"]:
        raise ValueError(f"Destination {chosen['region_id']} is not reachable from {current_region_id}")
    context.world.simulation_snapshot.active_region_id = chosen["region_id"]
    context.region_snapshot = realize_region(context.world, chosen["region_id"])
    context.settlement_state = build_settlement_state(
        context.world, context.region_snapshot, context.adapter_id, context.player.name
    )
    apply_region_to_context(
        context=context,
        world=context.world,
        region_snapshot=context.region_snapshot,
        settlement_state=context.settlement_state,
        campaign_id=context.campaign_id,
        adapter_id=context.adapter_id,
        profile_id=context.profile_id,
        seed=context.seed,
    )
    travel_hours = int(chosen_edge.get("travel_hours", 4)) if chosen_edge is not None else 4
    context.campaign_state["last_travel_hours"] = travel_hours
    return f"Travel complete after {travel_hours}h. You arrive at {chosen['name']}."


# ---------------------------------------------------------------------------
# Talk command — opens authored dialog with an NPC
# ---------------------------------------------------------------------------

_TALK_RE = re.compile(r"^talk\s+(?:to\s+)?(.+)$", re.IGNORECASE)


def maybe_handle_talk_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Open authored dialog with a named NPC via kernel dialog bridge."""
    match = _TALK_RE.match(command_text.strip())
    if not match:
        return None
    npc_query = match.group(1).strip()
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    query_lower = npc_query.lower()
    target_actor = None
    target_id = ""
    talk_types = {"npc", "creature", "monster", "animal"}
    for actor_id, actor in actors.items():
        if actor_id == "player" or not getattr(actor, "alive", True):
            continue
        actor_type = str(getattr(getattr(actor, "identity", None), "actor_type", "")).lower()
        if actor_type not in talk_types:
            continue
        name = str(getattr(getattr(actor, "identity", None), "display_name", "")).strip()
        if not name:
            continue
        if query_lower in name.lower() or query_lower.replace(" ", "_") == actor_id.lower():
            target_actor = actor
            target_id = actor_id
            break
    if target_actor is None:
        return (f"No one named '{npc_query}' is here.", "dialog", 0)

    npc_name = str(getattr(target_actor.identity, "display_name", npc_query)).strip() or npc_query
    if target_id in allied_actor_ids(context):
        return (f"{npc_name} is already traveling with you.", "party", 0)
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": target_id,
        "npc_name": npc_name,
    }
    dialog_payload = build_dialog_payload(context, f"{npc_name} turns to face you.")
    if not dialog_payload:
        clear_dialog_state(context)
        return (f"{npc_name} has nothing to say.", "dialog", 0)
    runtime["_pending_dialog_payload"] = dialog_payload
    logger.info("Talk: opened dialog with %s (%s)", npc_name, target_id)
    return (dialog_payload.get("dialog_text", f"{npc_name} regards you."), "dialog", 0)


# ---------------------------------------------------------------------------
# Dialog commands (kernel dialog authority)
# ---------------------------------------------------------------------------

def maybe_handle_dialog_command(
    context: "CampaignContext", command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle dialog transition selection via kernel dialog state machine."""
    from engine.kernel.dialog import DialogDef, DialogState, get_available_transitions, select_transition

    lower = command_text.lower().strip()
    if not lower.startswith("dialog "):
        return None
    transition_id = command_text[7:].strip()
    if not transition_id:
        return None

    runtime = context.kernel_runtime or {}
    dialog_state = runtime.get("dialog_state")
    if not isinstance(dialog_state, DialogState):
        return ("No active dialog.", "dialog", 0)
    dialog_defs = runtime.get("dialog_defs", {})
    dialog_def = dialog_defs.get(dialog_state.dialog_id)
    if not isinstance(dialog_def, DialogDef):
        return ("Dialog definition not found.", "dialog", 0)
    current_node = next((n for n in dialog_def.states if n.state_id == dialog_state.current_state_id), None)
    if current_node is None:
        clear_dialog_state(context)
        return ("Dialog state is invalid.", "dialog", 0)

    actors = runtime.get("actors", {})
    npc_id = str(runtime.get("dialog_npc_id", "")).strip()
    player = actors.get("player")
    npc = actors.get(npc_id)
    if player is None or npc is None:
        clear_dialog_state(context)
        return ("Dialog actors are unavailable.", "dialog", 0)

    game_state = runtime.get("game_state")
    global_vars = getattr(game_state, "global_variables", {}) if game_state is not None else {}
    available = get_available_transitions(current_node, player, npc, dialog_state.variables, global_vars)
    transition = next((item for item in available if item.transition_id == transition_id), None)
    if transition is None:
        return ("That dialog option is not available.", "dialog", 0)

    new_state, next_node, events = select_transition(
        dialog_state,
        transition,
        dialog_defs,
        player,
        npc,
        global_vars,
    )
    if game_state is not None:
        game_state.global_variables = dict(global_vars)

    event_summaries = apply_dialog_events(context, events)
    logger.info(
        "Dialog transition: %s -> %s (events=%d)",
        transition_id,
        next_node.state_id if next_node else "END",
        len(events),
    )

    if not new_state.active or next_node is None:
        clear_dialog_state(context)
        runtime.pop("_pending_dialog_payload", None)
        narrative_parts = list(event_summaries)
        narrative_parts.append("The conversation ends.")
        return (" ".join(part.strip() for part in narrative_parts if part).strip(), "dialog", 0)

    next_dialog_def = dialog_defs.get(new_state.dialog_id, dialog_def)
    store_dialog_state(context, new_state, next_dialog_def, npc)
    dialog_payload = build_dialog_payload(context, next_node.text or f"{npc.identity.display_name} waits for your response.")
    if dialog_payload:
        runtime["_pending_dialog_payload"] = dialog_payload
    narrative_parts = list(event_summaries)
    if next_node.text:
        narrative_parts.append(next_node.text)
    narrative = " ".join(part.strip() for part in narrative_parts if part).strip()
    return (narrative or f"{npc.identity.display_name} waits for your response.", "dialog", 0)


# ---------------------------------------------------------------------------
# Commerce commands (kernel store authority)
# ---------------------------------------------------------------------------

def maybe_handle_commerce_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle buy/sell/rent/identify via kernel store.py."""
    from engine.kernel.store import buy_identification, buy_item, sell_item, rent_room
    lower = command_text.lower().strip()
    runtime = context.kernel_runtime or {}
    stores = runtime.get("stores", [])
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return None
    item_registry = _item_registry()
    if lower.startswith("buy "):
        item_name = command_text[4:].strip()
        npc_part = ""
        if " from " in item_name:
            item_name, npc_part = item_name.split(" from ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to buy '{item_name}' from.", "commerce", 1)
        ok, msg = buy_item(player, store, item_name, 1, item_registry)
        if not ok:
            return (msg, "commerce", 1)
        logger.info("Buy: %s bought %s", player.identity.display_name, item_name)
        return (f"Bought {item_name}. {msg}", "commerce", 1)
    if lower.startswith("sell "):
        item_name = command_text[5:].strip()
        npc_part = ""
        if " to " in item_name:
            item_name, npc_part = item_name.split(" to ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to sell '{item_name}' to.", "commerce", 1)
        # Find item in player inventory by def_id.
        item_instance = next((i for i in player.inventory if i.item_def_id == item_name), None)
        if item_instance is None:
            return (f"You don't have '{item_name}' to sell.", "commerce", 1)
        ok, msg = sell_item(player, store, item_instance, item_registry)
        if not ok:
            return (msg, "commerce", 1)
        logger.info("Sell: %s sold %s", player.identity.display_name, item_name)
        return (f"Sold {item_name}. {msg}", "commerce", 1)
    if lower.startswith("rent room") or lower.startswith("rent a room"):
        store = _find_store(stores, "")
        if store is None:
            return ("No inn found to rent a room.", "commerce", 1)
        ok, msg = rent_room(player, store, "room")
        if not ok:
            return (msg, "commerce", 8)
        return (f"Rented a room. You rest for the night.", "commerce", 8)
    if lower.startswith("identify "):
        item_name = command_text[9:].strip()
        store = _find_store_with_service(stores, "identify")
        if store is None:
            return ("No merchant with identification services found.", "commerce", 1)
        item_instance = _find_inventory_item(player, item_name)
        if item_instance is None:
            return (f"You don't have '{item_name}' to identify.", "commerce", 1)
        item_def = _item_def_from_registry(item_instance.item_def_id, item_registry)
        if item_def is None:
            return (f"Unknown item definition for '{item_name}'.", "commerce", 1)
        ok, msg = buy_identification(player, store, item_instance, item_def)
        if not ok:
            return (f"Cannot identify: {msg}.", "commerce", 1)
        logger.info("Identify: %s identified %s", player.identity.display_name, item_name)
        return (f"Identified {item_name}. {msg}", "commerce", 1)
    return None


def _find_store(stores: list, npc_hint: str) -> Any:
    """Find a store from kernel runtime, optionally matching NPC name."""
    if not stores:
        return None
    if npc_hint:
        for store in stores:
            npc_id = getattr(store, "npc_id", "") or ""
            if npc_hint.lower() in npc_id.lower():
                return store
    return stores[0] if stores else None


def _item_registry() -> dict:
    """Load item definitions from data registry."""
    try:
        from engine.data._shared import items_registry
        reg = items_registry()
        if isinstance(reg, dict):
            return reg
        return {item.get("id", ""): item for item in reg if isinstance(item, dict)}
    except Exception:
        return {}


def _find_store_with_service(stores: list, service_type: str) -> Any:
    for store in stores:
        if any(getattr(s, "service_type", "") == service_type for s in getattr(store, "services", [])):
            return store
    return None


def _find_inventory_item(player: Any, item_name: str) -> Any:
    name_lower = item_name.lower().replace(" ", "_")
    for item in player.inventory:
        def_id = getattr(item, "item_def_id", "")
        if def_id == name_lower or name_lower in def_id.lower():
            return item
    return None


def _item_def_from_registry(item_def_id: str, registry: dict) -> Any:
    raw = registry.get(item_def_id)
    if raw is None:
        return None
    try:
        from engine.kernel.items import ItemDef
        return ItemDef(
            item_def_id=str(raw.get("id", item_def_id)), label=str(raw.get("name", item_def_id)),
            item_type=str(raw.get("type", "misc")), rarity=str(raw.get("rarity", "common")).upper(),
            base_price=int(raw.get("value", 0)), weight=float(raw.get("weight", 0.0)),
            lore_to_identify=int(raw.get("lore_to_identify", 0)),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Medical commands — delegated to medical_bridge.py for kernel pipeline
# ---------------------------------------------------------------------------

from engine.api.medical_bridge import maybe_handle_medical_command  # noqa: E402, F811
