"""Command parsing helpers for campaign-first runtime.

Handles text resolution, commander commands, travel, and kernel-delegated
commands for commerce (buy/sell), medical (diagnose/treat), and spells.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from engine.worldgen import realize_region

from .campaign_state import apply_region_to_session, build_settlement_state

if TYPE_CHECKING:
    from engine.api.campaign_runtime import CampaignContext

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
        context.world, context.region_snapshot, context.adapter_id, context.session.player.name
    )
    apply_region_to_session(
        session=context.session,
        world=context.world,
        region_snapshot=context.region_snapshot,
        settlement_state=context.settlement_state,
        campaign_id=context.campaign_id,
        adapter_id=context.adapter_id,
        profile_id=context.profile_id,
        seed=context.seed,
    )
    travel_hours = int(chosen_edge.get("travel_hours", 4)) if chosen_edge is not None else 4
    context.session.campaign_state["last_travel_hours"] = travel_hours
    return f"Travel complete after {travel_hours}h. You arrive at {chosen['name']}."


def hours_for_avatar_command(command_text: str) -> int:
    if command_text.startswith("rest"):
        return 8
    if command_text.startswith("travel"):
        return 4
    if command_text.startswith("craft"):
        return 2
    return 1


def merge_avatar_narrative(context: "CampaignContext", narrative: str) -> str:
    # Explainability metadata is for debug logging only, not player-facing narrative.
    return narrative


# ---------------------------------------------------------------------------
# Commerce commands (kernel store authority)
# ---------------------------------------------------------------------------

def maybe_handle_commerce_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle buy/sell/rent/identify via kernel store.py."""
    from engine.kernel.store import buy_item, sell_item, rent_room
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
            return (f"No merchant found to buy '{item_name}' from.", "avatar", 1)
        ok, msg = buy_item(player, store, item_name, 1, item_registry)
        if not ok:
            return (msg, "avatar", 1)
        logger.info("Buy: %s bought %s", player.identity.display_name, item_name)
        return (f"Bought {item_name}. {msg}", "avatar", 1)
    if lower.startswith("sell "):
        item_name = command_text[5:].strip()
        npc_part = ""
        if " to " in item_name:
            item_name, npc_part = item_name.split(" to ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to sell '{item_name}' to.", "avatar", 1)
        # Find item in player inventory by def_id.
        item_instance = next((i for i in player.inventory if i.item_def_id == item_name), None)
        if item_instance is None:
            return (f"You don't have '{item_name}' to sell.", "avatar", 1)
        ok, msg = sell_item(player, store, item_instance, item_registry)
        if not ok:
            return (msg, "avatar", 1)
        logger.info("Sell: %s sold %s", player.identity.display_name, item_name)
        return (f"Sold {item_name}. {msg}", "avatar", 1)
    if lower.startswith("rent room") or lower.startswith("rent a room"):
        store = _find_store(stores, "")
        if store is None:
            return ("No inn found to rent a room.", "avatar", 1)
        ok, msg = rent_room(player, store, "room")
        if not ok:
            return (msg, "avatar", 8)
        return (f"Rented a room. You rest for the night.", "avatar", 8)
    if lower.startswith("identify "):
        item_name = command_text[9:].strip()
        return (f"Identifying {item_name} requires a sage or scholarly merchant.", "avatar", 1)
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


# ---------------------------------------------------------------------------
# Medical commands (kernel medical authority)
# ---------------------------------------------------------------------------

def maybe_handle_medical_command(
    context: "CampaignContext",
    command_text: str,
) -> Optional[tuple[str, str, int]]:
    """Handle diagnose/treat/surgery via kernel medical.py."""
    from engine.kernel.medical import check_lethal_conditions
    lower = command_text.lower().strip()
    runtime = context.kernel_runtime or {}
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return None
    if lower.startswith("diagnose"):
        target_name = command_text[8:].strip() or "self"
        target = _resolve_medical_target(actors, target_name, player)
        if target is None:
            return (f"No target '{target_name}' found to diagnose.", "avatar", 1)
        if target.body_state is None:
            return (f"{target.identity.display_name} has no injuries to diagnose.", "avatar", 1)
        # Check for wounds across body parts.
        wound_summaries = []
        for part_id, part in target.body_state.parts.items():
            if part.current_hp < part.max_hp:
                wound_summaries.append(f"{part_id}: {part.current_hp}/{part.max_hp} hp")
        lethal, reason = check_lethal_conditions(target)
        status = f"CRITICAL ({reason})" if lethal else "stable"
        summary = ", ".join(wound_summaries[:3]) if wound_summaries else "no visible wounds"
        return (f"Diagnosis for {target.identity.display_name}: {summary}. Status: {status}.", "avatar", 1)
    if lower.startswith("treat ") or lower.startswith("surgery "):
        target_name = command_text[8 if lower.startswith("surgery") else 6:].strip() or "self"
        target = _resolve_medical_target(actors, target_name, player)
        if target is None:
            return (f"No target '{target_name}' found to treat.", "avatar", 1)
        if target.body_state is None:
            return (f"{target.identity.display_name} has nothing to treat.", "avatar", 2)
        # Apply basic healing to most damaged body part.
        worst_part = min(target.body_state.parts.values(), key=lambda p: p.current_hp / max(1, p.max_hp), default=None)
        if worst_part is None:
            return (f"No wounds found on {target.identity.display_name}.", "avatar", 2)
        healed = min(5, worst_part.max_hp - worst_part.current_hp)
        worst_part.current_hp = min(worst_part.max_hp, worst_part.current_hp + healed)
        return (f"Treated {target.identity.display_name}: healed {healed} hp.", "avatar", 2)
    return None


def _resolve_medical_target(actors: dict, name: str, player: Any) -> Any:
    if name.lower() in ("self", "me", "player"):
        return player
    for actor in actors.values():
        if hasattr(actor, "identity") and name.lower() in actor.identity.display_name.lower():
            return actor
    return None
