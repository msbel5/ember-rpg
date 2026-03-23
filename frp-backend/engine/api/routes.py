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
                        "You are the Dungeon Master for Ember RPG, a dark fantasy tabletop RPG. "
                        "Always respond in character — never say you don't understand. "
                        "For NPC dialogue: give the NPC a voice and have them speak directly. "
                        "For actions: describe what happens narratively in 2nd person. "
                        "For ambiguous input: make a creative interpretation that fits the scene. "
                        "Use 2-4 sentences. No markdown headers. No game mechanic references."
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

# Save manager for persistence across restarts
from engine.save import SaveManager as _SaveManager
_save_manager = _SaveManager()


def _autosave_session(session: GameSession) -> None:
    """Autosave session to disk after every action."""
    try:
        state = session.to_dict()
        _save_manager.save(
            player_id=session.player.name,
            session_data={"session_id": session.session_id, **state}
        )
    except Exception:
        pass  # autosave is best-effort


def _try_restore_session(session_id: str) -> Optional[GameSession]:
    """
    Try to restore a session from disk after a restart.
    Returns None if not found or corrupt.
    """
    try:
        # Find any save with matching session_id
        from pathlib import Path
        saves_dir = Path("saves")
        if not saves_dir.exists():
            return None
        for f in saves_dir.glob("*.json"):
            import json
            try:
                data = json.loads(f.read_text())
                if data.get("session_data", {}).get("session_id") == session_id:
                    sd = data["session_data"]
                    # Reconstruct minimal session
                    from engine.core.character import Character
                    from engine.core.dm_agent import DMContext, SceneType
                    player = Character(
                        name=sd["player"]["name"],
                        hp=sd["player"]["hp"],
                        max_hp=sd["player"]["max_hp"],
                        spell_points=sd["player"].get("spell_points", 0),
                        max_spell_points=sd["player"].get("max_spell_points", 0),
                        level=sd["player"]["level"],
                        xp=sd["player"].get("xp", 0),
                    )
                    dm_ctx = DMContext(
                        scene_type=SceneType(sd.get("scene", "exploration")),
                        location=sd.get("location", "unknown"),
                    )
                    session = GameSession(player=player, dm_context=dm_ctx, session_id=session_id)
                    return session
            except Exception:
                continue
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
