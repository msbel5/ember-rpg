"""Targeted tests for campaign-first character creation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)

ABILITY_ORDER = ["MIG", "AGI", "END", "MND", "INS", "PRE"]


def _start_creation(adapter_id: str = "fantasy_ember", seed: int = 77) -> dict:
    response = client.post(
        "/game/campaigns/creation/start",
        json={
            "player_name": "Creator",
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": seed,
            "location": "Harbor Town",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_creation_catalog_endpoint_returns_backend_authority():
    response = client.get("/game/campaigns/creation/catalog")
    assert response.status_code == 200
    payload = response.json()

    assert payload["mechanics_version"] == "ember_hybrid_v1"
    assert payload["default_class_id"] == "warrior"
    assert payload["default_adapter_id"] == "fantasy_ember"
    assert payload["default_profile_id"] == "standard"
    assert payload["ability_order"] == ABILITY_ORDER
    assert len(payload["class_catalog"]) >= 4
    assert any(entry["id"] == "mage" for entry in payload["class_catalog"])
    assert any(entry["id"] == "scifi_frontier" for entry in payload["adapter_catalog"])
    assert payload["settlement_labels"]["border_keep"] == "border keep"
    assert payload["faction_labels"]["research_conclave"] == "research conclave"


def test_start_creation_returns_guided_creation_state():
    payload = _start_creation()

    assert payload["player_name"] == "Creator"
    assert payload["adapter_id"] == "fantasy_ember"
    assert payload["profile_id"] == "standard"
    assert payload["seed"] == 77
    assert len(payload["question_groups"]) >= 5
    assert len(payload["questions"]) >= 3
    assert len(payload["current_roll"]) == 6
    assert payload["roll_pool"] == sorted(payload["current_roll"], reverse=True)
    assert payload["allocation_rules"]["mode"] == "rolled_array_assignment"
    assert payload["campaign_genesis"]["world_premise"]
    assert payload["world_seed_hints"]["preferred_adapter"] == "fantasy_ember"
    assert payload["recommended_class"]
    assert payload["recommended_alignment"]
    assert payload["catalog"]["default_adapter_id"] == "fantasy_ember"
    assert payload["catalog"]["ability_order"] == ABILITY_ORDER
    assert any(entry["id"] == "warrior" for entry in payload["catalog"]["class_catalog"])


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
    assert payload["campaign"]["character_sheet"]["creation_summary"]["campaign_genesis"]["world_premise"]
    assert payload["campaign"]["character_sheet"]["creation_summary"]["world_seed_hints"]["preferred_adapter"] in {
        "fantasy_ember",
        "scifi_frontier",
    }


def test_creation_seed_produces_deterministic_initial_and_reroll_values():
    first = _start_creation("fantasy_ember")
    second = _start_creation("fantasy_ember")

    assert first["current_roll"] == second["current_roll"]

    rerolled_first = client.post(f"/game/campaigns/creation/{first['creation_id']}/reroll")
    rerolled_second = client.post(f"/game/campaigns/creation/{second['creation_id']}/reroll")

    assert rerolled_first.status_code == 200
    assert rerolled_second.status_code == 200
    assert rerolled_first.json()["current_roll"] == rerolled_second.json()["current_roll"]


def test_creation_answers_emit_history_reveal_lines():
    started = _start_creation("fantasy_ember")
    creation_id = started["creation_id"]

    for question in started["questions"]:
        answer = question["answers"][0]
        response = client.post(
            f"/game/campaigns/creation/{creation_id}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert response.status_code == 200
        started = response.json()

    history_events = started["campaign_genesis"].get("history_events", [])
    history_timeline = started["campaign_genesis"].get("history_timeline", [])

    assert history_events
    assert history_timeline
    assert len(history_events) >= 8
    assert len(history_timeline) >= 8
    assert all(str(entry).startswith("Year ") for entry in history_events)
    years = [int(str(entry).split(":")[0].replace("Year", "").strip()) for entry in history_events]
    timeline_years = [int(entry["year"]) for entry in history_timeline]
    assert years[0] == 1
    assert years[-1] >= 1000
    assert years[-1] - years[0] >= 900
    assert timeline_years[0] == 1
    assert timeline_years[-1] >= 1000
    assert timeline_years[-1] - timeline_years[0] >= 900
    assert all(entry["headline"] for entry in history_timeline)
    assert all(entry["summary"] for entry in history_timeline)
    assert all(isinstance(entry["tags"], list) for entry in history_timeline)
    assert all(int(entry["importance"]) >= 1 for entry in history_timeline)


def test_creation_history_changes_with_seed_and_answer_signature():
    first = _start_creation("fantasy_ember", seed=77)
    second = _start_creation("fantasy_ember", seed=901)

    for question in first["questions"]:
        answer = question["answers"][0]
        response = client.post(
            f"/game/campaigns/creation/{first['creation_id']}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert response.status_code == 200
        first = response.json()

    for question in second["questions"]:
        answers = question["answers"]
        answer = answers[min(1, len(answers) - 1)]
        response = client.post(
            f"/game/campaigns/creation/{second['creation_id']}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert response.status_code == 200
        second = response.json()

    assert first["campaign_genesis"]["history_events"] != second["campaign_genesis"]["history_events"]


def test_creation_answers_change_world_selection_with_same_seed():
    first = _start_creation("fantasy_ember")
    second = _start_creation("fantasy_ember")

    for question in first["questions"]:
        answer = question["answers"][0]
        response = client.post(
            f"/game/campaigns/creation/{first['creation_id']}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert response.status_code == 200
        first = response.json()

    for question in second["questions"]:
        answers = question["answers"]
        answer = answers[min(1, len(answers) - 1)]
        response = client.post(
            f"/game/campaigns/creation/{second['creation_id']}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert response.status_code == 200
        second = response.json()

    first_stats = {ability: int(first["current_roll"][index]) for index, ability in enumerate(ABILITY_ORDER)}
    second_stats = {ability: int(second["current_roll"][index]) for index, ability in enumerate(ABILITY_ORDER)}

    first_finalized = client.post(
        f"/game/campaigns/creation/{first['creation_id']}/finalize",
        json={
            "player_class": "warrior",
            "alignment": "TN",
            "skill_proficiencies": ["athletics"],
            "assigned_stats": first_stats,
        },
    )
    second_finalized = client.post(
        f"/game/campaigns/creation/{second['creation_id']}/finalize",
        json={
            "player_class": "warrior",
            "alignment": "TN",
            "skill_proficiencies": ["athletics"],
            "assigned_stats": second_stats,
        },
    )

    assert first_finalized.status_code == 200
    assert second_finalized.status_code == 200

    first_campaign = first_finalized.json()["campaign"]
    second_campaign = second_finalized.json()["campaign"]

    first_signature = (
        first_campaign["world_state"]["seed"],
        first_campaign["settlement"]["name"],
        first_campaign["current_region_summary"]["region_id"],
    )
    second_signature = (
        second_campaign["world_state"]["seed"],
        second_campaign["settlement"]["name"],
        second_campaign["current_region_summary"]["region_id"],
    )

    assert first_signature != second_signature
