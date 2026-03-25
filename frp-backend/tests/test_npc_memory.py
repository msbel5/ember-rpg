"""
Ember RPG - Per-NPC Persistent Memory Tests
Phase 3b
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from engine.npc.npc_memory import NPCMemory, NPCMemoryManager

client = TestClient(app)


def _new_session():
    resp = client.post("/game/session/new", json={"player_name": "Aria", "player_class": "warrior"})
    assert resp.status_code == 200
    return resp.json()["session_id"]


class TestNPCMemoryUnit:
    def test_memory_initialized_as_stranger(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        assert mem.relationship_score == 0
        assert mem.relationship_label == "stranger"
        assert mem.conversations == []
        assert mem.known_facts == []

    def test_positive_conversation_increases_relationship(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.add_conversation("Nice chat", "positive", "Day 1, 10:00")
        assert mem.relationship_score == 5

    def test_negative_conversation_decreases_relationship(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.add_conversation("Argument", "negative", "Day 1, 10:00")
        assert mem.relationship_score == -5

    def test_relationship_label_changes_with_score(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.update_relationship(60)
        assert mem.relationship_label == "ally"
        mem.update_relationship(-110)  # 60 - 110 = -50 → enemy
        assert mem.relationship_label == "enemy"
        mem2 = NPCMemory(npc_id="npc2", name="Jane")
        mem2.update_relationship(30)
        assert mem2.relationship_label == "friend"
        mem2.update_relationship(-30)  # 30 - 30 = 0 → stranger
        assert mem2.relationship_label == "stranger"

    def test_conversations_capped_at_10_merge_into_longterm(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        for i in range(11):
            mem.add_conversation(f"Talk {i}", "neutral", f"Day {i}")
        assert len(mem.conversations) == 10
        assert "Talk 0" in mem.long_term_memory

    def test_known_facts_stored(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.add_known_fact("Player killed bandit leader")
        assert "Player killed bandit leader" in mem.known_facts

    def test_no_duplicate_facts(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.add_known_fact("Player is a mage")
        mem.add_known_fact("Player is a mage")
        assert mem.known_facts.count("Player is a mage") == 1

    def test_gossip_propagation(self):
        mgr = NPCMemoryManager("sess1")
        mgr.get_memory("npc1", "Tom")
        mgr.propagate_gossip("npc1", "npc2", "Player stole gold")
        npc2 = mgr.get_memory("npc2")
        assert any("Player stole gold" in f for f in npc2.known_facts)

    def test_build_context_includes_relationship(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.update_relationship(35)
        ctx = mem.build_context()
        assert "friend" in ctx
        assert "Tom" in ctx

    def test_build_context_includes_known_facts(self):
        mem = NPCMemory(npc_id="npc1", name="Tom")
        mem.add_known_fact("Player saved the village")
        ctx = mem.build_context()
        assert "Player saved the village" in ctx

    def test_memory_serialization_round_trip(self):
        mgr = NPCMemoryManager("sess1")
        mem = mgr.get_memory("npc1", "Tom")
        mem.add_conversation("Good talk", "positive", "Day 1, 10:00")
        mem.add_known_fact("Player is brave")

        data = mgr.to_dict()
        mgr2 = NPCMemoryManager.from_dict("sess1", data)
        mem2 = mgr2.get_memory("npc1")
        assert mem2.relationship_score == 5
        assert "Player is brave" in mem2.known_facts
        assert len(mem2.conversations) == 1


class TestNPCMemoryAPI:
    def test_get_npc_memory_endpoint(self):
        sid = _new_session()
        resp = client.get(f"/game/session/{sid}/npc/npc1/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["npc_id"] == "npc1"
        assert data["relationship_label"] == "stranger"

    def test_add_fact_endpoint(self):
        sid = _new_session()
        resp = client.post(
            f"/game/session/{sid}/npc/npc1/fact",
            json={"fact": "Player saved the village"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Player saved the village" in data["known_facts"]
