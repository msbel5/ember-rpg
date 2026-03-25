"""
Tests for engine.world.history -- World History Seed (AC-20..AC-22)
"""
import pytest

from engine.world.history import (
    HistoryEvent,
    HistorySeed,
    NotableFigure,
    get_history_context,
    get_npc_known_facts,
)


# ---------------------------------------------------------------------------
# AC-20: Deterministic generation
# ---------------------------------------------------------------------------

class TestDeterministicGeneration:
    """Same seed must always produce the same history."""

    def test_same_seed_same_wars(self):
        h1 = HistorySeed().generate(42)
        h2 = HistorySeed().generate(42)
        wars1 = [(w.year, w.name) for w in h1.get_wars()]
        wars2 = [(w.year, w.name) for w in h2.get_wars()]
        assert wars1 == wars2

    def test_same_seed_same_figures(self):
        h1 = HistorySeed().generate(99)
        h2 = HistorySeed().generate(99)
        names1 = [f.name for f in h1.get_figures()]
        names2 = [f.name for f in h2.get_figures()]
        assert names1 == names2

    def test_different_seed_different_history(self):
        h1 = HistorySeed().generate(1)
        h2 = HistorySeed().generate(2)
        wars1 = [w.name for w in h1.get_wars()]
        wars2 = [w.name for w in h2.get_wars()]
        # Extremely unlikely to be identical with different seeds
        assert wars1 != wars2 or h1.get_figures() != h2.get_figures()


# ---------------------------------------------------------------------------
# AC-21: Content requirements
# ---------------------------------------------------------------------------

class TestContentRequirements:
    """History must contain required event types and counts."""

    @pytest.fixture()
    def history(self):
        return HistorySeed().generate(42)

    def test_has_3_to_5_wars(self, history):
        wars = history.get_wars()
        assert 3 <= len(wars) <= 5

    def test_has_2_to_3_fallen_kingdoms(self, history):
        fallen = history.get_fallen_kingdoms()
        assert 2 <= len(fallen) <= 3

    def test_has_exactly_1_catastrophe(self, history):
        cats = history.get_catastrophes()
        assert len(cats) == 1

    def test_has_5_to_10_notable_figures(self, history):
        figs = history.get_figures()
        assert 5 <= len(figs) <= 10

    def test_has_current_tensions(self, history):
        tensions = history.get_tensions()
        assert len(tensions) >= 2

    def test_events_are_sorted_chronologically(self, history):
        years = [e.year for e in history.events]
        assert years == sorted(years)

    def test_war_events_have_factions(self, history):
        for war in history.get_wars():
            assert len(war.factions) == 2

    def test_war_has_winner_and_loser(self, history):
        for war in history.get_wars():
            assert "winner" in war.consequences
            assert "loser" in war.consequences


# ---------------------------------------------------------------------------
# AC-22: NPC knowledge filter and LLM context
# ---------------------------------------------------------------------------

class TestNPCKnowledge:
    """Test that NPC knowledge filtering works correctly."""

    @pytest.fixture()
    def history(self):
        return HistorySeed().generate(42)

    def test_young_commoner_knows_less_than_old_scholar(self, history):
        young = get_npc_known_facts("farmer", 20, "harbor_guard", history)
        old_scholar = get_npc_known_facts("scholar", 80, "harbor_guard", history)
        assert len(young) <= len(old_scholar)

    def test_npc_always_knows_own_faction_events(self, history):
        facts = get_npc_known_facts("farmer", 10, "harbor_guard", history)
        faction_events = [e for e in history.events if "harbor_guard" in e.factions]
        for event in faction_events:
            assert event in facts

    def test_npc_always_knows_current_tensions(self, history):
        facts = get_npc_known_facts("farmer", 20, "harbor_guard", history)
        tensions = history.get_tensions()
        for t in tensions:
            assert t in facts

    def test_scholar_knows_ancient_events(self, history):
        facts = get_npc_known_facts("scholar", 50, "temple_order", history)
        # Scholars can know events from 500 years back
        ancient = [e for e in history.events if e.year >= 500]
        for event in ancient:
            # They should know if it's within 500 year window or own faction
            if event.year >= history.current_year - 500 or "temple_order" in event.factions:
                assert event in facts


class TestHistoryContext:
    """Test LLM context formatting."""

    def test_context_is_non_empty_string(self):
        h = HistorySeed().generate(42)
        ctx = get_history_context(h)
        assert isinstance(ctx, str)
        assert len(ctx) > 100

    def test_context_contains_section_headers(self):
        h = HistorySeed().generate(42)
        ctx = get_history_context(h)
        assert "WORLD HISTORY" in ctx
        assert "Major Wars" in ctx
        assert "Notable Figures" in ctx

    def test_history_event_dataclass_to_dict(self):
        event = HistoryEvent(
            year=500,
            event_type="war",
            name="Test War",
            factions=["a", "b"],
            outcome="A won",
            consequences={"winner": "a"},
        )
        d = event.to_dict()
        assert d["year"] == 500
        assert d["name"] == "Test War"

    def test_notable_figure_to_dict(self):
        fig = NotableFigure(
            name="Test Person",
            born_year=800,
            died_year=870,
            faction="harbor_guard",
            role="general",
            legacy="Was great.",
        )
        d = fig.to_dict()
        assert d["name"] == "Test Person"
        assert d["died_year"] == 870
