"""Tests for engine.world.rumors — AC-40..AC-42."""

import pytest
from engine.world.rumors import NPCInfo, Rumor, RumorNetwork


class TestRumorCreation:
    def test_add_rumor_returns_rumor(self):
        net = RumorNetwork()
        r = net.add_rumor("Dragon spotted", "npc_guard", "town_square")
        assert isinstance(r, Rumor)
        assert r.fact == "Dragon spotted"
        assert "town_square" in r.locations

    def test_rumor_id_increments(self):
        net = RumorNetwork()
        r1 = net.add_rumor("Fact A", "npc1", "loc1")
        r2 = net.add_rumor("Fact B", "npc2", "loc2")
        assert r1.rumor_id != r2.rumor_id

    def test_confidence_clamped(self):
        net = RumorNetwork()
        r = net.add_rumor("Over", "npc", "loc", confidence=5.0)
        assert r.confidence == 1.0
        r2 = net.add_rumor("Under", "npc", "loc", confidence=-1.0)
        assert r2.confidence == 0.0


class TestPropagation:
    def test_npc_hears_rumor_at_same_location(self):
        net = RumorNetwork()
        net.add_rumor("Bandits nearby", "npc_guard", "town_square")
        npc = NPCInfo(npc_id="npc_baker", location="town_square")
        events = net.propagate([npc])
        assert len(events) == 1
        assert events[0]["npc_id"] == "npc_baker"

    def test_npc_at_different_location_doesnt_hear(self):
        net = RumorNetwork()
        net.add_rumor("Secret", "npc_spy", "castle")
        npc = NPCInfo(npc_id="npc_farmer", location="farm")
        events = net.propagate([npc])
        assert len(events) == 0

    def test_faction_filter_blocks(self):
        net = RumorNetwork()
        net.add_rumor("Guild secret", "npc_guildmaster", "guild_hall",
                      faction_filter="thieves_guild")
        npc = NPCInfo(npc_id="npc_guard", location="guild_hall", faction="city_guard")
        events = net.propagate([npc])
        assert len(events) == 0

    def test_faction_filter_allows(self):
        net = RumorNetwork()
        net.add_rumor("Guild secret", "npc_guildmaster", "guild_hall",
                      faction_filter="thieves_guild")
        npc = NPCInfo(npc_id="npc_thief", location="guild_hall",
                      faction="thieves_guild")
        events = net.propagate([npc])
        assert len(events) == 1

    def test_npc_doesnt_hear_twice(self):
        net = RumorNetwork()
        net.add_rumor("News", "npc1", "market")
        npc = NPCInfo(npc_id="npc2", location="market")
        net.propagate([npc])
        events2 = net.propagate([npc])
        assert len(events2) == 0


class TestDecay:
    def test_decay_reduces_confidence(self):
        net = RumorNetwork()
        r = net.add_rumor("Old news", "npc1", "loc1", confidence=0.8, decay_rate=0.1)
        net.decay(5)  # 5 hours × 0.1 = 0.5 decay
        assert abs(r.confidence - 0.3) < 0.01

    def test_decay_returns_expired(self):
        net = RumorNetwork()
        net.add_rumor("Stale", "npc1", "loc1", confidence=0.1, decay_rate=0.1)
        expired = net.decay(2)
        assert len(expired) == 1

    def test_prune_removes_expired(self):
        net = RumorNetwork()
        net.add_rumor("Gone", "npc1", "loc1", confidence=0.01, decay_rate=0.1)
        net.decay(1)
        count = net.prune_expired()
        assert count == 1
        assert len(net.rumors) == 0


class TestGetRumorsForNpc:
    def test_returns_heard_rumors(self):
        net = RumorNetwork()
        net.add_rumor("Fact", "npc1", "market")
        npc = NPCInfo(npc_id="npc2", location="market")
        net.propagate([npc])
        rumors = net.get_rumors_for_npc(npc)
        assert len(rumors) == 1

    def test_excludes_expired(self):
        net = RumorNetwork()
        net.add_rumor("Dead rumor", "npc1", "loc1", confidence=0.01, decay_rate=1.0)
        net.decay(1)
        npc = NPCInfo(npc_id="npc1", location="loc1")
        assert len(net.get_rumors_for_npc(npc)) == 0

    def test_spread_to_location(self):
        net = RumorNetwork()
        r = net.add_rumor("News", "npc1", "loc1", spread_radius=2)
        ok = net.spread_to_location(r.rumor_id, "loc2")
        assert ok is True
        npc = NPCInfo(npc_id="npc3", location="loc2")
        events = net.propagate([npc])
        assert len(events) == 1
