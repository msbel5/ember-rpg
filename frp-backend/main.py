"""
Ember RPG - FastAPI Application Entry Point
"""
from fastapi import FastAPI
from engine.api.campaign_routes import router as campaign_router
from engine.api.ws_campaign import ws_router

app = FastAPI(
    title="Ember RPG API",
    description="AI-driven FRP game engine. Natural language in, narrative out.",
    version="0.1.0",
)

# HTTP campaign routes.
app.include_router(campaign_router, prefix="/game")
# WebSocket campaign transport (real-time bidirectional).
app.include_router(ws_router, prefix="/game")


@app.get("/")
def root():
    return {"name": "Ember RPG", "version": "0.1.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
