from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import aiohttp
from dotenv import load_dotenv
from elevenlabs import AsyncElevenLabs
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli

load_dotenv()
load_dotenv(".env.local", override=True)

elevenlabs = AsyncElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
elevenlabs_agent_id = os.environ["ELEVENLABS_AGENT_ID"]
agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "gameday-elevenlabs")
user_input_rate = int(os.environ.get("MIRROR_USER_INPUT_RATE", "16000"))
agent_output_rate = int(os.environ.get("MIRROR_AGENT_OUTPUT_RATE", "24000"))
mirror_api_url = os.environ.get("MIRROR_API_URL", "http://127.0.0.1:8001").rstrip("/")
categories = ("sleep", "training", "fuel", "spending")


async def signed_url() -> str:
    response = await elevenlabs.conversational_ai.conversations.get_signed_url(
        agent_id=elevenlabs_agent_id,
    )
    return response.signed_url


async def entrypoint(ctx: JobContext) -> None:
    websocket_ready: asyncio.Future[aiohttp.ClientWebSocketResponse] = (
        asyncio.get_running_loop().create_future()
    )

    async def send_user_audio(track: rtc.Track) -> None:
        websocket = await websocket_ready
        stream = rtc.AudioStream(track, sample_rate=user_input_rate, num_channels=1)
        async for event in stream:
            encoded = base64.b64encode(bytes(event.frame.data)).decode()
            await websocket.send_str(json.dumps({"user_audio_chunk": encoded}))

    last_agent_state = ""

    async def publish_event(event: dict[str, object]) -> None:
        nonlocal last_agent_state
        if event.get("type") == "agent_state_changed":
            state = str(event.get("state") or "")
            if state == last_agent_state:
                return
            last_agent_state = state
        payload = {
            "session_id": ctx.room.name,
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        await ctx.room.local_participant.publish_data(
            json.dumps(payload).encode(),
            reliable=True,
            topic="mirror-events",
        )

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if participant.identity == ctx.room.local_participant.identity:
            return
        asyncio.create_task(send_user_audio(track))

    await ctx.connect()
    await publish_event({"type": "agent_state_changed", "state": "connecting"})

    source = rtc.AudioSource(sample_rate=agent_output_rate, num_channels=1)
    output_track = rtc.LocalAudioTrack.create_audio_track("nova", source)
    await ctx.room.local_participant.publish_track(
        output_track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )

    http = aiohttp.ClientSession()
    recent_memory = "No prior check-in is available yet."
    try:
        async with http.get(f"{mirror_api_url}/api/mirror/sessions/{ctx.room.name}/context") as response:
            if response.ok:
                recent_memory = str((await response.json()).get("recentMemory") or recent_memory)
    except aiohttp.ClientError:
        pass
    websocket = await http.ws_connect(await signed_url())
    await websocket.send_str(
        json.dumps(
            {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": {
                    "athlete_name": os.environ.get("MIRROR_ATHLETE_NAME", "Jordan"),
                    "recent_memory": recent_memory,
                    "session_id": ctx.room.name,
                },
            }
        )
    )
    websocket_ready.set_result(websocket)

    captured_answers: list[dict[str, str]] = []

    async def process_answer(transcript: str) -> None:
        category = categories[min(len(captured_answers), len(categories) - 1)]
        captured_answers.append({"category": category, "transcript": transcript})
        try:
            async with http.post(
                f"{mirror_api_url}/api/mirror/answers",
                json={
                    "room_name": ctx.room.name,
                    "category": category,
                    "transcript": transcript,
                    "answers": captured_answers,
                },
            ) as response:
                response.raise_for_status()
                body = await response.json()
                for mirror_event in body.get("events", []):
                    await publish_event(mirror_event)
        except (aiohttp.ClientError, ValueError, TypeError):
            await publish_event(
                {
                    "type": "recoverable_error",
                    "message": "Your answer was heard, but the mirror could not save it yet.",
                }
            )

    async def send_agent_audio() -> None:
        async for message in websocket:
            if message.type != aiohttp.WSMsgType.TEXT:
                continue
            event = json.loads(message.data)
            event_type = event.get("type")
            if event_type == "audio":
                await publish_event({"type": "agent_state_changed", "state": "speaking"})
                pcm = base64.b64decode(event["audio_event"]["audio_base_64"])
                frame = rtc.AudioFrame(
                    pcm,
                    agent_output_rate,
                    1,
                    len(pcm) // 2,
                )
                await source.capture_frame(frame)
            elif event_type == "interruption":
                source.clear_queue()
                await publish_event({"type": "agent_state_changed", "state": "listening"})
            elif event_type == "user_transcript":
                transcript = event.get("user_transcription_event", {}).get("user_transcript", "").strip()
                if transcript:
                    await publish_event(
                        {
                            "type": "transcript_finalized",
                            "speaker": "athlete",
                            "text": transcript,
                        }
                    )
                    await publish_event({"type": "agent_state_changed", "state": "thinking"})
                    asyncio.create_task(process_answer(transcript))
            elif event_type == "agent_response":
                response = event.get("agent_response_event", {}).get("agent_response", "").strip()
                if response:
                    await publish_event(
                        {
                            "type": "transcript_finalized",
                            "speaker": "agent",
                            "text": response,
                        }
                    )
            elif event_type == "ping":
                event_id = event.get("ping_event", {}).get("event_id")
                await websocket.send_str(json.dumps({"type": "pong", "event_id": event_id}))

    audio_task = asyncio.create_task(send_agent_audio())

    async def cleanup() -> None:
        audio_task.cancel()
        await websocket.close()
        await http.close()

    ctx.add_shutdown_callback(cleanup)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_name,
        )
    )
