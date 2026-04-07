"""
Crime/consequence request and payload contract tests.

Freezes the public shapes for theft, assault, murder, and trespass
crime tracking. The crime system records incidents, tracks wanted
status, and surfaces crime_state in campaign payloads.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import campaign_routes
from main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────


def _create_campaign(seed: int = 42) -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "CrimeProbe",
            "player_class": "rogue",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _first_npc(payload: dict) -> dict | None:
    npcs = [
        a for a in payload["campaign"]["actors"]
        if a["identity"]["actor_id"] != "player"
        and a["identity"].get("actor_type") == "npc"
        and a.get("alive", True)
    ]
    return npcs[0] if npcs else None


def _campaign_context(campaign_id: str):
    return campaign_routes.campaign_runtime.get_campaign(campaign_id)


def _first_store_item(payload: dict) -> tuple[str, str]:
    stores = list(payload["campaign"].get("stores", []))
    assert stores, "Expected at least one store in campaign payload"
    store = stores[0]
    items = list(store.get("items", []))
    assert items, "Expected at least one stocked store item"
    return str(store["store_id"]), str(items[0]["item_def_id"])


def _prepare_neutral_npc(campaign_id: str):
    context = _campaign_context(campaign_id)
    actors = context.kernel_runtime["actors"]
    player = actors["player"]
    npc = next(
        actor
        for actor_id, actor in actors.items()
        if actor_id != "player" and getattr(actor.identity, "actor_type", "") == "npc"
    )
    npc.position.x = int(player.position.x) + 1
    npc.position.y = int(player.position.y)
    record = context.entities.setdefault(npc.identity.actor_id, {})
    record["position"] = [int(npc.position.x), int(npc.position.y)]
    record["attitude"] = "friendly"
    record["disposition"] = "friendly"
    record["role"] = "merchant"
    npc.raw_payload["hostile"] = False
    npc.raw_payload["disposition"] = "friendly"
    npc.raw_payload["role"] = "merchant"
    return context, npc


def _inject_locked_door(campaign_id: str) -> None:
    context = _campaign_context(campaign_id)
    player = context.kernel_runtime["actors"]["player"]
    player.stats["MIG"] = 40
    context.entities["locked_test_door"] = {
        "name": "Locked Door",
        "role": "door",
        "template": "door",
        "locked": True,
        "position": [int(player.position.x) + 1, int(player.position.y)],
    }


# ═════════════════════════════════════════════════════════════════════
#  Raw theft request shape
# ═════════════════════════════════════════════════════════════════════


class TestTheftRawRequestShape:
    """Freeze 'steal <item>' and 'steal <item> from <merchant>' shapes."""

    def test_steal_command_returns_commerce_type(self):
        payload = _create_campaign(seed=80)
        _store_id, item_id = _first_store_item(payload)
        response = client.post(
            f"/game/campaigns/{payload['campaign_id']}/commands",
            json={"input": f"steal {item_id}"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["command_type"] == "commerce"

    def test_steal_from_merchant_returns_commerce_type(self):
        payload = _create_campaign(seed=81)
        store_id, item_id = _first_store_item(payload)
        response = client.post(
            f"/game/campaigns/{payload['campaign_id']}/commands",
            json={"input": f"steal {item_id} from {store_id}"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["command_type"] == "commerce"


# ═════════════════════════════════════════════════════════════════════
#  Structured theft request shape
# ═════════════════════════════════════════════════════════════════════


class TestTheftStructuredRequestShape:
    """Freeze shortcut=commerce, action_id=steal_item."""

    def test_shortcut_steal_item_accepted(self):
        payload = _create_campaign(seed=82)
        _store_id, item_id = _first_store_item(payload)
        response = client.post(
            f"/game/campaigns/{payload['campaign_id']}/commands",
            json={
                "input": "",
                "shortcut": "commerce",
                "args": {
                    "action_id": "steal_item",
                    "item_id": item_id,
                },
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["command_type"] == "commerce"

    def test_shortcut_steal_with_store_id(self):
        payload = _create_campaign(seed=83)
        store_id, item_id = _first_store_item(payload)
        response = client.post(
            f"/game/campaigns/{payload['campaign_id']}/commands",
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
        result = response.json()
        assert result["command_type"] == "commerce"


# ═════════════════════════════════════════════════════════════════════
#  Crime state payload shape
# ═════════════════════════════════════════════════════════════════════


class TestCrimeStatePayloadShape:
    """campaign.crime_state must exist and have required fields."""

    def test_crime_state_exists_in_campaign(self):
        payload = _create_campaign(seed=84)
        campaign = payload["campaign"]
        assert "crime_state" in campaign
        assert isinstance(campaign["crime_state"], dict)

    def test_crime_state_has_wanted_flag(self):
        payload = _create_campaign(seed=85)
        crime = payload["campaign"]["crime_state"]
        assert "wanted" in crime
        assert isinstance(crime["wanted"], bool)

    def test_crime_state_has_active_bounty(self):
        payload = _create_campaign(seed=86)
        crime = payload["campaign"]["crime_state"]
        assert "active_bounty" in crime
        assert isinstance(crime["active_bounty"], (int, float))

    def test_crime_state_has_witness_count(self):
        payload = _create_campaign(seed=87)
        crime = payload["campaign"]["crime_state"]
        assert "witness_count" in crime
        assert isinstance(crime["witness_count"], int)

    def test_crime_state_has_last_incident(self):
        payload = _create_campaign(seed=88)
        crime = payload["campaign"]["crime_state"]
        assert "last_incident" in crime
        # last_incident is None when no crime has been committed
        assert crime["last_incident"] is None or isinstance(crime["last_incident"], dict)

    def test_fresh_campaign_is_not_wanted(self):
        payload = _create_campaign(seed=89)
        crime = payload["campaign"]["crime_state"]
        assert crime["wanted"] is False
        assert crime["active_bounty"] == 0
        assert crime["witness_count"] == 0


# ═════════════════════════════════════════════════════════════════════
#  Last incident shape
# ═════════════════════════════════════════════════════════════════════


class TestLastIncidentShape:
    """Freeze the incident record shape when a crime has been committed."""

    def test_last_incident_has_required_fields_after_theft(self):
        payload = _create_campaign(seed=90)
        campaign_id = payload["campaign_id"]
        _store_id, item_id = _first_store_item(payload)
        # Attempt theft to generate an incident
        response = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"steal {item_id}"},
        )
        assert response.status_code == 200
        incident = response.json()["campaign"]["crime_state"]["last_incident"]
        assert incident is not None

        required_fields = {
            "crime_type", "severity", "target_id", "target_name",
            "faction_id", "settlement_id", "witnessed", "reported",
            "responses", "tick",
        }
        assert required_fields.issubset(set(incident.keys())), (
            f"Incident missing fields: {required_fields - set(incident.keys())}"
        )

    def test_incident_crime_type_is_theft(self):
        payload = _create_campaign(seed=91)
        campaign_id = payload["campaign_id"]
        _store_id, item_id = _first_store_item(payload)
        response = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"steal {item_id}"},
        )
        assert response.status_code == 200
        incident = response.json()["campaign"]["crime_state"]["last_incident"]
        assert incident is not None
        assert incident["crime_type"] == "theft"


# ═════════════════════════════════════════════════════════════════════
#  Truthfulness: assault before murder, trespass on locked entry
# ═════════════════════════════════════════════════════════════════════


class TestCrimeTruthfulness:
    """Crime type escalation must be truthful."""

    def test_attacking_nonhostile_npc_records_assault(self):
        payload = _create_campaign(seed=92)
        campaign_id = payload["campaign_id"]
        _context, npc = _prepare_neutral_npc(campaign_id)
        target_name = npc.identity.display_name

        result = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"attack {target_name}"},
        ).json()

        crime = result["campaign"].get("crime_state", {})
        incident = crime.get("last_incident")
        assert incident is not None
        assert incident["crime_type"] == "assault"

    def test_killing_nonhostile_npc_upgrades_to_murder(self):
        """After killing, the incident should escalate to murder."""
        from engine.api.campaign.crime import current_crime_state
        from engine.api.combat_bridge import maybe_handle_combat_command

        payload = _create_campaign(seed=93)
        campaign_id = payload["campaign_id"]
        context, npc = _prepare_neutral_npc(campaign_id)
        context.kernel_runtime["actors"]["player"].stats["MIG"] = 30
        target_name = npc.identity.display_name
        npc.hp = 1
        npc.max_hp = 1

        for tick in range(40):
            context.kernel_runtime["game_state"].world_time.game_tick = tick
            context.kernel_runtime["game_state"].raw_payload.pop("combat", None)
            maybe_handle_combat_command(context, f"attack {target_name}")
            if not npc.alive:
                break

        incident = current_crime_state(context).get("last_incident")
        assert incident is not None
        assert npc.alive is False
        assert incident["crime_type"] == "murder"

    def test_trespass_only_on_successful_locked_entry(self):
        """Trespass should only be recorded when actually entering a locked area."""
        payload = _create_campaign(seed=94)
        campaign_id = payload["campaign_id"]
        _inject_locked_door(campaign_id)

        result = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "open locked door"},
        ).json()

        crime = result.get("campaign", {}).get("crime_state", {})
        incident = crime.get("last_incident")
        assert incident is not None
        assert incident["crime_type"] == "trespass"


# ═════════════════════════════════════════════════════════════════════
#  Negative: no crime on legitimate actions
# ═════════════════════════════════════════════════════════════════════


class TestNoCrimeOnLegitimate:
    """Legitimate actions must not generate crime state."""

    def test_buying_item_does_not_create_crime(self):
        payload = _create_campaign(seed=95)
        campaign_id = payload["campaign_id"]
        client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "buy bread"},
        )
        snapshot = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "look around"},
        ).json()
        crime = snapshot["campaign"].get("crime_state")
        if crime is not None:
            assert crime.get("wanted") is False
            assert crime.get("last_incident") is None

    def test_talking_to_npc_does_not_create_crime(self):
        payload = _create_campaign(seed=96)
        campaign_id = payload["campaign_id"]
        npc = _first_npc(payload)
        if npc is None:
            pytest.skip("No NPCs available")
        client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"talk {npc['identity']['display_name']}"},
        )
        snapshot = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "look around"},
        ).json()
        crime = snapshot["campaign"].get("crime_state")
        if crime is not None:
            assert crime.get("wanted") is False
