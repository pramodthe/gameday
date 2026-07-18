from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

import aiohttp


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# Per-movement scoring rubrics. Each tracked exercise defines how its pose
# metrics map to a form score + coaching cues, so the same analyzer works for
# the whole Core-5 library. Squat keeps its original tuning exactly.
#   kind "flexion"   -> good form reaches a LOW primary angle at the bottom
#   kind "extension" -> good form reaches a HIGH primary angle at the top
#   kind "hold"      -> static hold scored on time + alignment, no reps
MOVEMENT_RUBRICS: dict[str, dict[str, Any]] = {
    "squat": {
        "kind": "flexion",
        "target_angle": 92, "angle_scale": 1.15,
        "sym_scale": 2.5, "align_good": 18,
        "weights": (0.4, 0.35, 0.25),
        "depth_cue_threshold": 115, "sym_cue_threshold": 10, "align_cue_threshold": 25,
        "headline": "Movement baseline captured",
        "summary": "Pose tracking measured your squat depth, symmetry, and torso control.",
        "prompt_hint": "Judge squat depth (aim ~90° knee), knee symmetry, and an upright braced torso.",
        "cues": {
            "depth": "Sit a little deeper while keeping both heels planted.",
            "symmetry": "Drive both knees evenly and keep pressure balanced through both feet.",
            "align": "Brace before descending and keep your chest stacked over your hips.",
        },
        "default_cue": "Keep this tempo and finish each rep with balanced foot pressure.",
    },
    "pushup": {
        "kind": "flexion",
        "target_angle": 88, "angle_scale": 1.0,
        "sym_scale": 2.0, "align_good": 12,
        "weights": (0.45, 0.25, 0.30),
        "depth_cue_threshold": 110, "sym_cue_threshold": 12, "align_cue_threshold": 15,
        "headline": "Push-up mechanics captured",
        "summary": "Pose tracking measured your push-up depth, elbow symmetry, and body-line control.",
        "prompt_hint": "Judge elbow depth (aim ~90° at the bottom) and a straight shoulder-to-heel line (no sagging or piking).",
        "cues": {
            "depth": "Lower until your elbows reach about 90 degrees.",
            "symmetry": "Press evenly through both hands so your shoulders stay square.",
            "align": "Keep a straight line from shoulders to heels — no sagging or piking.",
        },
        "default_cue": "Control the descent and press back to a strong plank position.",
    },
    "lunge": {
        "kind": "flexion",
        "target_angle": 95, "angle_scale": 1.1,
        "sym_scale": 1.5, "align_good": 20,
        "weights": (0.45, 0.20, 0.35),
        "depth_cue_threshold": 120, "sym_cue_threshold": 15, "align_cue_threshold": 25,
        "headline": "Lunge mechanics captured",
        "summary": "Pose tracking measured your front-knee depth and torso control.",
        "prompt_hint": "Judge front-knee depth (aim ~90°), a vertical front shin, and an upright torso.",
        "cues": {
            "depth": "Drop until your front thigh is about parallel to the floor.",
            "symmetry": "Keep your front knee tracking over your toes, not caving inward.",
            "align": "Stay tall through your torso instead of leaning over the front leg.",
        },
        "default_cue": "Push through your front heel and stand tall between reps.",
    },
    "glute_bridge": {
        "kind": "extension",
        "target_angle": 170, "angle_scale": 1.2,
        "sym_scale": 2.0, "align_good": 20,
        "weights": (0.5, 0.2, 0.3),
        "depth_cue_threshold": 155, "sym_cue_threshold": 12, "align_cue_threshold": 25,
        "headline": "Glute bridge captured",
        "summary": "Pose tracking measured your hip extension and control.",
        "prompt_hint": "Judge hip extension (aim for a straight shoulder-hip-knee line at the top) and steady control.",
        "cues": {
            "depth": "Drive your hips higher to full extension and squeeze your glutes at the top.",
            "symmetry": "Keep your hips level as you rise — don't let one side lead.",
            "align": "Keep your ribs down and avoid overarching your lower back.",
        },
        "default_cue": "Pause at the top and lower with control each rep.",
    },
    "plank": {
        "kind": "hold",
        "hold_target": 30, "align_good": 10, "align_scale": 4.0,
        "align_cue_threshold": 12,
        "headline": "Plank hold captured",
        "summary": "Pose tracking measured your plank alignment and hold time.",
        "prompt_hint": "Judge a straight shoulder-hip-heel line held steadily; there are no reps, only hold quality.",
        "cues": {
            "align": "Keep your hips level — one straight line from shoulders to heels.",
        },
        "default_cue": "Brace your core and breathe steadily to extend the hold.",
    },
}


def fallback_analysis(pose_metrics: dict[str, Any], movement: str = "squat") -> dict[str, Any]:
    rubric = MOVEMENT_RUBRICS.get(movement, MOVEMENT_RUBRICS["squat"])
    reps = max(0, int(_number(pose_metrics.get("reps"))))
    symmetry_gap = _number(pose_metrics.get("symmetry_gap"), 30)
    # Accept generalized keys, falling back to the original squat-named keys.
    alignment = _number(
        pose_metrics.get("alignment_deviation", pose_metrics.get("torso_lean")), 30
    )
    min_angle = _number(
        pose_metrics.get("min_primary_angle", pose_metrics.get("min_knee_angle")), 180
    )
    max_angle = _number(pose_metrics.get("max_primary_angle"), 0)
    hold_seconds = _number(pose_metrics.get("hold_seconds"), 0)
    cues: list[str] = []

    if rubric["kind"] == "hold":
        hold_score = max(30, min(100, round(hold_seconds / rubric["hold_target"] * 100)))
        align_score = max(
            30, min(100, round(100 - max(0.0, alignment - rubric["align_good"]) * rubric["align_scale"]))
        )
        score = round(hold_score * 0.55 + align_score * 0.45)
        if alignment > rubric["align_cue_threshold"]:
            cues.append(rubric["cues"]["align"])
        if hold_seconds < rubric["hold_target"]:
            cues.append(f"Hold for the full {rubric['hold_target']} seconds with a braced core.")
        effort = hold_seconds / 10
    else:
        achieved = min_angle if rubric["kind"] == "flexion" else max_angle
        depth_w, sym_w, control_w = rubric["weights"]
        depth_score = max(35, min(100, round(100 - abs(achieved - rubric["target_angle"]) * rubric["angle_scale"])))
        symmetry_score = max(35, min(100, round(100 - symmetry_gap * rubric["sym_scale"])))
        control_score = max(40, min(100, 55 + reps * 15 - max(0.0, alignment - rubric["align_good"])))
        score = round(depth_score * depth_w + symmetry_score * sym_w + control_score * control_w)
        missed_depth = (
            achieved > rubric["depth_cue_threshold"]
            if rubric["kind"] == "flexion"
            else achieved < rubric["depth_cue_threshold"]
        )
        if missed_depth:
            cues.append(rubric["cues"]["depth"])
        if symmetry_gap > rubric["sym_cue_threshold"]:
            cues.append(rubric["cues"]["symmetry"])
        if alignment > rubric["align_cue_threshold"]:
            cues.append(rubric["cues"]["align"])
        effort = reps

    if not cues:
        cues.append(rubric["default_cue"])
    return {
        "score": score,
        "headline": rubric["headline"],
        "summary": rubric["summary"],
        "cues": cues[:3],
        "confidence": round(min(0.92, 0.55 + effort * 0.1), 2),
        "source": "pose_fallback",
    }


def _extract_text(event: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in event.get("response", {}).get("output", []):
        for content in item.get("content", []):
            text = content.get("text") or content.get("transcript")
            if text:
                chunks.append(str(text))
    return "".join(chunks)


def _parse_analysis(raw: str, pose_metrics: dict[str, Any], movement: str, model: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not match:
        raise ValueError("Realtime vision returned no JSON object")
    parsed = json.loads(match.group(0))
    fallback = fallback_analysis(pose_metrics, movement)
    cues = [str(cue).strip() for cue in parsed.get("cues", []) if str(cue).strip()]
    return {
        "score": max(0, min(100, int(_number(parsed.get("score"), fallback["score"])))),
        "headline": str(parsed.get("headline") or fallback["headline"])[:80],
        "summary": str(parsed.get("summary") or fallback["summary"])[:320],
        "cues": (cues or fallback["cues"])[:3],
        "confidence": round(max(0, min(1, _number(parsed.get("confidence"), fallback["confidence"]))), 2),
        "source": model,
    }


async def analyze_movement(
    image_data_url: str,
    movement: str,
    pose_metrics: dict[str, Any],
) -> dict[str, Any]:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    model = (os.environ.get("OPENAI_REALTIME_MODEL") or "gpt-realtime-2.1-mini").strip()
    if not api_key:
        return fallback_analysis(pose_metrics, movement)

    rubric = MOVEMENT_RUBRICS.get(movement, MOVEMENT_RUBRICS["squat"])
    prompt = (
        "You are a concise sports movement coach. Analyze only visible movement mechanics; "
        "do not diagnose injuries or medical conditions. Use the supplied pose measurements as "
        "the precise source for angles and use the image for context. Return ONLY one JSON object "
        "with score (0-100 integer), headline (max 8 words), summary (max 40 words), cues "
        "(1-3 short actionable strings), and confidence (0-1 number). "
        f"Movement: {movement}. Focus: {rubric['prompt_hint']} "
        f"Pose measurements: {json.dumps(pose_metrics, separators=(',', ':'))}"
    )
    url = f"wss://api.openai.com/v1/realtime?model={quote(model)}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Safety-Identifier": "gameday-mirror-athlete",
    }
    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.ws_connect(url, headers=headers, heartbeat=15) as websocket:
            await websocket.send_json(
                {
                    "type": "session.update",
                    "session": {
                        "type": "realtime",
                        "model": model,
                        "output_modalities": ["text"],
                        "instructions": "Return compact JSON movement coaching without markdown.",
                    },
                }
            )
            await websocket.send_json(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": image_data_url},
                        ],
                    },
                }
            )
            await websocket.send_json(
                {
                    "type": "response.create",
                    "response": {"output_modalities": ["text"]},
                }
            )
            chunks: list[str] = []
            while True:
                message = await websocket.receive(timeout=35)
                if message.type != aiohttp.WSMsgType.TEXT:
                    raise RuntimeError("Realtime vision connection closed before completion")
                event = json.loads(message.data)
                event_type = event.get("type")
                if event_type == "response.output_text.delta":
                    chunks.append(str(event.get("delta") or ""))
                elif event_type == "response.done":
                    raw = "".join(chunks) or _extract_text(event)
                    return _parse_analysis(raw, pose_metrics, movement, model)
                elif event_type == "error":
                    error = event.get("error", {})
                    raise RuntimeError(str(error.get("message") or "Realtime vision request failed"))
