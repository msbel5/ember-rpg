"""
Ember RPG — SaveManager
Handles save/load/list/delete operations on JSON save files.
Thread-safe via per-save-id locks.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from engine.save.save_models import SaveFile, CURRENT_SCHEMA_VERSION


class SaveNotFoundError(Exception):
    """Raised when a save_id does not correspond to any file on disk."""


class CorruptSaveError(Exception):
    """Raised when a save file cannot be parsed as valid JSON."""


class SaveManager:
    """
    Manages game session saves as JSON files in a saves/ directory.

    Usage:
        mgr = SaveManager()
        save_id = mgr.save(player_id="p1", session_data={...})
        sf = mgr.load(save_id)
        saves = mgr.list_saves("p1")
        mgr.delete(save_id)
    """

    _SAFE_PATTERN = re.compile(r'^[A-Za-z0-9_\-]+$')

    def __init__(self, saves_dir: str = "saves"):
        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lock(self, save_id: str) -> threading.Lock:
        with self._registry_lock:
            if save_id not in self._locks:
                self._locks[save_id] = threading.Lock()
            return self._locks[save_id]

    def _sanitize(self, value: str, field: str) -> str:
        """Raise ValueError if value contains path-traversal characters."""
        if not self._SAFE_PATTERN.match(value):
            raise ValueError(f"Invalid characters in {field}: {value!r}")
        return value

    def _find_file(self, save_id: str) -> Path:
        """Locate the file for a given save_id (searches all player prefixes)."""
        # Try exact glob first
        matches = list(self.saves_dir.glob(f"*_{save_id}.json"))
        if matches:
            return matches[0]
        # Also accept files where the entire name is save_id.json (corrupt test helper)
        direct = self.saves_dir / f"{save_id}.json"
        if direct.exists():
            return direct
        raise SaveNotFoundError(f"Save not found: {save_id}")

    def _filepath(self, player_id: str, save_id: str) -> Path:
        return self.saves_dir / f"{player_id}_{save_id}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, player_id: str, session_data: Dict[str, Any]) -> str:
        """
        Persist session_data to disk.
        Returns the new save_id (UUID string).
        """
        self._sanitize(player_id, "player_id")
        save_id = str(uuid.uuid4())
        sf = SaveFile(
            save_id=save_id,
            player_id=player_id,
            session_data=session_data,
            timestamp=datetime.now().isoformat(),
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        lock = self._get_lock(save_id)
        with lock:
            target = self._filepath(player_id, save_id)
            # Atomic write: write to temp file then rename
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(sf.to_dict(), indent=2), encoding="utf-8")
            tmp.rename(target)

        return save_id

    def load(self, save_id: str) -> SaveFile:
        """
        Load and return a SaveFile by save_id.
        Raises SaveNotFoundError if not found.
        Raises CorruptSaveError if JSON is invalid.
        """
        try:
            filepath = self._find_file(save_id)
        except SaveNotFoundError:
            raise

        lock = self._get_lock(save_id)
        with lock:
            text = filepath.read_text(encoding="utf-8")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise CorruptSaveError(f"Save file is corrupt: {filepath.name} — {e}") from e

        return SaveFile.from_dict(data)

    def list_saves(self, player_id: str) -> List[SaveFile]:
        """Return all SaveFile objects belonging to player_id."""
        self._sanitize(player_id, "player_id")
        result = []
        for f in self.saves_dir.glob(f"{player_id}_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append(SaveFile.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                pass  # Skip corrupt files silently during listing
        return result

    def delete(self, save_id: str) -> None:
        """
        Delete a save file by save_id.
        Raises SaveNotFoundError if not found.
        """
        filepath = self._find_file(save_id)  # raises if missing
        lock = self._get_lock(save_id)
        with lock:
            if filepath.exists():
                filepath.unlink()
            with self._registry_lock:
                self._locks.pop(save_id, None)
