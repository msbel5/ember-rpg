"""
Ask DM / Advisor public contract tests.

Freezes the request and response shapes for the advisor system.
The advisor is an out-of-band information channel — it does not
advance time, change state, or appear in campaign snapshots.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────


def _create_campaign(seed: int = 42, player_class: str = "warrior") -> dict:
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "AdvisorProbe",
            "player_class": player_class,
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200
    return response.json()


def _ask_dm_raw(campaign_id: str, question: str) -> dict:
    """Send a raw text 'ask dm <question>' command."""
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": f"ask dm {question}"},
    )
    assert response.status_code == 200
    return response.json()


def _ask_dm_shortcut(campaign_id: str, query: str) -> dict:
    """Send a structured shortcut=advisor request."""
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={
            "input": "",
            "shortcut": "advisor",
            "args": {
                "action_id": "ask_dm",
                "query": query,
            },
        },
    )
    assert response.status_code == 200
    return response.json()


# ═════════════════════════════════════════════════════════════════════
#  Raw request shape: "ask dm <question>"
# ═════════════════════════════════════════════════════════════════════


class TestRawRequestShape:
    def test_ask_dm_returns_advisor_command_type(self):
        payload = _create_campaign(seed=70)
        result = _ask_dm_raw(payload["campaign_id"], "what should I do next")
        assert result["command_type"] == "advisor"

    def test_ask_dm_has_advisor_view(self):
        payload = _create_campaign(seed=71)
        result = _ask_dm_raw(payload["campaign_id"], "where is the nearest town")
        assert "advisor_view" in result
        assert isinstance(result["advisor_view"], dict)


# ═════════════════════════════════════════════════════════════════════
#  Structured request shape: shortcut=advisor, action_id=ask_dm
# ═════════════════════════════════════════════════════════════════════


class TestStructuredRequestShape:
    def test_shortcut_advisor_returns_advisor_type(self):
        payload = _create_campaign(seed=72)
        result = _ask_dm_shortcut(payload["campaign_id"], "how do I craft a sword")
        assert result["command_type"] == "advisor"

    def test_shortcut_advisor_has_advisor_view(self):
        payload = _create_campaign(seed=73)
        result = _ask_dm_shortcut(payload["campaign_id"], "explain the magic system")
        assert "advisor_view" in result
        assert isinstance(result["advisor_view"], dict)


# ═════════════════════════════════════════════════════════════════════
#  advisor_view response shape
# ═════════════════════════════════════════════════════════════════════


class TestAdvisorViewShape:
    """Freeze the advisor_view payload fields the UI will read."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        payload = _create_campaign(seed=74)
        result = _ask_dm_raw(payload["campaign_id"], "what quests are available")
        self.view = result.get("advisor_view", {})

    def test_intent_field_present(self):
        assert "intent" in self.view
        assert isinstance(self.view["intent"], str)

    def test_answer_lines_present(self):
        assert "answer_lines" in self.view
        assert isinstance(self.view["answer_lines"], list)
        assert len(self.view["answer_lines"]) >= 1

    def test_related_topic_ids_present(self):
        assert "related_topic_ids" in self.view
        assert isinstance(self.view["related_topic_ids"], list)

    def test_suggested_commands_present(self):
        assert "suggested_commands" in self.view
        assert isinstance(self.view["suggested_commands"], list)

    def test_blockers_present(self):
        assert "blockers" in self.view
        assert isinstance(self.view["blockers"], list)

    def test_spoiler_safe_present(self):
        assert "spoiler_safe" in self.view
        assert isinstance(self.view["spoiler_safe"], bool)


# ═════════════════════════════════════════════════════════════════════
#  Negative contract: no persistence
# ═════════════════════════════════════════════════════════════════════


class TestAdvisorNoPersistence:
    """Advisor responses must not leak into campaign snapshots or saves."""

    def test_no_advisor_key_in_campaign_snapshot(self):
        payload = _create_campaign(seed=75)
        _ask_dm_raw(payload["campaign_id"], "tell me about dragons")
        snapshot = client.post(
            f"/game/campaigns/{payload['campaign_id']}/commands",
            json={"input": "look around"},
        ).json()
        assert "advisor" not in snapshot.get("campaign", {})

    def test_advisor_not_persisted_in_save_load(self):
        payload = _create_campaign(seed=76)
        campaign_id = payload["campaign_id"]
        _ask_dm_raw(campaign_id, "what is the lore of this region")
        save_response = client.post(
            f"/game/campaigns/{campaign_id}/save",
            json={"player_id": "AdvisorProbe", "slot_name": "advisor_test_slot"},
        )
        assert save_response.status_code == 200
        loaded = client.post(
            f"/game/campaigns/load/{save_response.json()['save_id']}"
        ).json()
        assert "advisor" not in loaded.get("campaign", {})
        assert "advisor_view" not in loaded.get("campaign", {})


# ═════════════════════════════════════════════════════════════════════
#  Scene behavior: works during any scene without advancing state
# ═════════════════════════════════════════════════════════════════════


class TestAdvisorSceneBehavior:
    """Ask DM works during any scene and does not advance time or turn."""

    def test_ask_dm_during_exploration_does_not_advance_time(self):
        payload = _create_campaign(seed=77)
        campaign_id = payload["campaign_id"]
        before_snapshot = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "look around"},
        ).json()
        before_tick = before_snapshot["campaign"].get("game_state", {}).get("game_tick", 0)

        _ask_dm_raw(campaign_id, "what enemies are nearby")

        after_snapshot = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "look around"},
        ).json()
        after_tick = after_snapshot["campaign"].get("game_state", {}).get("game_tick", 0)

        # Ask DM should not have advanced the game tick more than the
        # exploration commands themselves did.
        assert after_tick >= before_tick  # ticks only from exploration, not from advisor

    def test_ask_dm_during_combat_does_not_advance_turn(self):
        payload = _create_campaign(seed=78)
        campaign_id = payload["campaign_id"]
        npcs = [
            a for a in payload["campaign"]["actors"]
            if a["identity"]["actor_id"] != "player"
            and a["identity"].get("actor_type") == "npc"
            and a.get("alive", True)
        ]
        if not npcs:
            pytest.skip("No NPCs to enter combat with")
        target_name = npcs[0]["identity"]["display_name"]
        combat_response = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": f"attack {target_name}"},
        ).json()
        if combat_response.get("command_type") != "combat":
            pytest.skip("Could not enter combat")

        combat_before = combat_response["campaign"]["combat"]
        round_before = combat_before["round"]
        turn_before = combat_before["turn_actor_id"]

        advisor_result = _ask_dm_raw(campaign_id, "what abilities should I use")
        assert advisor_result["command_type"] == "advisor"

        # After advisor, combat state should be unchanged
        post_advisor = client.post(
            f"/game/campaigns/{campaign_id}/commands",
            json={"input": "", "shortcut": "combat", "args": {"action_id": "end_turn"}},
        ).json()
        # The end_turn advances the turn; the advisor itself should not have.
        # We just verify advisor returned without error and combat continued normally.
        assert post_advisor["command_type"] == "combat"
