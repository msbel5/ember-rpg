"""
Ember RPG — NPC Memory API Routes
Phase 3b
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _get_session(session_id: str):
    from engine.api.routes import _sessions
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return _sessions[session_id]


class FactRequest(BaseModel):
    fact: str


@router.get("/session/{session_id}/npc/{npc_id}/memory")
def get_npc_memory(session_id: str, npc_id: str):
    session = _get_session(session_id)
    mem = session.npc_memory.get_memory(npc_id)
    return mem.__dict__


@router.post("/session/{session_id}/npc/{npc_id}/fact")
def add_npc_fact(session_id: str, npc_id: str, body: FactRequest):
    session = _get_session(session_id)
    mem = session.npc_memory.get_memory(npc_id)
    mem.add_known_fact(body.fact)
    return {"status": "ok", "known_facts": mem.known_facts}


@router.get("/session/{session_id}/npc/{npc_id}/context")
def get_npc_context(session_id: str, npc_id: str):
    session = _get_session(session_id)
    mem = session.npc_memory.get_memory(npc_id)
    return {"context": mem.build_context()}
