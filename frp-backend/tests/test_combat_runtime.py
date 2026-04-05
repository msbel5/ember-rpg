"""Combat runtime contract tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _create_campaign(seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CombatRuntimeProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _enter_combat(payload: dict) -> dict:
    campaign_id = payload["campaign_id"]
    npcs = [
        actor for actor in payload["campaign"]["actors"]
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
    body = response.json()
    assert body["command_type"] == "combat"
    return body["campaign"]["combat"]


class TestCombatRuntimeContract:
    def test_available_actions_do_not_advertise_unsupported_combat_time_actions(self):
        combat = _enter_combat(_create_campaign(seed=60))
        actions = combat["available_actions"]
        assert "attack" in actions
        assert "defend" in actions
        assert "flee" in actions
        assert "move" in actions
        assert "end_turn" in actions
        assert "cast" not in actions
        assert "use_item" not in actions

    def test_move_options_payload_shape_when_body_state_exists(self):
        combat = _enter_combat(_create_campaign(seed=61))
        assert "move_options" in combat
        move_options = combat["move_options"]
        assert isinstance(move_options, list)
        for option in move_options:
            assert isinstance(option["direction"], str)
            assert isinstance(option["position"], list)
            assert len(option["position"]) == 2
            assert all(isinstance(value, int) for value in option["position"])
            assert isinstance(option["available"], bool)
            assert "blocked_reason" in option

    def test_called_shot_zones_payload_shape_when_body_state_exists(self):
        combat = _enter_combat(_create_campaign(seed=62))
        assert combat["targets"]
        zones = [target.get("called_shot_zones", []) for target in combat["targets"]]
        assert any(isinstance(zone_list, list) and zone_list for zone_list in zones)
        for zone_list in zones:
            assert isinstance(zone_list, list)
            for zone in zone_list:
                assert isinstance(zone, str)

    def test_combatant_position_fields_are_present_in_payload(self):
        combat = _enter_combat(_create_campaign(seed=63))
        combatants = combat["combatants"]
        assert combatants
        for combatant in combatants:
            assert "position" in combatant
            position = combatant["position"]
            assert isinstance(position, list)
            assert len(position) == 2
            assert all(isinstance(value, int) for value in position)
