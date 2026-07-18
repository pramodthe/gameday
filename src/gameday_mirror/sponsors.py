from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from gameday_mirror.lyzr import invoke_json

EMBED_DIM = 256

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


class PlanAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    eyebrow: str
    title: str
    detail: str


class ReadinessPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[PlanAction] = Field(min_length=3, max_length=3)


def _hash_embedding(text: str, dimensions: int = EMBED_DIM) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += -1.0 if digest[4] & 1 else 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _embedding(text: str) -> list[float]:
    """Semantic embedding via OpenAI when configured, else a deterministic hash sketch.

    Both paths return an ``EMBED_DIM``-length vector so the same Qdrant collection
    accepts either, keeping the demo functional without an API key.
    """
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return _hash_embedding(text)
    model = (os.environ.get("OPENAI_EMBEDDING_MODEL") or "text-embedding-3-small").strip()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "input": text, "dimensions": EMBED_DIM},
            )
            response.raise_for_status()
            vector = response.json()["data"][0]["embedding"]
            if isinstance(vector, list) and len(vector) == EMBED_DIM:
                return [float(value) for value in vector]
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        pass
    return _hash_embedding(text)


def _qdrant_headers() -> dict[str, str]:
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    return {"api-key": key, "Content-Type": "application/json"}


def retrieve_memories(user_id: str, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    url = (os.environ.get("QDRANT_URL") or "").rstrip("/")
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    if not (url and key):
        return []
    collection = os.environ.get("QDRANT_MIRROR_COLLECTION", "gameday_memories_v2")
    payload = {
        "query": _embedding(query),
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


def _store_memory_payload(user_id: str, room_name: str, summary: str, payload: dict[str, Any]) -> bool:
    url = (os.environ.get("QDRANT_URL") or "").rstrip("/")
    key = (os.environ.get("QDRANT_API_KEY") or "").strip()
    if not (url and key):
        return False
    collection = os.environ.get("QDRANT_MIRROR_COLLECTION", "gameday_memories_v2")
    try:
        with httpx.Client(timeout=10.0) as client:
            client.put(
                f"{url}/collections/{collection}",
                headers=_qdrant_headers(),
                json={"vectors": {"size": EMBED_DIM, "distance": "Cosine"}},
            )
            index_response = client.put(
                f"{url}/collections/{collection}/index?wait=true",
                headers=_qdrant_headers(),
                json={"field_name": "user_id", "field_schema": "keyword"},
            )
            index_response.raise_for_status()
            response = client.put(
                f"{url}/collections/{collection}/points?wait=true",
                headers=_qdrant_headers(),
                json={
                    "points": [
                        {
                            "id": str(uuid4()),
                            "vector": _embedding(summary),
                            "payload": {
                                "user_id": user_id,
                                "session_id": room_name,
                                "summary": summary,
                                **payload,
                            },
                        }
                    ]
                },
            )
            response.raise_for_status()
            return True
    except (httpx.HTTPError, ValueError, TypeError):
        return False


def store_memory(user_id: str, room_name: str, summary: str, actions: list[dict[str, Any]]) -> bool:
    return _store_memory_payload(user_id, room_name, summary, {"kind": "checkin", "actions": actions})


def store_performance_memory(
    user_id: str,
    room_name: str,
    movement: str,
    pose_metrics: dict[str, Any],
    analysis: dict[str, Any],
    adaptation: dict[str, Any] | None,
) -> bool:
    reps = int(pose_metrics.get("reps") or 0)
    score = int(analysis.get("score") or 0)
    summary = (
        f"{movement.replace('_', ' ')} set: {reps} verified reps, score {score}/100. "
        f"{analysis.get('headline') or 'Set completed'}."
    )
    return _store_memory_payload(
        user_id,
        room_name,
        summary,
        {
            "kind": "movement",
            "movement": movement,
            "pose_metrics": pose_metrics,
            "analysis": analysis,
            "adaptation": adaptation,
        },
    )


def generate_plan(
    answers: list[dict[str, str]],
    memories: list[dict[str, Any]],
    *,
    session_id: str,
    user_id: str,
) -> tuple[list[dict[str, str]], str]:
    prompt = (
        "You are the GameDay Performance Director. Create exactly three concise, safe actions for a student "
        "athlete's day. Use relevant memory only when it changes a recommendation. Return only a JSON object "
        "with an actions array containing id, eyebrow, title, and detail. Avoid diagnosis or financial advice.\n"
        f"Answers: {json.dumps(answers)}\nMemories: {json.dumps(memories[:3])}"
    )
    parsed, _ = invoke_json(
        "plan",
        prompt,
        session_id=session_id,
        user_id=user_id,
        memory_used=bool(memories),
    )
    if isinstance(parsed, dict):
        parsed = parsed.get("actions")
    if isinstance(parsed, list) and len(parsed) == 3 and all(isinstance(item, dict) for item in parsed):
        required = {"id", "eyebrow", "title", "detail"}
        if all(required.issubset(item) for item in parsed):
            return [{str(key): str(value) for key, value in item.items()} for item in parsed], "lyzr"
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
