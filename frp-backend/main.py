"""
Ember RPG - FastAPI Application Entry Point
"""
from fastapi import FastAPI
from engine.api.routes import router
from engine.api.save_routes import router as save_router

app = FastAPI(
    title="Ember RPG API",
    description="AI-driven FRP game engine. Natural language in, narrative out.",
    version="0.1.0",
)

app.include_router(router, prefix="/game")
app.include_router(save_router, prefix="/game")


@app.get("/")
def root():
    return {"name": "Ember RPG", "version": "0.1.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
