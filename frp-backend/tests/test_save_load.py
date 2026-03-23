"""
TDD: Save/Load System Tests — Ember RPG Backend
Written BEFORE implementation (failing tests first).
All tests map to Acceptance Criteria in PRD_save_load.md.
"""
import json
import os
import pytest
import tempfile
import threading
from pathlib import Path

from engine.save import SaveManager, SaveNotFoundError, CorruptSaveError
from engine.save.save_models import SaveFile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_saves_dir(tmp_path):
    """Provide a temporary saves directory."""
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    return saves_dir


@pytest.fixture
def manager(tmp_saves_dir):
    """SaveManager pointed at a temp directory."""
    return SaveManager(saves_dir=str(tmp_saves_dir))


SAMPLE_SESSION_DATA = {
    "session_id": "sess-abc",
    "scene": "exploration",
    "location": "Dark Forest",
    "player": {
        "name": "Thorin",
        "level": 3,
        "hp": 28,
        "max_hp": 30,
        "xp": 450,
    },
}


# ---------------------------------------------------------------------------
# AC-01: Save creates a file on disk
# ---------------------------------------------------------------------------

def test_save_session_creates_file(manager, tmp_saves_dir):
    """AC-01: Calling save() creates a JSON file in the saves directory."""
    save_id = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)

    files = list(tmp_saves_dir.glob("*.json"))
    assert len(files) == 1, "Expected exactly one save file to be created"
    assert save_id in files[0].name, "Save file name should contain the save_id"


# ---------------------------------------------------------------------------
# AC-02: Save returns a non-empty save_id
# ---------------------------------------------------------------------------

def test_save_session_returns_save_id(manager):
    """AC-02: save() returns a non-empty string save_id."""
    save_id = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)

    assert isinstance(save_id, str)
    assert len(save_id) > 0


# ---------------------------------------------------------------------------
# AC-03: Load restores saved state
# ---------------------------------------------------------------------------

def test_load_session_restores_state(manager):
    """AC-03: load() returns session_data identical to what was saved."""
    save_id = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)
    save_file = manager.load(save_id)

    assert save_file.session_data == SAMPLE_SESSION_DATA
    assert save_file.player_id == "player_001"
    assert save_file.save_id == save_id


# ---------------------------------------------------------------------------
# AC-04: List saves for a player
# ---------------------------------------------------------------------------

def test_list_saves_for_player(manager):
    """AC-04: list_saves() returns only saves belonging to the given player_id."""
    # Save twice for player_001, once for player_002
    id1 = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)
    id2 = manager.save(player_id="player_001", session_data={"scene": "combat"})
    manager.save(player_id="player_002", session_data={"scene": "town"})

    saves = manager.list_saves(player_id="player_001")
    save_ids = [s.save_id for s in saves]

    assert len(saves) == 2
    assert id1 in save_ids
    assert id2 in save_ids


# ---------------------------------------------------------------------------
# AC-05: Delete a save removes the file
# ---------------------------------------------------------------------------

def test_delete_save(manager, tmp_saves_dir):
    """AC-05: delete() removes the save file from disk."""
    save_id = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)

    # Confirm file exists
    files_before = list(tmp_saves_dir.glob("*.json"))
    assert len(files_before) == 1

    manager.delete(save_id)

    files_after = list(tmp_saves_dir.glob("*.json"))
    assert len(files_after) == 0, "Save file should be deleted"


# ---------------------------------------------------------------------------
# AC-06: Load non-existent save raises SaveNotFoundError
# ---------------------------------------------------------------------------

def test_save_not_found_raises_error(manager):
    """AC-06: Loading a non-existent save_id raises SaveNotFoundError."""
    with pytest.raises(SaveNotFoundError):
        manager.load("nonexistent-save-id-12345")


# ---------------------------------------------------------------------------
# AC-07: Load corrupt save raises CorruptSaveError
# ---------------------------------------------------------------------------

def test_load_corrupt_save_raises_error(manager, tmp_saves_dir):
    """AC-07: Loading a file with invalid JSON raises CorruptSaveError."""
    # Manually create a corrupt save file using a known naming pattern
    save_id = "corrupt-save-001"
    corrupt_file = tmp_saves_dir / f"player_001_{save_id}.json"
    corrupt_file.write_text("{ this is not valid json !!!")

    with pytest.raises(CorruptSaveError):
        manager.load(save_id)


# ---------------------------------------------------------------------------
# AC-08: Save files contain schema_version == "1.0"
# ---------------------------------------------------------------------------

def test_save_versioning_field(manager, tmp_saves_dir):
    """AC-08: Every save file contains schema_version == '1.0'."""
    save_id = manager.save(player_id="player_001", session_data=SAMPLE_SESSION_DATA)

    # Read raw JSON from disk to verify the field is persisted
    files = list(tmp_saves_dir.glob("*.json"))
    assert len(files) == 1
    raw = json.loads(files[0].read_text())

    assert "schema_version" in raw
    assert raw["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# Bonus: Thread-safety — concurrent saves don't corrupt files
# ---------------------------------------------------------------------------

def test_concurrent_saves_are_thread_safe(manager, tmp_saves_dir):
    """Multiple threads saving simultaneously should each produce valid files."""
    errors = []

    def do_save(player_id, i):
        try:
            manager.save(player_id=player_id, session_data={"index": i})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=do_save, args=("player_thread", i)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    files = list(tmp_saves_dir.glob("*.json"))
    assert len(files) == 10


# ---------------------------------------------------------------------------
# Bonus: SaveFile model has all required fields
# ---------------------------------------------------------------------------

def test_save_file_model_fields(manager):
    """SaveFile returned by load() has all required PRD fields."""
    save_id = manager.save(player_id="player_fields", session_data={"x": 1})
    sf = manager.load(save_id)

    assert hasattr(sf, "save_id")
    assert hasattr(sf, "player_id")
    assert hasattr(sf, "session_data")
    assert hasattr(sf, "timestamp")
    assert hasattr(sf, "schema_version")
    assert sf.schema_version == "1.0"


# ---------------------------------------------------------------------------
# Bonus: Delete non-existent save raises SaveNotFoundError
# ---------------------------------------------------------------------------

def test_delete_nonexistent_save_raises_error(manager):
    """Deleting a non-existent save should raise SaveNotFoundError."""
    with pytest.raises(SaveNotFoundError):
        manager.delete("no-such-save-xyz")
