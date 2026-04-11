from __future__ import annotations

import pytest
from collections.abc import Iterator

from fastapi.testclient import TestClient

from engine.api import campaign_routes
from main import app
from _seed_robust_helpers import ensure_attack_target


REQUIRED_COMBAT_INFO_FIELDS = {
    "in_combat",
    "initiative",
    "action_available",
    "bonus_action_available",
    "reaction_available",
    "movement_remaining",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _create_campaign(client: TestClient, *, seed: int) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "TurnEconomyProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _actors_by_id(payload: dict) -> dict[str, dict]:
    actors = payload["campaign"].get("actors", [])
    return {
        str(actor.get("identity", {}).get("actor_id", "")).strip(): actor
        for actor in actors
        if isinstance(actor, dict)
    }


def _enter_combat(client: TestClient, *, seed: int) -> tuple[str, dict]:
    created = _create_campaign(client, seed=seed)
    campaign_id = created["campaign_id"]
    target = ensure_attack_target(campaign_id, actor_id=f"turn_surface_{seed}", name="Turn Surface Fang")
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target['name']}"},
    )
    assert response.status_code == 200
    return campaign_id, response.json()


def test_non_combat_snapshot_uses_empty_actor_combat_info(client: TestClient) -> None:
    payload = _create_campaign(client, seed=411)
    actors = _actors_by_id(payload)
    assert actors
    for actor in actors.values():
        combat_info = actor.get("combat_info", {})
        assert combat_info in ({}, None)


def test_combat_snapshot_surfaces_combat_info_for_live_combat_actors(client: TestClient) -> None:
    campaign_id, payload = _enter_combat(client, seed=412)
    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    combat_payload = context.kernel_runtime["game_state"].raw_payload["combat"]
    player_entry = next(entry for entry in combat_payload["combatants"] if entry["actor_id"] == "player")
    player_entry["turn_resources"]["action"] = False

    snapshot = campaign_routes.campaign_runtime.snapshot(campaign_id)
    actors = _actors_by_id(snapshot)
    combatants = snapshot["campaign"]["combat"]["combatants"]
    combat_actor_ids = {entry["actor_id"] for entry in combatants}

    for combatant in combatants:
        combat_info = combatant.get("combat_info", {})
        assert REQUIRED_COMBAT_INFO_FIELDS <= set(combat_info)
        assert combat_info["in_combat"] is True
        actor_info = actors[combatant["actor_id"]].get("combat_info", {})
        assert REQUIRED_COMBAT_INFO_FIELDS <= set(actor_info)
        assert actor_info == combat_info

    assert actors["player"]["combat_info"]["action_available"] is False
    assert "player" in combat_actor_ids


def test_websocket_state_snapshot_includes_actor_combat_info(client: TestClient) -> None:
    created = _create_campaign(client, seed=413)
    campaign_id = created["campaign_id"]
    target = ensure_attack_target(campaign_id, actor_id="turn_ws_surface", name="Turn WS Fang")

    with client.websocket_connect(f"/game/ws/campaigns/{campaign_id}") as ws:
        initial = ws.receive_json()
        assert initial["type"] == "state"
        ws.send_json({"type": "command", "input": f"attack {target['name']}"})
        state = ws.receive_json()
        assert state["type"] == "state"
        snapshot = state["snapshot"]
        actors = _actors_by_id(snapshot)
        combatants = snapshot["campaign"]["combat"]["combatants"]
        assert actors
        assert combatants
        for combatant in combatants:
            combat_info = actors[combatant["actor_id"]].get("combat_info", {})
            assert REQUIRED_COMBAT_INFO_FIELDS <= set(combat_info)
            assert combat_info["initiative"] == int(combatant["initiative"])
