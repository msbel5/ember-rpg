"""Combat runtime contract tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import campaign_routes
from main import app
from _seed_robust_helpers import ensure_attack_target


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
    target = ensure_attack_target(campaign_id, actor_id="combat_runtime_target", name="Combat Runtime Fang")
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target['name']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["command_type"] == "combat"
    return body["campaign"]["combat"]


def _strip_usable_items(campaign_id: str) -> None:
    from engine.api.gameplay_bridge import _runtime_item_is_usable_now, _runtime_item_source

    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    player = context.kernel_runtime["actors"]["player"]
    player.inventory[:] = [
        item
        for item in player.inventory
        if not _runtime_item_is_usable_now(item, _runtime_item_source(item))
    ]


class TestCombatRuntimeContract:
    def test_available_actions_do_not_advertise_unsupported_combat_time_actions(self):
        payload = _create_campaign(seed=60)
        _strip_usable_items(payload["campaign_id"])
        combat = _enter_combat(payload)
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
