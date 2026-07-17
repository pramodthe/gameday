"""Check-in WebSocket (Req 1.3, 3.1, 5, 13).

Turn-based over a WebSocket: the client sends either a JSON control message
(`text_answer`, `demo_run`, `complete`) or a binary audio utterance for the
current question. The server transcribes (Deepgram), runs the state machine, and
streams back state / question / metric.update / coach.log / result events. TTS
audio is attached as base64 when Deepgram is configured.
"""
from __future__ import annotations

import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import deepgram_client
from ..session.demo import DEMO_ANSWERS
from ..session.registry import get_session

router = APIRouter()


async def _send(ws: WebSocket, event: dict) -> None:
    if event.get("type") == "question" and event.get("text"):
        audio = await deepgram_client.synthesize(event["text"])
        if audio:
            event = {**event, "audio_b64": base64.b64encode(audio).decode(), "audio_mime": "audio/mpeg"}
    await ws.send_text(json.dumps(event, default=str))


async def _process_answer(ws: WebSocket, session, transcript: str) -> None:
    for event in session.submit_answer(transcript):
        await _send(ws, event)
    if session.state == "READY_TO_COMPLETE":
        await _complete(ws, session)


async def _complete(ws: WebSocket, session) -> None:
    await _send(ws, {"type": "state", "value": "SAVING"})
    result = session.complete()
    audio = await deepgram_client.synthesize(result.get("coaching_text", ""))
    if audio:
        result = {**result, "audio_b64": base64.b64encode(audio).decode(), "audio_mime": "audio/mpeg"}
    await _send(ws, result)
    await _send(ws, {"type": "state", "value": "COMPLETE"})


async def _handle_control(ws: WebSocket, session, data: dict) -> None:
    kind = data.get("type")
    if kind == "text_answer":
        await _process_answer(ws, session, data.get("text", ""))
    elif kind == "demo_run":
        for answer in DEMO_ANSWERS:
            if session.state in ("COMPLETE", "SAVING"):
                break
            await _process_answer(ws, session, answer)
    elif kind == "complete":
        if session.state != "COMPLETE":
            await _complete(ws, session)


@router.websocket("/ws/checkin/{session_id}")
async def checkin_ws(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    session = get_session(session_id)
    if session is None:
        await ws.send_text(json.dumps({"type": "error", "code": "NO_SESSION", "recoverable": False}))
        await ws.close()
        return

    await _send(ws, {"type": "state", "value": "LIVE"})
    first = session.current_question()
    if first:
        await _send(ws, first)

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            text = msg.get("text")
            audio = msg.get("bytes")
            if text is not None:
                await _handle_control(ws, session, json.loads(text))
            elif audio is not None:
                transcript = await deepgram_client.transcribe(audio)
                if transcript is None:
                    await _send(ws, {"type": "error", "code": "STT_UNAVAILABLE", "recoverable": True})
                else:
                    # submit_answer emits the transcript event itself
                    await _process_answer(ws, session, transcript)
            if session.state == "COMPLETE":
                break
    except WebSocketDisconnect:
        pass
