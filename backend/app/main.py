"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import seed
from .api import athletes, coach, sessions
from .config import settings
from .ws import checkin as ws_checkin


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed.seed_demo_data()
    yield


app = FastAPI(title="ReadyRoom API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "readyroom", "persistence": settings.persistence}


@app.get("/api/config")
def get_config() -> dict:
    """Non-secret runtime config for the frontend."""
    return {
        "persistence": settings.persistence,
        "voice": {"deepgram": bool(settings.deepgram_api_key)},
        "features": {
            "guardrail": settings.enable_guardrail,
            "lyzr": settings.enable_lyzr,
            "qdrant": settings.enable_qdrant,
        },
        "readiness_weights": settings.readiness_weights,
    }


app.include_router(athletes.router)
app.include_router(sessions.router)
app.include_router(coach.router)
app.include_router(ws_checkin.router)
