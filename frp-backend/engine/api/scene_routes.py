"""
Scene orchestrator routes.
POST /game/scene/enter → full scene response (non-streaming)
POST /game/scene/enter/stream → SSE streaming response
GET  /game/scene/available-types → list of valid location types
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


@router.post("/scene/enter")
def enter_scene(req: SceneEnterRequest):
    """
    Orchestrator endpoint: generates map + entities + LLM narrative.
    Returns full SceneResponse as JSON.
    """
    scene_req = SceneRequest(**req.model_dump())
    result = _orchestrator.enter_scene(scene_req)
    return result.__dict__


@router.post("/scene/enter/stream")
async def enter_scene_stream(req: SceneEnterRequest):
    """
    Streaming version: yields NDJSON events.
    Events: map_ready, narrative (repeated), entities_ready, scene_complete
    """
    scene_req = SceneRequest(**req.model_dump())

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
