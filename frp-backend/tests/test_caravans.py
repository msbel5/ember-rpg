"""Tests for engine.world.caravans — AC-37..AC-39."""

import pytest
from engine.world.caravans import CARAVANS, CaravanManager, CaravanRoute


class TestCaravanRoutes:
    def test_three_caravan_routes_exist(self):
        assert "iron_caravan" in CARAVANS
        assert "food_caravan" in CARAVANS
        assert "luxury_caravan" in CARAVANS

    def test_routes_have_goods(self):
        for key, route in CARAVANS.items():
            assert len(route.goods) > 0, f"{key} has no goods"

    def test_travel_hours_positive(self):
        for key, route in CARAVANS.items():
            assert route.travel_hours > 0


class TestCaravanManager:
    def test_tick_spawns_caravans(self):
        mgr = CaravanManager()
        events = mgr.tick(0)
        departures = [e for e in events if e["type"] == "departure"]
        assert len(departures) == len(CARAVANS)  # all spawn at hour 0

    def test_caravan_arrives_after_travel(self):
        mgr = CaravanManager()
        mgr.tick(0)  # spawn all
        # Advance past the longest travel time + a bit
        events = mgr.tick(50)
        arrivals = [e for e in events if e["type"] == "arrival"]
        assert len(arrivals) >= 1

    def test_no_double_spawn_before_frequency(self):
        mgr = CaravanManager()
        mgr.tick(0)
        events = mgr.tick(1)  # 1 hour later — no new departures
        departures = [e for e in events if e["type"] == "departure"]
        assert len(departures) == 0

    def test_respawn_after_frequency(self):
        mgr = CaravanManager()
        mgr.tick(0)
        # Food caravan freq = 18h. Tick through hours 1-17 to clear arrivals.
        for h in range(1, 18):
            mgr.tick(h)
        # At hour 18 the food_caravan frequency has elapsed (18 - 0 = 18 >= 18).
        events = mgr.tick(18)
        departures = [e for e in events if e["type"] == "departure"]
        route_keys = {e["route"] for e in departures}
        assert "food_caravan" in route_keys

    def test_get_active_caravans(self):
        mgr = CaravanManager()
        mgr.tick(0)
        active = mgr.get_active_caravans()
        assert len(active) >= 1
        assert "caravan_id" in active[0]

    def test_raid_delays_and_loses_goods(self):
        mgr = CaravanManager()
        mgr.tick(0)
        cid = list(mgr.active.keys())[0]
        result = mgr.raid_caravan(cid)
        assert result["delay_hours"] >= 4
        assert len(result["goods_lost"]) > 0
        ac = mgr.active[cid]
        assert ac.raided is True

    def test_raid_nonexistent_raises(self):
        mgr = CaravanManager()
        with pytest.raises(KeyError):
            mgr.raid_caravan("caravan_999")

    def test_raided_caravan_arrives_late(self):
        mgr = CaravanManager()
        mgr.tick(0)
        cid = list(mgr.active.keys())[0]
        original_eta = mgr.active[cid].arrival_hour
        mgr.raid_caravan(cid)
        new_eta = mgr.active[cid].arrival_hour + mgr.active[cid].delayed_hours
        assert new_eta > original_eta
