"""Targeted tests for campaign-first character creation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)

ABILITY_ORDER = ["MIG", "AGI", "END", "MND", "INS", "PRE"]


def _start_creation(adapter_id: str = "fantasy_ember") -> dict:
    response = client.post(
        "/game/campaigns/creation/start",
        json={
            "player_name": "Creator",
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": 77,
            "location": "Harbor Town",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_start_creation_returns_guided_creation_state():
    payload = _start_creation()

    assert payload["player_name"] == "Creator"
    assert payload["adapter_id"] == "fantasy_ember"
    assert payload["profile_id"] == "standard"
    assert payload["seed"] == 77
    assert len(payload["questions"]) >= 3
    assert len(payload["current_roll"]) == 6
    assert payload["recommended_class"]
    assert payload["recommended_alignment"]


def test_creation_answer_roll_management_and_finalize_yield_campaign_snapshot():
    started = _start_creation("scifi_frontier")
    creation_id = started["creation_id"]
    first_question = started["questions"][0]
    first_answer = first_question["answers"][0]

    answered = client.post(
        f"/game/campaigns/creation/{creation_id}/answer",
        json={
            "question_id": first_question["id"],
            "answer_id": first_answer["id"],
        },
    )
    assert answered.status_code == 200
    answered_payload = answered.json()
    assert answered_payload["answers"][0]["question_id"] == first_question["id"]

    saved = client.post(f"/game/campaigns/creation/{creation_id}/save-roll")
    assert saved.status_code == 200
    saved_payload = saved.json()
    assert saved_payload["saved_roll"] == started["current_roll"]

    rerolled = client.post(f"/game/campaigns/creation/{creation_id}/reroll")
    assert rerolled.status_code == 200
    rerolled_payload = rerolled.json()
    assert len(rerolled_payload["current_roll"]) == 6

    swapped = client.post(f"/game/campaigns/creation/{creation_id}/swap-roll")
    assert swapped.status_code == 200
    swapped_payload = swapped.json()
    assert swapped_payload["current_roll"] == started["current_roll"]

    assigned_stats = {
        ability: int(swapped_payload["current_roll"][index])
        for index, ability in enumerate(ABILITY_ORDER)
    }
    finalized = client.post(
        f"/game/campaigns/creation/{creation_id}/finalize",
        json={
            "player_class": "mage",
            "alignment": "CG",
            "skill_proficiencies": ["arcana", "history"],
            "assigned_stats": assigned_stats,
        },
    )
    assert finalized.status_code == 200
    payload = finalized.json()

    assert payload["adapter_id"] == "scifi_frontier"
    assert payload["campaign"]["player"]["name"] == "Creator"
    assert payload["campaign"]["player"]["alignment"] == "CG"
    assert payload["campaign"]["player"]["stats"] == assigned_stats
    assert payload["campaign"]["character_sheet"]["class_name"] == "Mage"
    assert payload["campaign"]["character_sheet"]["alignment"] == "CG"
    assert payload["campaign"]["character_sheet"]["creation_summary"]["recommended_class"]
    assert payload["campaign"]["character_sheet"]["creation_summary"]["answers"]


def test_creation_seed_produces_deterministic_initial_and_reroll_values():
    first = _start_creation("fantasy_ember")
    second = _start_creation("fantasy_ember")

    assert first["current_roll"] == second["current_roll"]

    rerolled_first = client.post(f"/game/campaigns/creation/{first['creation_id']}/reroll")
    rerolled_second = client.post(f"/game/campaigns/creation/{second['creation_id']}/reroll")

    assert rerolled_first.status_code == 200
    assert rerolled_second.status_code == 200
    assert rerolled_first.json()["current_roll"] == rerolled_second.json()["current_roll"]
