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


def fallback_analysis(pose_metrics: dict[str, Any]) -> dict[str, Any]:
    reps = max(0, int(_number(pose_metrics.get("reps"))))
    knee_angle = _number(pose_metrics.get("min_knee_angle"), 180)
    symmetry_gap = _number(pose_metrics.get("symmetry_gap"), 30)
    torso_lean = _number(pose_metrics.get("torso_lean"), 30)
    depth_score = max(35, min(100, round(100 - abs(knee_angle - 92) * 1.15)))
    symmetry_score = max(35, min(100, round(100 - symmetry_gap * 2.5)))
    control_score = max(40, min(100, 55 + reps * 15 - max(0, torso_lean - 18)))
    score = round(depth_score * 0.4 + symmetry_score * 0.35 + control_score * 0.25)
    cues: list[str] = []
    if knee_angle > 115:
        cues.append("Sit a little deeper while keeping both heels planted.")
    if symmetry_gap > 10:
        cues.append("Drive both knees evenly and keep pressure balanced through both feet.")
    if torso_lean > 25:
        cues.append("Brace before descending and keep your chest stacked over your hips.")
    if not cues:
        cues.append("Keep this tempo and finish each rep with balanced foot pressure.")
    return {
        "score": score,
        "headline": "Movement baseline captured",
        "summary": "Pose tracking measured your squat depth, symmetry, and torso control.",
        "cues": cues[:3],
        "confidence": round(min(0.92, 0.55 + reps * 0.1), 2),
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


def _parse_analysis(raw: str, pose_metrics: dict[str, Any], model: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not match:
        raise ValueError("Realtime vision returned no JSON object")
    parsed = json.loads(match.group(0))
    fallback = fallback_analysis(pose_metrics)
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
        return fallback_analysis(pose_metrics)

    prompt = (
        "You are a concise sports movement coach. Analyze only visible movement mechanics; "
        "do not diagnose injuries or medical conditions. Use the supplied pose measurements as "
        "the precise source for angles and use the image for context. Return ONLY one JSON object "
        "with score (0-100 integer), headline (max 8 words), summary (max 40 words), cues "
        "(1-3 short actionable strings), and confidence (0-1 number). "
        f"Movement: {movement}. Pose measurements: {json.dumps(pose_metrics, separators=(',', ':'))}"
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
                    return _parse_analysis(raw, pose_metrics, model)
                elif event_type == "error":
                    error = event.get("error", {})
                    raise RuntimeError(str(error.get("message") or "Realtime vision request failed"))
