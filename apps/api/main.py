from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)
load_dotenv(ROOT / ".env.local", override=True)

from apps.api.routers import mirror  # noqa: E402

app = FastAPI(
    title="GameDay Mirror API",
    version="0.1.0",
    description="LiveKit tokens and sponsor-backed check-in orchestration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "API_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "product": "gameday-mirror"}


app.include_router(mirror.router)
