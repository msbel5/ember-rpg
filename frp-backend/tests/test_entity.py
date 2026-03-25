"""Tests for engine.world.entity — Entity dataclass and EntityType enum."""
import pytest
from engine.world.entity import Entity, EntityType
from engine.world.npc_needs import NPCNeeds
from engine.world.body_parts import BodyPartTracker


# ── helpers ──────────────────────────────────────────────────────────

def _make_npc(**overrides) -> Entity:
    defaults = dict(
        id="npc_01",
        entity_type=EntityType.NPC,
        name="Guard",
        position=(5, 10),
        glyph="G",
        color="yellow",
        blocking=True,
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_item(**overrides) -> Entity:
    defaults = dict(
        id="item_01",
        entity_type=EntityType.ITEM,
        name="Sword",
        position=(3, 3),
        glyph=")",
        color="white",
        blocking=False,
    )
    defaults.update(overrides)
    return Entity(**defaults)


# ── EntityType enum ──────────────────────────────────────────────────

class TestEntityType:
    def test_all_members_exist(self):
        assert EntityType.NPC.value == "npc"
        assert EntityType.CREATURE.value == "creature"
        assert EntityType.ITEM.value == "item"
        assert EntityType.BUILDING.value == "building"
        assert EntityType.FURNITURE.value == "furniture"

    def test_from_string(self):
        assert EntityType("npc") == EntityType.NPC
        assert EntityType("creature") == EntityType.CREATURE

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            EntityType("invalid_type")


# ── Entity creation ──────────────────────────────────────────────────

class TestEntityCreation:
    def test_basic_npc(self):
        e = _make_npc()
        assert e.id == "npc_01"
        assert e.entity_type == EntityType.NPC
        assert e.name == "Guard"
        assert e.position == (5, 10)
        assert e.glyph == "G"
        assert e.color == "yellow"
        assert e.blocking is True

    def test_default_state(self):
        e = _make_npc()
        assert e.alive is True
        assert e.hp == 10
        assert e.max_hp == 10
        assert e.disposition == "neutral"
        assert e.ap == 4
        assert e.max_ap == 4

    def test_optional_components_default_none(self):
        e = _make_npc()
        assert e.needs is None
        assert e.inventory is None
        assert e.skills is None
        assert e.body is None
        assert e.faction is None
        assert e.schedule is None
        assert e.job is None

    def test_npc_with_needs(self):
        needs = NPCNeeds(safety=50, sustenance=30)
        e = _make_npc(needs=needs)
        assert e.needs is not None
        assert e.needs.safety == 50.0
        assert e.needs.sustenance == 30.0

    def test_npc_with_body(self):
        body = BodyPartTracker()
        e = _make_npc(body=body)
        assert e.body is not None
        assert e.body.is_alive() is True

    def test_npc_with_inventory(self):
        inv = [{"name": "Sword", "damage": 5}]
        e = _make_npc(inventory=inv)
        assert len(e.inventory) == 1

    def test_npc_with_skills(self):
        skills = {"smithing": 12, "alchemy": 8}
        e = _make_npc(skills=skills)
        assert e.skills["smithing"] == 12

    def test_generate_id(self):
        id1 = Entity.generate_id()
        id2 = Entity.generate_id()
        assert isinstance(id1, str)
        assert len(id1) == 8
        assert id1 != id2


# ── Disposition queries ──────────────────────────────────────────────

class TestDisposition:
    def test_is_hostile(self):
        e = _make_npc(disposition="hostile")
        assert e.is_hostile() is True
        assert e.is_friendly() is False

    def test_is_friendly(self):
        e = _make_npc(disposition="friendly")
        assert e.is_friendly() is True
        assert e.is_hostile() is False

    def test_neutral_neither(self):
        e = _make_npc(disposition="neutral")
        assert e.is_hostile() is False
        assert e.is_friendly() is False

    def test_afraid_neither(self):
        e = _make_npc(disposition="afraid")
        assert e.is_hostile() is False
        assert e.is_friendly() is False


# ── Type queries ─────────────────────────────────────────────────────

class TestTypeQueries:
    def test_is_npc(self):
        assert _make_npc().is_npc() is True
        assert _make_item().is_npc() is False

    def test_is_item(self):
        assert _make_item().is_item() is True
        assert _make_npc().is_item() is False

    def test_is_creature(self):
        e = _make_npc(entity_type=EntityType.CREATURE)
        assert e.is_creature() is True


# ── HP / damage / heal ───────────────────────────────────────────────

class TestCombat:
    def test_take_damage(self):
        e = _make_npc(hp=10, max_hp=10)
        dealt = e.take_damage(3)
        assert dealt == 3
        assert e.hp == 7
        assert e.alive is True

    def test_take_lethal_damage(self):
        e = _make_npc(hp=5, max_hp=10)
        dealt = e.take_damage(10)
        assert dealt == 5  # only had 5 HP
        assert e.hp == 0
        assert e.alive is False

    def test_take_exact_lethal(self):
        e = _make_npc(hp=3, max_hp=10)
        e.take_damage(3)
        assert e.hp == 0
        assert e.alive is False

    def test_is_alive(self):
        e = _make_npc(hp=1)
        assert e.is_alive() is True
        e.take_damage(1)
        assert e.is_alive() is False

    def test_heal(self):
        e = _make_npc(hp=5, max_hp=10)
        healed = e.heal(3)
        assert healed == 3
        assert e.hp == 8

    def test_heal_capped_at_max(self):
        e = _make_npc(hp=8, max_hp=10)
        healed = e.heal(5)
        assert healed == 2
        assert e.hp == 10


# ── Action Points ────────────────────────────────────────────────────

class TestActionPoints:
    def test_spend_ap(self):
        e = _make_npc(ap=4, max_ap=4)
        assert e.spend_ap(2) is True
        assert e.ap == 2

    def test_spend_ap_insufficient(self):
        e = _make_npc(ap=1, max_ap=4)
        assert e.spend_ap(2) is False
        assert e.ap == 1  # unchanged

    def test_reset_ap(self):
        e = _make_npc(ap=1, max_ap=4)
        e.reset_ap()
        assert e.ap == 4


# ── Movement ─────────────────────────────────────────────────────────

class TestMovement:
    def test_move_to(self):
        e = _make_npc(position=(0, 0))
        e.move_to(5, 10)
        assert e.position == (5, 10)


# ── Serialisation ────────────────────────────────────────────────────

class TestSerialisation:
    def test_to_dict_basic(self):
        e = _make_npc()
        d = e.to_dict()
        assert d["id"] == "npc_01"
        assert d["entity_type"] == "npc"
        assert d["position"] == [5, 10]
        assert d["glyph"] == "G"
        assert d["alive"] is True

    def test_to_dict_with_needs(self):
        e = _make_npc(needs=NPCNeeds(safety=40))
        d = e.to_dict()
        assert "needs" in d
        assert d["needs"]["safety"] == 40.0

    def test_to_dict_with_faction(self):
        e = _make_npc(faction="harbor_guard")
        d = e.to_dict()
        assert d["faction"] == "harbor_guard"

    def test_from_dict_roundtrip(self):
        original = _make_npc(
            needs=NPCNeeds(safety=55, commerce=30),
            faction="thieves_guild",
            job="spy",
            hp=7,
            disposition="hostile",
        )
        d = original.to_dict()
        restored = Entity.from_dict(d)
        assert restored.id == original.id
        assert restored.entity_type == original.entity_type
        assert restored.position == tuple(d["position"])
        assert restored.faction == "thieves_guild"
        assert restored.needs.safety == 55.0
        assert restored.hp == 7
        assert restored.disposition == "hostile"

    def test_repr(self):
        e = _make_npc()
        r = repr(e)
        assert "npc_01" in r
        assert "Guard" in r
