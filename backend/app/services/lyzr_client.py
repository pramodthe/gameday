"""Lyzr Agent API client (sponsor integration).

Powers the coaching message when LYZR_API_KEY + LYZR_AGENT_ID are configured.
Synchronous, defensively parsed, and degrades to None on any error so callers
fall back to the deterministic coaching message. The endpoint is env-overridable
(`LYZR_API_URL`) since Lyzr exposes a couple of inference routes.
"""
from __future__ import annotations

import httpx

from ..config import settings

# Synchronous chat inference endpoint (returns the reply directly).
DEFAULT_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"


def available() -> bool:
    return bool(settings.lyzr_api_key and settings.lyzr_agent_id)


def _extract_reply(data) -> str | None:
    if isinstance(data, str):
        return data.strip() or None
    if isinstance(data, dict):
        for key in ("response", "answer", "message", "text", "output", "result"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:  # OpenAI-style shape, just in case
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content.strip()
        except (KeyError, IndexError, TypeError):
            pass
    return None


def chat(message: str, session_id: str = "readyroom") -> str | None:
    if not available():
        return None
    url = settings.lyzr_api_url or DEFAULT_URL
    headers = {
        "x-api-key": settings.lyzr_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "user_id": settings.lyzr_user_id or "readyroom",
        "agent_id": settings.lyzr_agent_id,
        "session_id": session_id,
        "message": message,
    }
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return _extract_reply(resp.json())
    except Exception:
        return None
