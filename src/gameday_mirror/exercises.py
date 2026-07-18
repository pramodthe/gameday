from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def is_exercise_request(transcript: str) -> bool:
    normalized = " ".join(transcript.lower().split())
    direct_phrases = (
        "start exercise",
        "do an exercise",
        "do a workout",
        "check my form",
        "check my squat",
        "check my pushup",
        "check my push-up",
        "check my lunge",
        "check my plank",
        "check my glute bridge",
        "squat exercise",
        "practice squats",
        "practice pushups",
        "practice push-ups",
        "practice lunges",
        "practice plank",
        "practice glute bridges",
        "start squats",
        "start pushups",
        "start push-ups",
        "start lunges",
        "start plank",
        "start glute bridges",
        "movement session",
        "teach me",
        "show me how",
        "demonstrate",
        "how do i do",
        "how to do",
    )
    return any(phrase in normalized for phrase in direct_phrases)


def exercise_context_update(event: Mapping[str, Any]) -> str | None:
    event_type = str(event.get("type") or "")
    reps = int(event.get("reps") or 0)
    target_reps = int(event.get("target_reps") or 5)
    cue = str(event.get("cue") or "").strip()
    exercise_name = str(event.get("exercise_name") or "exercise").strip()
    # The tracked-movement label for sensor strings; defaults to squat for the
    # legacy squat-only voice flow (and so existing telemetry stays unchanged).
    movement = str(event.get("exercise") or "squat").replace("_", " ").strip()

    if event_type == "exercise_lesson_loading":
        return f"Exercise lesson: building a visual {exercise_name} guide now."
    if event_type == "exercise_lesson_ready":
        summary = str(event.get("summary") or "The visual guide is ready.").strip()
        form_cues = event.get("form_cues")
        cue_text = ""
        if isinstance(form_cues, list):
            cue_text = " Key cues: " + "; ".join(str(item).strip() for item in form_cues[:3] if str(item).strip())
        return f"Exercise lesson: the {exercise_name} visual guide is ready. {summary}{cue_text}".strip()
    if event_type == "exercise_lesson_failed":
        return f"Exercise lesson: the {exercise_name} guide could not be generated. Offer another exercise or try again."
    if event_type == "exercise_lesson_closed":
        return f"Exercise lesson: the athlete closed the {exercise_name} visual guide."

    if event_type == "exercise_opened":
        return f"{movement.capitalize()} exercise opened. The camera is checking whether the athlete's full body is visible."
    if event_type == "exercise_waiting":
        return "Exercise sensor: full body is not visible. Ask the athlete to step back until their working joints are in frame."
    if event_type == "exercise_ready":
        return f"Exercise sensor: full body detected. The {movement} countdown will start automatically."
    if event_type == "exercise_started":
        return f"Exercise sensor: the athlete started a {target_reps}-rep {movement} set."
    if event_type == "exercise_progress":
        return f"Exercise sensor verified {movement} rep {reps} of {target_reps}. {cue}".strip()
    if event_type == "exercise_reset":
        return f"Exercise sensor: the {movement} set was reset and is waiting to begin again."
    if event_type == "exercise_closed":
        return f"Exercise sensor: the athlete closed the {movement} session after {reps} verified reps."
    if event_type != "exercise_completed":
        return None

    analysis = event.get("analysis")
    if not isinstance(analysis, Mapping):
        return f"Exercise sensor: {movement} set complete with {reps} verified reps."
    score = int(analysis.get("score") or 0)
    headline = str(analysis.get("headline") or "Set complete").strip()
    adaptation = event.get("adaptation")
    adaptation_text = ""
    if isinstance(adaptation, Mapping):
        message = str(adaptation.get("message") or "").strip()
        if message:
            adaptation_text = f" Lyzr next-set decision: {message}"
    return (
        f"Exercise sensor: {movement} set complete with {reps} verified reps and score {score} out of 100. "
        f"Result: {headline}. {cue}{adaptation_text}"
    ).strip()


def checkin_resume_context(completed: int, total: int) -> str:
    if completed >= total:
        return (
            "Check-in status: complete. Do not restart readiness questions. "
            "Return the athlete to the generated workout and ask whether to start the next exercise or finish."
        )
    return (
        f"Check-in status: {completed} of {total} primary questions complete. "
        "Resume with the next unanswered question only; never restart from sleep."
    )


def exercise_is_active(event_type: str) -> bool | None:
    if event_type in {
        "exercise_opened",
        "exercise_waiting",
        "exercise_ready",
        "exercise_started",
        "exercise_progress",
        "exercise_reset",
        "exercise_lesson_loading",
        "exercise_lesson_ready",
    }:
        return True
    if event_type in {
        "exercise_completed",
        "exercise_closed",
        "exercise_lesson_failed",
        "exercise_lesson_closed",
    }:
        return False
    return None
