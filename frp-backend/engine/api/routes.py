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
    CreationStartRequest,
    CreationAnswerRequest,
    CreationFinalizeRequest,
    CreationStateResponse,
)
from engine.core.character_creation import CreationState, assign_stats_to_class
from engine.core.dm_agent import DMEvent, EventType, SceneType

router = APIRouter()
_save_system = SaveSystem()

def _make_llm_callable():
    from engine.llm import build_game_narrator

    return build_game_narrator()

engine = GameEngine(llm=_make_llm_callable())

# In-memory session store
_sessions: Dict[str, GameSession] = {}
_creation_states: Dict[str, CreationState] = {}


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
        alignment=req.alignment,
        skill_proficiencies=req.skill_proficiencies,
        stats=req.stats,
        creation_answers=req.creation_answers,
        creation_profile=req.creation_profile,
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


def _creation_state_response(state: CreationState, player_name: str, location: Optional[str]) -> CreationStateResponse:
    effective_player_name = player_name or str(state.creation_profile.get("_player_name", "") or "")
    effective_location = location or state.creation_profile.get("_location")
    payload = state.to_dict()
    return CreationStateResponse(
        creation_id=payload["creation_id"],
        player_name=effective_player_name,
        location=effective_location,
        questions=payload["questions"],
        answers=payload["answers"],
        class_weights=payload["class_weights"],
        skill_weights=payload["skill_weights"],
        alignment_axes=payload["alignment_axes"],
        recommended_class=payload["recommended_class"],
        recommended_alignment=payload["recommended_alignment"],
        recommended_skills=payload["recommended_skills"],
        current_roll=payload["current_roll"],
        saved_roll=payload["saved_roll"],
    )


@router.post("/session/creation/start", response_model=CreationStateResponse)
def start_creation(req: CreationStartRequest):
    state = CreationState(player_name=req.player_name, location=req.location)
    state.ensure_roll()
    state.creation_profile["_player_name"] = req.player_name
    state.creation_profile["_location"] = req.location
    _creation_states[state.creation_id] = state
    return _creation_state_response(state, req.player_name, req.location)


@router.post("/session/creation/{creation_id}/answer", response_model=CreationStateResponse)
def answer_creation(creation_id: str, req: CreationAnswerRequest):
    state = _creation_states.get(creation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Creation flow not found")
    state.answer_question(req.question_id, req.answer_id)
    return _creation_state_response(state, "", None)


@router.post("/session/creation/{creation_id}/reroll", response_model=CreationStateResponse)
def reroll_creation(creation_id: str):
    state = _creation_states.get(creation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Creation flow not found")
    state.reroll()
    return _creation_state_response(state, "", None)


@router.post("/session/creation/{creation_id}/save-roll", response_model=CreationStateResponse)
def save_creation_roll(creation_id: str):
    state = _creation_states.get(creation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Creation flow not found")
    state.save_current_roll()
    return _creation_state_response(state, "", None)


@router.post("/session/creation/{creation_id}/swap-roll", response_model=CreationStateResponse)
def swap_creation_roll(creation_id: str):
    state = _creation_states.get(creation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Creation flow not found")
    state.swap_rolls()
    return _creation_state_response(state, "", None)


@router.post("/session/creation/{creation_id}/finalize", response_model=NewSessionResponse)
def finalize_creation(creation_id: str, req: CreationFinalizeRequest):
    state = _creation_states.get(creation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Creation flow not found")
    chosen_class = (req.player_class or state.recommended_class() or "warrior").lower()
    chosen_alignment = req.alignment or state.recommended_alignment()
    proficiencies = req.skill_proficiencies or state.recommended_skills()
    stats = assign_stats_to_class(state.current_roll, chosen_class)
    player_name = str(state.creation_profile.get("_player_name", "") or "Adventurer")
    location = req.location or state.creation_profile.get("_location")
    session = engine.new_session(
        player_name=player_name,
        player_class=chosen_class,
        location=location,
        alignment=chosen_alignment,
        skill_proficiencies=proficiencies,
        stats=stats,
        creation_answers=list(state.answers),
        creation_profile={
            "class_weights": dict(state.class_weights),
            "skill_weights": dict(state.skill_weights),
            "alignment_axes": dict(state.alignment_axes),
            "recommended_class": state.recommended_class(),
            "recommended_alignment": state.recommended_alignment(),
            "player_name": player_name,
        },
    )
    _sessions[session.session_id] = session
    _creation_states.pop(creation_id, None)
    return NewSessionResponse(
        session_id=session.session_id,
        narrative=f"{session.player.name} the {chosen_class.capitalize()} enters {session.dm_context.location}.",
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
        conversation_state=snapshot.get("conversation_state", {}),
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
    from engine.llm import (
        LiveNarrationRequiredError,
        get_fallback_model_name,
        get_live_model_name,
        get_llm_router,
        get_narration_mode,
    )

    router = get_llm_router()
    mode = get_narration_mode()
    error = None
    try:
        test_response = router.narrative(
            "You are a fantasy game DM. Keep responses to 1 sentence.",
            "Player looks around a dark dungeon corridor.",
            narration_mode=mode,
        )
    except LiveNarrationRequiredError as exc:
        test_response = None
        error = str(exc)
    return {
        "available": test_response is not None,
        "mode": mode,
        "model": get_live_model_name(),
        "fallback_model": get_fallback_model_name(),
        "auth_source": router.last_auth_source,
        "test_response": test_response or "(LLM unavailable — templates active)",
        "error": error,
    }
