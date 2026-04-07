"""Targeted tests for the campaign-first API."""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from engine.api.campaign.runtime import CampaignRuntime
from engine.api import campaign_routes
from engine.kernel.gameplay import spawn_ground_item_entity
from main import app
from _seed_robust_helpers import (
    ensure_ask_about_topic,
    ensure_attack_target,
    ensure_talkable_authored_dialog_target,
)


client = TestClient(app)


def _inject_runtime_actor(context, actor_id: str, display_name: str, *, role: str, alive: bool = True):
    from engine.kernel.actor import ActorIdentity, ActorPosition
    from engine.kernel.actor_records import ActorRecord

    player = context.kernel_runtime["actors"]["player"]
    actor = ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=display_name, actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=3,
        max_action_points=3,
        alive=alive,
        stats=dict(player.stats),
        skills={},
        raw_payload={"role": role, "template": role},
    )
    context.kernel_runtime["actors"][actor_id] = actor
    return actor


def _inventory_quantity(context, item_def_id: str) -> int:
    total = 0
    for item in context.kernel_runtime["actors"]["player"].inventory:
        if getattr(item, "item_def_id", "") == item_def_id:
            total += max(1, int(getattr(item, "quantity", 1)))
    return total


def _create_campaign(adapter_id: str = "fantasy_ember", *, seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CampaignTester",
            "player_class": "warrior",
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _inject_usable_inventory_item(campaign_id: str, *, item_def_id: str = "field_tonic") -> None:
    from engine.kernel import item_stack_from_payload

    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    context.kernel_runtime["actors"]["player"].inventory.append(
        item_stack_from_payload(
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


def _first_travel_destination(payload: dict) -> dict:
    travel_options = list(payload["campaign"]["travel_options"])
    destination = next(option for option in travel_options if not option.get("is_current"))
    assert destination["route_id"]
    assert destination["destination_region_id"]
    return destination


def _first_store_item(payload: dict) -> tuple[str, str]:
    stores = list(payload["campaign"].get("stores", []))
    assert stores
    store = stores[0]
    items = list(store.get("items", []))
    assert items
    return str(store["store_id"]), str(items[0]["item_def_id"])


def test_create_campaign_returns_campaign_snapshot():
    payload = _create_campaign()
    assert payload["adapter_id"] == "fantasy_ember"
    assert payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["world_state"]["active_region_id"]
    assert payload["campaign"]["game_state"]["campaign_id"] == payload["campaign_id"]
    assert payload["campaign"]["game_state"]["current_area_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["game_state"]["actors"]["player"]["identity"]["actor_id"] == "player"
    assert payload["campaign"]["world_state"]["regions"]
    assert payload["campaign"]["actors"]
    assert payload["campaign"]["actors"][0]["identity"]["actor_id"] == "player"
    assert payload["campaign"]["jobs"]
    assert payload["campaign"]["reactions"]
    assert payload["campaign"]["worksites"]
    assert payload["campaign"]["colony_pressure"]["food"] >= 0
    assert "shortages" in payload["campaign"]["production_ledger"]
    assert payload["campaign"]["path_authority"]["active_region_id"]
    assert payload["campaign"]["local_map_state"]["region_id"] == payload["campaign"]["world"]["active_region_id"]
    assert payload["campaign"]["military"]["squads"]
    assert "power_network" in payload["campaign"]["systems"]
    assert "syndrome_registry" in payload["campaign"]["systems"]
    assert payload["campaign"]["world_graph"]["nodes"]
    assert payload["campaign"]["travel_options"]
    assert all(entry["route_id"] for entry in payload["campaign"]["travel_options"])
    assert all(entry["reachable"] is True for entry in payload["campaign"]["travel_options"])
    assert all("is_current" in entry for entry in payload["campaign"]["travel_options"])
    assert payload["campaign"]["current_region_summary"]["settlement_node_id"]
    assert payload["campaign"]["settlement"]["residents"]
    assert payload["campaign"]["region"]["width"] == 80
    assert payload["campaign"]["region"]["height"] == 60


def test_campaign_client_health_endpoint_reports_required_capabilities():
    response = client.get("/game/health/campaign-client")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "campaign_creation": True,
        "campaign_runtime": True,
        "campaign_save_load": True,
        "schema_version": "4.0",
    }


def test_create_scifi_campaign_returns_scifi_world_state():
    payload = _create_campaign("scifi_frontier")
    assert payload["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["world"]["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["settlement"]["adapter_id"] == "scifi_frontier"


def test_campaign_command_and_region_endpoints_work():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    command = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": "look around"})
    assert command.status_code == 200
    body = command.json()
    assert body["command_type"] == "exploration"
    assert body["campaign"]["recent_event_log"]
    assert body["campaign"]["jobs"]
    assert "unrest" in body["campaign"]["colony_pressure"]
    assert body["campaign"]["path_authority"]["active_region_id"] == body["campaign"]["world"]["active_region_id"]
    assert body["campaign"]["systems"]["power_network"]["total_required"] >= 0

    region = client.get(f"/game/campaigns/{campaign_id}/region/current")
    assert region.status_code == 200
    region_payload = region.json()
    assert region_payload["metadata"]["explainability"]["terrain_driver"]

    settlement = client.get(f"/game/campaigns/{campaign_id}/settlement/current")
    assert settlement.status_code == 200
    assert settlement.json()["rooms"]


def test_campaign_travel_shortcut_starts_active_travel_without_immediate_region_switch():
    payload = _create_campaign(seed=123)
    campaign_id = payload["campaign_id"]
    origin_region_id = payload["campaign"]["world"]["active_region_id"]
    origin_path_region_id = payload["campaign"]["path_authority"]["active_region_id"]
    destination = _first_travel_destination(payload)

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
    body = response.json()
    campaign = body["campaign"]

    assert body["command_type"] == "travel"
    assert campaign["scene"] == "travel"
    assert campaign["world"]["active_region_id"] == origin_region_id
    assert campaign["path_authority"]["active_region_id"] == origin_path_region_id
    assert isinstance(campaign["travel_state"], dict)
    assert campaign["travel_state"]["route_id"] == destination["route_id"]
    assert campaign["travel_state"]["origin_region_id"] == origin_region_id
    assert campaign["travel_state"]["destination_region_id"] == destination["destination_region_id"]
    assert campaign["travel_state"]["destination_settlement_id"] == destination["destination_settlement_id"]
    assert campaign["travel_state"]["destination_name"] == destination["destination_name"]
    assert campaign["travel_state"]["travel_hours_total"] >= campaign["travel_state"]["travel_hours_remaining"] >= 0
    assert "danger_level" in campaign["travel_state"]
    assert "encounter_triggered" in campaign["travel_state"]
    assert "paused_for_encounter" in campaign["travel_state"]
    assert "encounter_resolved" in campaign["travel_state"]
    assert "can_advance" in campaign["travel_state"]
    assert "requires_resolution" in campaign["travel_state"]


def test_campaign_knowledge_shortcut_returns_knowledge_view_shape():
    payload = _create_campaign(seed=321)
    campaign_id = payload["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "knowledge",
            "args": {"action_id": "topics"},
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["command_type"] == "knowledge"
    assert isinstance(body["campaign"]["knowledge"], dict)
    assert "knowledge_view" in body
    assert isinstance(body["knowledge_view"]["topics"], list)
    assert isinstance(body["campaign"]["knowledge"]["discovered_topic_ids"], list)
    assert isinstance(body["campaign"]["knowledge"]["pinned_topic_ids"], list)


def test_campaign_advisor_shortcut_returns_advisor_view_shape():
    payload = _create_campaign(seed=322)
    campaign_id = payload["campaign_id"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "advisor",
            "args": {"action_id": "ask_dm", "query": "what should I do next"},
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["command_type"] == "advisor"
    assert body["hours_advanced"] == 0
    assert isinstance(body["advisor_view"], dict)
    assert isinstance(body["advisor_view"]["answer_lines"], list)
    assert isinstance(body["advisor_view"]["related_topic_ids"], list)
    assert body["advisor_view"]["spoiler_safe"] is True
    assert "advisor" not in body["campaign"]
    assert "advisor_view" not in body["campaign"]


def test_campaign_raw_ask_dm_works_during_active_travel():
    payload = _create_campaign(seed=323)
    campaign_id = payload["campaign_id"]
    destination = _first_travel_destination(payload)

    started = client.post(
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
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["command_type"] == "travel"

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": "ask dm how dangerous is this road"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["command_type"] == "advisor"
    assert body["hours_advanced"] == 0
    assert body["campaign"]["scene"] == "travel"
    assert body["campaign"]["travel_state"]["route_id"] == destination["route_id"]
    assert isinstance(body["advisor_view"], dict)


def test_campaign_commerce_shortcut_steal_item_returns_crime_state_shape():
    payload = _create_campaign(seed=324)
    campaign_id = payload["campaign_id"]
    store_id, item_id = _first_store_item(payload)

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
    body = response.json()

    assert body["command_type"] == "commerce"
    assert isinstance(body["campaign"]["crime_state"], dict)
    assert {"wanted", "active_bounty", "witness_count", "last_incident"} <= set(body["campaign"]["crime_state"])
    assert body["campaign"]["crime_state"]["last_incident"]["crime_type"] == "theft"


def test_campaign_talk_command_returns_dialog_payload_when_conversation_is_active():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    talkable = ensure_talkable_authored_dialog_target(campaign_id, actor_id="campaign_api_talker", name="Campaign API Scholar")

    response = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": f"talk {talkable['name']}"})
    assert response.status_code == 200
    body = response.json()

    assert body.get("dialog_npc") == talkable["name"]
    assert body.get("dialog_text")
    assert body.get("dialog_options")
    assert all(opt["command"].startswith("dialog ") for opt in body["dialog_options"])
    assert all("enabled" in option for option in body["dialog_options"])
    assert all("disabled_reason" in option for option in body["dialog_options"])
    assert any("skill_check" in option for option in body["dialog_options"])


def test_campaign_dialog_shortcut_ask_about_returns_additive_payload_during_active_conversation():
    payload = _create_campaign(seed=42)
    campaign_id = payload["campaign_id"]
    talkable = ensure_talkable_authored_dialog_target(campaign_id, actor_id="campaign_api_asker", name="Campaign API Chronicler")
    topic_id = ensure_ask_about_topic(campaign_id, actor_id=talkable["actor_id"], actor_name=talkable["name"])

    opened = client.post(f"/game/campaigns/{campaign_id}/commands", json={"input": f"talk {talkable['name']}"})
    assert opened.status_code == 200
    assert opened.json().get("dialog_npc") == talkable["name"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "dialog",
            "args": {"action_id": "ask_about", "topic_id": topic_id},
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["command_type"] == "dialog"
    assert isinstance(body["knowledge_view"], dict)
    assert isinstance(body["knowledge_view"]["ask_about"], dict)
    assert body["knowledge_view"]["ask_about"]["topic"]["topic_id"] == topic_id
    assert body["knowledge_view"]["ask_about"]["response_type"] in {"fact", "rumor", "redirect", "refusal"}
    assert isinstance(body["knowledge_view"]["ask_about"]["facts"], list)
    assert isinstance(body["knowledge_view"]["ask_about"]["rumors"], list)
    assert isinstance(body["knowledge_view"]["ask_about"]["redirect_topic_ids"], list)
    assert isinstance(body["campaign"]["conversation_state"]["ask_about"], dict)
    assert body["campaign"]["conversation_state"]["ask_about"]["topic"]["topic_id"] == topic_id


def test_campaign_attack_command_marks_scene_as_combat_when_combat_payload_exists():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    target = ensure_attack_target(campaign_id, actor_id="campaign_api_combat_target", name="Campaign API Fang")

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target['name']}"},
    )
    assert response.status_code == 200
    body = response.json()

    # Combat bridge returns command_type="combat" and builds combat state.
    assert body["command_type"] == "combat"
    assert body["campaign"]["scene"] == "combat"
    assert body["campaign"]["combat"]
    assert body["campaign"]["combat"]["phase"]
    assert "turn_actor_id" in body["campaign"]["combat"]
    assert "available_actions" in body["campaign"]["combat"]
    assert "targets" in body["campaign"]["combat"]


def test_campaign_command_accepts_shortcut_combat_request_shape():
    payload = _create_campaign(seed=50)
    campaign_id = payload["campaign_id"]
    target = ensure_attack_target(campaign_id, actor_id="campaign_api_structured_target", name="Campaign API Raider")

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "combat",
            "args": {"action_id": "attack", "target_id": target["actor_id"], "called_shot": "head"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["command_type"] == "combat"
    assert body["campaign"]["combat"]
    assert isinstance(body["campaign"]["combat"]["available_actions"], list)
    assert "cast" not in body["campaign"]["combat"]["available_actions"]


def test_campaign_command_accepts_structured_combat_use_item_request_shape():
    payload = _create_campaign(seed=150)
    campaign_id = payload["campaign_id"]
    _inject_usable_inventory_item(campaign_id, item_def_id="field_tonic")
    target = ensure_attack_target(campaign_id, actor_id="campaign_api_use_item_target", name="Campaign API Brute")

    attack = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target['name']}"},
    )
    assert attack.status_code == 200
    started = attack.json()
    assert "use_item" in started["campaign"]["combat"]["available_actions"]

    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "combat",
            "args": {"action_id": "use_item", "item_id": "field_tonic"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["command_type"] == "combat"
    assert "used field tonic" in body["narrative"].lower()
    assert body["campaign"]["scene"] == "combat"


def test_campaign_save_and_load_round_trip():
    payload = _create_campaign()
    campaign_id = payload["campaign_id"]
    saved = client.post(
        f"/game/campaigns/{campaign_id}/save",
        json={"player_id": "CampaignTester", "slot_name": "campaign_v3_slot"},
    )
    assert saved.status_code == 200
    save_id = saved.json()["save_id"]

    saves = client.get(f"/game/campaigns/{campaign_id}/saves")
    assert saves.status_code == 200
    assert any(entry["save_id"] == save_id for entry in saves.json())

    loaded = client.post(f"/game/campaigns/load/{save_id}")
    assert loaded.status_code == 200
    loaded_payload = loaded.json()
    assert loaded_payload["campaign"]["world"]["seed"] == 42
    assert loaded_payload["campaign"]["world_state"]["seed"] == 42
    assert loaded_payload["campaign"]["game_state"]["seed"] == 42
    assert loaded_payload["campaign"]["game_state"]["party"] == ["player"]
    assert loaded_payload["campaign"]["actors"]
    assert loaded_payload["campaign"]["systems"]["temperature_state"]["ambient_band"]
    assert loaded_payload["campaign"]["settlement"]["name"]


def test_report_quest_marks_completion_and_applies_rewards_once():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Reporter", "warrior", "fantasy_ember", "standard", 42)
    context.quest_offers = [{
        "id": "supply_run",
        "quest_id": "supply_run",
        "title": "Supply Run",
        "reward_gold": 25,
        "reward_xp": 50,
        "objectives": [{"type": "visit", "region_id": context.region_snapshot.region_id, "required": 1}],
    }]
    context.campaign_state["quest_offers"] = list(context.quest_offers)

    from engine.api.campaign.quest_bridge import start_quest, sync_runtime_objectives

    start_quest(context, "supply_run")
    sync_runtime_objectives(context)
    player = context.kernel_runtime["actors"]["player"]
    before_gold = int(player.raw_payload.get("gold", 0))
    before_xp = int(player.raw_payload.get("xp", 0))

    first = runtime.run_command(context.campaign_id, "report supply_run")
    second = runtime.run_command(context.campaign_id, "report supply_run")

    assert first["command_type"] == "quest"
    assert "Completed quest: Supply Run." in first["narrative"]
    assert second["narrative"] == "Quest 'supply_run' has already been reported."
    assert "supply_run" in context.campaign_state["completed_quest_ids"]
    assert "supply_run" not in {entry.get("quest_id") for entry in context.campaign_state.get("active_quests", [])}
    assert int(player.raw_payload.get("gold", 0)) == before_gold + 25
    assert int(player.raw_payload.get("xp", 0)) == before_xp + 50


def test_new_campaign_seeds_only_level_gated_authored_act_one_offers():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Author", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers

    offers = {offer["quest_id"] for offer in current_quest_offers(context)}

    assert "tutorial_troubled_village" in offers
    assert "side_road_to_peaks" not in offers
    assert "main_shadows_over_aldenmoor" not in offers


def test_new_campaign_also_exposes_live_procedural_region_offers():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("WorldQuester", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers

    procedural = [offer for offer in current_quest_offers(context) if offer.get("source") == "procedural_region"]

    assert procedural
    assert all(str(offer.get("quest_id", "")).startswith(f"{context.region_snapshot.region_id}_") for offer in procedural)
    assert all(offer.get("kind") for offer in procedural)


def test_accepting_authored_offer_normalizes_required_count_objectives():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Normalizer", "warrior", "fantasy_ember", "standard", 42)

    result = runtime.run_command(context.campaign_id, "accept tutorial_troubled_village")

    assert result["command_type"] == "quest"
    quest = next(entry for entry in context.campaign_state["active_quests"] if entry["quest_id"] == "tutorial_troubled_village")
    required_by_id = {objective["id"]: objective["required"] for objective in quest["objectives"]}
    assert required_by_id["tutorial_act_1_speak_with_elder"] == 1
    assert required_by_id["tutorial_act_1_reach_farmstead"] == 1
    assert required_by_id["tutorial_act_1_defeat_wolves"] == 3
    assert required_by_id["tutorial_act_1_drive_off_scouts"] == 2
    assert quest["source"] == "authored_campaign"
    assert quest["campaign_id"] == "tutorial_campaign"
    assert quest["act_id"] == "act_1"


def test_authored_campaign_progress_report_unlocks_next_act_and_survives_save_load():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Questline", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers, start_quest, sync_runtime_objectives

    quest = start_quest(context, "main_shadows_over_aldenmoor")
    assert quest is not None

    spawn_ground_item_entity(context, item={"id": "wanted_poster", "name": "Wanted Poster", "qty": 1})
    pickup = runtime.run_command(context.campaign_id, "pickup wanted poster")
    assert pickup["command_type"] == "inventory"

    context.dm_context.location = "Kings Road Checkpoint"
    context.conversation_state = {
        "target_type": "npc",
        "npc_id": "aldenmoor_gate_captain",
        "npc_name": "Aldenmoor Gate Captain",
    }
    for index in range(3):
        _inject_runtime_actor(context, f"bandit_{index}", f"Bandit {index}", role="bandit", alive=False)
    _inject_runtime_actor(context, "captain_malgrave", "Captain Malgrave", role="bandit_captain", alive=False)

    before_longsword = _inventory_quantity(context, "longsword")
    before_chain = _inventory_quantity(context, "chain_shirt")
    before_potions = _inventory_quantity(context, "potion_of_healing")
    before_captain_scimitar = _inventory_quantity(context, "captain_scimitar")
    before_gold_coins = _inventory_quantity(context, "gold_coin")

    sync_runtime_objectives(context)
    active_quest = next(entry for entry in context.campaign_state["active_quests"] if entry["quest_id"] == "main_shadows_over_aldenmoor")
    objective_progress = {objective["id"]: objective for objective in active_quest["objectives"]}
    assert objective_progress["main_act_1_reach_kings_road"]["progress"] == 1
    assert objective_progress["main_act_1_clear_bandit_toll"]["progress"] == 3
    assert objective_progress["main_act_1_defeat_captain_malgrave"]["progress"] == 1
    assert objective_progress["main_act_1_recover_wanted_poster"]["progress"] == 1
    assert objective_progress["main_act_1_report_to_gate_captain"]["progress"] == 1
    assert active_quest["report_ready"] is True

    first = runtime.run_command(context.campaign_id, "report main_shadows_over_aldenmoor")
    second = runtime.run_command(context.campaign_id, "report main_shadows_over_aldenmoor")

    assert first["command_type"] == "quest"
    assert second["narrative"] == "Quest 'main_shadows_over_aldenmoor' has already been reported."
    assert _inventory_quantity(context, "longsword") == before_longsword + 1
    assert _inventory_quantity(context, "chain_shirt") == before_chain + 1
    assert _inventory_quantity(context, "potion_of_healing") == before_potions + 3
    assert _inventory_quantity(context, "captain_scimitar") == before_captain_scimitar + 1
    assert _inventory_quantity(context, "gold_coin") == before_gold_coins + 75
    unlocked = {offer["quest_id"] for offer in current_quest_offers(context)}
    assert "main_archmages_tower" in unlocked

    runtime.save_campaign(context.campaign_id, "authored_campaign_slot", "Questline")
    loaded = runtime.load_campaign("authored_campaign_slot")
    loaded_offers = {offer["quest_id"] for offer in current_quest_offers(loaded)}
    assert "main_archmages_tower" in loaded_offers
    assert "main_shadows_over_aldenmoor" in loaded.campaign_state["completed_quest_ids"]


def test_travel_does_not_erase_authored_offers():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Traveler", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers

    before = {offer["quest_id"] for offer in current_quest_offers(context)}
    destination = next(option for option in runtime.snapshot(context.campaign_id)["campaign"]["travel_options"] if not option["is_current"])

    travel = runtime.run_command(context.campaign_id, f"travel {destination['destination_region_id']}")
    after = {offer["quest_id"] for offer in current_quest_offers(context)}

    assert travel["command_type"] == "travel"
    assert "tutorial_troubled_village" in before
    assert "tutorial_troubled_village" in after


def test_world_tick_refreshes_live_region_procedural_offer_ids():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Ticker", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers
    from engine.api.campaign.runtime_commands import advance_world_tick

    before = {
        offer["quest_id"]
        for offer in current_quest_offers(context)
        if offer.get("source") == "procedural_region"
    }

    advance_world_tick(context, hours=24)

    after = {
        offer["quest_id"]
        for offer in current_quest_offers(context)
        if offer.get("source") == "procedural_region"
    }

    assert before
    assert after
    assert before != after
    assert all(quest_id.startswith(f"{context.region_snapshot.region_id}_") for quest_id in after)


def test_travel_switches_procedural_offers_to_destination_region():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("TravelerOffers", "warrior", "fantasy_ember", "standard", 42)

    from engine.api.campaign.quest_bridge import current_quest_offers

    start_region_id = context.region_snapshot.region_id
    before = {
        offer["quest_id"]
        for offer in current_quest_offers(context)
        if offer.get("source") == "procedural_region"
    }
    destination = next(option for option in runtime.snapshot(context.campaign_id)["campaign"]["travel_options"] if not option["is_current"])

    started = runtime.run_command(
        context.campaign_id,
        "",
        shortcut="travel",
        args={
            "action_id": "start",
            "route_id": destination["route_id"],
            "destination_region_id": destination["destination_region_id"],
            "destination_settlement_id": destination["destination_settlement_id"],
        },
    )
    assert started["command_type"] == "travel"

    while context.region_snapshot.region_id != destination["destination_region_id"]:
        runtime.run_command(context.campaign_id, "continue travel")

    after = {
        offer["quest_id"]
        for offer in current_quest_offers(context)
        if offer.get("source") == "procedural_region"
    }
    assert context.region_snapshot.region_id == destination["destination_region_id"]
    assert context.region_snapshot.region_id != start_region_id
    assert before
    assert after
    assert before != after
    assert all(quest_id.startswith(f"{context.region_snapshot.region_id}_") for quest_id in after)


def test_collect_objective_survives_inventory_command_and_keeps_progress_details():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Collector", "warrior", "fantasy_ember", "standard", 42)
    context.quest_offers = [{
        "id": "collect_ore",
        "quest_id": "collect_ore",
        "title": "Collect Ore",
        "description": "Bring back one bundle of ore.",
        "objectives": [{"type": "collect", "item_def_id": "iron_ore", "required": 1}],
    }]
    context.campaign_state["quest_offers"] = list(context.quest_offers)

    from engine.api.campaign.quest_bridge import start_quest

    start_quest(context, "collect_ore")
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1})

    result = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert result["command_type"] == "inventory"
    active_quest = context.campaign_state["active_quests"][0]
    objective = active_quest["objectives"][0]
    assert objective["type"] == "collect"
    assert objective["item_def_id"] == "iron_ore"
    assert objective["progress"] == 1
    assert objective["completed"] is True
    assert active_quest["report_ready"] is True


def test_visit_objective_survives_projection_refresh_and_keeps_progress_details():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Scout", "warrior", "fantasy_ember", "standard", 42)
    context.quest_offers = [{
        "id": "survey_region",
        "quest_id": "survey_region",
        "title": "Survey Region",
        "description": "Confirm the current region is secure.",
        "objectives": [{"type": "visit", "region_id": context.region_snapshot.region_id, "required": 1}],
    }]
    context.campaign_state["quest_offers"] = list(context.quest_offers)

    from engine.api.campaign.quest_bridge import start_quest

    start_quest(context, "survey_region")
    result = runtime.run_command(context.campaign_id, "look around")

    assert result["command_type"] == "exploration"
    active_quest = context.campaign_state["active_quests"][0]
    objective = active_quest["objectives"][0]
    assert objective["type"] == "visit"
    assert objective["region_id"] == context.region_snapshot.region_id
    assert objective["progress"] == 1
    assert objective["completed"] is True
    assert active_quest["report_ready"] is True


def test_load_campaign_preserves_active_quest_objectives_and_progress():
    runtime = CampaignRuntime()
    context = runtime.create_campaign("Loader", "warrior", "fantasy_ember", "standard", 42)
    context.quest_offers = [{
        "id": "collect_ore",
        "quest_id": "collect_ore",
        "title": "Collect Ore",
        "description": "Bring back one bundle of ore.",
        "objectives": [{"type": "collect", "item_def_id": "iron_ore", "required": 1}],
    }]
    context.campaign_state["quest_offers"] = list(context.quest_offers)

    from engine.api.campaign.quest_bridge import start_quest

    start_quest(context, "collect_ore")
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1})
    runtime.run_command(context.campaign_id, "pickup iron ore")
    runtime.save_campaign(context.campaign_id, "quest_progress_slot", "Loader")

    loaded = runtime.load_campaign("quest_progress_slot")

    active_quest = loaded.campaign_state["active_quests"][0]
    objective = active_quest["objectives"][0]
    assert active_quest["quest_id"] == "collect_ore"
    assert objective["type"] == "collect"
    assert objective["item_def_id"] == "iron_ore"
    assert objective["progress"] == 1
    assert objective["completed"] is True
    assert active_quest["report_ready"] is True


def test_campaign_save_listing_filters_legacy_and_other_campaign_slots(tmp_path: Path):
    runtime = CampaignRuntime()
    runtime.save_system.save_dir = tmp_path / "campaign_api_saves"
    runtime.save_system.save_dir.mkdir(parents=True, exist_ok=True)
    old_runtime = campaign_routes.campaign_runtime
    campaign_routes.campaign_runtime = runtime
    try:
        first = client.post(
            "/game/campaigns",
            json={
                "player_name": "CampaignTester",
                "player_class": "warrior",
                "adapter_id": "fantasy_ember",
                "profile_id": "standard",
                "seed": 100,
            },
        ).json()
        second = client.post(
            "/game/campaigns",
            json={
                "player_name": "CampaignTester",
                "player_class": "rogue",
                "adapter_id": "scifi_frontier",
                "profile_id": "standard",
                "seed": 101,
            },
        ).json()
        first_id = first["campaign_id"]
        client.post(f"/game/campaigns/{first_id}/save", json={"player_id": "CampaignTester", "slot_name": "first_slot"})
        client.post(f"/game/campaigns/{second['campaign_id']}/save", json={"player_id": "CampaignTester", "slot_name": "second_slot"})
        player_saves = client.get("/game/campaigns/saves/player/CampaignTester")
        assert player_saves.status_code == 200
        player_entries = {entry["save_id"]: entry for entry in player_saves.json()}
        assert set(player_entries) == {"first_slot", "second_slot"}
        assert player_entries["first_slot"]["player_id"] == "CampaignTester"
        assert player_entries["second_slot"]["player_id"] == "CampaignTester"

        scoped = client.get(f"/game/campaigns/{first_id}/saves")
        assert scoped.status_code == 200
        assert [entry["save_id"] for entry in scoped.json()] == ["first_slot"]
    finally:
        campaign_routes.campaign_runtime = old_runtime


def test_legacy_session_routes_are_not_mounted():
    create_response = client.post("/game/session/new", json={"player_name": "Legacy", "player_class": "warrior"})
    save_response = client.get("/game/saves/Legacy")

    assert create_response.status_code == 404
    assert save_response.status_code == 404

