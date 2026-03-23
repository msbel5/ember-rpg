"""
Ember RPG — Save/Load API Routes
FastAPI router for save management endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from engine.save import SaveManager, SaveNotFoundError, CorruptSaveError

router = APIRouter()
save_manager = SaveManager()


class SaveRequest(BaseModel):
    player_id: str


class SaveResponse(BaseModel):
    save_id: str
    timestamp: str
    schema_version: str


class SaveSummary(BaseModel):
    save_id: str
    player_id: str
    timestamp: str
    schema_version: str


class LoadResponse(BaseModel):
    save_id: str
    status: str
    session_data: Dict[str, Any]


@router.post("/session/{session_id}/save", response_model=SaveResponse)
def save_session(session_id: str, req: SaveRequest):
    """Save current session state to disk."""
    # Import here to avoid circular imports
    from engine.api.routes import _sessions

    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session_data = session.to_dict()
    try:
        save_id = save_manager.save(player_id=req.player_id, session_data=session_data)
        sf = save_manager.load(save_id)
        return SaveResponse(
            save_id=sf.save_id,
            timestamp=sf.timestamp,
            schema_version=sf.schema_version,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saves/{player_id}", response_model=List[SaveSummary])
def list_saves(player_id: str):
    """List all saves for a player."""
    saves = save_manager.list_saves(player_id=player_id)
    return [
        SaveSummary(
            save_id=s.save_id,
            player_id=s.player_id,
            timestamp=s.timestamp,
            schema_version=s.schema_version,
        )
        for s in saves
    ]


@router.get("/saves/file/{save_id}", response_model=SaveSummary)
def get_save(save_id: str):
    """Get metadata for a specific save."""
    try:
        sf = save_manager.load(save_id)
        return SaveSummary(
            save_id=sf.save_id,
            player_id=sf.player_id,
            timestamp=sf.timestamp,
            schema_version=sf.schema_version,
        )
    except SaveNotFoundError:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}")
    except CorruptSaveError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/saves/{save_id}")
def delete_save(save_id: str):
    """Delete a save file."""
    try:
        save_manager.delete(save_id)
        return {"status": "deleted", "save_id": save_id}
    except SaveNotFoundError:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}")


@router.post("/session/load/{save_id}", response_model=LoadResponse)
def load_session(save_id: str):
    """Load a session from a save file."""
    try:
        sf = save_manager.load(save_id)
        return LoadResponse(
            save_id=sf.save_id,
            status="loaded",
            session_data=sf.session_data,
        )
    except SaveNotFoundError:
        raise HTTPException(status_code=404, detail=f"Save not found: {save_id}")
    except CorruptSaveError as e:
        raise HTTPException(status_code=422, detail=str(e))
