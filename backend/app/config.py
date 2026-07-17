"""Application settings, feature flags, and scoring weights.

Kept dependency-light (plain env parsing) so the scoring core and tests run
without any settings framework installed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_READINESS_WEIGHTS: dict[str, float] = {
    "sleep": 0.30,
    "fatigue": 0.25,
    "soreness": 0.20,
    "nutrition": 0.15,
    "mood": 0.10,
}

DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    deepgram_api_key: str = ""
    anthropic_api_key: str = ""
    persistence: str = "local"  # "local" | "insforge"
    insforge_api_key: str = ""
    # Lyzr Agent API (sponsor integration) — powers coaching when configured.
    lyzr_api_key: str = ""
    lyzr_agent_id: str = ""
    lyzr_user_id: str = "readyroom"
    lyzr_api_url: str = ""  # override; defaults to the v3 inference chat endpoint
    enable_guardrail: bool = False
    enable_lyzr: bool = False
    enable_qdrant: bool = False
    readiness_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_READINESS_WEIGHTS)
    )
    cors_origins: list[str] = field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    @classmethod
    def from_env(cls) -> "Settings":
        weights = dict(DEFAULT_READINESS_WEIGHTS)
        raw_weights = os.getenv("READINESS_WEIGHTS")
        if raw_weights:
            try:
                weights.update(json.loads(raw_weights))
            except json.JSONDecodeError:
                pass

        raw_origins = os.getenv("CORS_ORIGINS")
        origins = (
            [o.strip() for o in raw_origins.split(",") if o.strip()]
            if raw_origins
            else list(DEFAULT_CORS_ORIGINS)
        )

        return cls(
            deepgram_api_key=os.getenv("DEEPGRAM_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            persistence=os.getenv("PERSISTENCE", "local"),
            insforge_api_key=os.getenv("INSFORGE_API_KEY", ""),
            lyzr_api_key=os.getenv("LYZR_API_KEY", ""),
            lyzr_agent_id=os.getenv("LYZR_AGENT_ID", ""),
            lyzr_user_id=os.getenv("LYZR_USER_ID", "readyroom"),
            lyzr_api_url=os.getenv("LYZR_API_URL", ""),
            enable_guardrail=_flag("ENABLE_GUARDRAIL"),
            enable_lyzr=_flag("ENABLE_LYZR"),
            enable_qdrant=_flag("ENABLE_QDRANT"),
            readiness_weights=weights,
            cors_origins=origins,
        )


settings = Settings.from_env()
