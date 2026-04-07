from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from main import app
from engine.api import campaign_routes
from engine.kernel.actor_records import create_monster_actor
from engine.kernel.combat_engine import CombatState, CombatantEntry
from engine.kernel.hybrid_types import TravelState
from engine.world.entity import Entity, EntityType

client = TestClient(app)


def _create_campaign(seed: int) -> tuple[str, object]:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "AdvisorRuntime",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    campaign_id = response.json()["campaign_id"]
    return campaign_id, campaign_routes.campaign_runtime.get_campaign(campaign_id)


def _ask_dm(campaign_id: str, query: str) -> dict:
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"ask dm {query}"},
    )
    assert response.status_code == 200
    return response.json()


def _save_and_load(campaign_id: str, slot_name: str) -> tuple[dict, object]:
    save_response = client.post(
        f"/game/campaigns/{campaign_id}/save",
        json={"player_id": "AdvisorRuntime", "slot_name": slot_name},
    )
    assert save_response.status_code == 200
    loaded = client.post(f"/game/campaigns/load/{save_response.json()['save_id']}")
    assert loaded.status_code == 200
    payload = loaded.json()
    return payload, campaign_routes.campaign_runtime.get_campaign(payload["campaign_id"])


def _inject_companion(
    context,
    *,
    base_id: str,
    name: str,
    role: str,
    hostile: bool = False,
):
    companion = create_monster_actor(
        {
            "id": base_id,
            "name": name,
            "type": "monster",
            "hp": 12,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="raiders" if hostile else "allies",
    )
    companion.identity.actor_type = "npc"
    companion.raw_payload["role"] = role
    companion.raw_payload["hostile"] = hostile
    context.kernel_runtime["actors"][companion.identity.actor_id] = companion
    return companion


def _project_actor_entity(
    context,
    actor,
    *,
    position: tuple[int, int],
    attitude: str = "hostile",
    disposition: str = "hostile",
):
    entity = Entity(
        id=actor.identity.actor_id,
        entity_type=EntityType.NPC,
        name=actor.identity.display_name,
        position=(int(position[0]), int(position[1])),
        glyph="!" if attitude == "hostile" else "A",
        color="red" if attitude == "hostile" else "light_blue",
        blocking=True,
        hp=int(actor.stats.get("hp", 1)),
        max_hp=int(actor.stats.get("max_hp", actor.stats.get("hp", 1))),
        disposition=disposition,
        attitude=attitude,
        faction=getattr(actor.identity, "faction_id", None),
        job=str(actor.raw_payload.get("role", "companion")),
    )
    actor.position.x = int(position[0])
    actor.position.y = int(position[1])
    if context.spatial_index.get_position(actor.identity.actor_id) is None:
        context.spatial_index.add(entity)
    context.entities[actor.identity.actor_id] = {
        "name": actor.identity.display_name,
        "type": "npc",
        "position": [int(position[0]), int(position[1])],
        "faction": getattr(actor.identity, "faction_id", None),
        "role": str(actor.raw_payload.get("role", "companion")),
        "attitude": attitude,
        "disposition": disposition,
        "template": str(actor.raw_payload.get("template", actor.raw_payload.get("role", "companion"))),
        "context_actions": ["attack", "examine"] if attitude == "hostile" else ["talk", "examine"],
        "entity_ref": entity,
    }


def _install_combat_state(context, combat_state: CombatState) -> None:
    context.kernel_runtime["game_state"].raw_payload["combat"] = combat_state.to_dict()
    if context.dm_context is not None:
        context.dm_context.scene_type_name = "combat"


def _install_travel_state(
    context,
    *,
    status: str = "traveling",
    travel_hours_remaining: int | None = None,
    travel_hours_total: int | None = None,
):
    origin_region_id = str(context.region_snapshot.region_id)
    edge = next(
        item
        for item in context.world.travel_edges
        if str(item.get("from_region_id", "")) == origin_region_id or str(item.get("to_region_id", "")) == origin_region_id
    )
    destination_region_id = str(edge.get("to_region_id", "")) if str(edge.get("from_region_id", "")) == origin_region_id else str(edge.get("from_region_id", ""))
    total_hours = int(travel_hours_total if travel_hours_total is not None else edge.get("travel_hours", 4))
    remaining_hours = int(travel_hours_remaining if travel_hours_remaining is not None else max(0, total_hours - 1))
    travel_state = TravelState(
        status=status,
        origin_region_id=origin_region_id,
        destination_region_id=destination_region_id,
        travel_hours_remaining=remaining_hours,
        travel_hours_total=total_hours,
        edge_id=str(edge.get("id", f"{origin_region_id}->{destination_region_id}")),
        danger_level=2,
        encounter_triggered=False,
        paused_for_encounter=False,
        encounter_resolved=False,
        encounter_checked=False,
    )
    context.kernel_runtime["game_state"].raw_payload["travel_state"] = travel_state.to_dict()
    return travel_state


def _assert_no_advisor_keys(payload: dict) -> None:
    assert "advisor" not in payload
    assert "advisor_view" not in payload


def _assert_no_advisor_in_campaign(campaign: dict) -> None:
    _assert_no_advisor_keys(campaign)
    game_state = campaign.get("game_state", {})
    if isinstance(game_state, dict):
        _assert_no_advisor_keys(game_state.get("raw_payload", {}))
    for actor in campaign.get("actors", []):
        if isinstance(actor, dict):
            _assert_no_advisor_keys(actor.get("raw_payload", {}))


def _assert_no_advisor_in_context(context) -> None:
    _assert_no_advisor_keys(context.campaign_state)
    _assert_no_advisor_keys(context.campaign_state.get("campaign", {}))
    _assert_no_advisor_keys(context.kernel_runtime["game_state"].raw_payload)
    for actor in context.kernel_runtime["actors"].values():
        _assert_no_advisor_keys(actor.raw_payload)


def test_ask_dm_does_not_mutate_knowledge_raw_owner() -> None:
    campaign_id, context = _create_campaign(seed=90)
    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": ["fact.bridge", "region.start"],
        "pinned_topic_ids": ["fact.bridge"],
    }
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["knowledge"])

    result = _ask_dm(campaign_id, "what do I already know here")

    assert result["command_type"] == "advisor"
    assert "advisor_view" in result
    assert context.kernel_runtime["game_state"].raw_payload["knowledge"] == before
    _assert_no_advisor_in_campaign(result["campaign"])
    _assert_no_advisor_in_context(context)


def test_ask_dm_during_combat_does_not_change_turn_resources_or_turn_actor() -> None:
    campaign_id, context = _create_campaign(seed=91)
    companion = _inject_companion(context, base_id="api_advisor_ally", name="Api Rowan", role="guard")
    hostile = _inject_companion(context, base_id="api_advisor_enemy", name="Api Fang", role="raider", hostile=True)
    _project_actor_entity(context, companion, position=(int(context.position[0]) + 1, int(context.position[1])), attitude="friendly", disposition="friendly")
    _project_actor_entity(context, hostile, position=(int(context.position[0]) + 3, int(context.position[1])), attitude="hostile")

    combat_state = CombatState(
        combatants=[
            CombatantEntry(actor_id="player", initiative=21, is_player=True),
            CombatantEntry(actor_id=companion.identity.actor_id, initiative=18, is_player=True),
            CombatantEntry(actor_id=hostile.identity.actor_id, initiative=11, is_player=False),
        ],
        current_turn_index=1,
        phase="active",
    )
    combat_state.combatants[1].turn_resources.action = False
    combat_state.combatants[1].turn_resources.bonus_action = False
    combat_state.combatants[1].turn_resources.reaction = True
    combat_state.combatants[1].turn_resources.movement = 2
    combat_state.combatants[1].turn_resources.max_movement = 7
    _install_combat_state(context, combat_state)
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["combat"])

    result = _ask_dm(campaign_id, "what abilities should I use")

    assert result["command_type"] == "advisor"
    after = context.kernel_runtime["game_state"].raw_payload["combat"]
    assert after["phase"] == before["phase"]
    assert after["current_turn_index"] == before["current_turn_index"]
    assert after["combatants"][1]["actor_id"] == before["combatants"][1]["actor_id"]
    assert after["combatants"][1]["turn_resources"] == before["combatants"][1]["turn_resources"]
    assert result["campaign"]["combat"]["turn_actor_id"] == companion.identity.actor_id
    _assert_no_advisor_in_campaign(result["campaign"])
    _assert_no_advisor_in_context(context)


def test_ask_dm_during_travel_does_not_change_travel_state() -> None:
    campaign_id, context = _create_campaign(seed=92)
    travel_state = _install_travel_state(context, status="traveling", travel_hours_remaining=2, travel_hours_total=5)
    before = copy.deepcopy(context.kernel_runtime["game_state"].raw_payload["travel_state"])

    result = _ask_dm(campaign_id, "how dangerous is this road")

    assert result["command_type"] == "advisor"
    assert context.kernel_runtime["game_state"].raw_payload["travel_state"] == before
    assert result["campaign"]["travel_state"]["destination_region_id"] == travel_state.destination_region_id
    _assert_no_advisor_in_campaign(result["campaign"])
    _assert_no_advisor_in_context(context)


def test_ask_dm_during_dialog_does_not_mutate_conversation_ask_about_state() -> None:
    campaign_id, context = _create_campaign(seed=93)
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": "dialog_npc",
        "npc_name": "Dialog Sage",
        "ask_about_topic_ids": ["fact.bridge", "rumor.market"],
        "ask_about_selected_topic_id": "fact.bridge",
    }
    before = copy.deepcopy(context.conversation_state)

    result = _ask_dm(campaign_id, "what should I ask next")

    assert result["command_type"] == "advisor"
    assert context.conversation_state == before
    assert result["campaign"]["conversation_state"] == before
    _assert_no_advisor_in_campaign(result["campaign"])
    _assert_no_advisor_in_context(context)


def test_save_load_after_ask_dm_preserves_exact_gameplay_state() -> None:
    from engine.kernel.actor_items import ItemStack

    campaign_id, context = _create_campaign(seed=94)
    companion = _inject_companion(context, base_id="api_save_ally", name="Save Kest", role="guard")
    hostile = _inject_companion(context, base_id="api_save_enemy", name="Save Claw", role="raider", hostile=True)
    _project_actor_entity(context, companion, position=(int(context.position[0]) + 1, int(context.position[1]) + 1), attitude="friendly", disposition="friendly")
    _project_actor_entity(context, hostile, position=(int(context.position[0]) + 3, int(context.position[1]) + 1), attitude="hostile")

    player = context.kernel_runtime["actors"]["player"]
    player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) - 5)
    player.inventory.append(
        ItemStack(
            instance_id="advisor_api_bundle_1",
            item_def_id="rope",
            quantity=1,
            payload={"name": "Rope", "identified": True},
        )
    )
    context.kernel_runtime["game_state"].raw_payload["knowledge"] = {
        "discovered_topic_ids": ["fact.bridge", "region.start"],
        "pinned_topic_ids": ["fact.bridge"],
    }
    combat_state = CombatState(
        combatants=[
            CombatantEntry(actor_id="player", initiative=20, is_player=True),
            CombatantEntry(actor_id=companion.identity.actor_id, initiative=16, is_player=True),
            CombatantEntry(actor_id=hostile.identity.actor_id, initiative=10, is_player=False),
        ],
        current_turn_index=0,
        phase="active",
    )
    combat_state.combatants[0].turn_resources.action = False
    combat_state.combatants[0].turn_resources.bonus_action = True
    combat_state.combatants[0].turn_resources.reaction = True
    combat_state.combatants[0].turn_resources.movement = 3
    combat_state.combatants[0].turn_resources.max_movement = 6
    _install_combat_state(context, combat_state)

    ask_result = _ask_dm(campaign_id, "what should I prioritize")
    loaded_payload, loaded_context = _save_and_load(campaign_id, "advisor_api_stability_slot")

    assert ask_result["command_type"] == "advisor"
    assert ask_result["campaign"]["combat"] == loaded_payload["campaign"]["combat"]
    assert ask_result["campaign"]["knowledge"] == loaded_payload["campaign"]["knowledge"]
    assert ask_result["campaign"]["player"]["inventory"] == loaded_payload["campaign"]["player"]["inventory"]
    assert ask_result["campaign"]["character_sheet"]["inventory"] == loaded_payload["campaign"]["character_sheet"]["inventory"]
    assert ask_result["campaign"]["character_sheet"]["resources"] == loaded_payload["campaign"]["character_sheet"]["resources"]
    _assert_no_advisor_in_campaign(ask_result["campaign"])
    _assert_no_advisor_in_campaign(loaded_payload["campaign"])
    _assert_no_advisor_in_context(loaded_context)
