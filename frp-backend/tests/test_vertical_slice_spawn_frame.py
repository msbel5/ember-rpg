from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from main import app


SERVICE_TOKENS = ("merchant", "shop", "inn", "smith", "trader", "vendor", "barkeep", "keeper")


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _player_tile(payload: dict) -> tuple[int, int]:
    position = payload["campaign"]["player"]["position"]
    return int(position["x"]), int(position["y"])


def _nearby_entities(payload: dict, radius: int = 8) -> list[dict]:
    player_tile = _player_tile(payload)
    nearby: list[dict] = []
    for entry in payload["campaign"].get("world_entities", []):
        position = entry.get("position", {})
        if isinstance(position, dict):
            tile = (int(position.get("x", 0)), int(position.get("y", 0)))
        elif isinstance(position, (list, tuple)) and len(position) >= 2:
            tile = (int(position[0]), int(position[1]))
        else:
            continue
        if _chebyshev(player_tile, tile) <= radius:
            nearby.append(entry)
    return nearby


def _projects_to_npc_bucket(entry: dict) -> bool:
    entity_type = str(entry.get("entity_type", entry.get("type", "npc"))).strip().lower()
    entity_kind = str(entry.get("entity_kind", entity_type)).strip().lower()
    disposition = str(entry.get("disposition", "")).strip().lower()
    if entity_kind == "item" or entity_type == "item":
        return False
    if entity_kind in {"furniture", "object", "fixture"} or entity_type in {"furniture", "object", "fixture"}:
        return False
    if entity_kind in {"hostile", "enemy"} or entity_type == "creature" or disposition == "hostile":
        return False
    return True


def _finalize_payload(client: TestClient) -> dict:
    started = client.post(
        "/game/campaigns/creation/start",
        json={
            "player_name": "RescueGate",
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": 404,
            "location": "Harbor Town",
        },
    )
    assert started.status_code == 200
    creation = started.json()
    creation_id = creation["creation_id"]

    for question in creation["questions"]:
        answer = question["answers"][0]
        answered = client.post(
            f"/game/campaigns/creation/{creation_id}/answer",
            json={"question_id": question["id"], "answer_id": answer["id"]},
        )
        assert answered.status_code == 200
        creation = answered.json()

    assigned_stats = {
        ability: int(creation["current_roll"][index])
        for index, ability in enumerate(creation["catalog"]["ability_order"])
    }
    finalized = client.post(
        f"/game/campaigns/creation/{creation_id}/finalize",
        json={
            "player_class": creation["recommended_class"],
            "alignment": creation["recommended_alignment"],
            "skill_proficiencies": creation["recommended_skills"],
            "assigned_stats": assigned_stats,
        },
    )
    assert finalized.status_code == 200
    return finalized.json()


def test_finalize_snapshot_guarantees_first_frame_spawn_contract() -> None:
    with TestClient(app) as client:
        payload = _finalize_payload(client)

        nearby = _nearby_entities(payload)
        npcs = [
            entry for entry in nearby
            if _projects_to_npc_bucket(entry)
            and str(entry.get("name", "")).strip()
        ]
        service_or_furniture = [
            entry for entry in nearby
            if str(entry.get("entity_kind", entry.get("entity_type", ""))).strip().lower() == "furniture"
            or str(entry.get("entity_type", "")).strip().lower() in {"furniture", "object", "fixture"}
            or any(token in ("%s %s" % (entry.get("name", ""), entry.get("role", ""))).lower() for token in SERVICE_TOKENS)
        ]

        assert npcs, "fresh finalize snapshot should stage at least one nearby named npc"
        assert service_or_furniture, "fresh finalize snapshot should stage nearby furniture or a service npc"
        assert int(payload["tick_state"]["tick_index"]) >= 0


@pytest.mark.asyncio
async def test_tick_state_tick_index_advances_with_live_loop() -> None:
    with TestClient(app) as client:
        payload = _finalize_payload(client)
        campaign_id = payload["campaign_id"]
        initial_tick = int(payload["tick_state"]["tick_index"])
        assert float(payload["tick_state"]["interval_seconds"]) <= 5.0

        await asyncio.sleep(6.5)

        updated = client.get(f"/game/campaigns/{campaign_id}")
        assert updated.status_code == 200
        later_tick = int(updated.json()["tick_state"]["tick_index"])
        assert later_tick > initial_tick