"""
Ember RPG - API Layer
FastAPI routes
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional

from engine.api.game_engine import GameEngine
from engine.api.game_session import GameSession
from engine.api.save_system import SaveSystem
from engine.api.models import (
    NewSessionRequest, NewSessionResponse,
    ActionRequest, ActionResponse,
    SessionStateResponse,
)
from engine.core.dm_agent import DMEvent, EventType, SceneType

router = APIRouter()
_save_system = SaveSystem()

# Wire LLM to GameEngine — narrative uses claude-haiku-4.5 via Copilot API
def _make_llm_callable():
    import re
    from engine.llm import get_llm_router, MODEL_FAST
    llm_router = get_llm_router()

    def _llm(prompt: str) -> str:
        result = llm_router.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the Dungeon Master for Ember RPG, a grounded dark-fantasy RPG. "
                        "Respect the supplied game state and mechanics exactly; never invent extra outcomes "
                        "or contradict deterministic results. Write concise second-person narration with a "
                        "consistent, low-flourish tone. For NPC dialogue, let the NPC speak directly. For "
                        "ambiguous input, acknowledge the uncertainty inside the fiction instead of claiming "
                        "mechanics that did not happen. Use 2-4 sentences. No markdown headers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=MODEL_FAST,
        )
        if result:
            result = re.sub(r'^#+\s+[^\n]*\n+', '', result, flags=re.MULTILINE).strip()
        return result  # None → GameEngine falls back to template

    return _llm

engine = GameEngine(llm=_make_llm_callable())

# In-memory session store
_sessions: Dict[str, GameSession] = {}


def _autosave_slot_name(session_id: str) -> str:
    return f"autosave_{session_id}"


def _autosave_session(session: GameSession) -> None:
    """Autosave session to disk after every action."""
    try:
        _save_system.save_game(
            session,
            _autosave_slot_name(session.session_id),
            player_name=session.player.name if session.player else None,
        )
    except Exception:
        pass  # autosave is best-effort


def _try_restore_session(session_id: str) -> Optional[GameSession]:
    """
    Try to restore a session from disk after a restart.
    Returns None if not found or corrupt.
    """
    try:
        autosave_slot = _autosave_slot_name(session_id)
        session = _save_system.load_game(autosave_slot)
        if session and session.session_id == session_id:
            return session
    except Exception:
        pass
    return None


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
    narrative = dm.narrate(opening_event, session.dm_context, llm=_make_llm_callable())

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
    # Flatten player stats to top level for easy client access
    player = state.get("player", {})
    state["hp"] = player.get("hp")
    state["max_hp"] = player.get("max_hp")
    state["level"] = player.get("level")
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

    _autosave_session(session)
    snapshot = session.to_dict()
    player_data = snapshot["player"]
    return ActionResponse(
        narrative=result.narrative,
        scene=result.scene_type.value,
        player=player_data,
        combat=result.combat_state,
        state_changes=result.state_changes,
        level_up=level_up_dict,
        active_quests=snapshot.get("active_quests", []),
        quest_offers=snapshot.get("quest_offers", []),
        ground_items=snapshot.get("ground_items", []),
        campaign_state=snapshot.get("campaign_state", {}),
    )


@router.delete("/session/{session_id}")
def end_session(session_id: str):
    """End and remove a game session."""
    session = _get_session(session_id)
    del _sessions[session_id]
    try:
        _save_system.delete_save(_autosave_slot_name(session_id))
    except Exception:
        pass
    try:
        last_slot = getattr(session, "last_save_slot", None)
        if last_slot and str(last_slot).startswith("autosave_"):
            _save_system.delete_save(last_slot)
    except Exception:
        pass
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
    map_data = getattr(session, "map_data", None)
    if map_data is None:
        from engine.map import DungeonGenerator, TownGenerator, WildernessGenerator

        map_seed = seed if seed is not None else abs(hash(session.session_id)) % (2**31)
        location = session.dm_context.location.lower()
        if any(w in location for w in ["town", "tavern", "village", "harbor", "city", "inn", "market"]):
            generator = TownGenerator(seed=map_seed)
        elif any(w in location for w in ["forest", "road", "wild", "field", "camp"]):
            generator = WildernessGenerator(seed=map_seed)
        else:
            generator = DungeonGenerator(seed=map_seed)
        map_data = generator.generate(width=40, height=40)
        session.map_data = map_data

    return {
        "session_id": session_id,
        "location": session.dm_context.location,
        "map": map_data.to_dict(),
    }


def _get_session(session_id: str) -> GameSession:
    session = _sessions.get(session_id)
    if not session:
        # Try to restore from disk (handles restart scenario)
        session = _try_restore_session(session_id)
        if session:
            _sessions[session_id] = session
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/llm/status")
def llm_status():
    """Check LLM availability and return a test response."""
    from engine.llm import get_llm_router, MODEL_FAST
    router = get_llm_router()
    test_response = router.narrative(
        "You are a fantasy game DM. Keep responses to 1 sentence.",
        "Player looks around a dark dungeon corridor."
    )
    return {
        "available": test_response is not None,
        "model": MODEL_FAST,
        "test_response": test_response or "(LLM unavailable — templates active)",
    }
