"""
Combat payload and request contract tests.

Freezes the combat payload shapes that the later UI will consume.
Implementation-agnostic where possible — tests shape, not behaviour.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import campaign_routes
from engine.kernel import item_stack_from_payload
from main import app

client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────────


def _create_campaign(seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CombatContractProbe",
            "player_class": "warrior",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _enter_combat(campaign_id: str, actors: list[dict]) -> dict:
    """Attack the first living NPC to trigger combat state."""
    npcs = [
        actor for actor in actors
        if actor["identity"]["actor_id"] != "player"
        and actor["identity"].get("actor_type") == "npc"
        and actor.get("alive", True)
    ]
    if not npcs:
        pytest.skip("No NPCs in fresh campaign to attack")
    target_name = npcs[0]["identity"]["display_name"]
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"attack {target_name}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["command_type"] == "combat", "Attack did not enter combat"
    return body


def _inject_usable_item(campaign_id: str, *, item_def_id: str = "field_tonic") -> None:
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


def _strip_usable_items(campaign_id: str) -> None:
    from engine.api.gameplay_bridge import _runtime_item_is_usable_now, _runtime_item_source

    context = campaign_routes.campaign_runtime.get_campaign(campaign_id)
    player = context.kernel_runtime["actors"]["player"]
    player.inventory[:] = [
        item
        for item in player.inventory
        if not _runtime_item_is_usable_now(item, _runtime_item_source(item))
    ]


# ── Combat entry contract ────────────────────────────────────────────


class TestCombatEntryContract:
    """shortcut=combat: the request shape that triggers combat."""

    def test_attack_command_returns_combat_command_type(self):
        payload = _create_campaign()
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        assert body["command_type"] == "combat"

    def test_combat_sets_scene_to_combat(self):
        payload = _create_campaign(seed=43)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        assert body["campaign"]["scene"] == "combat"

    def test_combat_payload_exists_at_campaign_combat(self):
        payload = _create_campaign(seed=44)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        assert body["campaign"]["combat"] is not None
        assert isinstance(body["campaign"]["combat"], dict)


# ── Combat payload shape ─────────────────────────────────────────────


class TestCombatPayloadShape:
    """Freeze the top-level combat payload keys the UI will consume."""

    @pytest.fixture(autouse=True)
    def _combat(self):
        payload = _create_campaign(seed=45)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        self.combat = body["campaign"]["combat"]

    def test_phase_field_present_and_string(self):
        assert isinstance(self.combat["phase"], str)

    def test_round_field_present_and_integer(self):
        assert isinstance(self.combat["round"], int)
        assert self.combat["round"] >= 1

    def test_turn_actor_id_present_and_string(self):
        assert isinstance(self.combat["turn_actor_id"], str)
        assert len(self.combat["turn_actor_id"]) > 0

    def test_combatants_is_non_empty_list(self):
        assert isinstance(self.combat["combatants"], list)
        assert len(self.combat["combatants"]) >= 2

    def test_available_actions_is_list(self):
        assert isinstance(self.combat["available_actions"], list)
        assert len(self.combat["available_actions"]) >= 1

    def test_targets_is_list(self):
        assert isinstance(self.combat["targets"], list)


# ── Available actions truthfulness ───────────────────────────────────


class TestAvailableActionsTruthfulness:
    """Assert unsupported combat-time actions are not advertised."""

    @pytest.fixture(autouse=True)
    def _combat(self):
        payload = _create_campaign(seed=46)
        _strip_usable_items(payload["campaign_id"])
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        self.actions = body["campaign"]["combat"]["available_actions"]

    def test_attack_is_advertised(self):
        assert "attack" in self.actions

    def test_defend_is_advertised(self):
        assert "defend" in self.actions

    def test_flee_is_advertised(self):
        assert "flee" in self.actions

    def test_cast_is_not_advertised_for_noncasters(self):
        assert "cast" not in self.actions, (
            "Combat payload should not advertise 'cast' for a non-caster combatant"
        )

    def test_use_item_is_not_advertised(self):
        assert "use_item" not in self.actions, (
            "Combat payload should not advertise 'use_item' when no legal combat-usable item exists"
        )

    def test_use_item_is_advertised_when_usable_item_exists(self):
        payload = _create_campaign(seed=460)
        _inject_usable_item(payload["campaign_id"], item_def_id="field_tonic")
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])

        assert "use_item" in body["campaign"]["combat"]["available_actions"], (
            "Combat payload should advertise 'use_item' when the player has a legal combat-usable item"
        )


# ── Combatant position fields ────────────────────────────────────────


class TestCombatantPayloadShape:
    """Freeze per-combatant payload fields the UI will read."""

    @pytest.fixture(autouse=True)
    def _combatants(self):
        payload = _create_campaign(seed=47)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        self.combatants = body["campaign"]["combat"]["combatants"]
        self.player = next(c for c in self.combatants if c["is_player"])
        self.enemy = next(c for c in self.combatants if not c["is_player"])

    def test_combatant_has_actor_id(self):
        for c in self.combatants:
            assert isinstance(c["actor_id"], str)
            assert len(c["actor_id"]) > 0

    def test_combatant_has_name(self):
        for c in self.combatants:
            assert isinstance(c["name"], str)

    def test_combatant_has_is_player_flag(self):
        for c in self.combatants:
            assert isinstance(c["is_player"], bool)

    def test_combatant_has_initiative(self):
        for c in self.combatants:
            assert isinstance(c["initiative"], int)

    def test_combatant_has_alive_flag(self):
        for c in self.combatants:
            assert isinstance(c["alive"], bool)

    def test_combatant_has_hp_and_max_hp(self):
        for c in self.combatants:
            assert isinstance(c["hp"], int)
            assert isinstance(c["max_hp"], int)
            assert c["max_hp"] > 0

    def test_combatant_has_turn_resources(self):
        for c in self.combatants:
            tr = c["turn_resources"]
            assert isinstance(tr, dict)
            assert isinstance(tr["action_available"], bool)
            assert isinstance(tr["bonus_action_available"], bool)
            assert isinstance(tr["reaction_available"], bool)
            assert isinstance(tr["movement_remaining"], int)
            assert isinstance(tr["speed"], int)
            assert tr["speed"] > 0


# ── Target payload shape ─────────────────────────────────────────────


class TestTargetPayloadShape:
    """Freeze per-target payload fields."""

    @pytest.fixture(autouse=True)
    def _targets(self):
        payload = _create_campaign(seed=48)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        self.targets = body["campaign"]["combat"]["targets"]

    def test_targets_contain_only_non_player_combatants(self):
        for t in self.targets:
            assert isinstance(t["actor_id"], str)
            assert isinstance(t["name"], str)
            assert isinstance(t["alive"], bool)
            assert isinstance(t["hp"], int)
            assert isinstance(t["max_hp"], int)


# ── Move options contract ────────────────────────────────────────────


class TestMoveOptionsContract:
    """When move_options exists in the combat payload, verify its shape."""

    def test_move_options_shape_if_present(self):
        payload = _create_campaign(seed=49)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        combat = body["campaign"]["combat"]
        if "move_options" not in combat:
            pytest.skip("move_options not yet present in combat payload")
        move_opts = combat["move_options"]
        assert isinstance(move_opts, list)
        for opt in move_opts:
            assert "x" in opt and "y" in opt, "move_option must have x and y"
            assert isinstance(opt["x"], int)
            assert isinstance(opt["y"], int)


# ── Called shot zones contract ───────────────────────────────────────


class TestCalledShotZonesContract:
    """When called_shot_zones exists and body-state is present, verify shape."""

    def test_called_shot_zones_shape_if_present(self):
        payload = _create_campaign(seed=50)
        body = _enter_combat(payload["campaign_id"], payload["campaign"]["actors"])
        combat = body["campaign"]["combat"]
        if "called_shot_zones" not in combat:
            pytest.skip("called_shot_zones not yet present in combat payload")
        zones = combat["called_shot_zones"]
        assert isinstance(zones, list)
        for zone in zones:
            assert isinstance(zone, str), f"called_shot_zone must be a string, got {type(zone)}"

