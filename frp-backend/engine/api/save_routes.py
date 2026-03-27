"""
Ember RPG -- Save/Load API Routes
FastAPI router for save management endpoints.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.api.save_system import SaveSystem
from engine.save import CorruptSaveError, SaveNotFoundError
from engine.save.save_models import SaveFile

router = APIRouter()


class SaveRequest(BaseModel):
    player_id: str
    slot_name: Optional[str] = None


class SaveResponse(BaseModel):
    save_id: str
    slot_name: str
    timestamp: str
    schema_version: str


class SaveSummary(BaseModel):
    save_id: str
    slot_name: str
    player_id: str
    timestamp: str
    schema_version: str
    location: Optional[str] = None
    game_time: Optional[str] = None
    campaign_compatible: bool = False


class LoadResponse(BaseModel):
    save_id: str
    slot_name: str
    status: str
    session_data: Dict[str, Any]


class SaveManagerCompat:
    """Compatibility facade that exposes SaveManager-style methods over SaveSystem."""

    _SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

    def __init__(self, save_system: Optional[SaveSystem] = None):
        self.save_system = save_system or SaveSystem()

    def _sanitize(self, value: str, field: str) -> str:
        if not value or not self._SAFE_PATTERN.match(value):
            raise ValueError(f"Invalid characters in {field}: {value!r}")
        return value

    def _make_slot_name(self, player_id: str, requested_slot: Optional[str] = None) -> str:
        if requested_slot:
            return self._sanitize(requested_slot, "slot_name")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{self._sanitize(player_id, 'player_id')}_{timestamp}"

    def save(self, player_id: str, session, slot_name: Optional[str] = None) -> str:
        slot_name = self._make_slot_name(player_id, slot_name)
        self.save_system.save_game(session, slot_name, player_name=player_id)
        return slot_name

    def load(self, save_id: str) -> SaveFile:
        try:
            save_data = self.save_system.read_save(save_id)
        except json.JSONDecodeError as exc:
            raise CorruptSaveError(f"Save file is corrupt: {save_id}.json -- {exc}") from exc

        if save_data is None:
            raise SaveNotFoundError(f"Save not found: {save_id}")

        session_data = save_data.get("session_state")
        if not isinstance(session_data, dict):
            raise CorruptSaveError(f"Save file is corrupt: {save_id}.json -- missing session_state")

        return SaveFile(
            save_id=save_id,
            player_id=save_data.get("player_name", "Unknown"),
            session_data=session_data,
            timestamp=save_data.get("timestamp", ""),
            schema_version=save_data.get("schema_version", ""),
        )

    def restore_session(self, save_id: str):
        try:
            session = self.save_system.load_game(save_id, strict=True)
        except FileNotFoundError as exc:
            raise SaveNotFoundError(f"Save not found: {save_id}") from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CorruptSaveError(f"Save file is corrupt: {save_id}.json -- {exc}") from exc
        if session is None:
            raise SaveNotFoundError(f"Save not found: {save_id}")
        return session

    def list_saves(self, player_id: str) -> List[SaveFile]:
        self._sanitize(player_id, "player_id")
        return [
            SaveFile(
                save_id=entry["slot_name"],
                player_id=entry.get("player_name", "Unknown"),
                session_data={},
                timestamp=entry.get("timestamp", ""),
                schema_version=entry.get("schema_version", ""),
            )
            for entry in self.save_system.list_saves(player_name=player_id)
        ]

    def delete(self, save_id: str) -> None:
        if not self.save_system.delete_save(save_id):
            raise SaveNotFoundError(f"Save not found: {save_id}")


save_manager = SaveManagerCompat()


def _build_summary(save_id: str) -> SaveSummary:
    save_file = save_manager.load(save_id)
    metadata = save_manager.save_system.get_save_metadata(save_id) or {}
    return SaveSummary(
        save_id=save_id,
        slot_name=metadata.get("slot_name", save_id),
        player_id=save_file.player_id,
        timestamp=save_file.timestamp,
        schema_version=save_file.schema_version,
        location=metadata.get("location"),
        game_time=metadata.get("game_time"),
        campaign_compatible=bool(metadata.get("campaign_compatible", False)),
    )


@router.post("/session/{session_id}/save", response_model=SaveResponse)
def save_session(session_id: str, req: SaveRequest):
    """Save current session state to disk."""
    from engine.api.routes import _sessions

    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    try:
        save_id = save_manager.save(req.player_id, session, req.slot_name)
        metadata = save_manager.save_system.get_save_metadata(save_id) or {}
        return SaveResponse(
            save_id=save_id,
            slot_name=metadata.get("slot_name", save_id),
            timestamp=metadata.get("timestamp", ""),
            schema_version=metadata.get("schema_version", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/saves/{player_id}", response_model=List[SaveSummary])
def list_saves(player_id: str):
    """List all saves for a player."""
    try:
        saves = save_manager.list_saves(player_id=player_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return [_build_summary(save.save_id) for save in saves]


@router.get("/saves/file/{save_id}", response_model=SaveSummary)
def get_save(save_id: str):
    """Get metadata for a specific save."""
    try:
        return _build_summary(save_id)
    except SaveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}") from exc
    except CorruptSaveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/saves/{save_id}")
def delete_save(save_id: str):
    """Delete a save file."""
    try:
        save_manager.delete(save_id)
        return {"status": "deleted", "save_id": save_id, "slot_name": save_id}
    except SaveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}") from exc


@router.post("/session/load/{save_id}", response_model=LoadResponse)
def load_session(save_id: str):
    """Load a session from a save file."""
    try:
        save_manager.load(save_id)
        session = save_manager.restore_session(save_id)
        from engine.api.routes import _sessions

        _sessions[session.session_id] = session
        metadata = save_manager.save_system.get_save_metadata(save_id) or {}
        return LoadResponse(
            save_id=save_id,
            slot_name=metadata.get("slot_name", save_id),
            status="loaded",
            session_data=session.to_dict(),
        )
    except SaveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}") from exc
    except CorruptSaveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
