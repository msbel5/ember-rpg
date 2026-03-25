"""
Ember RPG -- Save/Load System Tests
Full roundtrip tests ensuring ALL game state is preserved.
"""
import json
import os
import pytest
import tempfile
from pathlib import Path

from engine.core.character import Character
from engine.core.dm_agent import DMContext, DMEvent, SceneType, EventType
from engine.api.game_engine import GameEngine
from engine.api.game_session import GameSession
from engine.api.save_system import SaveSystem
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport
from engine.world.action_points import ActionPointTracker
from engine.world.body_parts import BodyPartTracker
from engine.world.economy import LocationStock
from engine.world.rumors import RumorNetwork
from engine.world.quest_timeout import QuestTracker
from engine.world.caravans import CaravanManager
from engine.world.history import HistorySeed
from engine.world.schedules import GameTime as LivingGameTime
from engine.map import MapData, TileType, Room
from engine.api.action_parser import ActionParser, ActionIntent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_save_dir(tmp_path):
    """Provide a temporary saves directory."""
    d = tmp_path / "saves"
    d.mkdir()
    return d


@pytest.fixture
def save_system(tmp_save_dir):
    """SaveSystem pointed at a temp directory."""
    return SaveSystem(save_dir=tmp_save_dir)


@pytest.fixture
def sample_player():
    """Create a sample player character."""
    return Character(
        name="Thorin",
        race="Dwarf",
        classes={"Warrior": 3},
        stats={'MIG': 16, 'AGI': 12, 'END': 14, 'MND': 10, 'INS': 8, 'PRE': 10},
        hp=28,
        max_hp=30,
        ac=16,
        initiative_bonus=1,
        spell_points=0,
        max_spell_points=0,
        xp=450,
        level=3,
        skills={"athletics": 4, "melee": 2},
        gold=150,
        inventory=["iron_sword", "health_potion", "torch"],
        equipment={"weapon": "iron_sword", "armor": "chain_mail"},
        conditions=["blessed"],
    )


@pytest.fixture
def sample_session(sample_player):
    """Create a fully populated GameSession."""
    dm_ctx = DMContext(
        scene_type=SceneType.EXPLORATION,
        location="Dark Forest",
        party=[sample_player],
        turn=42,
    )
    dm_ctx.add_event(DMEvent(
        type=EventType.ENCOUNTER,
        description="A troll blocks the path.",
        data={"enemy_name": "Troll"},
    ))

    session = GameSession(
        player=sample_player,
        dm_context=dm_ctx,
    )
    session.facing = "east"
    session.position = [15, 22]

    return session


# ---------------------------------------------------------------------------
# Test: Full roundtrip (all fields preserved)
# ---------------------------------------------------------------------------

class TestSaveLoadRoundtrip:
    """Test that save+load preserves all game state."""

    def test_player_stats_preserved(self, save_system, sample_session):
        """Player stats survive roundtrip."""
        save_system.save_game(sample_session, "test_stats")
        loaded = save_system.load_game("test_stats")

        assert loaded is not None
        p = loaded.player
        assert p.name == "Thorin"
        assert p.race == "Dwarf"
        assert p.classes == {"Warrior": 3}
        assert p.stats == {'MIG': 16, 'AGI': 12, 'END': 14, 'MND': 10, 'INS': 8, 'PRE': 10}
        assert p.hp == 28
        assert p.max_hp == 30
        assert p.ac == 16
        assert p.initiative_bonus == 1
        assert p.spell_points == 0
        assert p.max_spell_points == 0
        assert p.xp == 450
        assert p.level == 3
        assert p.skills == {"athletics": 4, "melee": 2}
        assert p.gold == 150
        assert p.inventory == ["iron_sword", "health_potion", "torch"]
        assert p.equipment == {"weapon": "iron_sword", "armor": "chain_mail"}
        assert p.conditions == ["blessed"]

    def test_dm_context_preserved(self, save_system, sample_session):
        """DM context (scene, location, turn, history) survives roundtrip."""
        save_system.save_game(sample_session, "test_dm")
        loaded = save_system.load_game("test_dm")

        assert loaded.dm_context.scene_type == SceneType.EXPLORATION
        assert loaded.dm_context.location == "Dark Forest"
        assert loaded.dm_context.turn == 42
        assert len(loaded.dm_context.history) == 1
        assert loaded.dm_context.history[0].type == EventType.ENCOUNTER
        assert loaded.dm_context.history[0].description == "A troll blocks the path."
        assert loaded.dm_context.history[0].data == {"enemy_name": "Troll"}

    def test_position_and_facing_preserved(self, save_system, sample_session):
        """Position and facing survive roundtrip."""
        save_system.save_game(sample_session, "test_pos")
        loaded = save_system.load_game("test_pos")

        assert loaded.position == [15, 22]
        assert loaded.facing == "east"

    def test_game_time_preserved(self, save_system, sample_session):
        """Game time survives roundtrip."""
        sample_session.game_time = LivingGameTime(hour=14, minute=30, day=5)
        save_system.save_game(sample_session, "test_time")
        loaded = save_system.load_game("test_time")

        assert loaded.game_time.hour == 14
        assert loaded.game_time.minute == 30
        assert loaded.game_time.day == 5

    def test_map_data_preserved(self, save_system, sample_session):
        """Map data (tiles, rooms, spawn) survives roundtrip."""
        save_system.save_game(sample_session, "test_map")
        loaded = save_system.load_game("test_map")

        assert loaded.map_data is not None
        assert loaded.map_data.width == sample_session.map_data.width
        assert loaded.map_data.height == sample_session.map_data.height
        assert loaded.map_data.spawn_point == sample_session.map_data.spawn_point

        # Verify tile equality for a sample of tiles
        for y in range(min(5, loaded.map_data.height)):
            for x in range(min(5, loaded.map_data.width)):
                assert (
                    loaded.map_data.get_tile(x, y)
                    == sample_session.map_data.get_tile(x, y)
                ), f"Tile mismatch at ({x}, {y})"

    def test_entity_positions_preserved(self, save_system, sample_session):
        """Entity positions in spatial index survive roundtrip."""
        # Add some test entities
        npc = Entity(
            id="guard_01",
            entity_type=EntityType.NPC,
            name="Town Guard",
            position=(10, 10),
            glyph="G",
            color="red",
            blocking=True,
            hp=15,
            max_hp=20,
            disposition="neutral",
            faction="town_guard",
            job="guard",
        )
        sample_session.spatial_index.add(npc)

        item_ent = Entity(
            id="potion_01",
            entity_type=EntityType.ITEM,
            name="Health Potion",
            position=(12, 15),
            glyph="!",
            color="green",
            blocking=False,
        )
        sample_session.spatial_index.add(item_ent)

        save_system.save_game(sample_session, "test_entities")
        loaded = save_system.load_game("test_entities")

        # Find the guard
        guard_found = False
        for ent in loaded.spatial_index.all_entities():
            if ent.id == "guard_01":
                guard_found = True
                assert ent.name == "Town Guard"
                assert ent.position == (10, 10)
                assert ent.glyph == "G"
                assert ent.color == "red"
                assert ent.hp == 15
                assert ent.max_hp == 20
                assert ent.faction == "town_guard"
                assert ent.job == "guard"
                break
        assert guard_found, "Guard entity not found after load"

        # Find the potion
        potion_found = False
        for ent in loaded.spatial_index.all_entities():
            if ent.id == "potion_01":
                potion_found = True
                assert ent.name == "Health Potion"
                assert ent.position == (12, 15)
                break
        assert potion_found, "Potion entity not found after load"

    def test_inventory_preserved(self, save_system, sample_session):
        """Inventory items survive roundtrip."""
        sample_session.inventory = [
            {"id": "iron_sword", "name": "Iron Sword", "type": "weapon", "damage": 6},
            {"id": "health_potion", "name": "Health Potion", "type": "consumable", "heal": 10},
        ]
        sample_session.equipment = {
            "weapon": {"id": "iron_sword", "name": "Iron Sword"},
            "armor": {"id": "chain_mail", "name": "Chain Mail"},
            "shield": None,
            "helmet": None,
            "boots": None,
            "gloves": None,
            "ring": None,
            "amulet": None,
        }

        save_system.save_game(sample_session, "test_inv")
        loaded = save_system.load_game("test_inv")

        assert len(loaded.inventory) == 2
        assert loaded.inventory[0]["id"] == "iron_sword"
        assert loaded.inventory[1]["id"] == "health_potion"
        assert loaded.equipment["weapon"]["id"] == "iron_sword"

    def test_world_entity_refs_and_offer_sources_restored(self, save_system):
        engine = GameEngine()
        session = engine.new_session("Roundtrip", "warrior", location="Harbor Town")
        merchant_id, merchant = next(
            (entity_id, entity) for entity_id, entity in session.entities.items() if entity.get("role") == "merchant"
        )
        merchant["entity_ref"].hp = 6
        merchant["entity_ref"].max_hp = 8
        session.quest_offers = [{"id": "story_offer", "title": "Story Quest"}]

        save_system.save_game(session, "test_world_refs")
        loaded = save_system.load_game("test_world_refs")

        loaded_merchant = loaded.entities[merchant_id]
        assert loaded_merchant["entity_ref"] is not None
        assert loaded_merchant["hp"] == loaded_merchant["entity_ref"].hp == 6
        assert loaded_merchant["max_hp"] == loaded_merchant["entity_ref"].max_hp == 8
        assert loaded_merchant["alive"] == loaded_merchant["entity_ref"].alive
        assert loaded.quest_offers[0]["source"] == "authored"

        combatant = engine._character_from_world_entity(merchant_id, loaded_merchant)
        assert combatant is not None
        assert combatant.hp == 6
        assert loaded.equipment["armor"]["id"] == "chain_mail"

    def test_ap_tracker_preserved(self, save_system, sample_session):
        """AP tracker state survives roundtrip."""
        sample_session.ap_tracker.spend(2)
        sample_session.ap_tracker.set_armor("chain_mail")

        save_system.save_game(sample_session, "test_ap")
        loaded = save_system.load_game("test_ap")

        assert loaded.ap_tracker.current_ap == sample_session.ap_tracker.current_ap
        assert loaded.ap_tracker.max_ap == sample_session.ap_tracker.max_ap
        assert loaded.ap_tracker.armor_type == "chain_mail"

    def test_timed_conditions_roundtrip_and_expiry(self, save_system, sample_session):
        sample_session.game_time.day = 1
        sample_session.game_time.hour = 8
        sample_session.game_time.minute = 0
        sample_session.apply_timed_condition(
            "back_strain",
            1.0,
            movement_ap_penalty=1,
            agi_check_penalty=2,
        )

        save_system.save_game(sample_session, "test_timed_conditions")
        loaded = save_system.load_game("test_timed_conditions")

        assert loaded.has_timed_condition("back_strain")
        assert "back_strain" in loaded.player.conditions

        loaded.game_time.hour = 9
        loaded.game_time.minute = 1
        loaded.clear_expired_timed_conditions()
        loaded.sync_player_state()

        assert not loaded.has_timed_condition("back_strain")
        assert "back_strain" not in loaded.player.conditions

    def test_body_tracker_preserved(self, save_system, sample_session):
        """Body part tracker survives roundtrip."""
        sample_session.body_tracker.apply_damage("left_arm", 5)
        sample_session.body_tracker.apply_damage("chest", 3)

        save_system.save_game(sample_session, "test_body")
        loaded = save_system.load_game("test_body")

        assert loaded.body_tracker.current_hp["left_arm"] == sample_session.body_tracker.current_hp["left_arm"]
        assert loaded.body_tracker.current_hp["chest"] == sample_session.body_tracker.current_hp["chest"]
        assert loaded.body_tracker.max_hp == sample_session.body_tracker.max_hp

    def test_legacy_runtime_fields_are_reconstructed(self, save_system, sample_session):
        sample_session.player.classes = {"Warrior": 3}
        state = save_system._serialize_session(sample_session)
        state.pop("ap_tracker", None)
        state.pop("viewport", None)
        state.pop("player_entity", None)
        state.pop("spatial_entities", None)

        loaded = save_system._deserialize_session(state)

        assert loaded.ap_tracker is not None
        assert loaded.ap_tracker.max_ap == 4
        assert loaded.viewport is not None
        assert loaded.player_entity is not None
        assert loaded.spatial_index is not None
        assert loaded.spatial_index.get_position("player") == tuple(loaded.position)

    def test_location_stock_preserved(self, save_system, sample_session):
        """Location stock survives roundtrip."""
        sample_session.location_stock.remove_stock("ale", 5)
        sample_session.location_stock.add_stock("iron_bar", 10)

        save_system.save_game(sample_session, "test_stock")
        loaded = save_system.load_game("test_stock")

        assert loaded.location_stock.location_id == sample_session.location_stock.location_id
        assert loaded.location_stock.get_stock("ale") == sample_session.location_stock.get_stock("ale")
        assert loaded.location_stock.get_stock("iron_bar") == sample_session.location_stock.get_stock("iron_bar")

    def test_rumor_network_preserved(self, save_system, sample_session):
        """Rumor network survives roundtrip."""
        sample_session.rumor_network.add_rumor(
            fact="The king is ill",
            source_npc="herald_01",
            location="tavern",
            confidence=0.8,
            timestamp=100.0,
        )
        sample_session.rumor_network.add_rumor(
            fact="Bandits on the road",
            source_npc="guard_02",
            location="gate",
            confidence=0.6,
            timestamp=120.0,
            faction_filter="town_guard",
        )

        save_system.save_game(sample_session, "test_rumors")
        loaded = save_system.load_game("test_rumors")

        assert len(loaded.rumor_network.rumors) == 2
        active = loaded.rumor_network.get_all_active()
        facts = {r.fact for r in active}
        assert "The king is ill" in facts
        assert "Bandits on the road" in facts

    def test_quest_tracker_preserved(self, save_system, sample_session):
        """Quest tracker survives roundtrip."""
        sample_session.quest_tracker.add_quest(
            quest_id="q1",
            title="Kill the Troll",
            current_hour=100.0,
            deadline_hour=200.0,
        )
        sample_session.quest_tracker.add_quest(
            quest_id="q2",
            title="Find the Amulet",
            current_hour=110.0,
        )

        save_system.save_game(sample_session, "test_quests")
        loaded = save_system.load_game("test_quests")

        assert len(loaded.quest_tracker.quests) == 2
        q1 = loaded.quest_tracker.get_quest("q1")
        assert q1 is not None
        assert q1.title == "Kill the Troll"
        assert q1.deadline_hour == 200.0
        assert q1.status.value == "active"

        q2 = loaded.quest_tracker.get_quest("q2")
        assert q2 is not None
        assert q2.title == "Find the Amulet"

    def test_caravan_manager_preserved(self, save_system, sample_session):
        """Caravan manager survives roundtrip."""
        # Tick the caravan manager to spawn some caravans
        sample_session.caravan_manager.tick(0)

        save_system.save_game(sample_session, "test_caravans")
        loaded = save_system.load_game("test_caravans")

        assert len(loaded.caravan_manager.active) == len(sample_session.caravan_manager.active)

    def test_history_seed_preserved(self, save_system, sample_session):
        """History seed data survives roundtrip."""
        save_system.save_game(sample_session, "test_history")
        loaded = save_system.load_game("test_history")

        assert loaded.history_seed is not None
        assert len(loaded.history_seed.events) == len(sample_session.history_seed.events)
        assert len(loaded.history_seed.figures) == len(sample_session.history_seed.figures)

    def test_viewport_fog_of_war_preserved(self, save_system, sample_session):
        """Viewport fog of war explored tiles survive roundtrip."""
        original_fog = set(sample_session.viewport.fog_of_war)

        save_system.save_game(sample_session, "test_fow")
        loaded = save_system.load_game("test_fow")

        assert loaded.viewport is not None
        assert loaded.viewport.center_x == sample_session.viewport.center_x
        assert loaded.viewport.center_y == sample_session.viewport.center_y
        # Fog of war should contain at least the original explored tiles
        # (compute_fov on load may add more visible tiles, but explored stays)
        for tile in original_fog:
            assert tile in loaded.viewport.fog_of_war, f"Explored tile {tile} lost"

    def test_world_state_preserved(self, save_system, sample_session):
        """World state ledger survives roundtrip."""
        sample_session.world_state.update_location_discovered("tavern", "The Rusty Anchor")
        sample_session.world_state.flags["dragon_slain"] = True

        save_system.save_game(sample_session, "test_ws")
        loaded = save_system.load_game("test_ws")

        assert loaded.world_state is not None
        assert "tavern" in loaded.world_state.locations
        assert loaded.world_state.locations["tavern"].discovered is True
        assert loaded.world_state.flags.get("dragon_slain") is True

    def test_session_id_preserved(self, save_system, sample_session):
        """Session ID survives roundtrip."""
        original_id = sample_session.session_id
        save_system.save_game(sample_session, "test_sid")
        loaded = save_system.load_game("test_sid")

        assert loaded.session_id == original_id


# ---------------------------------------------------------------------------
# Test: Save slot operations
# ---------------------------------------------------------------------------

class TestSaveSlotOperations:
    """Test save slot management: list, delete, overwrite."""

    def test_multiple_save_slots(self, save_system, sample_session):
        """Multiple save slots are independent."""
        save_system.save_game(sample_session, "slot_1")

        # Modify session
        sample_session.player.hp = 5
        sample_session.dm_context.location = "Goblin Cave"
        save_system.save_game(sample_session, "slot_2")

        loaded_1 = save_system.load_game("slot_1")
        loaded_2 = save_system.load_game("slot_2")

        assert loaded_1.player.hp == 28  # original
        assert loaded_2.player.hp == 5   # modified
        assert loaded_1.dm_context.location == "Dark Forest"
        assert loaded_2.dm_context.location == "Goblin Cave"

    def test_list_saves(self, save_system, sample_session):
        """list_saves returns metadata for all saves."""
        save_system.save_game(sample_session, "alpha")
        save_system.save_game(sample_session, "beta")

        saves = save_system.list_saves()
        slot_names = {s["slot_name"] for s in saves}

        assert "alpha" in slot_names
        assert "beta" in slot_names
        assert all("timestamp" in s for s in saves)
        assert all("player_name" in s for s in saves)

    def test_delete_save(self, save_system, sample_session):
        """delete_save removes the file."""
        save_system.save_game(sample_session, "to_delete")
        assert save_system.save_exists("to_delete")

        result = save_system.delete_save("to_delete")
        assert result is True
        assert not save_system.save_exists("to_delete")

    def test_delete_nonexistent_save(self, save_system):
        """Deleting a nonexistent save returns False."""
        result = save_system.delete_save("does_not_exist")
        assert result is False

    def test_load_nonexistent_save_returns_none(self, save_system):
        """Loading a nonexistent save returns None."""
        result = save_system.load_game("nonexistent")
        assert result is None

    def test_overwrite_save_slot(self, save_system, sample_session):
        """Saving to the same slot overwrites the previous save."""
        save_system.save_game(sample_session, "overwrite_test")
        sample_session.player.hp = 1
        save_system.save_game(sample_session, "overwrite_test")

        loaded = save_system.load_game("overwrite_test")
        assert loaded.player.hp == 1

    def test_autosave(self, save_system, sample_session):
        """autosave creates a save in the 'autosave' slot."""
        save_system.autosave(sample_session)
        loaded = save_system.load_game("autosave")
        assert loaded is not None
        assert loaded.player.name == "Thorin"

    def test_save_file_is_valid_json(self, save_system, sample_session, tmp_save_dir):
        """Save file is valid JSON with expected top-level keys."""
        save_system.save_game(sample_session, "json_check")
        filepath = tmp_save_dir / "json_check.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))

        assert "schema_version" in data
        assert "slot_name" in data
        assert "timestamp" in data
        assert "player_name" in data
        assert "session_state" in data
        assert data["slot_name"] == "json_check"
        assert data["player_name"] == "Thorin"


# ---------------------------------------------------------------------------
# Test: Individual from_dict methods
# ---------------------------------------------------------------------------

class TestFromDictMethods:
    """Test that individual from_dict methods work correctly."""

    def test_map_data_from_dict(self):
        """MapData roundtrip through to_dict/from_dict."""
        tiles = [
            [TileType.WALL, TileType.FLOOR, TileType.WALL],
            [TileType.FLOOR, TileType.FLOOR, TileType.DOOR],
            [TileType.WALL, TileType.CORRIDOR, TileType.WALL],
        ]
        rooms = [Room(0, 0, 3, 3, room_type="normal")]
        md = MapData(
            width=3, height=3, tiles=tiles, rooms=rooms,
            spawn_point=(1, 1), exit_points=[(2, 1)],
            metadata={"seed": 42},
        )

        d = md.to_dict()
        restored = MapData.from_dict(d)

        assert restored.width == 3
        assert restored.height == 3
        assert restored.spawn_point == (1, 1)
        assert restored.get_tile(1, 0) == TileType.FLOOR
        assert restored.get_tile(2, 1) == TileType.DOOR
        assert len(restored.rooms) == 1
        assert restored.rooms[0].room_type == "normal"

    def test_viewport_from_dict(self):
        """Viewport roundtrip."""
        vp = Viewport(width=30, height=15)
        vp.center_on(10, 20)
        vp.fog_of_war = {(1, 2), (3, 4), (10, 20)}

        d = vp.to_dict()
        restored = Viewport.from_dict(d)

        assert restored.width == 30
        assert restored.height == 15
        assert restored.center_x == 10
        assert restored.center_y == 20
        assert (1, 2) in restored.fog_of_war
        assert (3, 4) in restored.fog_of_war
        assert (10, 20) in restored.fog_of_war

    def test_ap_tracker_from_dict(self):
        """ActionPointTracker roundtrip."""
        apt = ActionPointTracker(max_ap=6, armor_type="chain_mail")
        apt.spend(3)

        d = apt.to_dict()
        restored = ActionPointTracker.from_dict(d)

        assert restored.max_ap == 6
        assert restored.current_ap == 3
        assert restored.armor_type == "chain_mail"

    def test_body_tracker_from_dict(self):
        """BodyPartTracker roundtrip."""
        bt = BodyPartTracker()
        bt.apply_damage("head", 3)
        bt.apply_damage("left_arm", 5)

        d = bt.to_dict()
        restored = BodyPartTracker.from_dict(d)

        assert restored.current_hp["head"] == bt.current_hp["head"]
        assert restored.current_hp["left_arm"] == bt.current_hp["left_arm"]

    def test_location_stock_from_dict(self):
        """LocationStock roundtrip."""
        ls = LocationStock(
            location_id="tavern",
            baseline={"ale": 10, "bread": 5},
        )
        ls.remove_stock("ale", 3)

        d = ls.to_dict()
        restored = LocationStock.from_dict(d)

        assert restored.location_id == "tavern"
        assert restored.get_stock("ale") == 7
        assert restored.get_stock("bread") == 5

    def test_rumor_network_from_dict(self):
        """RumorNetwork roundtrip."""
        rn = RumorNetwork()
        rn.add_rumor("The dragon sleeps", "bard_01", "tavern", confidence=0.9, timestamp=50.0)
        rn.add_rumor("War is coming", "soldier_01", "barracks", confidence=0.5, timestamp=60.0)

        d = rn.to_dict()
        restored = RumorNetwork.from_dict(d)

        assert len(restored.rumors) == 2
        assert restored._next_id == rn._next_id

    def test_quest_tracker_from_dict(self):
        """QuestTracker roundtrip."""
        qt = QuestTracker()
        qt.add_quest("q1", "Slay the Dragon", 100.0, deadline_hour=200.0)
        qt.add_quest("q2", "Gather Herbs", 110.0)

        d = qt.to_dict()
        restored = QuestTracker.from_dict(d)

        assert len(restored.quests) == 2
        assert restored.quests["q1"].title == "Slay the Dragon"
        assert restored.quests["q1"].deadline_hour == 200.0
        assert restored.quests["q2"].title == "Gather Herbs"

    def test_caravan_manager_from_dict(self):
        """CaravanManager roundtrip."""
        cm = CaravanManager()
        cm.tick(0)  # spawn caravans

        d = cm.to_dict()
        restored = CaravanManager.from_dict(d)

        assert len(restored.active) == len(cm.active)
        assert restored._next_id == cm._next_id

    def test_history_seed_from_dict(self):
        """HistorySeed roundtrip."""
        hs = HistorySeed().generate(seed=42)

        d = hs.to_dict()
        restored = HistorySeed.from_dict(d)

        assert len(restored.events) == len(hs.events)
        assert len(restored.figures) == len(hs.figures)
        assert restored.current_year == hs.current_year

    def test_dm_context_from_dict(self):
        """DMContext roundtrip."""
        player = Character(name="Test", classes={"Warrior": 1})
        ctx = DMContext(
            scene_type=SceneType.COMBAT,
            location="Arena",
            party=[player],
            turn=10,
        )
        ctx.add_event(DMEvent(
            type=EventType.COMBAT_START,
            description="Combat begins!",
            data={"enemy_name": "Goblin"},
        ))

        d = ctx.to_dict()
        restored = DMContext.from_dict(d, party=[player])

        assert restored.scene_type == SceneType.COMBAT
        assert restored.location == "Arena"
        assert restored.turn == 10
        assert len(restored.history) == 1
        assert restored.history[0].type == EventType.COMBAT_START

    def test_game_time_from_dict(self):
        """LivingGameTime roundtrip."""
        gt = LivingGameTime(hour=14, minute=30, day=5)

        d = gt.to_dict()
        restored = LivingGameTime.from_dict(d)

        assert restored.hour == 14
        assert restored.minute == 30
        assert restored.day == 5


# ---------------------------------------------------------------------------
# Test: Action parser save/load intents
# ---------------------------------------------------------------------------

class TestSaveLoadIntents:
    """Test that action parser recognizes save/load commands."""

    def setup_method(self):
        self.parser = ActionParser()

    def test_save_intent(self):
        assert self.parser.parse("save").intent == ActionIntent.SAVE_GAME
        assert self.parser.parse("save game").intent == ActionIntent.SAVE_GAME

    def test_save_as_intent(self):
        action = self.parser.parse("save as my_save")
        assert action.intent == ActionIntent.SAVE_GAME
        assert action.target == "my_save"

    def test_load_intent(self):
        assert self.parser.parse("load").intent == ActionIntent.LOAD_GAME
        assert self.parser.parse("load game").intent == ActionIntent.LOAD_GAME

    def test_load_slot_intent(self):
        action = self.parser.parse("load my_save")
        assert action.intent == ActionIntent.LOAD_GAME
        assert action.target == "my_save"

    def test_list_saves_intent(self):
        assert self.parser.parse("saves").intent == ActionIntent.LIST_SAVES
        assert self.parser.parse("list saves").intent == ActionIntent.LIST_SAVES

    def test_delete_save_intent(self):
        action = self.parser.parse("delete save my_save")
        assert action.intent == ActionIntent.DELETE_SAVE
        assert action.target == "my_save"


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_session_save_load(self, save_system):
        """Minimal session with default values."""
        player = Character(name="Minimal")
        dm = DMContext(
            scene_type=SceneType.EXPLORATION,
            location="Start",
            party=[player],
        )
        session = GameSession(player=player, dm_context=dm)

        save_system.save_game(session, "minimal")
        loaded = save_system.load_game("minimal")

        assert loaded is not None
        assert loaded.player.name == "Minimal"
        assert loaded.dm_context.location == "Start"

    def test_special_characters_in_location(self, save_system):
        """Location names with special characters."""
        player = Character(name="Hero")
        dm = DMContext(
            scene_type=SceneType.EXPLORATION,
            location="The Dragon's Lair (Level 3)",
            party=[player],
        )
        session = GameSession(player=player, dm_context=dm)

        save_system.save_game(session, "special_chars")
        loaded = save_system.load_game("special_chars")

        assert loaded.dm_context.location == "The Dragon's Lair (Level 3)"

    def test_large_fog_of_war(self, save_system):
        """Large fog of war set serializes correctly."""
        player = Character(name="Explorer")
        dm = DMContext(scene_type=SceneType.EXPLORATION, location="Maze", party=[player])
        session = GameSession(player=player, dm_context=dm)

        # Add many explored tiles
        for x in range(50):
            for y in range(50):
                session.viewport.fog_of_war.add((x, y))

        save_system.save_game(session, "large_fow")
        loaded = save_system.load_game("large_fow")

        # All 2500 originally added tiles should be present
        for x in range(50):
            for y in range(50):
                assert (x, y) in loaded.viewport.fog_of_war

    def test_npc_memory_preserved(self, save_system, sample_session):
        """NPC memory survives roundtrip."""
        sample_session.npc_memory.record_interaction(
            npc_id="innkeeper_01",
            summary="Asked about rooms",
            sentiment="positive",
            game_time="Day 1, 10:00",
            facts=["Player is a warrior", "Player came from the north"],
        )

        save_system.save_game(sample_session, "test_npc_mem")
        loaded = save_system.load_game("test_npc_mem")

        mem = loaded.npc_memory.get_memory("innkeeper_01")
        assert mem.name == "innkeeper_01"
        assert len(mem.conversations) == 1
        assert "Player is a warrior" in mem.known_facts
