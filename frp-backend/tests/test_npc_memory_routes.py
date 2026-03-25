"""
Tests for NPC Memory API Routes (engine/api/npc_memory_routes.py)
TDD: covers get_npc_memory, add_npc_fact, get_npc_context endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _create_session(name="Hero", cls="warrior"):
    resp = client.post("/game/session/new", json={"player_name": name, "player_class": cls})
    assert resp.status_code == 200
    return resp.json()["session_id"]


# ── /session/{id}/npc/{npc_id}/memory ─────────────────────────────────────────

def test_get_npc_memory_returns_default():
    """GET npc memory for a new npc should return default NPCMemory fields."""
    sid = _create_session()
    resp = client.get(f"/game/session/{sid}/npc/innkeeper/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["npc_id"] == "innkeeper"
    assert data["relationship_score"] == 0
    assert data["relationship_label"] == "stranger"
    assert isinstance(data["conversations"], list)
    assert isinstance(data["known_facts"], list)


def test_get_npc_memory_session_not_found():
    """GET npc memory for unknown session should return 404."""
    resp = client.get("/game/session/nonexistent-session/npc/guard/memory")
    assert resp.status_code == 404


# ── /session/{id}/npc/{npc_id}/fact ───────────────────────────────────────────

def test_add_npc_fact_adds_to_known_facts():
    """POST fact should add it to the NPC's known_facts list."""
    sid = _create_session()
    resp = client.post(
        f"/game/session/{sid}/npc/merchant/fact",
        json={"fact": "Player saved the village"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "Player saved the village" in data["known_facts"]


def test_add_npc_fact_no_duplicates():
    """POSTing the same fact twice should not duplicate it."""
    sid = _create_session()
    url = f"/game/session/{sid}/npc/guard/fact"
    fact = {"fact": "Hero carries a golden sword"}
    client.post(url, json=fact)
    client.post(url, json=fact)

    resp = client.get(f"/game/session/{sid}/npc/guard/memory")
    facts = resp.json()["known_facts"]
    assert facts.count("Hero carries a golden sword") == 1


def test_add_npc_fact_session_not_found():
    """POST fact for unknown session returns 404."""
    resp = client.post(
        "/game/session/bad-session-id/npc/npc1/fact",
        json={"fact": "some fact"}
    )
    assert resp.status_code == 404


# ── /session/{id}/npc/{npc_id}/context ────────────────────────────────────────

def test_get_npc_context_returns_string():
    """GET npc context should return a non-empty string."""
    sid = _create_session()
    resp = client.get(f"/game/session/{sid}/npc/elder/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "context" in data
    assert isinstance(data["context"], str)
    assert len(data["context"]) > 0


def test_get_npc_context_includes_relationship():
    """Context string should mention relationship label."""
    sid = _create_session()
    resp = client.get(f"/game/session/{sid}/npc/sage/context")
    assert resp.status_code == 200
    context = resp.json()["context"]
    # Default relationship is stranger
    assert "stranger" in context.lower() or "relationship" in context.lower()


def test_get_npc_context_includes_known_fact():
    """After adding a fact, context should reference it."""
    sid = _create_session()
    client.post(
        f"/game/session/{sid}/npc/librarian/fact",
        json={"fact": "Seeker of ancient scrolls"}
    )
    resp = client.get(f"/game/session/{sid}/npc/librarian/context")
    context = resp.json()["context"]
    assert "Seeker of ancient scrolls" in context


def test_get_npc_context_session_not_found():
    """GET npc context for unknown session returns 404."""
    resp = client.get("/game/session/no-such-session/npc/npc1/context")
    assert resp.status_code == 404


# ── Integration: memory persists across calls ──────────────────────────────────

def test_npc_memory_persists_across_endpoints():
    """Facts added via POST should appear in GET memory and GET context."""
    sid = _create_session()
    npc = "blacksmith"

    # Add multiple facts
    for fact in ["Repaired hero's sword", "Owes hero a favor", "Knows about the dragon"]:
        client.post(f"/game/session/{sid}/npc/{npc}/fact", json={"fact": fact})

    mem_resp = client.get(f"/game/session/{sid}/npc/{npc}/memory")
    assert mem_resp.status_code == 200
    known = mem_resp.json()["known_facts"]
    assert "Repaired hero's sword" in known
    assert "Owes hero a favor" in known
    assert "Knows about the dragon" in known

    ctx_resp = client.get(f"/game/session/{sid}/npc/{npc}/context")
    ctx = ctx_resp.json()["context"]
    assert "Repaired hero's sword" in ctx
