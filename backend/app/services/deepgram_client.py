"""Deepgram STT (prerecorded) + TTS over REST (Req 3, 8).

Per-question utterances are transcribed with a single prerecorded call (simpler and
more reliable than live streaming for a 5-question check-in). Both functions return
None when no key is configured, so the app degrades gracefully to text/demo input.
"""
from __future__ import annotations

import httpx

from ..config import settings

_BASE = "https://api.deepgram.com/v1"


def available() -> bool:
    return bool(settings.deepgram_api_key)


async def transcribe(audio: bytes, content_type: str = "audio/webm") -> str | None:
    if not settings.deepgram_api_key or not audio:
        return None
    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        "Content-Type": content_type,
    }
    params = {"model": "nova-2", "smart_format": "true", "punctuate": "true"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE}/listen", headers=headers, params=params, content=audio)
        resp.raise_for_status()
        data = resp.json()
    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript or None
    except (KeyError, IndexError):
        return None


async def synthesize(text: str, voice: str = "aura-2-thalia-en") -> bytes | None:
    if not settings.deepgram_api_key or not text:
        return None
    headers = {
        "Authorization": f"Token {settings.deepgram_api_key}",
        "Content-Type": "application/json",
    }
    params = {"model": voice, "encoding": "mp3"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE}/speak", headers=headers, params=params, json={"text": text})
        resp.raise_for_status()
        return resp.content
