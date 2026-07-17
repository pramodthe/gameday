from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from livekit.api import AccessToken, RoomAgentDispatch, RoomConfiguration, VideoGrants
from pydantic import BaseModel, Field

from gameday_mirror.persistence import complete_session, ensure_session, record_answer, record_movement_analysis
from gameday_mirror.sponsors import generate_plan, retrieve_memories, store_memory, validate_plan
from gameday_mirror.vision import analyze_movement, fallback_analysis

router = APIRouter(prefix="/api/mirror", tags=["mirror"])

CATEGORIES = ("sleep", "training", "fuel", "spending")


class MirrorAnswerIn(BaseModel):
    room_name: str = Field(min_length=1, max_length=128)
    category: Literal["sleep", "training", "fuel", "spending"]
    transcript: str = Field(min_length=1, max_length=2000)
    answers: list[dict[str, str]] = Field(default_factory=list, max_length=4)


class MovementAnalysisIn(BaseModel):
    room_name: str = Field(min_length=1, max_length=128)
    movement: Literal["squat"] = "squat"
    image_data_url: str = Field(min_length=100, max_length=2_500_000)
    pose_metrics: dict[str, float] = Field(default_factory=dict)


def _livekit_settings() -> tuple[str, str, str, str]:
    return (
        (os.environ.get("LIVEKIT_URL") or "").strip(),
        (os.environ.get("LIVEKIT_API_KEY") or "").strip(),
        (os.environ.get("LIVEKIT_API_SECRET") or "").strip(),
        (os.environ.get("LIVEKIT_AGENT_NAME") or "gameday-elevenlabs").strip(),
    )


def _sponsor_status() -> dict[str, bool]:
    return {
        "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_AGENT_ID")),
        "insforge": bool(
            os.environ.get("INSFORGE_PROFILE_ID")
            and (os.environ.get("INSFORGE_DATABASE_URL") or (os.environ.get("INSFORGE_URL") and os.environ.get("INSFORGE_API_KEY")))
        ),
        "qdrant": bool(os.environ.get("QDRANT_URL") and os.environ.get("QDRANT_API_KEY")),
        "lyzr": bool(os.environ.get("LYZR_API_KEY") and os.environ.get("LYZR_AGENT_ID")),
        "enkrypt": bool(os.environ.get("ENKRYPTAI_API_KEY") or os.environ.get("ENKRYPT_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }


def _event(event_type: str, room_name: str, **payload: object) -> dict[str, object]:
    return {
        "type": event_type,
        "session_id": room_name,
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


def _number(text: str) -> float | None:
    match = re.search(r"(?:\$\s*)?(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _metric(category: str, transcript: str) -> dict[str, Any]:
    lowered = transcript.lower()
    numeric = _number(transcript)
    if category == "sleep":
        hours = numeric if numeric is not None else 6.0
        return {
            "key": "sleep",
            "numeric_value": hours,
            "display_value": f"{hours:g} hrs",
            "status": "good" if hours >= 7 else "attention",
            "detail": "Recovery protected" if hours >= 7 else "Below the 7-hour target",
            "unit": "hours",
            "confidence": 0.92 if numeric is not None else 0.58,
        }
    if category == "training":
        skipped = any(word in lowered for word in ("rest", "off", "none", "no training"))
        return {
            "key": "training",
            "numeric_value": 0 if skipped else 1,
            "display_value": "Recovery" if skipped else "Planned",
            "status": "attention" if "hard" in lowered or "intense" in lowered else "good",
            "detail": "Rest day" if skipped else "Training load captured",
            "unit": "session",
            "confidence": 0.82,
        }
    if category == "fuel":
        missed = any(word in lowered for word in ("skip", "miss", "nothing", "haven't eaten"))
        return {
            "key": "fuel",
            "numeric_value": 0 if missed else 1,
            "display_value": "Missed" if missed else "On track",
            "status": "risk" if missed else "good",
            "detail": "Meal needs recovery" if missed else "Fuel plan is steady",
            "unit": "signal",
            "confidence": 0.86,
        }
    amount = numeric if numeric is not None else 0
    return {
        "key": "spending",
        "numeric_value": amount,
        "display_value": f"${amount:g}",
        "status": "risk" if amount > 15 or any(word in lowered for word in ("ate out", "overspent")) else "good",
        "detail": "$15 daily target",
        "unit": "usd",
        "confidence": 0.88 if numeric is not None else 0.65,
    }


@router.get("/config")
def mirror_config() -> dict[str, object]:
    server_url, api_key, api_secret, _ = _livekit_settings()
    return {
        "configured": bool(server_url and api_key and api_secret),
        "serverUrl": server_url or None,
        "sponsors": _sponsor_status(),
    }


@router.post("/token")
def mirror_token() -> dict[str, object]:
    server_url, api_key, api_secret, agent_name = _livekit_settings()
    if not (server_url and api_key and api_secret):
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.",
        )

    room_name = f"gameday-{uuid4().hex[:12]}"
    identity = f"athlete-{uuid4().hex[:10]}"
    session_id: str | None = None
    try:
        session = ensure_session(room_name)
        session_id = str(session["id"]) if session else None
    except Exception:
        session_id = None
    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    memories = retrieve_memories(profile_id, "sleep recovery training fuel spending plan", limit=3)
    token = (
        AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(os.environ.get("MIRROR_ATHLETE_NAME", "Jordan Lee"))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            RoomConfiguration(
                agents=[RoomAgentDispatch(agent_name=agent_name)],
            )
        )
        .to_jwt()
    )

    return {
        "configured": True,
        "serverUrl": server_url,
        "token": token,
        "roomName": room_name,
        "sessionId": session_id or room_name,
        "identity": identity,
        "memory": memories[0] if memories else None,
        "sponsors": _sponsor_status(),
    }


@router.get("/sessions/{room_name}/context")
def mirror_context(room_name: str) -> dict[str, object]:
    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    memories = retrieve_memories(profile_id, "today's readiness and prior commitments", limit=3)
    return {
        "roomName": room_name,
        "athleteName": os.environ.get("MIRROR_ATHLETE_NAME", "Jordan"),
        "recentMemory": memories[0].get("summary") if memories else "No prior check-in is available yet.",
        "memories": memories,
    }


@router.post("/answers")
def mirror_answer(body: MirrorAnswerIn) -> dict[str, object]:
    metric = _metric(body.category, body.transcript)
    try:
        record_answer(body.room_name, category=body.category, transcript=body.transcript, metric=metric)
    except Exception:
        pass
    events: list[dict[str, object]] = [
        _event(
            "metric_updated",
            body.room_name,
            metric_key=metric["key"],
            display_value=metric["display_value"],
            detail=metric["detail"],
            status=metric["status"],
            confidence=metric["confidence"],
        ),
        _event(
            "checkin_progressed",
            body.room_name,
            completed_step=CATEGORIES.index(body.category) + 1,
            total_steps=4,
        ),
    ]
    if body.category != "spending":
        return {"events": events}

    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    memories = retrieve_memories(profile_id, "recovery training fuel and spending choices", limit=3)
    actions, plan_source = generate_plan(body.answers, memories)
    actions, safety_status = validate_plan(actions)
    try:
        streak = complete_session(
            body.room_name,
            actions=actions,
            memory_sources=memories,
            safety_status=safety_status,
        )
    except Exception:
        streak = 6
    summary = "Check-in completed with a recovery-first plan and one off-field accountability target."
    store_memory(profile_id, body.room_name, summary, actions)
    if memories:
        events.append(
            _event(
                "memory_used",
                body.room_name,
                message=memories[0].get("summary", "A recent check-in changed today's plan."),
                source_session=memories[0].get("session_id"),
            )
        )
    events.extend(
        [
            _event(
                "plan_ready",
                body.room_name,
                actions=actions,
                plan_source=plan_source,
                safety_status=safety_status,
            ),
            _event("checkin_completed", body.room_name, streak=streak),
        ]
    )
    return {"events": events}


@router.post("/movement/analyze")
async def movement_analysis(body: MovementAnalysisIn) -> dict[str, object]:
    if not body.image_data_url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")):
        raise HTTPException(status_code=422, detail="A JPEG or PNG camera frame is required.")
    try:
        analysis = await analyze_movement(body.image_data_url, body.movement, body.pose_metrics)
    except Exception:
        analysis = fallback_analysis(body.pose_metrics)
    persisted = False
    try:
        persisted = bool(
            record_movement_analysis(
                body.room_name,
                movement=body.movement,
                pose_metrics=body.pose_metrics,
                analysis=analysis,
            )
        )
    except Exception:
        persisted = False
    return {"analysis": analysis, "persisted": persisted}
