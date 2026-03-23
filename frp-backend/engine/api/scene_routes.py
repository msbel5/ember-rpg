"""
Scene orchestrator routes.
POST /game/scene/enter → full scene response (non-streaming)
POST /game/scene/enter/stream → SSE streaming response
GET  /game/scene/available-types → list of valid location types

Session integration:
- If session_id matches an active GameSession, player_name/level are pulled from it
  and the session's location is updated to the new scene.
- World context is pulled from session.world_state if available.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from engine.orchestrator import SceneOrchestrator, SceneRequest

router = APIRouter(prefix="/game", tags=["scene"])
_orchestrator = SceneOrchestrator()


class SceneEnterRequest(BaseModel):
    session_id: str
    location: str
    location_type: str = "town"
    time_of_day: str = "morning"
    player_name: str = "Adventurer"
    player_level: int = 1
    is_first_visit: bool = True
    world_context: Optional[str] = ""
    npc_context: Optional[str] = ""


def _enrich_from_session(req: SceneEnterRequest) -> SceneRequest:
    """
    If session_id is an active game session, pull player info + world context from it
    and update the session's current location.
    Falls back to request data if session not found.
    """
    # Import here to avoid circular imports
    try:
        from engine.api.routes import _sessions, _autosave_session
        session = _sessions.get(req.session_id)
        if session:
            # Update location in session
            session.dm_context.location = req.location

            # Build world context from WorldState
            world_ctx = req.world_context or ""
            try:
                world_ctx = session.world_state.build_ai_context(req.location) or world_ctx
            except Exception:
                pass

            # Build NPC context from memory
            npc_ctx = req.npc_context or ""

            # Log scene entry in world state
            try:
                session.world_state.update_location_discovered(req.location, req.location)
            except Exception:
                pass

            _autosave_session(session)

            return SceneRequest(
                session_id=req.session_id,
                location=req.location,
                location_type=req.location_type,
                time_of_day=req.time_of_day,
                player_name=session.player.name,
                player_level=session.player.level,
                is_first_visit=req.is_first_visit,
                world_context=world_ctx,
                npc_context=npc_ctx,
            )
    except Exception:
        pass

    return SceneRequest(**req.model_dump())


@router.post("/scene/enter")
def enter_scene(req: SceneEnterRequest):
    """
    Orchestrator endpoint: generates map + entities + LLM narrative.
    Integrates with active GameSession if session_id matches.
    Returns full SceneResponse as JSON.
    """
    scene_req = _enrich_from_session(req)
    result = _orchestrator.enter_scene(scene_req)
    return result.__dict__


@router.post("/scene/enter/stream")
async def enter_scene_stream(req: SceneEnterRequest):
    """
    Streaming version: yields NDJSON events.
    Events: map_ready, narrative (repeated), entities_ready, scene_complete
    Integrates with active GameSession if session_id matches.
    """
    scene_req = _enrich_from_session(req)

    async def generate():
        async for chunk in _orchestrator.enter_scene_streaming(scene_req):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff"}
    )


@router.get("/scene/available-types")
def get_available_types():
    """List of valid location types for scene enter."""
    return {
        "types": ["town", "dungeon", "tavern", "wilderness", "cave"],
        "time_of_day": ["morning", "afternoon", "evening", "night"]
    }
