from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any
from uuid import uuid4

import httpx

DEFAULT_PLAN = [
    {
        "id": "fuel",
        "eyebrow": "Before noon",
        "title": "Refuel on purpose",
        "detail": "Eat one balanced meal and finish a full bottle of water before the afternoon.",
    },
    {
        "id": "recover",
        "eyebrow": "Before practice",
        "title": "Protect the evening session",
        "detail": "Take a 20-minute recovery reset instead of adding extra training volume.",
    },
    {
        "id": "spend",
        "eyebrow": "Off field",
        "title": "Hold the $15 line",
        "detail": "Use the meal already available and keep dining spend under today’s target.",
    },
]


def _hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _qdrant_headers() -> dict[str, str]:
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    return {"api-key": key, "Content-Type": "application/json"}


def retrieve_memories(user_id: str, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    url = (os.environ.get("QDRANT_URL") or "").rstrip("/")
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    if not (url and key):
        return []
    collection = os.environ.get("QDRANT_MIRROR_COLLECTION", "gameday_memories")
    payload = {
        "query": _hash_embedding(query),
        "filter": {"must": [{"key": "user_id", "match": {"value": user_id}}]},
        "limit": limit,
        "with_payload": True,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                f"{url}/collections/{collection}/points/query",
                headers=_qdrant_headers(),
                json=payload,
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            points = response.json().get("result", {}).get("points", [])
            return [point.get("payload", {}) for point in points if point.get("payload")]
    except (httpx.HTTPError, ValueError, TypeError):
        return []


def store_memory(user_id: str, room_name: str, summary: str, actions: list[dict[str, Any]]) -> bool:
    url = (os.environ.get("QDRANT_URL") or "").rstrip("/")
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    if not (url and key):
        return False
    collection = os.environ.get("QDRANT_MIRROR_COLLECTION", "gameday_memories")
    try:
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"{url}/collections/{collection}",
                headers=_qdrant_headers(),
                json={"vectors": {"size": 64, "distance": "Cosine"}},
            )
            response = client.put(
                f"{url}/collections/{collection}/points?wait=true",
                headers=_qdrant_headers(),
                json={
                    "points": [
                        {
                            "id": str(uuid4()),
                            "vector": _hash_embedding(summary),
                            "payload": {
                                "user_id": user_id,
                                "session_id": room_name,
                                "summary": summary,
                                "actions": actions,
                            },
                        }
                    ]
                },
            )
            response.raise_for_status()
            return True
    except (httpx.HTTPError, ValueError, TypeError):
        return False


def generate_plan(answers: list[dict[str, str]], memories: list[dict[str, Any]]) -> tuple[list[dict[str, str]], str]:
    api_key = (os.environ.get("LYZR_API_KEY") or "").strip()
    agent_id = (os.environ.get("LYZR_AGENT_ID") or "").strip()
    if not (api_key and agent_id):
        return DEFAULT_PLAN, "deterministic"
    prompt = (
        "Create exactly three concise, safe actions for a student athlete's day. "
        "Return only a JSON array with id, eyebrow, title, and detail. Avoid diagnosis or financial advice.\n"
        f"Answers: {json.dumps(answers)}\nMemories: {json.dumps(memories[:3])}"
    )
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                "https://agent-prod.studio.lyzr.ai/v3/inference/chat/",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "user_id": os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo"),
                    "agent_id": agent_id,
                    "session_id": f"gameday-{uuid4().hex}",
                    "message": prompt,
                },
            )
            response.raise_for_status()
            body = response.json()
            raw = body.get("response") or body.get("message") or body.get("content") or body
            if isinstance(raw, str):
                match = re.search(r"\[[\s\S]*\]", raw)
                parsed = json.loads(match.group(0) if match else raw)
            else:
                parsed = raw
            if isinstance(parsed, list) and len(parsed) == 3:
                return [{str(key): str(value) for key, value in item.items()} for item in parsed], "lyzr"
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        pass
    return DEFAULT_PLAN, "deterministic"


def validate_plan(actions: list[dict[str, str]]) -> tuple[list[dict[str, str]], str]:
    text = "\n".join(f"{action.get('title', '')}: {action.get('detail', '')}" for action in actions)
    risky = re.compile(r"\b(diagnose|prescribe|guaranteed return|invest all|ignore pain|play through injury)\b", re.I)
    if risky.search(text):
        return DEFAULT_PLAN, "rules_rewritten"
    api_key = (os.environ.get("ENKRYPTAI_API_KEY") or os.environ.get("ENKRYPT_API_KEY") or "").strip()
    if not api_key:
        return actions, "rules_checked"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.enkryptai.com/guardrails/detect",
                headers={"apikey": api_key, "Content-Type": "application/json"},
                json={"text": text},
            )
            response.raise_for_status()
            summary = response.json().get("summary", {})
            blocked = any(
                bool(summary.get(key))
                for key in ("nsfw", "toxicity", "injection_attack", "policy_violation")
            )
            return (DEFAULT_PLAN, "enkrypt_rewritten") if blocked else (actions, "enkrypt_passed")
    except (httpx.HTTPError, ValueError, TypeError):
        return actions, "rules_checked_enkrypt_unavailable"
