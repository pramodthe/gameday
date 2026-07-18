from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from livekit.api import AccessToken, RoomAgentDispatch, RoomConfiguration, VideoGrants
from pydantic import BaseModel, Field

from gameday_mirror.checkin import CATEGORIES, CHECKIN_TOTAL_STEPS, checkin_complete, completed_steps
from gameday_mirror.persistence import complete_session, ensure_session, record_answer, record_movement_analysis
from gameday_mirror.lessons import generate_exercise_lesson
from gameday_mirror.sponsors import (
    generate_plan,
    retrieve_memories,
    store_memory,
    store_performance_memory,
    validate_plan,
)
from gameday_mirror.vision import analyze_movement, fallback_analysis
from gameday_mirror.workouts import adapt_after_set, generate_workout

router = APIRouter(prefix="/api/mirror", tags=["mirror"])


class MirrorAnswerIn(BaseModel):
    room_name: str = Field(min_length=1, max_length=128)
    category: Literal["sleep", "recovery", "training", "fuel", "mindset", "spending"]
    categories: list[Literal["sleep", "recovery", "training", "fuel", "mindset", "spending"]] = Field(
        default_factory=list,
        max_length=6,
    )
    transcript: str = Field(min_length=1, max_length=2000)
    answers: list[dict[str, str]] = Field(default_factory=list, max_length=64)


class MovementAnalysisIn(BaseModel):
    room_name: str = Field(min_length=1, max_length=128)
    movement: Literal["squat", "pushup", "lunge", "plank", "glute_bridge"] = "squat"
    image_data_url: str = Field(min_length=100, max_length=2_500_000)
    pose_metrics: dict[str, float] = Field(default_factory=dict)


class ExerciseLessonIn(BaseModel):
    exercise_name: str = Field(min_length=2, max_length=80)


class WorkoutIn(BaseModel):
    goal: str = Field(default="", max_length=200)
    recovery_status: str = Field(default="", max_length=40)
    room_name: str = Field(default="", max_length=128)


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
        "lyzr": bool(
            os.environ.get("LYZR_API_KEY")
            and any(
                os.environ.get(name)
                for name in (
                    "LYZR_AGENT_ID",
                    "LYZR_PLAN_AGENT_ID",
                    "LYZR_WORKOUT_AGENT_ID",
                    "LYZR_ADAPTATION_AGENT_ID",
                )
            )
        ),
        "enkrypt": bool(os.environ.get("ENKRYPTAI_API_KEY") or os.environ.get("ENKRYPT_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
    }


def _lyzr_capabilities() -> dict[str, object]:
    specialist_ids = [
        (os.environ.get("LYZR_PLAN_AGENT_ID") or "").strip(),
        (os.environ.get("LYZR_WORKOUT_AGENT_ID") or "").strip(),
        (os.environ.get("LYZR_ADAPTATION_AGENT_ID") or "").strip(),
    ]
    return {
        "manager_agent": bool((os.environ.get("LYZR_MANAGER_AGENT_ID") or "").strip()),
        "specialists": sum(bool(agent_id) for agent_id in specialist_ids),
        "memory": "cognis" if any(specialist_ids) else None,
        "global_context": bool((os.environ.get("LYZR_CONTEXT_ID") or "").strip()),
        "rai_guardrail": bool((os.environ.get("LYZR_RAI_POLICY_ID") or "").strip()),
        "structured_outputs": any(specialist_ids),
        "superflow": bool(
            (os.environ.get("LYZR_SUPERFLOW_ID") or "").strip()
            and (os.environ.get("LYZR_SUPERFLOW_ENABLED") or "").strip().lower()
            not in {"0", "false", "no", "off"}
        ),
        "context_tool_provisioned": bool((os.environ.get("LYZR_CONTEXT_TOOL_ID") or "").strip()),
        "context_tool_enabled": (os.environ.get("LYZR_CONTEXT_TOOL_ENABLED") or "").strip().lower()
        in {"1", "true", "yes"},
    }


def _event(event_type: str, room_name: str, **payload: object) -> dict[str, object]:
    return {
        "type": event_type,
        "session_id": room_name,
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def _word_number(text: str) -> float | None:
    """Parse a spelled-out number ("eight", "twenty five", "seven and a half").

    Speech-to-text often transcribes spoken numbers as words, so digit-only
    parsing would miss "eight hours" and fall back to a default.
    """
    tokens = re.findall(r"[a-z]+", text.lower())
    total: float | None = None
    for i, token in enumerate(tokens):
        if token in _TENS:
            value = _TENS[token]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in _ONES and _ONES[nxt] < 10:
                value += _ONES[nxt]
            total = value
            break
        if token in _ONES:
            total = _ONES[token]
            break
    if total is None:
        return None
    if "half" in tokens:
        total += 0.5
    return float(total)


def _number(text: str) -> float | None:
    match = re.search(r"(?:\$\s*)?(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return _word_number(text)


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
    if category == "recovery":
        low = any(word in lowered for word in ("sore", "ache", "tired", "fatigue", "stiff", "heavy", "exhausted"))
        pct = numeric if (numeric is not None and numeric <= 100) else (45.0 if low else 78.0)
        return {
            "key": "recovery",
            "numeric_value": pct,
            "display_value": f"{pct:g}%",
            "status": "attention" if pct < 60 or low else "good",
            "detail": "Recovery needs attention" if pct < 60 or low else "Recovery on track",
            "unit": "percent",
            "confidence": 0.8 if (numeric is not None or low) else 0.55,
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
    if category == "mindset":
        strained = any(word in lowered for word in ("stress", "nervous", "anxious", "unfocused", "distracted", "worried"))
        return {
            "key": "mindset",
            "numeric_value": 0 if strained else 1,
            "display_value": "Strained" if strained else "Focused",
            "status": "attention" if strained else "good",
            "detail": "Reset focus before load" if strained else "Clear accountability target",
            "unit": "signal",
            "confidence": 0.78,
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


def _memory_summary(answers: list[dict[str, str]], actions: list[dict[str, str]]) -> str:
    """A meaningful, offline-safe recap of the session for semantic recall."""
    today = datetime.now(timezone.utc).date().isoformat()
    # Keep the last answer per category so extra chatter never double-counts a dimension.
    latest: dict[str, str] = {}
    for answer in answers:
        category = str(answer.get("category") or "").strip()
        transcript = str(answer.get("transcript") or "").strip()
        if category and transcript:
            latest[category] = transcript
    parts: list[str] = []
    for category in CATEGORIES:
        if category not in latest:
            continue
        metric = _metric(category, latest[category])
        parts.append(f"{category} {metric['display_value']} ({metric['status']})")
    readiness = "; ".join(parts) if parts else "no readiness answers captured"
    focus = actions[0].get("title") if actions else "recovery-first"
    return f"{today} · {readiness}. Plan focus: {focus}."


@router.get("/config")
def mirror_config() -> dict[str, object]:
    server_url, api_key, api_secret, _ = _livekit_settings()
    return {
        "configured": bool(server_url and api_key and api_secret),
        "serverUrl": server_url or None,
        "sponsors": _sponsor_status(),
        "lyzr": _lyzr_capabilities(),
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
    categories = list(dict.fromkeys(body.categories or [body.category]))
    metrics = [_metric(category, body.transcript) for category in categories]
    for category, metric in zip(categories, metrics, strict=True):
        try:
            record_answer(body.room_name, category=category, transcript=body.transcript, metric=metric)
        except Exception:
            pass
    answers = list(body.answers)
    for category in categories:
        if not any(
            answer.get("category") == category and answer.get("transcript") == body.transcript
            for answer in answers
        ):
            answers.append({"category": category, "transcript": body.transcript})
    captured = {str(answer.get("category") or "") for answer in answers} | set(categories)
    captured.discard("")
    events: list[dict[str, object]] = [
        _event(
            "metric_updated",
            body.room_name,
            metric_key=metric["key"],
            display_value=metric["display_value"],
            detail=metric["detail"],
            status=metric["status"],
            confidence=metric["confidence"],
        )
        for metric in metrics
    ]
    events.append(
        _event(
            "checkin_progressed",
            body.room_name,
            completed_step=completed_steps(captured),
            total_steps=CHECKIN_TOTAL_STEPS,
        )
    )
    if not checkin_complete(captured):
        return {"events": events}

    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    memories = retrieve_memories(profile_id, "recovery training fuel and spending choices", limit=3)
    actions, plan_source = generate_plan(
        answers,
        memories,
        session_id=body.room_name,
        user_id=profile_id,
    )
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
    summary = _memory_summary(answers, actions)
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
        analysis = fallback_analysis(body.pose_metrics, body.movement)
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
    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    try:
        memories = retrieve_memories(
            profile_id,
            f"{body.movement} movement score form coaching next set",
            limit=3,
        )
    except Exception:
        memories = []
    adaptation = await adapt_after_set(
        body.movement,
        body.pose_metrics,
        analysis,
        memories,
        session_id=body.room_name,
        user_id=profile_id,
    )
    try:
        memory_persisted = store_performance_memory(
            profile_id,
            body.room_name,
            body.movement,
            body.pose_metrics,
            analysis,
            adaptation,
        )
    except Exception:
        memory_persisted = False
    return {
        "analysis": analysis,
        "persisted": persisted,
        "memory_persisted": memory_persisted,
        "adaptation": adaptation,
    }


@router.post("/exercise/lesson")
async def exercise_lesson(body: ExerciseLessonIn) -> dict[str, object]:
    return {"lesson": await generate_exercise_lesson(body.exercise_name)}


@router.post("/workout")
async def workout(body: WorkoutIn) -> dict[str, object]:
    profile_id = os.environ.get("INSFORGE_PROFILE_ID", "gameday-demo")
    memory = ""
    try:
        memories = retrieve_memories(profile_id, body.goal or "training readiness workout", limit=1)
        if memories:
            memory = str(memories[0].get("summary") or "")
    except Exception:
        memory = ""
    session_id = body.room_name or f"gameday-{profile_id}"
    return {
        "workout": await generate_workout(
            body.goal,
            body.recovery_status,
            memory,
            session_id=session_id,
            user_id=profile_id,
        )
    }
