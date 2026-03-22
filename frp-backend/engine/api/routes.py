"""
Ember RPG - API Layer
FastAPI routes
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional

from engine.api.game_engine import GameEngine
from engine.api.game_session import GameSession
from engine.api.models import (
    NewSessionRequest, NewSessionResponse,
    ActionRequest, ActionResponse,
    SessionStateResponse,
)
from engine.core.dm_agent import DMEvent, EventType, SceneType

router = APIRouter()
engine = GameEngine()

# In-memory session store (replace with Redis in production)
_sessions: Dict[str, GameSession] = {}


@router.post("/session/new", response_model=NewSessionResponse)
def new_session(req: NewSessionRequest):
    """Create a new game session."""
    session = engine.new_session(
        player_name=req.player_name,
        player_class=req.player_class,
        location=req.location,
    )
    _sessions[session.session_id] = session

    # Opening narrative
    from engine.core.dm_agent import DMAIAgent
    dm = DMAIAgent()
    opening_event = DMEvent(
        type=EventType.DISCOVERY,
        description=f"{req.player_name} begins their adventure.",
    )
    narrative = dm.narrate(opening_event, session.dm_context)

    return NewSessionResponse(
        session_id=session.session_id,
        narrative=narrative,
        player=session.to_dict()["player"],
        scene=session.dm_context.scene_type.value,
        location=session.dm_context.location,
    )


@router.get("/session/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str):
    """Get current session state."""
    session = _get_session(session_id)
    state = session.to_dict()
    return SessionStateResponse(**state)


@router.post("/session/{session_id}/action", response_model=ActionResponse)
def take_action(session_id: str, req: ActionRequest):
    """Process a player action and return DM narrative."""
    session = _get_session(session_id)
    result = engine.process_action(session, req.input)

    level_up_dict = None
    if result.level_up:
        lu = result.level_up
        level_up_dict = {
            "old_level": lu.old_level,
            "new_level": lu.new_level,
            "new_abilities": [a.name for a in lu.new_abilities],
            "stat_bonus": lu.stat_bonus,
            "hp_increase": lu.hp_increase,
        }

    return ActionResponse(
        narrative=result.narrative,
        scene=result.scene_type.value,
        player=session.to_dict()["player"],
        combat=result.combat_state,
        state_changes=result.state_changes,
        level_up=level_up_dict,
    )


@router.delete("/session/{session_id}")
def end_session(session_id: str):
    """End and remove a game session."""
    _get_session(session_id)
    del _sessions[session_id]
    return {"message": "Session ended."}


@router.get("/session/{session_id}/map")
def get_map(session_id: str, seed: Optional[int] = None):
    """
    Get the procedurally generated tile map for the current session location.

    Query params:
        seed (int, optional): RNG seed for deterministic generation (default: session-based)

    Returns:
        Map data including tile grid, rooms, and metadata.
    """
    session = _get_session(session_id)
    from engine.map import DungeonGenerator, TownGenerator

    map_seed = seed if seed is not None else abs(hash(session.session_id)) % (2**31)
    location = session.dm_context.location.lower()

    # Choose map type based on location name heuristics
    if any(w in location for w in ["town", "tavern", "village", "harbor", "city", "inn", "market"]):
        generator = TownGenerator(seed=map_seed)
        map_data = generator.generate(width=40, height=40)
    else:
        generator = DungeonGenerator(seed=map_seed)
        map_data = generator.generate(width=40, height=40)

    return {
        "session_id": session_id,
        "location": session.dm_context.location,
        "map": map_data.to_dict(),
    }


def _get_session(session_id: str) -> GameSession:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
