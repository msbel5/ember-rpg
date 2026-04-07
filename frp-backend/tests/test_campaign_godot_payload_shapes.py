import pytest
from fastapi.testclient import TestClient

from engine.api import campaign_routes
from main import app


client = TestClient(app)


def _create_campaign(*, seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _inject_usable_inventory_item(campaign_id: str, *, item_def_id: str = "field_tonic") -> None:
    from engine.kernel import item_stack_from_legacy_payload

    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    context.kernel_runtime["actors"]["player"].inventory.append(
        item_stack_from_legacy_payload(
            {
                "item_def_id": item_def_id,
                "name": "Field Tonic" if item_def_id == "field_tonic" else item_def_id.replace("_", " ").title(),
                "type": "consumable" if item_def_id == "field_tonic" else "wand",
                "heal": 6 if item_def_id == "field_tonic" else 0,
                "charges": 2 if item_def_id != "field_tonic" else 1,
                "quantity": 1,
            }
        )
    )


def _strip_usable_inventory_items(campaign_id: str) -> None:
    from engine.api.gameplay_bridge import _runtime_item_is_usable_now, _runtime_item_source

    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    player = context.kernel_runtime["actors"]["player"]
    player.inventory[:] = [
        item
        for item in player.inventory
        if not _runtime_item_is_usable_now(item, _runtime_item_source(item))
    ]


def _first_travel_destination(payload: dict) -> dict:
    travel_options = list(payload["campaign"]["travel_options"])
    destination = next(option for option in travel_options if not option.get("is_current"))
    assert destination["route_id"]
    return destination


def _first_store_item(payload: dict) -> tuple[str, str]:
    stores = list(payload["campaign"].get("stores", []))
    assert stores
    store = stores[0]
    items = list(store.get("items", []))
    assert items
    return str(store["store_id"]), str(items[0]["item_def_id"])


def test_campaign_snapshot_contains_godot_ready_map_and_settlement_payload():
    payload = _create_campaign(seed=42)
    campaign = payload["campaign"]
    sheet = campaign["character_sheet"]

    assert campaign["world_state"]["seed"] == 42
    assert campaign["game_state"]["campaign_id"] == payload["campaign_id"]
    assert campaign["game_state"]["party"] == ["player"]
    assert campaign["actors"]
    assert campaign["jobs"]
    assert campaign["systems"]["power_network"]["total_required"] >= 0
    assert campaign["map_data"]["metadata"]["map_type"] == "campaign_region"
    assert len(campaign["map_data"]["tiles"]) == 60
    assert len(campaign["map_data"]["tiles"][0]) == 80
    assert campaign["world_entities"]
    assert campaign["settlement"]["residents"]
    assert campaign["recent_event_log"]
    assert isinstance(sheet["equipment_topology"], dict)
    assert isinstance(sheet["equipment_modifiers"], dict)
    assert isinstance(sheet["attunement"], dict)
    assert isinstance(sheet["equipment_topology"]["slots"], dict)
    assert isinstance(sheet["equipment_topology"]["legacy_slot_aliases"], dict)
    assert isinstance(sheet["equipment_topology"]["coverage_summary"], dict)
    assert {"total_movement_penalty", "total_stealth_noise", "total_spell_interference"} <= set(sheet["equipment_modifiers"])
    assert {"slot_count", "attuned_item_ids", "available_slots"} <= set(sheet["attunement"])
    assert all("danger_level" in entry for entry in campaign["travel_options"])
    assert all("known" in entry for entry in campaign["travel_options"])
    assert all("visited" in entry for entry in campaign["travel_options"])


def test_campaign_command_preserves_godot_payload_shape():
    create = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotProbe",
            "player_class": "rogue",
            "adapter_id": "scifi_frontier",
            "profile_id": "standard",
            "seed": 99,
        },
    ).json()
    campaign_id = create["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": "defend"},
    )
    assert response.status_code == 200
    payload = response.json()
    sheet = payload["campaign"]["character_sheet"]

    assert payload["campaign"]["settlement"]["defense_posture"] == "fortified"
    assert payload["campaign"]["map_data"]["metadata"]["region_id"]
    assert payload["campaign"]["world"]["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["world_state"]["active_region_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["game_state"]["current_area_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["systems"]["temperature_state"]["ambient_band"]
    assert isinstance(sheet["equipment"]["slots"], dict)
    first_slot_items = next(iter(sheet["equipment"]["slots"].values()))
    assert isinstance(first_slot_items, list)
    assert {"canonical_slot", "coverage_zones", "armor_weight_class", "movement_penalty", "stealth_noise", "spell_interference", "attunement_required"} <= set(first_slot_items[0])


def test_campaign_advisor_response_shape_is_additive_for_godot_consumers():
    create = _create_campaign(seed=100)
    campaign_id = create["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "advisor",
            "args": {"action_id": "ask_dm", "query": "where should I go next"},
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["command_type"] == "advisor"
    assert payload["hours_advanced"] == 0
    assert isinstance(payload["advisor_view"], dict)
    assert {"intent", "answer_lines", "related_topic_ids", "suggested_commands", "blockers", "spoiler_safe"} <= set(payload["advisor_view"])
    assert "advisor" not in payload["campaign"]
    assert "advisor_view" not in payload["campaign"]


def test_campaign_combat_payload_shape_is_present_for_godot_consumers():
    create = client.post(
        "/game/campaigns",
        json={
            "player_name": "GodotCombatProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 101,
        },
    ).json()
    campaign_id = create["campaign_id"]
    _strip_usable_inventory_items(campaign_id)

    npcs = [
        actor for actor in create["campaign"]["actors"]
        if actor["identity"]["actor_id"] != "player"
        and actor["identity"].get("actor_type") == "npc"
        and actor.get("alive", True)
    ]
    if not npcs:
        pytest.skip("No NPCs in fresh campaign to attack")

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {npcs[0]['identity']['display_name']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    combat = payload["campaign"]["combat"]

    assert isinstance(combat["phase"], str)
    assert isinstance(combat["round"], int)
    assert isinstance(combat["turn_actor_id"], str)
    assert isinstance(combat["available_actions"], list)
    assert "cast" not in combat["available_actions"]
    assert "use_item" not in combat["available_actions"]
    assert isinstance(combat["combatants"], list)
    assert isinstance(combat["targets"], list)
    assert isinstance(combat["move_options"], list)
    assert any(entry["is_player"] for entry in combat["combatants"])
    assert all(isinstance(entry["position"], list) and len(entry["position"]) == 2 for entry in combat["combatants"])


def test_campaign_combat_payload_advertises_use_item_when_inventory_has_legal_item():
    create = _create_campaign(seed=151)
    campaign_id = create["campaign_id"]
    _inject_usable_inventory_item(campaign_id, item_def_id="field_tonic")

    npcs = [
        actor for actor in create["campaign"]["actors"]
        if actor["identity"]["actor_id"] != "player"
        and actor["identity"].get("actor_type") == "npc"
        and actor.get("alive", True)
    ]
    if not npcs:
        pytest.skip("No NPCs in fresh campaign to attack")

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {npcs[0]['identity']['display_name']}"},
    )
    assert response.status_code == 200
    payload = response.json()
    combat = payload["campaign"]["combat"]

    assert "use_item" in combat["available_actions"]


def test_campaign_crime_payload_shape_is_present_for_godot_consumers():
    create = _create_campaign(seed=188)
    campaign_id = create["campaign_id"]
    store_id, item_id = _first_store_item(create)

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "commerce",
            "args": {
                "action_id": "steal_item",
                "item_id": item_id,
                "store_id": store_id,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    crime = payload["campaign"]["crime_state"]

    assert payload["command_type"] == "commerce"
    assert isinstance(crime["wanted"], bool)
    assert isinstance(crime["active_bounty"], int)
    assert isinstance(crime["witness_count"], int)
    assert isinstance(crime["last_incident"], dict)
    assert {"crime_type", "severity", "target_id", "target_name", "faction_id", "settlement_id", "witnessed", "reported", "responses", "tick"} <= set(crime["last_incident"])


def test_campaign_travel_payload_shape_is_present_for_godot_consumers():
    create = _create_campaign(seed=202)
    campaign_id = create["campaign_id"]
    destination = _first_travel_destination(create)

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "travel",
            "args": {
                "action_id": "start",
                "route_id": destination["route_id"],
                "destination_region_id": destination["destination_region_id"],
                "destination_settlement_id": destination["destination_settlement_id"],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    campaign = payload["campaign"]
    travel_state = campaign["travel_state"]

    assert campaign["scene"] == "travel"
    assert isinstance(travel_state, dict)
    assert travel_state["route_id"] == destination["route_id"]
    assert travel_state["origin_region_id"] == create["campaign"]["world"]["active_region_id"]
    assert travel_state["destination_region_id"] == destination["destination_region_id"]
    assert travel_state["destination_settlement_id"] == destination["destination_settlement_id"]
    assert isinstance(campaign["travel_options"], list)
    assert all("danger_level" in entry for entry in campaign["travel_options"])
    assert all("known" in entry for entry in campaign["travel_options"])
    assert all("visited" in entry for entry in campaign["travel_options"])
