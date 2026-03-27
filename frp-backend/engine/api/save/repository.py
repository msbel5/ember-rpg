"""Save-slot repository operations."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.save.save_models import CURRENT_SCHEMA_VERSION


class SaveRepositoryMixin:
    """Slot-level save/load operations."""

    def __init__(self, save_dir: Path):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save_game(
        self,
        session,
        slot_name: str = "autosave",
        *,
        player_name: Optional[str] = None,
    ) -> str:
        if hasattr(session, "last_save_slot"):
            session.last_save_slot = slot_name
        state = self._serialize_session(session)
        save_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "slot_name": slot_name,
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name or (session.player.name if session.player else "Unknown"),
            "player_level": session.player.level if session.player else 1,
            "location": session.dm_context.location if session.dm_context else "Unknown",
            "game_time_display": (session.game_time.to_string() if session.game_time else "Day 1, 08:00"),
            "session_state": state,
        }
        filepath = self.save_dir / f"{slot_name}.json"
        tmp = filepath.with_suffix(".tmp")
        tmp.write_text(json.dumps(save_data, indent=2, default=str), encoding="utf-8")
        if filepath.exists():
            filepath.unlink()
        tmp.rename(filepath)
        return str(filepath)

    @staticmethod
    def _campaign_v2_state(save_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session_state = save_data.get("session_state", {})
        if not isinstance(session_state, dict):
            return None
        campaign_state = session_state.get("campaign_state", {})
        if not isinstance(campaign_state, dict):
            return None
        campaign_v2 = campaign_state.get("campaign_v2")
        if isinstance(campaign_v2, dict):
            return campaign_v2
        return None

    def read_save(self, slot_name: str) -> Optional[Dict[str, Any]]:
        filepath = self.save_dir / f"{slot_name}.json"
        if not filepath.exists():
            return None
        return json.loads(filepath.read_text(encoding="utf-8"))

    def get_save_metadata(self, slot_name: str) -> Optional[Dict[str, Any]]:
        try:
            save_data = self.read_save(slot_name)
        except json.JSONDecodeError:
            return None
        if save_data is None:
            return None
        campaign_v2 = self._campaign_v2_state(save_data)
        return {
            "slot_name": save_data.get("slot_name", slot_name),
            "player_name": save_data.get("player_name", "Unknown"),
            "player_level": save_data.get("player_level", 1),
            "location": save_data.get("location", "Unknown"),
            "timestamp": save_data.get("timestamp", ""),
            "game_time": save_data.get("game_time_display", ""),
            "schema_version": save_data.get("schema_version", ""),
            "session_id": save_data.get("session_state", {}).get("session_id"),
            "campaign_compatible": campaign_v2 is not None,
            "campaign_id": str(campaign_v2.get("campaign_id", "")) if campaign_v2 else "",
        }

    def find_slot_by_session_id(self, session_id: str) -> Optional[str]:
        for save in self.list_saves():
            if save.get("session_id") == session_id:
                return save.get("slot_name")
        return None

    def load_game(self, slot_name: str = "autosave", *, strict: bool = False):
        try:
            save_data = self.read_save(slot_name)
            if save_data is None:
                if strict:
                    raise FileNotFoundError(slot_name)
                return None
            state = save_data.get("session_state", {})
            if not state or "player" not in state:
                if strict:
                    raise ValueError(f"Corrupt save slot: {slot_name}")
                return None
            return self._deserialize_session(state)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            if strict:
                raise
            return None

    def list_saves(self, player_name: Optional[str] = None) -> List[Dict]:
        saves = []
        for path in sorted(self.save_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                campaign_v2 = self._campaign_v2_state(data)
                entry = {
                    "slot_name": data.get("slot_name", path.stem),
                    "player_name": data.get("player_name", "Unknown"),
                    "player_level": data.get("player_level", 1),
                    "location": data.get("location", "Unknown"),
                    "timestamp": data.get("timestamp", ""),
                    "game_time": data.get("game_time_display", ""),
                    "schema_version": data.get("schema_version", ""),
                    "session_id": data.get("session_state", {}).get("session_id"),
                    "campaign_compatible": campaign_v2 is not None,
                    "campaign_id": str(campaign_v2.get("campaign_id", "")) if campaign_v2 else "",
                }
                if player_name and entry["player_name"] != player_name:
                    continue
                saves.append(entry)
            except (json.JSONDecodeError, KeyError):
                pass
        return saves

    def delete_save(self, slot_name: str) -> bool:
        filepath = self.save_dir / f"{slot_name}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def autosave(self, session) -> str:
        return self.save_game(session, "autosave")

    def save_exists(self, slot_name: str) -> bool:
        return (self.save_dir / f"{slot_name}.json").exists()
