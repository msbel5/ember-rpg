"""Command parsing helpers for campaign-first runtime.

Handles text resolution, commander commands, travel, and kernel-delegated
commands for commerce (buy/sell), medical (diagnose/treat), and spells.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Any, Optional

from engine.worldgen import realize_region
from engine.api.campaign.dialog import build_dialog_payload, clear_dialog_state, store_dialog_state
from engine.api.campaign.knowledge import discover_npc_topics, discover_travel_topics
from engine.api.campaign.party_bridge import allied_actor_ids
from engine.api.campaign.quest_bridge import apply_dialog_events
from engine.api.campaign.region_projection import apply_region_to_context
from engine.api.campaign.runtime_common import stable_seed
from engine.api.campaign.settlement import build_settlement_state
from engine.api.campaign.actor_query import resolve_live_actor_query
from engine.api.campaign.world import build_travel_options
from engine.kernel import TravelState, complete_travel, hydrate_local_map, initiate_travel, tick_travel
from engine.kernel.hybrid_runtime import resolve_travel_encounter
from engine.kernel.gameplay import persist_ground_item_entities
from engine.world.interactions import InteractionHandler, INTERACTION_RULES
from engine.world.interactions_runtime import (
    interaction_target_type_for_entity,
    parse_interaction_type,
    perform_interaction,
)

if TYPE_CHECKING:
    from engine.api.campaign.context import CampaignContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuredInteractionTarget:
    target_id: str | None
    target_kind: str
    target_name: str
    target_type: str | None
    actor: Any = None
    record: dict[str, Any] | None = None
    tile_payload: dict[str, Any] | None = None


def resolve_command_text(*, input_text: str, shortcut: Optional[str], args: dict[str, Any]) -> str:
    text = input_text.strip()
    if text:
        return text
    shortcut_value = str(shortcut or "").strip().lower()
    if shortcut_value == "interact":
        verb_id = str(args.get("verb_id", "interact")).strip().lower() or "interact"
        interaction_id = str(args.get("interaction_id", "")).strip().lower()
        target_hint = str(args.get("target_id") or args.get("tile_name") or "").strip()
        parts = ["interact", verb_id]
        if interaction_id and interaction_id != verb_id:
            parts.append(interaction_id)
        if target_hint:
            parts.append(target_hint)
        return " ".join(parts)
    if shortcut_value == "combat":
        action_id = str(args.get("action_id", "attack")).strip().lower() or "attack"
        if action_id == "attack":
            target_hint = str(args.get("target_id", "")).strip()
            called_shot = str(args.get("called_shot", "")).strip().lower()
            parts = ["attack"]
            if target_hint:
                parts.append(target_hint)
            if called_shot:
                parts.extend(["at", called_shot])
            return " ".join(parts).strip()
        if action_id == "move":
            direction = str(args.get("direction", "")).strip().lower() or "north"
            return f"move {direction}"
        if action_id == "end_turn":
            return "end turn"
        if action_id in {"defend", "flee"}:
            return action_id
        return f"combat {action_id}".strip()
    if shortcut_value == "spell":
        action_id = str(args.get("action_id", "cast")).strip().lower() or "cast"
        spell_id = str(args.get("spell_id", "")).strip()
        if action_id == "memorize":
            return f"memorize {spell_id}".strip()
        target_hint = str(args.get("target_id", "")).strip()
        if target_hint:
            return f"cast {spell_id} at {target_hint}".strip()
        return f"cast {spell_id}".strip()
    if shortcut_value == "assign":
        return "assign %s to %s" % (args.get("resident", "resident"), args.get("job", "duty"))
    if shortcut_value == "travel":
        action_id = str(args.get("action_id", "start")).strip().lower() or "start"
        if action_id == "advance":
            return "continue travel"
        if action_id == "resolve_encounter":
            return "resolve travel encounter"
        if args.get("destination_region_id"):
            return "travel %s" % args.get("destination_region_id")
        if args.get("destination_settlement_id"):
            return "travel %s" % args.get("destination_settlement_id")
        if args.get("route_id"):
            return "travel %s" % args.get("route_id")
        if args.get("destination"):
            return "travel %s" % args.get("destination")
        return "travel next outpost"
    if shortcut_value == "knowledge":
        action_id = str(args.get("action_id", "topics")).strip().lower() or "topics"
        query = str(args.get("topic_id") or args.get("query") or "").strip()
        if action_id == "topics":
            return "topics"
        if action_id == "think":
            return f"think {query}".strip()
        if action_id == "pin":
            return f"pin {query}".strip()
        return f"knowledge {action_id}".strip()
    if shortcut_value == "advisor":
        action_id = str(args.get("action_id", "ask_dm")).strip().lower() or "ask_dm"
        query = str(args.get("query") or "").strip()
        if action_id == "ask_dm":
            return f"ask dm {query}".strip()
        return f"advisor {action_id}".strip()
    if shortcut_value == "dialog":
        action_id = str(args.get("action_id", "")).strip().lower()
        query = str(args.get("topic_id") or args.get("query") or "").strip()
        if action_id == "ask_about":
            return f"ask about {query}".strip()
        return f"dialog {action_id}".strip()
    if shortcut_value == "commerce":
        action_id = str(args.get("action_id", "")).strip().lower()
        item_id = str(args.get("item_id") or "").strip()
        store_id = str(args.get("store_id") or "").strip()
        if action_id == "steal_item":
            if store_id:
                return f"steal {item_id} from {store_id}".strip()
            return f"steal {item_id}".strip()
        return f"commerce {action_id}".strip()
    if shortcut_value == "build":
        return "build %s" % args.get("kind", "house")
    return "look around"


def maybe_handle_structured_interaction(
    context: "CampaignContext",
    args: dict[str, Any],
) -> Optional[tuple[str, str, int]]:
    verb_id = str(args.get("verb_id", "")).strip().lower()
    if not verb_id:
        return None
    if verb_id not in {"talk", "attack", "examine", "use", "skill", "rest"}:
        return (f"Unsupported structured interaction '{verb_id}'.", "exploration", 0)

    target = _resolve_structured_target(context, args, verb_id=verb_id)
    if isinstance(target, str):
        return (target, "exploration", 0)

    if verb_id == "talk":
        if target is None or target.actor is None:
            return ("Talk requires a live NPC target.", "dialog", 0)
        return maybe_handle_talk_command(context, f"talk {target.actor.identity.actor_id}")

    if verb_id == "attack":
        if target is None or target.actor is None:
            return ("Attack requires a live enemy target.", "combat", 0)
        from engine.api.combat_bridge import handle_attack_target_id

        return handle_attack_target_id(context, target.actor.identity.actor_id)

    if verb_id == "examine":
        from engine.api.exploration_bridge import handle_structured_examine

        if target is None:
            return ("Examine requires a target.", "exploration", 0)
        position = None
        if target.tile_payload is not None:
            position = tuple(target.tile_payload.get("position", []))
        return handle_structured_examine(
            context,
            target_id=target.target_id,
            target_kind=target.target_kind,
            target_position=position,
            tile_name=target.target_name if target.target_kind == "tile" else None,
        )

    if verb_id == "rest":
        if target is not None and target.target_type not in {"bed", "campfire"}:
            return (f"{target.target_name} does not support resting.", "exploration", 0)
        from engine.api.gameplay_bridge import maybe_handle_rest_command

        return maybe_handle_rest_command(context, "rest") or ("You cannot rest here.", "rest", 0)

    interaction_id = str(args.get("interaction_id", "")).strip().lower()
    interaction_type = parse_interaction_type(interaction_id)
    if interaction_type is None:
        return (f"Unknown interaction '{interaction_id}'.", "exploration", 0)
    if target is None:
        return ("This interaction requires a target.", "exploration", 0)
    if target.target_type is None:
        return (f"{target.target_name} does not support {interaction_id.replace('_', ' ')}.", "exploration", 0)

    runtime = context.kernel_runtime or {}
    player = runtime.get("actors", {}).get("player") or context.player
    if player is None:
        return ("No active player was found.", "exploration", 0)
    interaction_target = {
        "target_type": target.target_type,
        "name": target.target_name,
        "target_kind": target.target_kind,
    }
    seed = (int(context.seed) * 17) + len(str(target.target_id or target.target_name)) + len(interaction_id)
    result = perform_interaction(
        interaction_type,
        player,
        interaction_target,
        {"seed": seed},
        INTERACTION_RULES,
    )
    if result.success:
        _apply_interaction_state_changes(context, target, result.state_changes)
    command_type = "exploration"
    return (result.narrative_prompt, command_type, 0)


def _resolve_structured_target(
    context: "CampaignContext",
    args: dict[str, Any],
    *,
    verb_id: str,
) -> StructuredInteractionTarget | str | None:
    target_id = str(args.get("target_id", "")).strip()
    requested_kind = str(args.get("target_kind", "")).strip().lower()
    if verb_id == "rest" and not target_id and not args.get("target_position"):
        return None
    if target_id:
        runtime = context.kernel_runtime or {}
        actor = (runtime.get("actors") or {}).get(target_id)
        record = context.entities.get(target_id)
        live_entity = context.spatial_index.get_entity(target_id) if getattr(context, "spatial_index", None) is not None else None
        if actor is None and not isinstance(record, dict) and live_entity is None:
            return f"Target '{target_id}' is no longer present."
        target_kind = _structured_target_kind(actor=actor, record=record, live_entity=live_entity)
        if requested_kind and requested_kind != target_kind:
            return f"Target '{target_id}' is a {target_kind}, not a {requested_kind}."
        target_name = ""
        prefer_record = isinstance(record, dict) and str(record.get("type", "")).strip().lower() in {"furniture", "item"}
        if isinstance(record, dict) and prefer_record:
            target_name = str(record.get("name", target_id))
            payload = {
                "id": target_id,
                "entity_type": str(record.get("type", "")),
                "name": target_name,
                "disposition": str(record.get("disposition", record.get("attitude", "friendly"))),
                "template": str(record.get("template", record.get("role", ""))),
                "locked": bool(record.get("locked", False)),
                "trapped": bool(record.get("trapped", False)),
            }
        elif actor is not None:
            target_name = str(actor.identity.display_name)
            payload = {
                "id": target_id,
                "entity_type": str(getattr(actor.identity, "actor_type", "npc")).lower(),
                "name": target_name,
                "disposition": "hostile" if bool(actor.raw_payload.get("hostile")) else str(actor.raw_payload.get("disposition", "friendly")),
                "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", ""))),
            }
        elif isinstance(record, dict):
            target_name = str(record.get("name", target_id))
            payload = {
                "id": target_id,
                "entity_type": str(record.get("type", "")),
                "name": target_name,
                "disposition": str(record.get("disposition", record.get("attitude", "friendly"))),
                "template": str(record.get("template", record.get("role", ""))),
                "locked": bool(record.get("locked", False)),
                "trapped": bool(record.get("trapped", False)),
            }
        else:
            target_name = str(getattr(live_entity, "name", target_id))
            payload = {
                "id": target_id,
                "entity_type": str(getattr(getattr(live_entity, "entity_type", None), "value", "item")),
                "name": target_name,
                "disposition": str(getattr(live_entity, "disposition", "neutral")),
            }
        target_type = interaction_target_type_for_entity(payload)
        return StructuredInteractionTarget(
            target_id=target_id,
            target_kind=target_kind,
            target_name=target_name or target_id,
            target_type=target_type,
            actor=actor,
            record=record if isinstance(record, dict) else None,
        )

    raw_position = args.get("target_position")
    if isinstance(raw_position, (list, tuple)) and len(raw_position) >= 2:
        from engine.api.exploration_bridge import build_structured_tile_payload

        tile_name = str(args.get("tile_name", "")).strip() or "tile"
        tile_payload = build_structured_tile_payload(
            context,
            target_position=(int(raw_position[0]), int(raw_position[1])),
            tile_name=tile_name,
            interaction_id=str(args.get("interaction_id", "")).strip().lower() or verb_id,
        )
        if tile_payload is None:
            return f"Tile at ({int(raw_position[0])},{int(raw_position[1])}) is not valid."
        if requested_kind and requested_kind != "tile":
            return f"Target position resolves to a tile, not a {requested_kind}."
        return StructuredInteractionTarget(
            target_id=None,
            target_kind="tile",
            target_name=str(tile_payload.get("name", tile_name)),
            target_type=str(tile_payload.get("target_type", "")).strip() or None,
            tile_payload=tile_payload,
        )

    return "This interaction requires a valid target."


def _structured_target_kind(*, actor: Any = None, record: dict[str, Any] | None = None, live_entity: Any = None) -> str:
    if isinstance(record, dict):
        entity_type = str(record.get("type", "")).strip().lower()
        disposition = str(record.get("disposition", record.get("attitude", ""))).strip().lower()
        if entity_type in {"npc", "creature"}:
            return "enemy" if disposition == "hostile" else "npc"
        if entity_type == "furniture":
            return "furniture"
        if entity_type == "item":
            return "item"
    if live_entity is not None:
        live_type = str(getattr(getattr(live_entity, "entity_type", None), "value", "")).strip().lower()
        if live_type == "item":
            return "item"
        if live_type == "furniture":
            return "furniture"
        if live_type in {"npc", "creature"}:
            live_disposition = str(getattr(live_entity, "disposition", "")).strip().lower()
            return "enemy" if live_disposition == "hostile" else "npc"
    if actor is not None:
        actor_type = str(getattr(actor.identity, "actor_type", "")).strip().lower()
        if actor_type in {"npc", "creature"}:
            if bool(actor.raw_payload.get("hostile")):
                return "enemy"
            disposition = str(actor.raw_payload.get("disposition", "friendly")).strip().lower()
            return "enemy" if disposition == "hostile" else "npc"
    return "tile"


def _apply_interaction_state_changes(
    context: "CampaignContext",
    target: StructuredInteractionTarget,
    state_changes: dict[str, Any],
) -> None:
    if target.record is not None:
        for key in ("opened", "locked", "broken", "trapped"):
            if key in state_changes:
                target.record[key] = state_changes[key]
    if target.target_kind == "item" and state_changes.get("picked_up") and target.target_id and getattr(context, "spatial_index", None) is not None:
        entity = context.spatial_index.get_entity(target.target_id)
        if entity is not None:
            for item in list(getattr(entity, "inventory", []) or []):
                context.add_item(dict(item), merge=True)
            context.spatial_index.remove(entity)
            persist_ground_item_entities(context)


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


def _travel_runtime_state(context: "CampaignContext") -> TravelState:
    runtime = getattr(context, "kernel_runtime", {}) or {}
    travel_state = runtime.get("travel_state")
    if isinstance(travel_state, TravelState):
        return travel_state
    if isinstance(travel_state, dict):
        try:
            normalized = TravelState.from_dict(travel_state)
        except TypeError:
            normalized = TravelState(status=str(travel_state.get("status", "idle") or "idle"))
        runtime["travel_state"] = normalized
        return normalized
    normalized = TravelState(status="idle")
    runtime["travel_state"] = normalized
    return normalized


def _travel_is_active(context: "CampaignContext") -> bool:
    status = str(_travel_runtime_state(context).status).strip().lower()
    return status not in {"", "idle", "arrived"}


def _set_travel_scene(context: "CampaignContext", scene_name: str) -> None:
    if context.dm_context is not None:
        context.dm_context.scene_type_name = scene_name


def _travel_seed(context: "CampaignContext", travel_state: TravelState, action_id: str) -> int:
    simulation = context.world.simulation_snapshot
    current_day = int(getattr(simulation, "current_day", 0) or 0) if simulation is not None else 0
    current_hour = int(getattr(simulation, "current_hour", 0) or 0) if simulation is not None else 0
    return stable_seed(
        context.seed,
        context.campaign_id,
        action_id,
        travel_state.origin_region_id,
        travel_state.destination_region_id,
        travel_state.edge_id,
        current_day,
        current_hour,
        travel_state.travel_hours_remaining,
    )


def _current_travel_route(context: "CampaignContext") -> dict[str, Any] | None:
    travel_state = _travel_runtime_state(context)
    if not _travel_is_active(context):
        return None
    options = build_travel_options(context.world, context=context)
    route_id = str(travel_state.edge_id).strip()
    destination_region_id = str(travel_state.destination_region_id).strip()
    destination_settlement_id = str(
        getattr(travel_state, "destination_settlement_id", "") or ""
    ).strip()
    return next(
        (
            option
            for option in options
            if (
                route_id and str(option.get("route_id", "")).strip() == route_id
            ) or (
                str(option.get("destination_region_id", "")).strip() == destination_region_id
                and (
                    not destination_settlement_id
                    or str(option.get("destination_settlement_id", "")).strip() == destination_settlement_id
                )
            )
        ),
        None,
    )


def _select_travel_route(context: "CampaignContext", command_text: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    target = command_text[len("travel"):].strip().lower() if command_text.lower().startswith("travel") else ""
    route_id = str(payload.get("route_id", "")).strip()
    destination_region_id = str(payload.get("destination_region_id", "")).strip()
    destination_settlement_id = str(payload.get("destination_settlement_id", "")).strip()
    options = build_travel_options(context.world, context=context)
    if route_id:
        return next((item for item in options if str(item.get("route_id", "")).strip() == route_id), None)
    if destination_region_id:
        return next(
            (
                item
                for item in options
                if str(item.get("destination_region_id", "")).strip() == destination_region_id
                and (
                    not destination_settlement_id
                    or str(item.get("destination_settlement_id", "")).strip() == destination_settlement_id
                )
            ),
            None,
        )
    if target:
        return next(
            (
                item
                for item in options
                if target in str(item.get("destination_name", "")).lower()
                or target in str(item.get("destination_region_id", "")).lower()
                or target == str(item.get("destination_settlement_id", "")).lower()
                or target == str(item.get("route_id", "")).lower()
            ),
            None,
        )
    return options[0] if options else None


def _apply_completed_travel(context: "CampaignContext", travel_state: TravelState) -> str:
    runtime = context.kernel_runtime or {}
    kernel_world = runtime.get("world_state")
    if kernel_world is None:
        raise ValueError("Kernel world state is missing for travel completion.")
    authority = complete_travel(travel_state, kernel_world)
    runtime["path_authority"] = authority
    runtime["local_map_state"] = hydrate_local_map(kernel_world, authority.active_region_id)
    runtime["travel_state"] = TravelState(status="idle")
    if context.world.simulation_snapshot is not None:
        context.world.simulation_snapshot.active_region_id = authority.active_region_id
    discover_travel_topics(
        context,
        destination_region_id=str(travel_state.destination_region_id or authority.active_region_id),
    )
    _set_travel_scene(context, "exploration")
    route = _current_travel_route(context)
    destination_name = ""
    if route is not None:
        destination_name = str(route.get("destination_name", "")).strip()
    if not destination_name:
        destination_name = str(authority.active_region_id)
    return f"Travel complete. You arrive at {destination_name}."


def handle_travel(context: "CampaignContext", command_text: str, args: Optional[dict[str, Any]] = None) -> str:
    payload = dict(args or {})
    runtime = getattr(context, "kernel_runtime", {}) or {}
    if not runtime:
        from engine.api.campaign.live_kernel import ensure_kernel_runtime

        runtime = ensure_kernel_runtime(context)
    raw = command_text.strip().lower()
    action_id = str(payload.get("action_id", "")).strip().lower()
    if raw in {"continue travel", "resume travel"}:
        action_id = "advance"
    elif raw == "resolve travel encounter":
        action_id = "resolve_encounter"
    elif raw.startswith("travel") or not action_id:
        action_id = action_id or "start"

    active_state = _travel_runtime_state(context)
    if action_id == "start":
        if _travel_is_active(context):
            route = _current_travel_route(context)
            destination_name = str(route.get("destination_name", "your destination")) if route is not None else "your destination"
            context.campaign_state["last_travel_hours"] = 0
            _set_travel_scene(context, "travel")
            return f"You are already traveling to {destination_name}. Use continue travel to keep moving."
        selected = _select_travel_route(context, command_text, payload)
        if selected is None:
            context.campaign_state["last_travel_hours"] = 0
            return "No reachable travel route matches that destination."
        kernel_world = runtime.get("world_state")
        if kernel_world is None:
            raise ValueError("Kernel world state is missing for travel start.")
        kernel_world.active_region_id = str(context.world.simulation_snapshot.active_region_id)
        travel_state = initiate_travel(
            kernel_world,
            str(context.world.simulation_snapshot.active_region_id),
            str(selected["destination_region_id"]),
            seed=_travel_seed(context, TravelState(
                status="preparing",
                origin_region_id=str(context.world.simulation_snapshot.active_region_id),
                destination_region_id=str(selected["destination_region_id"]),
                travel_hours_remaining=int(selected.get("travel_hours", 0) or 0),
                travel_hours_total=int(selected.get("travel_hours", 0) or 0),
                edge_id=str(selected.get("route_id", "")),
                danger_level=int(selected.get("danger_level", 0) or 0),
            ), "start"),
        )
        travel_state.edge_id = str(selected.get("route_id", "")).strip() or travel_state.edge_id
        runtime["travel_state"] = travel_state
        discover_travel_topics(
            context,
            destination_region_id=str(selected.get("destination_region_id", "")).strip(),
            destination_settlement_id=str(selected.get("destination_settlement_id", "")).strip(),
        )
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return (
            f"You set out for {selected['destination_name']}. "
            f"The route will take about {int(selected.get('travel_hours', 0) or 0)}h."
        )

    if not _travel_is_active(context):
        context.campaign_state["last_travel_hours"] = 0
        return "No active travel route. Start traveling first."

    if action_id == "resolve_encounter":
        if not active_state.paused_for_encounter or active_state.encounter_resolved:
            context.campaign_state["last_travel_hours"] = 0
            _set_travel_scene(context, "travel")
            return "There is no unresolved travel encounter to resolve."
        runtime["travel_state"] = resolve_travel_encounter(active_state)
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return "You regroup and resolve the travel encounter. The route can continue."

    if action_id != "advance":
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return f"Unsupported travel action '{action_id}'."

    if active_state.paused_for_encounter and not active_state.encounter_resolved:
        context.campaign_state["last_travel_hours"] = 0
        _set_travel_scene(context, "travel")
        return "Travel is paused by an encounter. Resolve the travel encounter before moving on."

    ticking_state = TravelState.from_dict(active_state.to_dict())
    if str(ticking_state.status).strip().lower() == "preparing":
        ticking_state.status = "traveling"
    updated = tick_travel(ticking_state, seed=_travel_seed(context, ticking_state, "advance"))
    runtime["travel_state"] = updated
    context.campaign_state["last_travel_hours"] = 1
    _set_travel_scene(context, "travel")
    route = _current_travel_route(context)
    destination_name = str(route.get("destination_name", "your destination")) if route is not None else "your destination"
    if updated.paused_for_encounter and not updated.encounter_resolved:
        return f"Travel toward {destination_name} is interrupted by an encounter."
    if updated.status in {"arriving", "arrived"} or updated.travel_hours_remaining <= 0:
        return _apply_completed_travel(context, updated)
    return (
        f"You continue toward {destination_name}. "
        f"{int(updated.travel_hours_remaining)}h remain on the route."
    )


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
    talk_types = {"npc", "creature", "monster", "animal"}
    resolved = resolve_live_actor_query(
        actors,
        npc_query,
        allow_dead=False,
        actor_types=talk_types,
    )
    if resolved.error:
        return (resolved.error, "dialog", 0)
    target_actor = resolved.actor
    if target_actor is None:
        return (f"No one named '{npc_query}' is here.", "dialog", 0)
    target_id = str(target_actor.identity.actor_id)

    npc_name = str(getattr(target_actor.identity, "display_name", npc_query)).strip() or npc_query
    if target_id in allied_actor_ids(context):
        return (f"{npc_name} is already traveling with you.", "party", 0)
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": target_id,
        "npc_name": npc_name,
        "ask_about": {},
    }
    dialog_payload = build_dialog_payload(context, f"{npc_name} turns to face you.")
    if not dialog_payload:
        clear_dialog_state(context)
        return (f"{npc_name} has nothing to say.", "dialog", 0)
    discover_npc_topics(context, target_actor)
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
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": npc_id,
        "npc_name": str(getattr(npc.identity, "display_name", npc_id)).strip() or npc_id,
        "ask_about": {},
    }
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
    from engine.api.campaign.crime import record_theft_incident
    from engine.kernel.store import attempt_steal, buy_identification, buy_item, sell_item, rent_room
    lower = command_text.lower().strip()
    runtime = context.kernel_runtime or {}
    stores = runtime.get("stores", [])
    actors = runtime.get("actors", {})
    player = actors.get("player")
    if player is None:
        return None
    item_registry = _item_registry()
    if lower.startswith("steal "):
        item_name = command_text[6:].strip()
        npc_part = ""
        if " from " in item_name:
            item_name, npc_part = item_name.rsplit(" from ", 1)
        item_name = item_name.strip()
        store = _find_store(stores, npc_part.strip())
        if store is None:
            return (f"No merchant found to steal '{item_name}' from.", "commerce", 1)
        store_item_id = _find_store_item_id(store, item_name)
        if not store_item_id:
            return (f"'{item_name}' is not in stock there.", "commerce", 1)
        d100_roll = Random(_steal_roll_seed(context, store_id=str(getattr(store, "store_id", "") or ""), item_id=store_item_id)).randint(1, 100)
        success, msg = attempt_steal(player, store, store_item_id, d100_roll=d100_roll)
        _normalize_runtime_inventory_items(player, item_registry=item_registry)
        record_theft_incident(
            context,
            item_id=store_item_id,
            store=store,
            detected=not success,
        )
        if success:
            return (f"Stole {store_item_id}. {msg}.", "commerce", 1)
        return (f"Steal failed: {msg}.", "commerce", 1)
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
        normalized_hint = npc_hint.lower().strip()
        for store in stores:
            store_id = str(getattr(store, "store_id", "") or "")
            label = str(getattr(store, "label", "") or "")
            npc_id = getattr(store, "npc_id", "") or ""
            if (
                normalized_hint in npc_id.lower()
                or normalized_hint in store_id.lower()
                or normalized_hint in label.lower()
            ):
                return store
    return stores[0] if stores else None


def _find_store_item_id(store: Any, item_name: str) -> str:
    normalized_query = str(item_name or "").strip().lower().replace(" ", "_")
    if not normalized_query:
        return ""
    item_ids = [
        str(getattr(item, "item_def_id", "") or "").strip()
        for item in list(getattr(store, "items", []) or [])
    ]
    for item_id in item_ids:
        if item_id.lower() == normalized_query:
            return item_id
    for item_id in item_ids:
        lowered = item_id.lower()
        if normalized_query in lowered or lowered in normalized_query:
            return item_id
    return ""


def _steal_roll_seed(context: "CampaignContext", *, store_id: str, item_id: str) -> int:
    runtime = context.kernel_runtime or {}
    game_state = runtime.get("game_state")
    world_time = getattr(game_state, "world_time", None) if game_state is not None else None
    game_tick = int(getattr(world_time, "game_tick", 0) or 0)
    return stable_seed(
        context.seed,
        context.campaign_id,
        "steal",
        store_id,
        item_id,
        game_tick,
    )


def _normalize_runtime_inventory_items(player: Any, *, item_registry: dict[str, Any]) -> None:
    from engine.kernel import item_stack_from_payload
    from engine.kernel.items import ItemInstance as KernelItemInstance

    inventory = list(getattr(player, "inventory", []) or [])
    normalized_inventory: list[Any] = []
    changed = False
    for index, item in enumerate(inventory):
        if not isinstance(item, KernelItemInstance):
            normalized_inventory.append(item)
            continue
        raw_item = dict(item_registry.get(item.item_def_id, {}) or {})
        raw_charges = getattr(item, "charges", -1)
        payload = {
            "id": item.item_def_id,
            "item_def_id": item.item_def_id,
            "name": str(raw_item.get("name", item.item_def_id)).strip() or item.item_def_id.replace("_", " ").title(),
            "type": str(raw_item.get("type", "misc")).strip() or "misc",
            "quantity": max(1, int(getattr(item, "stack_count", 1) or 1)),
            "charges": int(raw_charges) if raw_charges is not None else -1,
            "identified": bool(getattr(item, "identified", False)),
            "wear": int(getattr(item, "wear", 0) or 0),
        }
        if getattr(item, "equipped_slot", None):
            payload["equipped_slot"] = str(item.equipped_slot)
        normalized_inventory.append(item_stack_from_payload(payload, index=index))
        changed = True
    if changed:
        player.inventory[:] = normalized_inventory


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
