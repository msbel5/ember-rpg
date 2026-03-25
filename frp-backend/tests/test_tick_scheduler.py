"""Tests for WorldTickScheduler (FR-01..FR-04, AC-01)."""
import time

import pytest

from engine.world.tick_scheduler import WorldEvent, WorldTickScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subsystem(event_type: str = "test"):
    """Return a subsystem function that produces one event per call."""
    def subsystem(hours: int) -> list[WorldEvent]:
        return [
            WorldEvent(
                event_type=event_type,
                description=f"{event_type} ticked {hours}h",
                data={"hours": hours},
            )
        ]
    return subsystem


def _noop_subsystem(hours: int) -> list[WorldEvent]:
    return []


def _failing_subsystem(hours: int) -> list[WorldEvent]:
    raise RuntimeError("subsystem blew up")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorldTickScheduler:

    def test_advance_no_subsystems(self):
        """Advance with zero subsystems produces no events."""
        scheduler = WorldTickScheduler()
        events = scheduler.advance(hours=1)
        assert events == []
        assert scheduler.elapsed_hours == 1

    def test_advance_single_subsystem(self):
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("a", _make_subsystem("alpha"))
        events = scheduler.advance(hours=1)
        assert len(events) == 1
        assert events[0].event_type == "alpha"
        assert events[0].data["hours"] == 1

    def test_advance_multiple_subsystems_order(self):
        """Subsystems run in registration order (FR-03)."""
        call_order = []

        def sub_a(hours):
            call_order.append("a")
            return [WorldEvent("a", "a")]

        def sub_b(hours):
            call_order.append("b")
            return [WorldEvent("b", "b")]

        def sub_c(hours):
            call_order.append("c")
            return [WorldEvent("c", "c")]

        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("a", sub_a)
        scheduler.register_subsystem("b", sub_b)
        scheduler.register_subsystem("c", sub_c)
        events = scheduler.advance(hours=1)

        assert call_order == ["a", "b", "c"]
        assert len(events) == 3

    def test_action_tick_advances_1_hour(self):
        """FR-01: player action -> 1-hour tick."""
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("x", _make_subsystem("x"))
        events = scheduler.action_tick()
        assert scheduler.elapsed_hours == 1
        assert events[0].data["hours"] == 1

    def test_rest_tick_advances_8_hours(self):
        """FR-02: resting -> 8-hour tick."""
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("x", _make_subsystem("x"))
        events = scheduler.rest_tick()
        assert scheduler.elapsed_hours == 8
        assert events[0].data["hours"] == 8

    def test_history_accumulates(self):
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("x", _make_subsystem("x"))
        scheduler.advance(hours=1)
        scheduler.advance(hours=1)
        assert len(scheduler.history) == 2

    def test_register_duplicate_raises(self):
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("dup", _noop_subsystem)
        with pytest.raises(ValueError, match="already registered"):
            scheduler.register_subsystem("dup", _noop_subsystem)

    def test_unregister_subsystem(self):
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("x", _noop_subsystem)
        assert scheduler.unregister_subsystem("x") is True
        assert scheduler.unregister_subsystem("x") is False
        assert scheduler.subsystem_names == []

    def test_failing_subsystem_captured(self):
        """A broken subsystem should not crash the scheduler."""
        scheduler = WorldTickScheduler()
        scheduler.register_subsystem("bad", _failing_subsystem)
        scheduler.register_subsystem("good", _make_subsystem("ok"))
        events = scheduler.advance(hours=1)
        assert len(events) == 2
        assert events[0].event_type == "subsystem_error"
        assert "blew up" in events[0].description
        assert events[1].event_type == "ok"

    def test_invalid_hours_raises(self):
        scheduler = WorldTickScheduler()
        with pytest.raises(ValueError, match="hours must be >= 1"):
            scheduler.advance(hours=0)

    def test_performance_100_ticks_under_1s(self):
        """AC-01: 100 ticks must complete in < 1 second."""
        scheduler = WorldTickScheduler()
        # Register 5 lightweight subsystems
        for i in range(5):
            scheduler.register_subsystem(f"sub_{i}", _make_subsystem(f"s{i}"))

        start = time.perf_counter()
        for _ in range(100):
            scheduler.advance(hours=1)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"100 ticks took {elapsed:.3f}s (limit 1s)"
        assert scheduler.elapsed_hours == 100
        assert len(scheduler.history) == 500  # 5 subsystems * 100 ticks
