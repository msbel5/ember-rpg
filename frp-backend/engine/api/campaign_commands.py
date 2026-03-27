"""Command parsing helpers for campaign-first runtime."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.worldgen import realize_region

from .campaign_state import apply_region_to_session, build_settlement_state

if TYPE_CHECKING:
    from engine.api.campaign_runtime import CampaignContext


def resolve_command_text(*, input_text: str, shortcut: Optional[str], args: dict[str, Any]) -> str:
    text = input_text.strip()
    if text:
        return text
    shortcut_value = str(shortcut or "").strip().lower()
    if shortcut_value == "assign":
        return "assign %s to %s" % (args.get("resident", "resident"), args.get("job", "duty"))
    if shortcut_value == "travel":
        return "travel %s" % args.get("destination", "next outpost")
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


def handle_travel(context: "CampaignContext", command_text: str) -> str:
    target = command_text[len("travel"):].strip().lower()
    destinations = list(context.world.settlements)
    current_region_id = context.world.simulation_snapshot.active_region_id
    chosen = None
    if target:
        for settlement in destinations:
            if target in settlement.center_name.lower() or target in settlement.region_id.lower():
                chosen = settlement
                break
    if chosen is None:
        current_index = next(
            (index for index, settlement in enumerate(destinations) if settlement.region_id == current_region_id),
            0,
        )
        chosen = destinations[(current_index + 1) % len(destinations)]
    context.world.simulation_snapshot.active_region_id = chosen.region_id
    context.region_snapshot = realize_region(context.world, chosen.region_id)
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
    return f"Travel complete. You arrive at {chosen.center_name}."


def hours_for_avatar_command(command_text: str) -> int:
    if command_text.startswith("rest"):
        return 8
    if command_text.startswith("travel"):
        return 4
    if command_text.startswith("craft"):
        return 2
    return 1


def merge_avatar_narrative(context: "CampaignContext", narrative: str) -> str:
    explanation = context.region_snapshot.metadata.get("explainability", {})
    if not explanation:
        return narrative
    return (
        f"{narrative} "
        f"[Region: terrain={explanation.get('terrain_driver', 'unknown')}, "
        f"climate={explanation.get('climate_driver', 'unknown')}]"
    )
