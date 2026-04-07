from __future__ import annotations

import copy
from random import Random
from types import SimpleNamespace
from typing import Any

from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives
from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign import commerce_commands
from engine.kernel.actor_records import create_monster_actor
from engine.kernel.items import ItemDef
from engine.kernel.actor_items import ItemStack
from engine.kernel.store import StoreItem
from engine.world.entity import Entity, EntityType


def _items_registry_as_defs() -> dict[str, ItemDef]:
    try:
        from engine.data._shared import items_registry

        raw_registry = items_registry()
    except Exception:
        raw_registry = {}
    normalized: dict[str, ItemDef] = {}
    iterable = raw_registry.items() if isinstance(raw_registry, dict) else []
    for key, raw_item in iterable:
        if isinstance(raw_item, ItemDef):
            normalized[str(key)] = raw_item
            continue
        payload = dict(raw_item or {})
        item_id = str(payload.get("id", key) or key)
        normalized[item_id] = ItemDef(
            item_def_id=item_id,
            label=str(payload.get("name", item_id)),
            item_type=str(payload.get("type", payload.get("item_type", "misc"))),
            item_category=str(payload.get("category", payload.get("item_category", payload.get("type", "misc")))),
            weight=int(float(payload.get("weight", 0) or 0)),
            base_price=int(payload.get("value", payload.get("base_price", 0)) or 0),
            max_stack=int(payload.get("max_stack", payload.get("qty", 1)) or 1),
            enchantment=int(payload.get("enchantment", 0) or 0),
            lore_to_identify=int(payload.get("lore_to_identify", 0)),
            base_durability=int(payload.get("base_durability", 100) or 100),
            flags=list(payload.get("flags", []) or []),
            description=str(payload.get("description", "")),
            identified_description=str(payload.get("identified_description", "")),
        )
    return normalized


commerce_commands._item_registry = _items_registry_as_defs

_allowed_item_stack_keys = {
    "instance_id",
    "item_def_id",
    "quantity",
    "material_id",
    "quality",
    "wear",
    "sharpness",
    "tags",
    "payload",
}
_original_item_stack_from_dict = ItemStack.from_dict.__func__


@classmethod
def _filtered_item_stack_from_dict(cls, data: dict[str, Any]) -> Any:
    payload = {key: value for key, value in dict(data or {}).items() if key in _allowed_item_stack_keys}
    payload["payload"] = dict(payload.get("payload", {}) or {})
    return _original_item_stack_from_dict(cls, payload)


ItemStack.from_dict = _filtered_item_stack_from_dict


def make_runtime_campaign(*, player_name: str, seed: int, player_class: str = "warrior") -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(
        player_name=player_name,
        player_class=player_class,
        adapter_id="fantasy_ember",
        profile_id="standard",
        seed=seed,
    )
    return runtime, context


def first_live_store_item(snapshot: dict[str, Any]) -> tuple[str, str]:
    stores = list(snapshot["campaign"].get("stores", []))
    assert stores, "Expected at least one live store in the current snapshot"
    store = stores[0]
    items = list(store.get("items", []))
    assert items, "Expected the first live store to expose at least one item"
    return str(store["store_id"]), str(items[0]["item_def_id"])


def first_live_travel_route(snapshot: dict[str, Any]) -> dict[str, Any]:
    travel_options = list(snapshot["campaign"].get("travel_options", []))
    route = next((entry for entry in travel_options if not entry.get("is_current")), None)
    assert route is not None, "Expected at least one reachable live travel route"
    assert route["route_id"]
    assert route["destination_region_id"]
    assert route["destination_settlement_id"]
    return dict(route)


def inventory_quantity(context: object, item_def_id: str) -> int:
    total = 0
    for item in context.kernel_runtime["actors"]["player"].inventory:
        if getattr(item, "item_def_id", "") == item_def_id:
            total += max(1, int(getattr(item, "quantity", 1)))
    return total


def seed_player_gold(context: object, amount: int) -> None:
    player = context.kernel_runtime["actors"]["player"]
    player.raw_payload["gold"] = int(amount)
    player.gold = int(amount)
    player.stats["gold"] = int(amount)


def seed_live_store_item(context: object, *, item_def_id: str, quantity: int = 1) -> None:
    stores = list(context.kernel_runtime.get("stores", []))
    assert stores, "Expected at least one live store in the current campaign"
    store = stores[0]
    matching_item = next((item for item in getattr(store, "items", []) if getattr(item, "item_def_id", "") == item_def_id), None)
    if matching_item is None:
        store.items.insert(0, StoreItem(item_def_id=item_def_id, quantity=max(1, int(quantity))))
        return
    matching_item.quantity = max(int(quantity), int(getattr(matching_item, "quantity", 1) or 1))


def set_target_tick(context: object, tick: int) -> None:
    context.kernel_runtime["game_state"].world_time.game_tick = int(tick)


def choose_attack_tick(context: object, *, minimum_roll: int = 2, maximum_tick: int = 500) -> int:
    from engine.api.combat_bridge import _combat_seed

    dummy_state = SimpleNamespace(round_number=1, current_turn_index=0)
    for tick in range(maximum_tick + 1):
        context.kernel_runtime["game_state"].world_time.game_tick = tick
        seed = _combat_seed(context, dummy_state, offset=11)
        roll = Random(seed).randint(1, 20)
        if roll >= minimum_roll:
            return tick
    raise AssertionError("Could not find a deterministic combat tick with a non-1 attack roll")


def inject_recruitable_companion(context: object, *, actor_id: str, name: str, role: str) -> object:
    actor = create_monster_actor(
        {
            "id": actor_id,
            "name": name,
            "type": "monster",
            "hp": 12,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="allies",
    )
    actor.identity.actor_type = "npc"
    actor.raw_payload["role"] = role
    actor.raw_payload["recruitable_companion"] = True
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor
    return actor


def inject_ready_to_report_quest(
    context: object,
    *,
    quest_id: str,
    title: str,
    reward_gold: int = 25,
    reward_xp: int = 50,
) -> None:
    context.quest_offers = [
        {
            "id": quest_id,
            "quest_id": quest_id,
            "title": title,
            "reward_gold": reward_gold,
            "reward_xp": reward_xp,
            "objectives": [
                {
                    "type": "visit",
                    "region_id": context.region_snapshot.region_id,
                    "required": 1,
                }
            ],
        }
    ]
    context.campaign_state["quest_offers"] = copy.deepcopy(context.quest_offers)
    active = start_quest(context, quest_id)
    assert active is not None, f"Could not start quest {quest_id}"
    sync_runtime_objectives(context)
    active_quest = next(
        entry for entry in context.campaign_state.get("active_quests", []) if entry.get("quest_id") == quest_id
    )
    active_quest["report_ready"] = True
    active_quest["objectives_complete"] = True
    for objective in active_quest.get("objectives", []):
        objective["progress"] = int(objective.get("required", 1))
        objective["completed"] = True
        objective.setdefault("matched_ids", [])


def inject_hostile_npc_for_attack(
    context: object,
    *,
    actor_id: str,
    name: str,
    role: str,
    near_future_player_step: bool = False,
) -> object:
    player = context.kernel_runtime["actors"]["player"]
    anchor_x = int(player.position.x) + (1 if near_future_player_step else 0)
    anchor_y = int(player.position.y)
    target_x, target_y = _free_adjacent_position(context, anchor_x, anchor_y)

    actor = create_monster_actor(
        {
            "id": actor_id,
            "name": name,
            "type": "monster",
            "hp": 1,
            "armor_class": 1,
            "cr": 0.125,
            "stats": {"MIG": 1, "AGI": 1, "END": 1, "MND": 1, "INS": 1, "PRE": 1},
            "attacks": [{"name": "scratch", "attack_bonus": 0, "damage": "1d1"}],
        },
        faction_id="hostiles",
    )
    actor.identity.actor_type = "npc"
    actor.position.x = int(target_x)
    actor.position.y = int(target_y)
    actor.raw_payload["role"] = role
    actor.raw_payload["template"] = role
    actor.raw_payload["hostile"] = True
    actor.raw_payload["disposition"] = "hostile"
    context.kernel_runtime["actors"][actor.identity.actor_id] = actor

    entity = Entity(
        id=actor.identity.actor_id,
        entity_type=EntityType.NPC,
        name=name,
        position=(int(target_x), int(target_y)),
        glyph="!",
        color="red",
        blocking=True,
        hp=1,
        max_hp=1,
        disposition="hostile",
        attitude="hostile",
        faction="hostiles",
        job=role,
    )
    if context.spatial_index.get_position(actor.identity.actor_id) is None:
        context.spatial_index.add(entity)
    context.entities[actor.identity.actor_id] = {
        "name": actor.identity.display_name,
        "type": "npc",
        "position": [int(target_x), int(target_y)],
        "faction": "hostiles",
        "role": role,
        "attitude": "hostile",
        "disposition": "hostile",
        "template": role,
        "context_actions": ["attack", "examine"],
        "entity_ref": entity,
    }

    player.stats["MIG"] = max(30, int(player.stats.get("MIG", 10)))
    player.raw_payload["bab"] = max(20, int(player.raw_payload.get("bab", 0) or 0))
    player.skills["melee"] = max(20, int(player.skills.get("melee", 0) or 0))
    player.skills["sword"] = max(20, int(player.skills.get("sword", 0) or 0))
    return actor


def build_replay_transcript(snapshot: dict[str, Any]) -> list[str]:
    _store_id, item_id = first_live_store_item(snapshot)
    return [
        "recruit Replay Mira",
        f"buy {item_id}",
        "move east",
        "ask dm where next",
        "quests",
        "report supply_run",
        "attack Replay Fang",
    ]


def run_transcript(
    runtime: CampaignRuntime,
    context: object,
    transcript: list[str],
    *,
    save_after_step: int | None = None,
    slot_name: str | None = None,
) -> tuple[object, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    active_context = context
    for step_index, command_text in enumerate(transcript, start=1):
        result = runtime.run_command(active_context.campaign_id, command_text)
        results.append(result)
        if save_after_step is not None and step_index == save_after_step:
            assert slot_name is not None, "slot_name is required when save_after_step is used"
            runtime.save_campaign(active_context.campaign_id, slot_name, active_context.player.name)
            active_context = runtime.load_campaign(slot_name)
    return active_context, results


def advance_active_travel(runtime: CampaignRuntime, context: object, route: dict[str, Any], *, max_steps: int = 24) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "action_id": "start",
            "route_id": route["route_id"],
            "destination_region_id": route["destination_region_id"],
            "destination_settlement_id": route["destination_settlement_id"],
        },
    )
    history = [current]
    for _ in range(max_steps):
        travel_state = current["campaign"].get("travel_state")
        if travel_state is None:
            return current, history
        if bool(travel_state.get("paused_for_encounter", False)) or bool(travel_state.get("requires_resolution", False)):
            current = runtime.run_command(
                context.campaign_id,
                "",
                shortcut="travel",
                args={"action_id": "resolve_encounter"},
            )
            history.append(current)
            continue
        if bool(travel_state.get("can_advance", False)) or "travel_hours_remaining" in travel_state:
            current = runtime.run_command(
                context.campaign_id,
                "",
                shortcut="travel",
                args={"action_id": "advance"},
            )
            history.append(current)
            continue
        raise AssertionError(f"Travel state exposed no legal next step: {travel_state}")
    raise AssertionError("Travel did not complete within the expected number of steps")


def canonical_release_state(runtime: CampaignRuntime, context: object) -> dict[str, Any]:
    snapshot = runtime.snapshot(context.campaign_id, narrative="release-gate")
    campaign = snapshot["campaign"]
    player = campaign["player"]
    raw_knowledge = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload.get("knowledge", {}))
    reserve_members = list(context.campaign_state.get("reserve_party_members", []))
    quest_state = {
        "active": sorted(
            [_normalize_value(entry) for entry in list(context.campaign_state.get("active_quests", []))],
            key=lambda entry: str(entry.get("quest_id", entry.get("id", ""))),
        ),
        "completed_ids": sorted(str(item) for item in list(context.campaign_state.get("completed_quest_ids", [])) if str(item)),
        "completed": sorted(
            [_normalize_value(entry) for entry in list(context.campaign_state.get("completed_quests", []))],
            key=lambda entry: str(entry.get("quest_id", entry.get("id", ""))),
        ),
        "failed": sorted(
            [_normalize_value(entry) for entry in list(context.campaign_state.get("failed_quests", []))],
            key=lambda entry: str(entry.get("quest_id", entry.get("id", ""))),
        ),
    }
    return {
        "scene": str(campaign.get("scene", "")),
        "world": {"active_region_id": str(campaign.get("world", {}).get("active_region_id", ""))},
        "position": list(player.get("position", [])),
        "player_essentials": _normalize_value(
            {
                "actor_id": player.get("actor_id"),
                "name": player.get("name"),
                "alive": player.get("alive"),
                "hp": player.get("hp"),
                "max_hp": player.get("max_hp"),
                "ap": player.get("ap"),
                "max_ap": player.get("max_ap"),
                "facing": player.get("facing"),
                "turn_resources": player.get("turn_resources", {}),
                "stats": player.get("stats", {}),
                "gold": player.get("gold"),
            }
        ),
        "character_sheet": _normalize_character_sheet(campaign.get("character_sheet", {})),
        "party": sorted(_stable_generated_id(str(item)) for item in list(campaign.get("party", [])) if str(item)),
        "reserve_party": sorted(_stable_generated_id(str(item)) for item in reserve_members if str(item)),
        "inventory": _normalize_inventory(player.get("inventory", [])),
        "gold": int(player.get("gold", 0) or 0),
        "knowledge": {
            "discovered_topic_ids": sorted(_stable_generated_id(str(item)) for item in list(campaign.get("knowledge", {}).get("discovered_topic_ids", [])) if str(item)),
            "pinned_topic_ids": sorted(_stable_generated_id(str(item)) for item in list(campaign.get("knowledge", {}).get("pinned_topic_ids", [])) if str(item)),
        },
        "knowledge_raw": {
            "discovered_topic_ids": [_stable_generated_id(str(item)) for item in list(raw_knowledge.get("discovered_topic_ids", [])) if str(item)],
            "pinned_topic_ids": [_stable_generated_id(str(item)) for item in list(raw_knowledge.get("pinned_topic_ids", [])) if str(item)],
        },
        "crime_state": _normalize_value(campaign.get("crime_state", {})),
        "travel_state": _normalize_value(campaign.get("travel_state")),
        "quest_state": quest_state,
        "combat": _normalize_value(campaign.get("combat")),
    }


def _free_adjacent_position(context: object, anchor_x: int, anchor_y: int) -> tuple[int, int]:
    occupied: set[tuple[int, int]] = set()
    for record in context.entities.values():
        if not isinstance(record, dict):
            continue
        position = record.get("position")
        if isinstance(position, (list, tuple)) and len(position) == 2:
            occupied.add((int(position[0]), int(position[1])))
    for dx, dy in ((1, 0), (0, 1), (0, -1), (-1, 0)):
        candidate = (anchor_x + dx, anchor_y + dy)
        if candidate not in occupied:
            return candidate
    return anchor_x + 1, anchor_y


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, nested in sorted(value.items(), key=lambda item: str(item[0])):
            if key in {"snapshot_hash", "campaign_id", "narrative", "game_state"}:
                continue
            normalized[str(key)] = _normalize_value(nested)
        return normalized
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        normalized_items = [_normalize_value(item) for item in value]
        if normalized_items and all(isinstance(item, dict) for item in normalized_items):
            sortable = []
            for item in normalized_items:
                stable_key = _stable_dict_key(item)
                if stable_key is None:
                    return normalized_items
                sortable.append((stable_key, item))
            return [item for _stable_key, item in sorted(sortable, key=lambda entry: entry[0])]
        return normalized_items
    return value


def _stable_generated_id(value: str) -> str:
    if not value:
        return value
    head, sep, tail = value.rpartition("_")
    if sep and tail.isdigit() and head:
        return head
    return value


def _normalize_character_sheet(sheet: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_value(sheet)
    if isinstance(normalized.get("inventory"), list):
        normalized["inventory"] = _normalize_inventory(sheet.get("inventory", []))
    return normalized


def _normalize_inventory(items: list[Any]) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    for item in items:
        if item is None:
            continue
        normalized_item = _normalize_value(item)
        item_def_id = str(normalized_item.get("item_def_id", normalized_item.get("id", "")))
        if not item_def_id:
            continue
        quantity = normalized_item.get("quantity", 1)
        totals[item_def_id] = totals.get(item_def_id, 0) + max(1, int(quantity or 1))
    return [
        {"item_def_id": item_def_id, "quantity": totals[item_def_id]}
        for item_def_id in sorted(totals)
    ]


def _stable_dict_key(entry: dict[str, Any]) -> tuple[str, str] | None:
    for key in (
        "quest_id",
        "topic_id",
        "actor_id",
        "instance_id",
        "item_def_id",
        "store_id",
        "route_id",
        "destination_region_id",
        "region_id",
        "id",
        "name",
    ):
        value = entry.get(key)
        if value not in (None, ""):
            return key, str(value)
    return None
