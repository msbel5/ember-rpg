"""Ember RPG - FastAPI Application Entry Point.

HTTP routes handle creation, bootstrap, save/load, and admin.
WebSocket is the primary runtime transport after campaign start.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from engine.api.campaign_routes import campaign_runtime, router as campaign_router
from engine.api.ws_campaign import set_runtime, ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire the shared CampaignRuntime into the WebSocket handler on startup."""
    set_runtime(campaign_runtime)
    logger.info("Ember RPG backend started — WS transport active")
    yield
    logger.info("Ember RPG backend shutting down")


app = FastAPI(
    title="Ember RPG API",
    description="Deterministic kernel RPG. HTTP for bootstrap, WebSocket for runtime.",
    version="0.2.0",
    lifespan=lifespan,
)

# HTTP: creation, save/load, admin, snapshots.
app.include_router(campaign_router, prefix="/game")
# WebSocket: real-time bidirectional game transport.
app.include_router(ws_router, prefix="/game")


@app.get("/")
def root():
    return {"name": "Ember RPG", "version": "0.2.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
