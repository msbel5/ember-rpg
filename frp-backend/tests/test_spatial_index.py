"""Tests for engine.world.spatial_index — SpatialIndex grid lookup."""
import pytest
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex


# ── helpers ──────────────────────────────────────────────────────────

def _entity(eid: str, x: int, y: int, blocking: bool = False, etype: EntityType = EntityType.NPC) -> Entity:
    return Entity(
        id=eid,
        entity_type=etype,
        name=f"E-{eid}",
        position=(x, y),
        glyph="@",
        color="white",
        blocking=blocking,
    )


# ── Add / Remove ─────────────────────────────────────────────────────

class TestAddRemove:
    def test_add_and_lookup(self):
        idx = SpatialIndex()
        e = _entity("a", 5, 5)
        idx.add(e)
        assert idx.at(5, 5) == [e]

    def test_add_multiple_same_cell(self):
        idx = SpatialIndex()
        e1 = _entity("a", 3, 3)
        e2 = _entity("b", 3, 3)
        idx.add(e1)
        idx.add(e2)
        result = idx.at(3, 3)
        assert len(result) == 2
        ids = {e.id for e in result}
        assert ids == {"a", "b"}

    def test_empty_cell_returns_empty(self):
        idx = SpatialIndex()
        assert idx.at(99, 99) == []

    def test_remove(self):
        idx = SpatialIndex()
        e = _entity("a", 5, 5)
        idx.add(e)
        idx.remove(e)
        assert idx.at(5, 5) == []

    def test_remove_nonexistent_no_error(self):
        idx = SpatialIndex()
        e = _entity("a", 5, 5)
        idx.remove(e)  # should not raise

    def test_count(self):
        idx = SpatialIndex()
        idx.add(_entity("a", 1, 1))
        idx.add(_entity("b", 2, 2))
        assert idx.count() == 2

    def test_count_after_remove(self):
        idx = SpatialIndex()
        e = _entity("a", 1, 1)
        idx.add(e)
        idx.add(_entity("b", 2, 2))
        idx.remove(e)
        assert idx.count() == 1

    def test_clear(self):
        idx = SpatialIndex()
        idx.add(_entity("a", 1, 1))
        idx.add(_entity("b", 2, 2))
        idx.clear()
        assert idx.count() == 0
        assert idx.at(1, 1) == []


# ── Move ─────────────────────────────────────────────────────────────

class TestMove:
    def test_move_updates_grid(self):
        idx = SpatialIndex()
        e = _entity("a", 1, 1)
        idx.add(e)
        idx.move(e, 5, 5)
        assert idx.at(1, 1) == []
        assert idx.at(5, 5) == [e]

    def test_move_updates_entity_position(self):
        idx = SpatialIndex()
        e = _entity("a", 1, 1)
        idx.add(e)
        idx.move(e, 7, 3)
        assert e.position == (7, 3)

    def test_move_preserves_count(self):
        idx = SpatialIndex()
        e = _entity("a", 0, 0)
        idx.add(e)
        idx.move(e, 10, 10)
        assert idx.count() == 1

    def test_get_position(self):
        idx = SpatialIndex()
        e = _entity("a", 3, 4)
        idx.add(e)
        assert idx.get_position("a") == (3, 4)
        idx.move(e, 7, 8)
        assert idx.get_position("a") == (7, 8)


# ── Blocking ─────────────────────────────────────────────────────────

class TestBlocking:
    def test_blocking_at_true(self):
        idx = SpatialIndex()
        idx.add(_entity("wall", 5, 5, blocking=True))
        assert idx.blocking_at(5, 5) is True

    def test_blocking_at_false(self):
        idx = SpatialIndex()
        idx.add(_entity("coin", 5, 5, blocking=False))
        assert idx.blocking_at(5, 5) is False

    def test_blocking_empty(self):
        idx = SpatialIndex()
        assert idx.blocking_at(5, 5) is False

    def test_blocking_mixed(self):
        idx = SpatialIndex()
        idx.add(_entity("coin", 5, 5, blocking=False))
        idx.add(_entity("wall", 5, 5, blocking=True))
        assert idx.blocking_at(5, 5) is True


# ── Radius query ─────────────────────────────────────────────────────

class TestRadius:
    def test_in_radius_includes_center(self):
        idx = SpatialIndex()
        e = _entity("a", 5, 5)
        idx.add(e)
        result = idx.in_radius(5, 5, 0)
        assert e in result

    def test_in_radius_includes_neighbors(self):
        idx = SpatialIndex()
        center = _entity("c", 5, 5)
        near = _entity("n", 6, 5)
        far = _entity("f", 20, 20)
        idx.add(center)
        idx.add(near)
        idx.add(far)
        result = idx.in_radius(5, 5, 2)
        ids = {e.id for e in result}
        assert "c" in ids
        assert "n" in ids
        assert "f" not in ids

    def test_in_radius_chebyshev(self):
        """Chebyshev: diagonal distance == max(|dx|,|dy|)"""
        idx = SpatialIndex()
        diag = _entity("d", 7, 7)
        idx.add(diag)
        # Distance from (5,5) to (7,7) is max(2,2) = 2
        result = idx.in_radius(5, 5, 2)
        assert diag in result
        result2 = idx.in_radius(5, 5, 1)
        assert diag not in result2

    def test_in_radius_empty(self):
        idx = SpatialIndex()
        assert idx.in_radius(0, 0, 5) == []


# ── Type queries ─────────────────────────────────────────────────────

class TestTypeQueries:
    def test_entities_of_type(self):
        idx = SpatialIndex()
        npc1 = _entity("n1", 1, 1, etype=EntityType.NPC)
        npc2 = _entity("n2", 2, 2, etype=EntityType.NPC)
        item = _entity("i1", 3, 3, etype=EntityType.ITEM)
        idx.add(npc1)
        idx.add(npc2)
        idx.add(item)
        npcs = idx.entities_of_type(EntityType.NPC)
        assert len(npcs) == 2
        items = idx.entities_of_type(EntityType.ITEM)
        assert len(items) == 1

    def test_all_entities(self):
        idx = SpatialIndex()
        idx.add(_entity("a", 1, 1))
        idx.add(_entity("b", 2, 2))
        idx.add(_entity("c", 3, 3))
        assert len(idx.all_entities()) == 3

    def test_entities_of_type_empty(self):
        idx = SpatialIndex()
        assert idx.entities_of_type(EntityType.BUILDING) == []


# ── at() returns copies ──────────────────────────────────────────────

class TestAtReturnsCopy:
    def test_at_returns_new_list(self):
        idx = SpatialIndex()
        e = _entity("a", 1, 1)
        idx.add(e)
        list1 = idx.at(1, 1)
        list2 = idx.at(1, 1)
        assert list1 is not list2
        assert list1 == list2
