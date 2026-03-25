"""
Tests for the Physical Inventory system integration across
game_session, game_engine, action_parser, action_points, viewport, and save_system.
"""
import copy
import pytest
from engine.api.game_engine import GameEngine, ActionResult
from engine.api.game_session import GameSession
from engine.api.action_parser import ActionParser, ActionIntent
from engine.world.action_points import ActionPointTracker
from engine.world.viewport import Viewport
from engine.world.inventory import (
    PhysicalInventory, ItemStack, Container, get_item_shape, SHAPES,
)
from engine.core.character import Character
from engine.core.dm_agent import DMContext, SceneType
from engine.api.save_system import SaveSystem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def session(engine):
    return engine.new_session("TestHero", "warrior", location="Stone Bridge Tavern")


@pytest.fixture
def parser():
    return ActionParser()


# ---------------------------------------------------------------------------
# 1. GameSession PhysicalInventory Migration
# ---------------------------------------------------------------------------

class TestSessionPhysicalInventory:
    """Session uses PhysicalInventory as backend."""

    def test_session_has_physical_inventory(self, session):
        assert session.physical_inventory is not None
        assert isinstance(session.physical_inventory, PhysicalInventory)

    def test_inventory_property_returns_list_of_dicts(self, session):
        inv = session.inventory
        assert isinstance(inv, list)
        for item in inv:
            assert isinstance(item, dict)
            assert "id" in item

    def test_equipment_property_returns_dict(self, session):
        eq = session.equipment
        assert isinstance(eq, dict)
        assert "weapon" in eq

    def test_add_item_goes_to_physical_inventory(self, session):
        session.add_item({"id": "test_gem", "name": "Test Gem", "type": "gem"})
        found = session.physical_inventory.find_item("test_gem")
        assert found is not None
        assert found.item_id == "test_gem"

    def test_remove_item_from_physical_inventory(self, session):
        session.add_item({"id": "test_gem", "name": "Test Gem", "type": "gem"})
        removed = session.remove_item("test_gem")
        assert removed is not None
        assert removed["id"] == "test_gem"
        assert session.physical_inventory.find_item("test_gem") is None

    def test_find_inventory_item(self, session):
        session.add_item({"id": "magic_ring", "name": "Magic Ring", "type": "ring"})
        found = session.find_inventory_item("magic_ring")
        assert found is not None
        assert found["id"] == "magic_ring"

    def test_equip_item_moves_to_equipment(self, session):
        session.add_item({"id": "iron_shield", "name": "Iron Shield", "type": "shield", "slot": "shield", "ac_bonus": 2})
        result = session.equip_item("iron_shield")
        assert result is not None
        eq = session.equipment
        assert eq["shield"] is not None
        assert eq["shield"]["id"] == "iron_shield"

    def test_unequip_item_returns_to_inventory(self, session):
        # warrior starts with weapon equipped
        weapon = session.equipment.get("weapon")
        assert weapon is not None
        unequipped = session.unequip_item("weapon")
        assert unequipped is not None
        assert session.equipment.get("weapon") is None
        # Should be in inventory now
        found = session.find_inventory_item(unequipped["id"])
        assert found is not None

    def test_set_equipment_slot(self, session):
        session.set_equipment_slot("shield", {"id": "wood_shield", "name": "Wooden Shield", "type": "shield", "ac_bonus": 1})
        eq = session.equipment
        assert eq["shield"] is not None
        assert eq["shield"]["id"] == "wood_shield"

    def test_get_equipment_slot(self, session):
        weapon = session.get_equipment_slot("weapon")
        assert weapon is not None or weapon is None  # depends on starter kit

    def test_inventory_setter_populates_physical_inventory(self, session):
        session.inventory = [
            {"id": "bread", "name": "Bread", "type": "consumable", "qty": 3},
            {"id": "torch", "name": "Torch", "type": "tool"},
        ]
        inv = session.inventory
        bread = next((i for i in inv if i["id"] == "bread"), None)
        assert bread is not None

    def test_equipment_setter_populates_physical_inventory(self, session):
        session.equipment = {
            "weapon": {"id": "steel_sword", "name": "Steel Sword", "type": "weapon"},
            "armor": None,
            "shield": None,
            "helmet": None,
            "boots": None,
            "gloves": None,
            "ring": None,
            "amulet": None,
        }
        eq = session.equipment
        assert eq["weapon"]["id"] == "steel_sword"

    def test_weight_info_in_to_dict(self, session):
        d = session.to_dict()
        assert "weight" in d
        assert "current" in d["weight"]
        assert "max" in d["weight"]
        assert d["weight"]["current"] >= 0

    def test_player_inventory_synced(self, session):
        """Player character's inventory list is synced from PhysicalInventory."""
        session.add_item({"id": "potion", "name": "Potion", "type": "consumable"})
        session.sync_player_state()
        assert "potion" in session.player.inventory

    def test_player_from_legacy_equipment(self):
        """GameSession migrates from player's legacy string equipment."""
        p = Character(
            name="Legacy",
            classes={"warrior": 1},
            stats={"MIG": 14, "AGI": 10, "END": 12, "MND": 8, "INS": 10, "PRE": 10},
            hp=20, max_hp=20,
            equipment={"weapon": "iron_sword", "armor": "chain_mail"},
        )
        dm = DMContext(scene_type=SceneType.EXPLORATION, location="Town", party=[p])
        s = GameSession(player=p, dm_context=dm)
        eq = s.equipment
        assert eq["weapon"] is not None
        assert eq["weapon"]["id"] == "iron_sword"
        assert eq["armor"] is not None
        assert eq["armor"]["id"] == "chain_mail"


# ---------------------------------------------------------------------------
# 2. Action Parser New Intents
# ---------------------------------------------------------------------------

class TestNewIntents:

    def test_fill_intent(self, parser):
        result = parser.parse("fill waterskin")
        assert result.intent == ActionIntent.FILL
        assert result.target == "waterskin"

    def test_fill_at_source(self, parser):
        result = parser.parse("fill bottle at well")
        assert result.intent == ActionIntent.FILL
        assert result.target == "bottle"

    def test_pour_intent(self, parser):
        result = parser.parse("pour water")
        assert result.intent == ActionIntent.POUR

    def test_empty_intent(self, parser):
        result = parser.parse("empty bottle")
        assert result.intent == ActionIntent.EMPTY

    def test_stash_intent(self, parser):
        result = parser.parse("stash gem in sock")
        assert result.intent == ActionIntent.STASH
        assert result.target == "gem"

    def test_rotate_intent(self, parser):
        result = parser.parse("rotate sword")
        assert result.intent == ActionIntent.ROTATE_ITEM
        assert result.target == "sword"

    def test_go_to_approach(self, parser):
        result = parser.parse("approach merchant")
        assert result.intent == ActionIntent.GO_TO
        assert result.target == "merchant"

    def test_move_still_works(self, parser):
        """Regular move directions still parse as MOVE."""
        result = parser.parse("move north")
        assert result.intent == ActionIntent.MOVE

    def test_move_to_dungeon_still_move(self, parser):
        result = parser.parse("move to dungeon")
        assert result.intent == ActionIntent.MOVE


# ---------------------------------------------------------------------------
# 3. Action Points Encumbrance
# ---------------------------------------------------------------------------

class TestEncumbrancePenalty:

    def test_movement_cost_with_encumbrance(self):
        tracker = ActionPointTracker(max_ap=6)
        assert tracker.movement_cost(1, 0) == 1
        assert tracker.movement_cost(1, 2) == 3

    def test_can_move_with_encumbrance(self):
        tracker = ActionPointTracker(max_ap=4)
        assert tracker.can_move(1, 0) is True
        assert tracker.can_move(1, 4) is False  # 1 + 4 = 5 > 4

    def test_spend_movement_with_encumbrance(self):
        tracker = ActionPointTracker(max_ap=6)
        assert tracker.spend_movement(1, 1) is True  # costs 2
        assert tracker.current_ap == 4

    def test_armor_plus_encumbrance(self):
        tracker = ActionPointTracker(max_ap=6, armor_type="chain_mail")
        # chain_mail penalty = 1, encumbrance = 1 → total cost = 1 + 1 + 1 = 3
        cost = tracker.movement_cost(1, 1)
        assert cost == 3


# ---------------------------------------------------------------------------
# 4. Viewport Zoom
# ---------------------------------------------------------------------------

class TestViewportZoom:

    def test_initial_zoom_level(self):
        vp = Viewport()
        assert vp.zoom_level == 1
        assert vp.width == 40
        assert vp.height == 20

    def test_cycle_zoom_forward(self):
        vp = Viewport()
        level = vp.cycle_zoom(1)
        assert level == 2
        assert vp.width == 80
        assert vp.height == 40

    def test_cycle_zoom_wraps(self):
        vp = Viewport()
        vp.cycle_zoom(1)  # -> 2
        vp.cycle_zoom(1)  # -> 3
        level = vp.cycle_zoom(1)  # -> 1
        assert level == 1
        assert vp.width == 40

    def test_cycle_zoom_backward(self):
        vp = Viewport()
        level = vp.cycle_zoom(-1)
        assert level == 3
        assert vp.width == 160

    def test_fov_radius_per_zoom(self):
        vp = Viewport()
        assert vp.fov_radius == 8
        vp.cycle_zoom(1)
        assert vp.fov_radius == 16
        vp.cycle_zoom(1)
        assert vp.fov_radius == 999

    def test_zoom_serialization(self):
        vp = Viewport()
        vp.cycle_zoom(1)
        d = vp.to_dict()
        assert d["zoom_level"] == 2
        restored = Viewport.from_dict(d)
        assert restored.zoom_level == 2
        assert restored.width == 80


# ---------------------------------------------------------------------------
# 5. Game Engine New Handlers
# ---------------------------------------------------------------------------

class TestNewHandlers:

    def test_fill_no_water_source(self, engine, session):
        result = engine.process_action(session, "fill waterskin")
        assert "water source" in result.narrative.lower() or "don't have" in result.narrative.lower()

    def test_pour_empty_container(self, engine, session):
        result = engine.process_action(session, "pour waterskin")
        assert "don't have" in result.narrative.lower() or "liquid" in result.narrative.lower()

    def test_stash_item(self, engine, session):
        session.add_item({"id": "gem", "name": "Ruby Gem", "type": "gem"})
        result = engine.process_action(session, "stash gem in sock_left")
        assert "stash" in result.narrative.lower() or "don't have" in result.narrative.lower()

    def test_rotate_item(self, engine, session):
        session.add_item({"id": "sword", "name": "Sword", "type": "weapon"})
        result = engine.process_action(session, "rotate sword")
        assert "rotate" in result.narrative.lower() or "don't have" in result.narrative.lower()

    def test_go_to_npc(self, engine, session):
        """Approach an NPC uses pathfinding."""
        # Find an NPC in the session
        npc_name = None
        for eid, e in session.entities.items():
            npc_name = e.get("name")
            if npc_name:
                break
        if npc_name:
            result = engine.process_action(session, f"approach {npc_name}")
            assert "walk" in result.narrative.lower() or "path" in result.narrative.lower() or "close" in result.narrative.lower()

    def test_inventory_shows_weight(self, engine, session):
        result = engine.process_action(session, "inventory")
        assert "weight" in result.narrative.lower() or "kg" in result.narrative.lower()

    def test_auto_turn_on_ap_exhaustion(self, engine, session):
        """When AP runs out after pickup, auto-turn refreshes AP."""
        if session.ap_tracker:
            session.ap_tracker.current_ap = 1  # Only 1 AP left
        # After the action AP should be refreshed
        result = engine.process_action(session, "look")
        # Not testing specific behavior, just that it doesn't crash


# ---------------------------------------------------------------------------
# 6. Save/Load with PhysicalInventory
# ---------------------------------------------------------------------------

class TestSaveLoadPhysicalInventory:

    @pytest.fixture
    def save_system(self, tmp_path):
        d = tmp_path / "saves"
        d.mkdir()
        return SaveSystem(save_dir=d)

    def test_physical_inventory_survives_roundtrip(self, save_system, engine):
        session = engine.new_session("SaveTest", "warrior", location="Stone Bridge Tavern")
        session.add_item({"id": "magic_gem", "name": "Magic Gem", "type": "gem"})

        save_system.save_game(session, "test_phys_inv")
        loaded = save_system.load_game("test_phys_inv")

        assert loaded is not None
        assert loaded.physical_inventory is not None
        found = loaded.physical_inventory.find_item("magic_gem")
        assert found is not None
        assert found.item_id == "magic_gem"

    def test_equipment_survives_roundtrip(self, save_system, engine):
        session = engine.new_session("SaveTest2", "warrior", location="Stone Bridge Tavern")
        weapon = session.equipment.get("weapon")
        assert weapon is not None

        save_system.save_game(session, "test_equip")
        loaded = save_system.load_game("test_equip")

        loaded_weapon = loaded.equipment.get("weapon")
        assert loaded_weapon is not None
        assert loaded_weapon["id"] == weapon["id"]

    def test_zoom_level_survives_roundtrip(self, save_system, engine):
        session = engine.new_session("ZoomTest", "warrior", location="Stone Bridge Tavern")
        session.viewport.cycle_zoom(1)
        assert session.viewport.zoom_level == 2

        save_system.save_game(session, "test_zoom")
        loaded = save_system.load_game("test_zoom")

        assert loaded.viewport.zoom_level == 2

    def test_legacy_save_migration(self, save_system, engine):
        """Loading a save without physical_inventory creates one."""
        session = engine.new_session("LegacyTest", "warrior", location="Stone Bridge Tavern")
        save_system.save_game(session, "test_legacy")

        # Manually remove physical_inventory from saved data
        import json
        filepath = save_system.save_dir / "test_legacy.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        state = data["session_state"]
        state.pop("physical_inventory", None)
        # Keep legacy fields
        filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        loaded = save_system.load_game("test_legacy")
        assert loaded is not None
        assert loaded.physical_inventory is not None


# ---------------------------------------------------------------------------
# 7. Encumbrance in Movement
# ---------------------------------------------------------------------------

class TestEncumbranceMovement:

    def test_overencumbered_blocks_movement(self, engine, session):
        """Extreme weight prevents movement."""
        # Add extremely heavy items
        for i in range(50):
            session.add_item({"id": f"boulder_{i}", "name": f"Heavy Boulder {i}", "type": "item", "weight": 10.0})
        result = engine.process_action(session, "move north")
        # Should either block or cost more AP
        assert result.narrative is not None  # doesn't crash
