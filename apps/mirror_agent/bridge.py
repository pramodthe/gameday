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

from gameday_mirror.agui import ExerciseSharedState, tool_result_event
from gameday_mirror.checkin import classify_answer
from gameday_mirror.exercises import exercise_context_update, is_exercise_request

load_dotenv()
load_dotenv(".env.local", override=True)

elevenlabs = AsyncElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
elevenlabs_agent_id = os.environ["ELEVENLABS_AGENT_ID"]
agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "gameday-elevenlabs")
user_input_rate = int(os.environ.get("MIRROR_USER_INPUT_RATE", "16000"))
agent_output_rate = int(os.environ.get("MIRROR_AGENT_OUTPUT_RATE", "24000"))
mirror_api_url = os.environ.get("MIRROR_API_URL", "http://127.0.0.1:8001").rstrip("/")


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
            if websocket.closed:
                return
            encoded = base64.b64encode(bytes(event.frame.data)).decode()
            try:
                await websocket.send_str(json.dumps({"user_audio_chunk": encoded}))
            except aiohttp.ClientError:
                return

    last_agent_state = ""
    exercise_state = ExerciseSharedState(ctx.room.name)
    pending_tool_acks: dict[str, asyncio.Future[dict[str, object]]] = {}

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

    async def publish_protocol_event(event: dict[str, object]) -> None:
        await ctx.room.local_participant.publish_data(
            json.dumps(event).encode(),
            reliable=True,
            topic="mirror-events",
        )

    async def forward_exercise_event(event: dict[str, object]) -> None:
        if event.get("type") == "CUSTOM":
            if event.get("name") == "gameday.state.request":
                await publish_protocol_event(exercise_state.snapshot_event())
                return
            if event.get("name") != "gameday.exercise.telemetry":
                return
            value = event.get("value")
            if not isinstance(value, dict):
                return
            event = value

        snapshot = exercise_state.apply_telemetry(event)
        if snapshot is None:
            return
        await publish_protocol_event(snapshot)
        request_id = str(event.get("request_id") or "")
        pending_ack = pending_tool_acks.get(request_id)
        if pending_ack is not None and not pending_ack.done():
            pending_ack.set_result(event)
            if event.get("type") in {"exercise_lesson_loading", "exercise_opened"}:
                return
        context = exercise_context_update(event)
        if not context:
            return
        websocket = await websocket_ready
        await websocket.send_str(json.dumps({"type": "contextual_update", "text": context}))

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        if packet.topic != "exercise-events":
            return
        try:
            event = json.loads(packet.data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(event, dict):
            asyncio.create_task(forward_exercise_event(event))

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
    await publish_protocol_event(exercise_state.snapshot_event())

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
        if exercise_state.is_active or is_exercise_request(transcript):
            return
        category = classify_answer(transcript, [answer["category"] for answer in captured_answers])
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

    async def handle_client_tool_call(event: dict[str, object]) -> None:
        tool_call = event.get("client_tool_call")
        if not isinstance(tool_call, dict):
            return
        tool_name = str(tool_call.get("tool_name") or "")
        tool_call_id = str(tool_call.get("tool_call_id") or "")
        if not tool_call_id:
            return

        async def finish_tool(result: dict[str, object], is_error: bool) -> None:
            await websocket.send_str(
                json.dumps(
                    {
                        "type": "client_tool_result",
                        "tool_call_id": tool_call_id,
                        "result": json.dumps(result),
                        "is_error": is_error,
                    }
                )
            )
            await publish_protocol_event(
                tool_result_event(tool_call_id, {**result, "is_error": is_error})
            )

        def expect_browser_ack() -> asyncio.Future[dict[str, object]]:
            acknowledgement: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
            pending_tool_acks[tool_call_id] = acknowledgement
            return acknowledgement

        async def wait_for_browser_ack(
            acknowledgement: asyncio.Future[dict[str, object]],
        ) -> dict[str, object] | None:
            try:
                return await asyncio.wait_for(acknowledgement, timeout=6)
            except asyncio.TimeoutError:
                return None
            finally:
                pending_tool_acks.pop(tool_call_id, None)

        if tool_name == "teach_exercise":
            parameters = tool_call.get("parameters")
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                except json.JSONDecodeError:
                    parameters = {}
            exercise_name = ""
            if isinstance(parameters, dict):
                exercise_name = str(parameters.get("exercise_name") or "").strip()[:80]
            if not exercise_name:
                await finish_tool(
                    {"status": "invalid", "message": "An exercise_name is required to build a visual lesson."},
                    True,
                )
                return

            acknowledgement_future = expect_browser_ack()
            for protocol_event in exercise_state.begin_lesson(tool_call_id, exercise_name):
                await publish_protocol_event(protocol_event)
            acknowledgement = await wait_for_browser_ack(acknowledgement_future)
            if acknowledgement is None:
                snapshot = exercise_state.fail_request(tool_call_id, "The browser did not acknowledge the lesson request.")
                if snapshot is not None:
                    await publish_protocol_event(snapshot)
                await finish_tool(
                    {
                        "status": "ui_timeout",
                        "exercise": exercise_name,
                        "message": "The visual lesson could not be opened in the athlete's browser.",
                    },
                    True,
                )
                return
            await finish_tool(
                {
                    "status": "generating",
                    "exercise": exercise_name,
                    "request_id": tool_call_id,
                    "next_step": "Tell the athlete the visual movement lesson is being built. Use the next Exercise lesson contextual update to coach from the generated card.",
                },
                False,
            )
            return

        if tool_name != "start_squat_exercise":
            await finish_tool(
                {"status": "unsupported", "message": f"Unsupported client tool: {tool_name}"},
                True,
            )
            return

        acknowledgement_future = expect_browser_ack()
        for protocol_event in exercise_state.begin_squat(tool_call_id, target_reps=5):
            await publish_protocol_event(protocol_event)
        acknowledgement = await wait_for_browser_ack(acknowledgement_future)
        if acknowledgement is None:
            snapshot = exercise_state.fail_request(tool_call_id, "The browser did not acknowledge the camera request.")
            if snapshot is not None:
                await publish_protocol_event(snapshot)
            await finish_tool(
                {
                    "status": "ui_timeout",
                    "exercise": "squat",
                    "message": "The camera exercise could not be opened in the athlete's browser.",
                },
                True,
            )
            return
        await finish_tool(
            {
                "status": "opened",
                "exercise": "squat",
                "target_reps": 5,
                "request_id": tool_call_id,
                "next_step": "Ask the athlete to step back until their full body and ankles are visible. The set starts automatically after body lock.",
            },
            False,
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
            elif event_type == "client_tool_call":
                await handle_client_tool_call(event)
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
            job_executor_type=agents.JobExecutorType.THREAD,
        )
    )
