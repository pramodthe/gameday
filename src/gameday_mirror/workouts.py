"""Workout planner: generate a structured, recovery-aware training session.

The planner may only program exercises the camera coach can actually track, so
``motion_pattern`` is constrained to the Core-5 tracked-movement library. Mirrors
the structured-output + curated-fallback pattern in ``lessons.py`` and stays fully
functional with no OpenAI key via ``WORKOUT_FALLBACK_LIBRARY``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from gameday_mirror.lessons import _response_text
from gameday_mirror.lyzr import invoke_json_async
from gameday_mirror.sponsors import validate_plan
from gameday_mirror.superflow import invoke_adaptation

TrackedMovement = Literal["squat", "pushup", "lunge", "plank", "glute_bridge"]
WorkoutIntensity = Literal["recovery", "moderate", "hard"]


class WorkoutExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    motion_pattern: TrackedMovement
    sets: int
    reps: int  # per set; 0 for timed holds (plank)
    hold_seconds: int  # for holds; 0 for rep-based movements
    rest_seconds: int
    coaching_cue: str


class WorkoutSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    focus: str
    intensity: WorkoutIntensity
    estimated_minutes: int
    summary: str
    exercises: list[WorkoutExercise]


class WorkoutAdaptation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["continue", "reduce_reps", "increase_rest", "replace_exercise", "finish"]
    message: str
    reason: str
    next_reps: int | None = Field(..., ge=1, le=20)
    next_hold_seconds: int | None = Field(..., ge=10, le=60)
    next_rest_seconds: int | None = Field(..., ge=15, le=180)
    replacement_movement: TrackedMovement | None


def _ex(name: str, pattern: str, sets: int, reps: int, hold: int, rest: int, cue: str) -> dict[str, object]:
    return {
        "name": name,
        "motion_pattern": pattern,
        "sets": sets,
        "reps": reps,
        "hold_seconds": hold,
        "rest_seconds": rest,
        "coaching_cue": cue,
    }


WORKOUT_FALLBACK_LIBRARY: dict[str, dict[str, object]] = {
    "recovery": {
        "title": "Recovery reset",
        "focus": "Mobility and low-impact activation",
        "intensity": "recovery",
        "estimated_minutes": 12,
        "summary": "A light, joint-friendly session to move well and protect a low-recovery day.",
        "exercises": [
            _ex("Glute Bridge", "glute_bridge", 2, 12, 0, 45, "Squeeze your glutes at the top; keep it smooth."),
            _ex("Forearm Plank", "plank", 2, 0, 20, 45, "Hold a straight line and breathe steadily."),
            _ex("Reverse Lunge", "lunge", 2, 8, 0, 45, "Stay tall and move with control, no rushing."),
        ],
    },
    "moderate": {
        "title": "Full-body base",
        "focus": "Balanced strength across legs, push, and core",
        "intensity": "moderate",
        "estimated_minutes": 22,
        "summary": "A steady bodyweight session covering the main movement patterns.",
        "exercises": [
            _ex("Bodyweight Squat", "squat", 3, 10, 0, 60, "Sit to depth and drive through both feet."),
            _ex("Push-Up", "pushup", 3, 8, 0, 60, "Straight line from shoulders to heels; chest to depth."),
            _ex("Reverse Lunge", "lunge", 3, 8, 0, 60, "Front shin vertical; push through the front heel."),
            _ex("Forearm Plank", "plank", 3, 0, 30, 45, "Brace your core and hold level hips."),
        ],
    },
    "hard": {
        "title": "Strength builder",
        "focus": "Higher-volume full-body strength",
        "intensity": "hard",
        "estimated_minutes": 30,
        "summary": "A fuller session for a well-recovered day, still bodyweight and joint-friendly.",
        "exercises": [
            _ex("Bodyweight Squat", "squat", 4, 12, 0, 60, "Control the descent; explode up."),
            _ex("Push-Up", "pushup", 4, 10, 0, 60, "Full range, no sagging hips."),
            _ex("Reverse Lunge", "lunge", 3, 10, 0, 60, "Keep your torso tall over the front leg."),
            _ex("Glute Bridge", "glute_bridge", 3, 15, 0, 45, "Pause and squeeze at full extension."),
            _ex("Forearm Plank", "plank", 3, 0, 40, 45, "Hold a rigid line; don't let hips drop."),
        ],
    },
}


def _intensity_for(recovery_status: str) -> str:
    status = (recovery_status or "").strip().lower()
    if status in {"attention", "risk", "low", "poor"}:
        return "recovery"
    if status in {"high", "peak", "strong"}:
        return "hard"
    return "moderate"


def fallback_workout(recovery_status: str = "") -> dict[str, Any]:
    session = WorkoutSession.model_validate(WORKOUT_FALLBACK_LIBRARY[_intensity_for(recovery_status)])
    return {
        **session.model_dump(),
        "source": "curated_fallback",
        "decision_trace": [
            "Performance Director fallback activated",
            "Recovery level matched to the Core-5 library",
            "Safe curated exercise dose selected",
        ],
    }


def fallback_adaptation(
    movement: str,
    pose_metrics: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    score = int(analysis.get("score") or 0)
    reps = int(pose_metrics.get("reps") or 0)
    if score < 55:
        action = "reduce_reps"
        message = "Reduce the next set and prioritize clean, controlled reps."
        reason = "The latest movement score needs a technique-first adjustment."
        next_reps = max(3, reps - 2) if reps else 5
        next_rest = 90
    elif score < 75:
        action = "increase_rest"
        message = "Take a longer reset, then repeat with the strongest form cue."
        reason = "The set was useful, but more recovery should improve movement quality."
        next_reps = reps or None
        next_rest = 75
    else:
        action = "continue"
        message = "Keep the current dose and carry the best cue into the next set."
        reason = "The verified score supports continuing without increasing load."
        next_reps = reps or None
        next_rest = 45
    return {
        "action": action,
        "message": message,
        "reason": reason,
        "next_reps": next_reps,
        "next_hold_seconds": None,
        "next_rest_seconds": next_rest,
        "replacement_movement": None,
        "source": "deterministic",
        "decision_trace": [
            f"Verified {movement.replace('_', ' ')} result received",
            "Deterministic adaptation fallback applied",
            "Next-set dose kept inside safe limits",
        ],
    }


async def adapt_after_set(
    movement: str,
    pose_metrics: dict[str, Any],
    analysis: dict[str, Any],
    memory: list[dict[str, Any]],
    *,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    prompt = (
        "You are the GameDay Adaptation Agent. Decide the safest next action after one camera-verified exercise set. "
        "Choose continue, reduce_reps, increase_rest, replace_exercise, or finish. Do not diagnose or prescribe "
        "rehabilitation. Use memory only when directly relevant. Return only JSON matching this schema: "
        f"{json.dumps(WorkoutAdaptation.model_json_schema())}\n"
        f"Movement: {movement}\nPose metrics: {json.dumps(pose_metrics)}\n"
        f"Analysis: {json.dumps(analysis)}\nRelevant memories: {json.dumps(memory[:3])}"
    )
    parsed, meta = await invoke_adaptation(
        prompt,
        session_id=session_id,
        user_id=user_id,
        memory_used=bool(memory),
    )
    if parsed is None:
        parsed, meta = await invoke_json_async(
            "adaptation",
            prompt,
            session_id=session_id,
            user_id=user_id,
            memory_used=bool(memory),
            timeout=20.0,
        )
    if isinstance(parsed, dict):
        try:
            adaptation = WorkoutAdaptation.model_validate(parsed)
        except ValueError:
            adaptation = None
        if adaptation is not None:
            _, safety_status = validate_plan([{"title": adaptation.action, "detail": adaptation.message}])
            if safety_status not in {"rules_rewritten", "enkrypt_rewritten"}:
                return {
                    **adaptation.model_dump(),
                    "source": "lyzr",
                    "decision_trace": [
                        "Lyzr SuperFlow ran the verified-set adaptation" if meta.get("workflow") else "Lyzr Adaptation Agent reviewed the verified set",
                        "Relevant performance memory influenced the next action" if memory else "No prior performance memory was required",
                        "Enkrypt safety policy validated the adjustment",
                    ],
                    "orchestration": meta,
                }
    fallback = fallback_adaptation(movement, pose_metrics, analysis)
    fallback["orchestration"] = meta
    return fallback


async def generate_workout(
    goal: str,
    recovery_status: str = "",
    memory: str = "",
    *,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    schema = json.dumps(WorkoutSession.model_json_schema())
    lyzr_prompt = (
        "You are the GameDay Workout Architect inside a Performance Director workflow. Program one bodyweight "
        "session with 3 to 5 exercises. Use only squat, pushup, lunge, plank, or glute_bridge as motion_pattern. "
        "For plank use hold_seconds 10-60 and reps 0. For other movements use reps 5-15 and hold_seconds 0. "
        "Adjust volume to recovery and relevant athlete memory. Never diagnose or encourage training through pain. "
        f"Return only JSON matching this schema: {schema}\n"
        f"Goal: {goal or 'general fitness'}\nRecovery: {recovery_status or 'unknown'}\n"
        f"Relevant memory: {memory or 'none'}"
    )
    lyzr_result, lyzr_meta = await invoke_json_async(
        "workout",
        lyzr_prompt,
        session_id=session_id,
        user_id=user_id,
        memory_used=bool(memory),
    )
    if isinstance(lyzr_result, dict):
        try:
            session = WorkoutSession.model_validate(lyzr_result)
        except ValueError:
            session = None
        if session is not None and session.exercises:
            actions = [{"title": exercise.name, "detail": exercise.coaching_cue} for exercise in session.exercises]
            _, safety_status = validate_plan(actions)
            if safety_status not in {"rules_rewritten", "enkrypt_rewritten"}:
                return {
                    **session.model_dump(),
                    "source": "lyzr",
                    "decision_trace": [
                        "Lyzr Performance Director recalled athlete context",
                        "Lyzr Workout Architect programmed the Core-5 session",
                        "Enkrypt safety policy validated the coaching dose",
                    ],
                    "orchestration": lyzr_meta,
                }

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return fallback_workout(recovery_status)
    model = (os.environ.get("OPENAI_LESSON_MODEL") or "gpt-5.6-terra").strip()

    developer = (
        "Program ONE bodyweight training session of 3 to 5 exercises for a generally healthy athlete. "
        "Choose motion_pattern ONLY from: squat, pushup, lunge, plank, glute_bridge. "
        "For plank use hold_seconds (10-60) with reps 0; for every other movement use reps (5-15) with hold_seconds 0. "
        "Tailor total volume to recovery: for low recovery, prescribe a shorter, lighter recovery session. "
        "Give each exercise one short coaching_cue. Do not diagnose, prescribe rehabilitation, or push through pain."
    )
    user = (
        f"Athlete goal: {goal or 'general fitness'}. "
        f"Recovery status: {recovery_status or 'unknown'}. "
        f"Recent context: {memory or 'none'}."
    )
    body = {
        "model": model,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1400,
        "input": [
            {"role": "developer", "content": developer},
            {"role": "user", "content": user},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workout_session",
                "strict": True,
                "schema": WorkoutSession.model_json_schema(),
            }
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            session = WorkoutSession.model_validate(json.loads(_response_text(response.json())))
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError):
        return fallback_workout(recovery_status)

    if not session.exercises:
        return fallback_workout(recovery_status)
    # Safety guardrail on the coaching language, reusing the plan validator.
    actions = [{"title": ex.name, "detail": ex.coaching_cue} for ex in session.exercises]
    _, status = validate_plan(actions)
    if status in {"rules_rewritten", "enkrypt_rewritten"}:
        return fallback_workout(recovery_status)
    return {
        **session.model_dump(),
        "source": model,
        "decision_trace": [
            "Lyzr response unavailable or invalid",
            "OpenAI structured-output fallback programmed the session",
            "Enkrypt safety policy validated the coaching dose",
        ],
        "orchestration": lyzr_meta,
    }
