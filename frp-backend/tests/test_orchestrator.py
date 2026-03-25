"""Tests for Scene Orchestrator — Phase 5."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# MapGenerator tests
def test_map_generator_town():
    from engine.orchestrator import MapGenerator
    gen = MapGenerator()
    result = gen.generate("town", seed=42)
    assert result.width == 20
    assert result.height == 15
    assert len(result.tiles) == 15
    assert len(result.tiles[0]) == 20
    assert len(result.rooms) > 0
    assert result.seed == 42

def test_map_generator_dungeon():
    from engine.orchestrator import MapGenerator
    gen = MapGenerator()
    result = gen.generate("dungeon", seed=99)
    assert result.width == 20
    room_types = [r["type"] for r in result.rooms]
    assert "chamber" in room_types or "corridor" in room_types

def test_map_generator_deterministic():
    from engine.orchestrator import MapGenerator
    gen = MapGenerator()
    a = gen.generate("town", seed=1234)
    b = gen.generate("town", seed=1234)
    assert a.tiles == b.tiles
    assert a.rooms == b.rooms

def test_map_generator_different_seeds():
    from engine.orchestrator import MapGenerator
    gen = MapGenerator()
    a = gen.generate("town", seed=1)
    b = gen.generate("town", seed=2)
    assert a.tiles != b.tiles


# EntityPlacer tests
def test_entity_placer_town_has_npcs():
    from engine.orchestrator import EntityPlacer, MapGenerator
    gen = MapGenerator()
    map_data = gen.generate("town", seed=42)
    placer = EntityPlacer()
    result = placer.place("town", map_data)
    assert len(result["npcs"]) > 0
    assert len(result["enemies"]) == 0  # town is peaceful

def test_entity_placer_dungeon_has_enemies():
    from engine.orchestrator import EntityPlacer, MapGenerator
    gen = MapGenerator()
    map_data = gen.generate("dungeon", seed=42)
    placer = EntityPlacer()
    result = placer.place("dungeon", map_data)
    assert len(result["enemies"]) > 0

def test_entity_placer_positions_in_bounds():
    from engine.orchestrator import EntityPlacer, MapGenerator
    gen = MapGenerator()
    map_data = gen.generate("town", seed=42)
    placer = EntityPlacer()
    result = placer.place("town", map_data)
    for entity in result["npcs"] + result["items"] + result["enemies"]:
        x, y = entity["position"]
        assert 0 <= x < map_data.width
        assert 0 <= y < map_data.height

def test_entity_has_context_actions():
    from engine.orchestrator import EntityPlacer, MapGenerator
    gen = MapGenerator()
    map_data = gen.generate("town", seed=42)
    placer = EntityPlacer()
    result = placer.place("town", map_data)
    for npc in result["npcs"]:
        assert len(npc["context_actions"]) > 0
        assert "examine" in npc["context_actions"]


# DMNarrator tests
def test_dm_narrator_falls_back_to_template():
    from engine.orchestrator import DMNarrator, SceneRequest
    narrator = DMNarrator()
    with patch('engine.llm.get_llm_router') as mock_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None
        mock_fn.return_value = mock_router
        req = SceneRequest(session_id="test", location="harbor_town", location_type="town")
        result = narrator.narrate(req, {"npcs": [], "items": [], "enemies": []})
        assert isinstance(result, str)
        assert len(result) > 20

def test_dm_narrator_uses_llm_when_available():
    from engine.orchestrator import DMNarrator, SceneRequest
    narrator = DMNarrator()
    with patch('engine.llm.get_llm_router') as mock_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = "The harbor town gleams in morning light. [REVEAL:merchant_1] A merchant arranges wares."
        mock_fn.return_value = mock_router
        req = SceneRequest(session_id="test", location="harbor_town", location_type="town")
        entities = {"npcs": [{"id": "merchant_1", "entity_type": "npc", "name": "Merchant"}], "items": [], "enemies": []}
        result = narrator.narrate(req, entities)
        assert "harbor town" in result.lower() or "merchant" in result.lower()

def test_parse_narrative_stream_splits_sentences():
    from engine.orchestrator import DMNarrator
    narrator = DMNarrator()
    text = "You enter the town. [REVEAL:guard_1] A guard watches you. [REVEAL:notice_board_1] A notice board stands nearby."
    entities = {
        "npcs": [{"id": "guard_1", "entity_type": "npc", "name": "Guard"}],
        "items": [{"id": "notice_board_1", "entity_type": "item", "name": "Notice Board"}],
        "enemies": []
    }
    chunks = narrator.parse_narrative_stream(text, entities)
    assert len(chunks) >= 3
    reveal_ids = [c["reveal"]["id"] for c in chunks if c["reveal"]]
    assert "guard_1" in reveal_ids
    assert "notice_board_1" in reveal_ids

def test_parse_narrative_chunks_have_increasing_delay():
    from engine.orchestrator import DMNarrator
    narrator = DMNarrator()
    text = "First sentence. Second sentence. Third sentence."
    chunks = narrator.parse_narrative_stream(text, {"npcs": [], "items": [], "enemies": []})
    delays = [c["delay_ms"] for c in chunks]
    assert delays == sorted(delays)


# SceneOrchestrator tests
def test_orchestrator_enter_scene_returns_complete_response():
    from engine.orchestrator import SceneOrchestrator, SceneRequest
    orch = SceneOrchestrator()
    with patch('engine.llm.get_llm_router') as mock_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None
        mock_fn.return_value = mock_router
        req = SceneRequest(session_id="s1", location="harbor_town", location_type="town")
        result = orch.enter_scene(req)
        assert result.session_id == "s1"
        assert result.location == "harbor_town"
        assert "tiles" in result.map_data
        assert "npcs" in result.entities
        assert len(result.narrative_stream) > 0
        assert len(result.available_actions) > 0

def test_orchestrator_scene_complete_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    with patch('engine.llm.get_llm_router') as mock_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None
        mock_fn.return_value = mock_router
        resp = client.post("/game/scene/enter", json={
            "session_id": "test_session",
            "location": "harbor_town",
            "location_type": "town",
            "time_of_day": "morning",
            "player_name": "Hero",
            "player_level": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test_session"
        assert "map_data" in data
        assert "entities" in data
        assert "narrative_stream" in data
        assert "available_actions" in data

def test_available_types_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.get("/game/scene/available-types")
    assert resp.status_code == 200
    data = resp.json()
    assert "town" in data["types"]
    assert "dungeon" in data["types"]

def test_orchestrator_streaming_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    with patch('engine.llm.get_llm_router') as mock_fn:
        mock_router = MagicMock()
        mock_router.narrative.return_value = None
        mock_fn.return_value = mock_router
        resp = client.post("/game/scene/enter/stream", json={
            "session_id": "test_stream",
            "location": "old_crypt",
            "location_type": "dungeon"
        })
        assert resp.status_code == 200
        lines = [l for l in resp.text.strip().split('\n') if l]
        import json
        events = [json.loads(l) for l in lines]
        event_types = [e["event"] for e in events]
        assert "map_ready" in event_types
        assert "narrative" in event_types
        assert "entities_ready" in event_types
        assert "scene_complete" in event_types
        # map_ready comes before scene_complete
        assert event_types.index("map_ready") < event_types.index("scene_complete")
