from __future__ import annotations

import json
import os
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


ExerciseCategory = Literal["strength", "mobility", "cardio", "balance", "recovery"]
ExerciseDifficulty = Literal["beginner", "intermediate", "advanced"]
MotionPattern = Literal[
    "squat",
    "lunge",
    "hinge",
    "push",
    "pull",
    "plank",
    "rotation",
    "jump",
    "stretch",
    "generic",
]


class LessonStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    instruction: str
    phase: Literal["setup", "move", "finish"]


class ExerciseLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_name: str
    category: ExerciseCategory
    difficulty: ExerciseDifficulty
    summary: str
    equipment: list[str]
    primary_muscles: list[str]
    steps: list[LessonStep]
    form_cues: list[str]
    avoid: list[str]
    prescription: str
    tempo: str
    safety_note: str
    motion_pattern: MotionPattern
    camera_support: Literal["squat", "pushup", "lunge", "plank", "glute_bridge", "none"]


FALLBACK_LIBRARY: dict[str, dict[str, object]] = {
    "squat": {
        "exercise_name": "Bodyweight Squat",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Build lower-body strength while practicing controlled hip, knee, and ankle motion.",
        "equipment": ["Bodyweight"],
        "primary_muscles": ["Quads", "Glutes", "Core"],
        "steps": [
            {"title": "Set", "instruction": "Stand tall with feet about shoulder-width apart and toes slightly turned out.", "phase": "setup"},
            {"title": "Lower", "instruction": "Sit your hips down between your feet while keeping your whole foot planted.", "phase": "move"},
            {"title": "Stand", "instruction": "Drive through both feet and finish tall without snapping the knees back.", "phase": "finish"},
        ],
        "form_cues": ["Keep knees tracking over toes", "Brace before each rep", "Keep heels planted"],
        "avoid": ["Knees collapsing inward", "Rushing the bottom position"],
        "prescription": "2–3 sets × 6–10 reps",
        "tempo": "3 seconds down · 1 second up",
        "safety_note": "Use a pain-free range and stop if you feel sharp or worsening pain.",
        "motion_pattern": "squat",
        "camera_support": "squat",
    },
    "lunge": {
        "exercise_name": "Reverse Lunge",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Train single-leg strength and balance with a controlled backward step.",
        "equipment": ["Bodyweight"],
        "primary_muscles": ["Glutes", "Quads", "Core"],
        "steps": [
            {"title": "Set", "instruction": "Stand tall with feet under your hips and brace your trunk.", "phase": "setup"},
            {"title": "Step", "instruction": "Reach one foot back and lower both knees while keeping the front foot planted.", "phase": "move"},
            {"title": "Return", "instruction": "Push through the front foot to return tall, then switch sides.", "phase": "finish"},
        ],
        "form_cues": ["Keep front knee over mid-foot", "Stay tall through the torso", "Land softly behind you"],
        "avoid": ["Front heel lifting", "Dropping quickly onto the back knee"],
        "prescription": "2–3 sets × 6–8 each side",
        "tempo": "2 seconds down · controlled return",
        "safety_note": "Shorten the step or range if balance breaks down; stop for sharp pain.",
        "motion_pattern": "lunge",
        "camera_support": "lunge",
    },
    "push": {
        "exercise_name": "Push-Up",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Build pushing strength while keeping the trunk and hips moving as one unit.",
        "equipment": ["Floor space"],
        "primary_muscles": ["Chest", "Triceps", "Core"],
        "steps": [
            {"title": "Set", "instruction": "Place hands just outside shoulder width and form a straight line from head to heels.", "phase": "setup"},
            {"title": "Lower", "instruction": "Bend the elbows about 30–45 degrees from your body and lower with control.", "phase": "move"},
            {"title": "Press", "instruction": "Push the floor away while keeping ribs and hips connected.", "phase": "finish"},
        ],
        "form_cues": ["Squeeze glutes", "Keep neck long", "Move chest and hips together"],
        "avoid": ["Hips sagging", "Elbows flaring straight sideways"],
        "prescription": "2–4 sets × 5–12 reps",
        "tempo": "2 seconds down · 1 second up",
        "safety_note": "Use an elevated surface if floor reps lose control; stop for sharp pain.",
        "motion_pattern": "push",
        "camera_support": "pushup",
    },
    "plank": {
        "exercise_name": "Forearm Plank",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Practice full-body tension and trunk control without spinal movement.",
        "equipment": ["Floor space"],
        "primary_muscles": ["Core", "Shoulders", "Glutes"],
        "steps": [
            {"title": "Set", "instruction": "Place elbows under shoulders and extend both legs behind you.", "phase": "setup"},
            {"title": "Brace", "instruction": "Tighten your stomach and glutes while pushing the floor away.", "phase": "move"},
            {"title": "Hold", "instruction": "Breathe quietly and maintain a straight line from head to heels.", "phase": "finish"},
        ],
        "form_cues": ["Pull ribs toward hips", "Push through forearms", "Keep glutes active"],
        "avoid": ["Lower back sagging", "Holding your breath"],
        "prescription": "3 holds × 15–30 seconds",
        "tempo": "Steady breathing throughout",
        "safety_note": "End the hold when alignment breaks or if you feel sharp pain.",
        "motion_pattern": "plank",
        "camera_support": "plank",
    },
    "glute_bridge": {
        "exercise_name": "Glute Bridge",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Strengthen the glutes and posterior chain by driving the hips to full extension.",
        "equipment": ["Floor space"],
        "primary_muscles": ["Glutes", "Hamstrings", "Core"],
        "steps": [
            {"title": "Set", "instruction": "Lie on your back with knees bent and feet flat, hip-width apart.", "phase": "setup"},
            {"title": "Drive", "instruction": "Push through your heels to lift your hips into a straight shoulder-to-knee line.", "phase": "move"},
            {"title": "Lower", "instruction": "Squeeze your glutes at the top, then lower with control without dropping.", "phase": "finish"},
        ],
        "form_cues": ["Squeeze glutes at the top", "Keep ribs down", "Keep hips level"],
        "avoid": ["Overarching the lower back", "Pushing through your toes"],
        "prescription": "2–3 sets × 10–15 reps",
        "tempo": "1 second up · 2 seconds down",
        "safety_note": "Reduce range if you feel it in your lower back; stop for sharp pain.",
        "motion_pattern": "hinge",
        "camera_support": "glute_bridge",
    },
    "hinge": {
        "exercise_name": "Bodyweight Hip Hinge",
        "category": "strength",
        "difficulty": "beginner",
        "summary": "Learn to load the hips while keeping the trunk braced and knees softly bent.",
        "equipment": ["Bodyweight"],
        "primary_muscles": ["Hamstrings", "Glutes", "Core"],
        "steps": [
            {"title": "Set", "instruction": "Stand tall with soft knees and hands on your hip creases.", "phase": "setup"},
            {"title": "Reach", "instruction": "Push your hips backward as your torso tips forward as one solid unit.", "phase": "move"},
            {"title": "Finish", "instruction": "Drive the floor away and squeeze your glutes to stand tall.", "phase": "finish"},
        ],
        "form_cues": ["Send hips back", "Keep shins nearly vertical", "Maintain a long spine"],
        "avoid": ["Turning it into a squat", "Rounding to reach lower"],
        "prescription": "2–3 sets × 8–12 reps",
        "tempo": "3 seconds back · 1 second stand",
        "safety_note": "Use a smaller range if you cannot maintain control; stop for sharp pain.",
        "motion_pattern": "hinge",
        "camera_support": "none",
    },
}


def _fallback_key(exercise_name: str) -> str:
    normalized = exercise_name.lower()
    if "bridge" in normalized or "glute" in normalized:
        return "glute_bridge"
    if "lunge" in normalized or "split squat" in normalized:
        return "lunge"
    if "push" in normalized:
        return "push"
    if "plank" in normalized:
        return "plank"
    if any(word in normalized for word in ("deadlift", "hinge", "good morning")):
        return "hinge"
    return "squat"


def fallback_lesson(exercise_name: str) -> dict[str, object]:
    lesson = ExerciseLesson.model_validate(FALLBACK_LIBRARY[_fallback_key(exercise_name)])
    return {**lesson.model_dump(), "source": "curated_fallback"}


def _response_text(payload: dict[str, object]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response did not include output items.")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise ValueError(str(part.get("refusal") or "Exercise lesson was refused."))
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                return str(part["text"])
    raise ValueError("OpenAI response did not include lesson text.")


async def generate_exercise_lesson(exercise_name: str) -> dict[str, object]:
    clean_name = re.sub(r"[^a-zA-Z0-9 '\-]", "", exercise_name).strip()[:80]
    if not clean_name:
        clean_name = "bodyweight squat"
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return fallback_lesson(clean_name)

    model = (os.environ.get("OPENAI_LESSON_MODEL") or "gpt-5.6-terra").strip()
    request = {
        "model": model,
        "store": False,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1200,
        "input": [
            {
                "role": "developer",
                "content": (
                    "Create a concise exercise teaching card for a generally healthy athlete. "
                    "Use the simplest bodyweight version when the request is ambiguous. Give exactly three steps, "
                    "three short form cues, and two common mistakes. Do not diagnose, prescribe rehabilitation, "
                    "promise outcomes, or encourage training through pain. Select the closest motion_pattern enum. "
                    "Set camera_support to the matching live-tracked movement when the exercise clearly is one of: "
                    "squat, pushup, lunge, plank, or glute_bridge; otherwise use none."
                ),
            },
            {"role": "user", "content": f"Teach me: {clean_name}"},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "exercise_lesson",
                "strict": True,
                "schema": ExerciseLesson.model_json_schema(),
            }
        },
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json=request,
            )
            response.raise_for_status()
        lesson = ExerciseLesson.model_validate(json.loads(_response_text(response.json())))
        return {**lesson.model_dump(), "source": model}
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        return fallback_lesson(clean_name)
