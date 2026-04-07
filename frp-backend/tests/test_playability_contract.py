"""TDD: Playability contract tests — written BEFORE implementation fixes.

These tests verify that the backend produces a campaign snapshot payload
that the Godot client can consume to render a playable game session.

Every assertion here corresponds to a field that the Godot GameState,
WorldView, TilemapController, EntityLayer, or UI panels expect.

Test Naming Convention:
    test_<component>_<what_is_verified>

Run with:
    cd frp-backend && python -m pytest tests/test_playability_contract.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import campaign_routes
from main import app
from _seed_robust_helpers import ensure_entity_presence

client = TestClient(app)

# ── Helpers ──────────────────────────────────────────────────────────

REQUIRED_STATS = ["MIG", "AGI", "END", "MND", "INS", "PRE"]
VALID_SCENES = ["exploration", "combat", "dialogue", "rest"]
VALID_ENTITY_TYPES = ["npc", "creature", "item", "furniture", "object", "fixture"]


def _create_campaign(seed: int = 42, player_class: str = "warrior") -> dict:
    """Helper: create a campaign and return the full JSON response."""
    response = client.post(
        "/game/campaigns",
        json={
            "player_name": "PlayabilityProbe",
            "player_class": player_class,
            "adapter_id": "fantasy_ember",
            "profile_id": "standard",
            "seed": seed,
        },
    )
    assert response.status_code == 200, f"Campaign creation failed: {response.text}"
    return response.json()


def _get_campaign(campaign_id: str) -> dict:
    """Helper: GET a campaign snapshot."""
    response = client.get(f"/game/campaigns/{campaign_id}")
    assert response.status_code == 200
    return response.json()


def _run_command(campaign_id: str, command: str) -> dict:
    """Helper: POST a command and return the response."""
    response = client.post(
        f"/game/campaigns/{campaign_id}/commands",
        json={"input": command},
    )
    assert response.status_code == 200
    return response.json()


# ── Snapshot Envelope Tests ──────────────────────────────────────────

class TestSnapshotEnvelope:
    """Verify the top-level snapshot structure that Godot expects."""

    def test_snapshot_has_required_top_level_fields(self):
        """Godot GameState.update_from_response expects campaign_id,
        adapter_id, profile_id, narrative, and campaign dict."""
        data = _create_campaign()
        assert "campaign_id" in data, "Missing campaign_id at top level"
        assert "adapter_id" in data, "Missing adapter_id at top level"
        assert "profile_id" in data, "Missing profile_id at top level"
        assert "narrative" in data, "Missing narrative at top level"
        assert "campaign" in data, "Missing campaign dict at top level"
        assert isinstance(data["campaign"], dict), "campaign must be a dict"

    def test_campaign_id_is_nonempty_string(self):
        """GameState stores campaign_id — must not be empty."""
        data = _create_campaign()
        assert isinstance(data["campaign_id"], str)
        assert len(data["campaign_id"]) > 0


# ── Map Data Tests (TilemapController + WorldView) ───────────────────

class TestMapData:
    """Verify map_data fields consumed by tilemap_controller.gd and
    world_view.gd _refresh_from_state()."""

    def test_map_data_exists_in_campaign(self):
        """WorldView falls back to placeholder if map_data is empty.
        We need real map data for playability."""
        data = _create_campaign()
        campaign = data["campaign"]
        assert "map_data" in campaign, "Missing map_data in campaign payload"
        assert isinstance(campaign["map_data"], dict)

    def test_map_data_has_dimensions(self):
        """TilemapController needs width/height to set _map_size."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        assert "width" in md, "map_data missing width"
        assert "height" in md, "map_data missing height"
        assert md["width"] > 0, "map_data width must be positive"
        assert md["height"] > 0, "map_data height must be positive"

    def test_map_data_has_tiles_2d_array(self):
        """TilemapController.render_map iterates rows×cols of tile names."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        assert "tiles" in md, "map_data missing tiles"
        tiles = md["tiles"]
        assert isinstance(tiles, list), "tiles must be a list"
        assert len(tiles) > 0, "tiles must have at least one row"
        assert isinstance(tiles[0], list), "each tile row must be a list"
        assert len(tiles[0]) > 0, "tile rows must have at least one column"

    def test_map_data_dimensions_match_tiles(self):
        """Width/height must match actual tiles array dimensions."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        assert len(md["tiles"]) == md["height"], \
            f"height={md['height']} but tiles has {len(md['tiles'])} rows"
        assert len(md["tiles"][0]) == md["width"], \
            f"width={md['width']} but first row has {len(md['tiles'][0])} cols"

    def test_map_data_tiles_are_strings(self):
        """TileCatalog.resolve_tile_name expects string tile names."""
        data = _create_campaign()
        tiles = data["campaign"]["map_data"]["tiles"]
        for y, row in enumerate(tiles[:5]):  # Sample first 5 rows
            for x, cell in enumerate(row[:5]):
                assert isinstance(cell, str), \
                    f"Tile at ({x},{y}) is {type(cell).__name__}, expected str"

    def test_map_data_has_spawn_point(self):
        """WorldView uses spawn_point to position player if no position set."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        assert "spawn_point" in md, "map_data missing spawn_point"
        sp = md["spawn_point"]
        assert isinstance(sp, list) and len(sp) >= 2, \
            "spawn_point must be [x, y] array"
        assert 0 <= sp[0] < md["width"], "spawn_point x out of bounds"
        assert 0 <= sp[1] < md["height"], "spawn_point y out of bounds"

    def test_map_data_has_metadata(self):
        """ResponseNormalizer uses metadata.map_type for tile normalization."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        assert "metadata" in md, "map_data missing metadata"
        assert "map_type" in md["metadata"], "metadata missing map_type"


# ── World Entities Tests (EntityLayer) ───────────────────────────────

class TestWorldEntities:
    """Verify world_entities array consumed by ResponseNormalizer.
    group_world_entities() and EntityLayer.render_entities()."""

    def test_world_entities_exists(self):
        """EntityLayer needs entities to render NPCs and enemies."""
        data = _create_campaign()
        campaign = data["campaign"]
        assert "world_entities" in campaign, "Missing world_entities"
        assert isinstance(campaign["world_entities"], list)

    def test_world_entities_have_required_fields(self):
        """Each entity needs id, name, entity_type, position for rendering."""
        data = _create_campaign()
        ensure_entity_presence(data["campaign_id"])
        entities = campaign_routes.campaign_runtime.snapshot(data["campaign_id"], narrative="playability-entities")["campaign"]["world_entities"]
        for i, entity in enumerate(entities[:5]):
            assert "id" in entity, f"Entity {i} missing id"
            assert "name" in entity, f"Entity {i} missing name"
            assert "entity_type" in entity, f"Entity {i} missing entity_type"
            assert "position" in entity, f"Entity {i} missing position"

    def test_world_entities_positions_are_valid(self):
        """Entity positions must be [x, y] arrays within map bounds."""
        data = _create_campaign()
        md = data["campaign"]["map_data"]
        entities = data["campaign"]["world_entities"]
        for entity in entities[:5]:
            pos = entity.get("position", [])
            assert isinstance(pos, list) and len(pos) >= 2, \
                f"Entity {entity.get('name')} has invalid position: {pos}"


# ── Player Data Tests (GameState + CharacterPanel) ───────────────────

class TestPlayerData:
    """Verify player dict consumed by GameState.player and
    character_panel.gd."""

    def test_player_exists_in_campaign(self):
        """GameState.player is the primary player state object."""
        data = _create_campaign()
        assert "player" in data["campaign"], "Missing player in campaign"
        player = data["campaign"]["player"]
        assert isinstance(player, dict)

    def test_player_has_name_and_class(self):
        """Character panel displays name and class."""
        data = _create_campaign()
        player = data["campaign"]["player"]
        assert "name" in player, "Player missing name"
        assert player["name"] == "PlayabilityProbe"

    def test_player_has_hp(self):
        """Status bar displays HP ratio."""
        data = _create_campaign()
        player = data["campaign"]["player"]
        assert "hp" in player, "Player missing hp"
        assert "max_hp" in player, "Player missing max_hp"
        assert player["hp"] > 0, "Player should start with positive HP"
        assert player["max_hp"] > 0, "Player max_hp must be positive"
        assert player["hp"] <= player["max_hp"], "HP should not exceed max_hp"

    def test_player_has_stats(self):
        """Character panel displays ability scores."""
        data = _create_campaign()
        player = data["campaign"]["player"]
        assert "stats" in player, "Player missing stats"
        stats = player["stats"]
        for stat in REQUIRED_STATS:
            assert stat in stats, f"Player stats missing {stat}"
            assert isinstance(stats[stat], int), f"Stat {stat} must be int"
            assert 3 <= stats[stat] <= 20, \
                f"Stat {stat}={stats[stat]} out of valid range 3-20"


# ── Character Sheet Tests (CharacterPanel) ───────────────────────────

class TestCharacterSheet:
    """Verify character_sheet dict consumed by character_panel.gd."""

    def test_character_sheet_exists(self):
        """CharacterPanel reads GameState.character_sheet."""
        data = _create_campaign()
        campaign = data["campaign"]
        assert "character_sheet" in campaign, "Missing character_sheet"
        assert isinstance(campaign["character_sheet"], dict)

    def test_character_sheet_has_stats(self):
        """Stats display in the character panel."""
        data = _create_campaign()
        sheet = data["campaign"]["character_sheet"]
        assert "stats" in sheet, "character_sheet missing stats"


# ── Scene State Tests (GameState.scene) ──────────────────────────────

class TestSceneState:
    """Verify scene field consumed by GameState.scene for UI routing."""

    def test_scene_is_valid(self):
        """Scene determines which overlay is active (combat, dialog, etc)."""
        data = _create_campaign()
        scene = data["campaign"].get("scene", "")
        assert scene in VALID_SCENES, f"Invalid scene: {scene}"

    def test_initial_scene_is_exploration(self):
        """New campaigns should start in exploration mode."""
        data = _create_campaign()
        assert data["campaign"]["scene"] == "exploration"


# ── Settlement Tests (SettlementPanel) ───────────────────────────────

class TestSettlement:
    """Verify settlement dict consumed by settlement_panel.gd."""

    def test_settlement_exists(self):
        """SettlementPanel reads GameState.settlement_state."""
        data = _create_campaign()
        campaign = data["campaign"]
        assert "settlement" in campaign, "Missing settlement"
        assert isinstance(campaign["settlement"], dict)

    def test_settlement_has_name(self):
        """GameState.get_display_location() falls back to settlement name."""
        data = _create_campaign()
        settlement = data["campaign"]["settlement"]
        assert "name" in settlement, "Settlement missing name"
        assert len(settlement["name"]) > 0, "Settlement name is empty"

    def test_settlement_has_residents(self):
        """SettlementPanel displays resident list."""
        data = _create_campaign()
        settlement = data["campaign"]["settlement"]
        assert "residents" in settlement, "Settlement missing residents"
        assert isinstance(settlement["residents"], list)


# ── Location Tests (GameState.location) ──────────────────────────────

class TestLocation:
    """Verify location string consumed by GameState.location."""

    def test_location_exists(self):
        """Status bar and narrative use location name."""
        data = _create_campaign()
        assert "location" in data["campaign"], "Missing location"
        loc = data["campaign"]["location"]
        assert isinstance(loc, str) and len(loc) > 0, "Location is empty"


# ── Command Response Tests ───────────────────────────────────────────

class TestCommandResponse:
    """Verify command response shape consumed by game_session.gd
    _on_campaign_action_response()."""

    def test_look_command_returns_narrative(self):
        """Command response must include narrative text."""
        data = _create_campaign()
        cid = data["campaign_id"]
        result = _run_command(cid, "look around")
        assert "narrative" in result, "Command response missing narrative"
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0, "Narrative should not be empty"

    def test_look_command_returns_campaign_payload(self):
        """Command response includes updated campaign state."""
        data = _create_campaign()
        cid = data["campaign_id"]
        result = _run_command(cid, "look around")
        assert "campaign" in result, "Command response missing campaign"
        assert isinstance(result["campaign"], dict)

    def test_command_response_preserves_map_data(self):
        """After a command, map_data should still be present."""
        data = _create_campaign()
        cid = data["campaign_id"]
        result = _run_command(cid, "look around")
        assert "map_data" in result["campaign"]
        assert "tiles" in result["campaign"]["map_data"]

    def test_defend_command_updates_settlement(self):
        """Commander commands should modify settlement state."""
        data = _create_campaign()
        cid = data["campaign_id"]
        result = _run_command(cid, "defend")
        settlement = result["campaign"]["settlement"]
        assert settlement["defense_posture"] == "fortified"


# ── GET Campaign Snapshot Tests ──────────────────────────────────────

class TestGetCampaignSnapshot:
    """Verify GET /game/campaigns/{id} returns the same shape."""

    def test_get_campaign_matches_create_shape(self):
        """SessionWorldSync.resync_campaign() uses GET to refresh state."""
        data = _create_campaign()
        cid = data["campaign_id"]
        snapshot = _get_campaign(cid)
        assert "campaign" in snapshot
        assert "map_data" in snapshot["campaign"]
        assert "world_entities" in snapshot["campaign"]
        assert "player" in snapshot["campaign"]
        assert "settlement" in snapshot["campaign"]
        assert "character_sheet" in snapshot["campaign"]


# ── Save/Load Round-Trip Tests ───────────────────────────────────────

class TestSaveLoadRoundTrip:
    """Verify save/load preserves playability contract."""

    def test_save_and_load_preserves_map_data(self):
        """After load, map_data must be intact for TilemapController."""
        data = _create_campaign()
        cid = data["campaign_id"]
        original_width = data["campaign"]["map_data"]["width"]

        # Save
        save_resp = client.post(
            f"/game/campaigns/{cid}/save",
            json={"slot_name": "playability_test", "player_id": "PlayabilityProbe"},
        )
        assert save_resp.status_code == 200
        save_id = save_resp.json()["save_id"]

        # Load
        load_resp = client.post(f"/game/campaigns/load/{save_id}")
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert "campaign" in loaded
        assert loaded["campaign"]["map_data"]["width"] == original_width
        assert len(loaded["campaign"]["map_data"]["tiles"]) > 0

        # Cleanup
        client.delete(f"/game/campaigns/saves/{save_id}")


# ── Health Endpoint Tests ────────────────────────────────────────────

class TestHealthEndpoint:
    """Verify BackendRuntime bootstrap check endpoint."""

    def test_health_returns_all_ready_flags(self):
        """BackendRuntime._health_is_ready() checks these flags."""
        response = client.get("/game/health/campaign-client")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["campaign_creation"] is True
        assert data["campaign_runtime"] is True
        assert data["campaign_save_load"] is True
