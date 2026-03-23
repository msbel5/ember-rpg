"""
Ember RPG — World State API Routes
Phase 3a
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional

router = APIRouter()

# Import session store from routes module
def _get_sessions():
    from engine.api.routes import _sessions
    return _sessions

def _get_session(session_id: str):
    sessions = _get_sessions()
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return sessions[session_id]


@router.get("/session/{session_id}/world-state")
def get_world_state(session_id: str):
    session = _get_session(session_id)
    return session.world_state.to_dict()


@router.get("/session/{session_id}/history")
def get_history(session_id: str, limit: Optional[int] = None):
    session = _get_session(session_id)
    history = [e.to_dict() for e in session.world_state.history]
    if limit:
        history = history[-limit:]
    return {"history": history, "total": len(session.world_state.history)}


@router.get("/session/{session_id}/factions")
def get_factions(session_id: str):
    session = _get_session(session_id)
    return {k: v.to_dict() for k, v in session.world_state.factions.items()}


@router.get("/session/{session_id}/flags")
def get_flags(session_id: str):
    session = _get_session(session_id)
    return session.world_state.flags


@router.get("/session/{session_id}/consequences")
def get_consequences(session_id: str):
    session = _get_session(session_id)
    return {"pending_effects": [pe.__dict__ for pe in session.cascade_engine.pending_effects]}


@router.post("/session/{session_id}/trigger")
def fire_trigger(session_id: str, body: dict):
    session = _get_session(session_id)
    trigger_type = body.pop("trigger_type", None)
    if not trigger_type:
        raise HTTPException(status_code=400, detail="trigger_type required")
    trigger = {"type": trigger_type, **body}
    effects = session.cascade_engine.process_trigger(trigger, session.world_state)
    return {"triggered_effects": [e.__dict__ for e in effects]}
