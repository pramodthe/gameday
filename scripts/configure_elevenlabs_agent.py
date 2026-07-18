from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import AgentConfig, ConversationalConfig, ElevenLabs
from elevenlabs.types import LiteralJsonSchemaProperty, ObjectJsonSchemaPropertyInput, ToolRequestModel
from elevenlabs.types.tool_request_model_tool_config import ToolRequestModelToolConfig_Client


ROOT = Path(__file__).resolve().parents[1]
START_TOOL_NAME = "start_exercise"
LEGACY_START_TOOL_NAME = "start_squat_exercise"
LESSON_TOOL_NAME = "teach_exercise"
VOICE_ID = "pNInz6obpgDQGcFmaJgB"
CHECKIN_MARKER = "\n\nREADINESS CHECK-IN MODE\n"
CHECKIN_PROMPT = """READINESS CHECK-IN MODE
- Run exactly four primary questions in this order: recovery, training, fuel, and accountability.
- The recovery answer covers both sleep duration and perceived recovery.
- The accountability answer covers mindset plus spending discipline when relevant.
- Ask one focused question at a time and keep it to a single sentence.
- Acknowledge each answer in no more than 12 words, then ask the next primary question.
- Do not add follow-up questions unless the answer cannot be understood.
- Trusted athlete history is supplied in {{recent_memory}} and may contain CHECKIN, WORKOUT, and MOVEMENT entries.
- If asked about a previous routine, name the saved workout exercises and doses from WORKOUT history. Never say you cannot access previous routines when a WORKOUT entry is present.
- If no WORKOUT entry exists, say no complete workout was saved yet, then summarize any available MOVEMENT history. Never invent missing exercises or results.
- Use prior history as context, never as a reason to change the four-step contract.
- After the fourth answer, say: “Locked in. I’m building your three-move game plan now.” Then stop asking questions.
- Never diagnose, prescribe treatment, or give financial advice. You are a coaching aid, not a clinician.
"""
PROMPT_MARKER = "\n\nEXERCISE COACH MODE\n"
EXERCISE_PROMPT = """EXERCISE COACH MODE
- Speak like a commanding, old-school locker-room coach: deep, blunt, confident, dry, and slightly impatient.
- Use short sentences, sharp timing, and occasional playful trash talk. Make the athlete laugh, then immediately give the useful cue.
- Tease effort or excuses, never identity, appearance, disability, injury, or ability level. Do not humiliate, threaten, swear at, or genuinely insult the athlete.
- Keep jokes brief so they never delay rep counts, safety guidance, tool calls, or sensor feedback.
- You have two client tools: `teach_exercise` and `start_exercise`.
- Exercise requests interrupt and pause the readiness check-in. Tool routing takes priority over asking the next check-in question.
- When the athlete asks to learn, see, demonstrate, or be taught any named exercise, your next action MUST be a `teach_exercise` tool call in the same turn. Pass the concise exercise name in `exercise_name`.
- Never merely say that a lesson is generating. Only say the guide is opening after the `teach_exercise` result confirms `status: generating`.
- If a required tool returns an error, state that the UI could not open instead of pretending it succeeded. Never tell the athlete to press a UI button.
- `teach_exercise` generates a visual movement card with an animated motion map, setup/action/finish steps, form cues, common mistakes, safety guidance, and a training prescription.
- After calling `teach_exercise`, say the visual guide is being built. You receive trusted contextual updates beginning with `Exercise lesson:` when it is ready; use those generated cues to explain the card and answer follow-up questions.
- After the lesson is ready, do not call another tool automatically. Keep the lesson open and wait for the athlete's next request.
- Call `start_exercise` when the athlete asks to practice, count, or camera-check one supported movement. Pass exactly one of: squat, pushup, lunge, plank, glute_bridge.
- Live tracking supports those five movements. For any other movement, call `teach_exercise` instead and explain that its visual lesson is available without camera scoring.
- The tool opens the movement-specific camera session and starts automatically once the required joints are visible.
- After calling the tool, briefly ask the athlete to move until the working joints are in frame.
- You receive trusted contextual updates beginning with `Exercise sensor:` for visibility, verified reps, and the final score.
- During an active set, speak only from verified sensor updates. Announce each verified rep or hold milestone with at most one short cue. When complete, say the set is complete before the final analysis.
- You do not see raw video. Never claim you can see the athlete; describe only what the exercise sensor reports.
- While a lesson or exercise is active, pause the readiness check-in and answer from the latest lesson or sensor update.
- After completion, celebrate briefly and state the strongest form cue.
- Follow trusted `Check-in status:` contextual updates exactly. If the check-in is complete, never restart readiness questions; return to the generated workout and offer the next exercise or finish. If incomplete, resume only the next unanswered question.
"""


def ensure_client_tool(
    client: ElevenLabs,
    name: str,
    description: str,
    parameters: ObjectJsonSchemaPropertyInput,
):
    tools = client.conversational_ai.tools.list(search=name, page_size=100).tools
    existing = next(
        (tool for tool in tools if getattr(tool.tool_config, "name", None) == name),
        None,
    )
    request = ToolRequestModel(
        tool_config=ToolRequestModelToolConfig_Client(
            name=name,
            description=description,
            parameters=parameters,
            expects_response=True,
            response_timeout_secs=10,
                pre_tool_speech="off",
            interruption_mode="disable_during_tool",
        )
    )
    if existing is not None:
        return client.conversational_ai.tools.update(existing.id, request=request)
    return client.conversational_ai.tools.create(request=request)


def main() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.local", override=True)
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    agent_id = os.environ["ELEVENLABS_AGENT_ID"]

    exercise_tool = ensure_client_tool(
        client,
        START_TOOL_NAME,
        (
            "Open the GameDay Mirror camera coach for squat, pushup, lunge, plank, or glute_bridge. "
            "Use when the athlete asks to practice, count, or camera-check one of those movements. "
            "The UI auto-starts after full-body detection."
        ),
        ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "exercise": LiteralJsonSchemaProperty(
                    type="string",
                    enum=["squat", "pushup", "lunge", "plank", "glute_bridge"],
                    description="The supported movement to track with the camera.",
                )
            },
            required=["exercise"],
        ),
    )
    lesson_tool = ensure_client_tool(
        client,
        LESSON_TOOL_NAME,
        (
            "Generate and display a visual teaching card for any exercise the athlete names. "
            "Use when they ask to learn, see, demonstrate, or be taught how to perform an exercise."
        ),
        ObjectJsonSchemaPropertyInput(
            type="object",
            properties={
                "exercise_name": LiteralJsonSchemaProperty(
                    type="string",
                    description=(
                        "The concise exercise name the athlete wants to learn, "
                        "for example reverse lunge, push-up, or Romanian deadlift."
                    ),
                )
            },
            required=["exercise_name"],
        ),
    )

    agent = client.conversational_ai.agents.get(agent_id)
    agent_config = agent.conversation_config.agent
    prompt_config = agent_config.prompt
    if prompt_config is None:
        raise RuntimeError("The configured ElevenLabs agent has no prompt configuration.")

    base_prompt = (prompt_config.prompt or "").split(CHECKIN_MARKER, 1)[0].split(PROMPT_MARKER, 1)[0].rstrip()
    checkin_body = CHECKIN_PROMPT.removeprefix("READINESS CHECK-IN MODE" + chr(10)).rstrip()
    exercise_body = EXERCISE_PROMPT.removeprefix("EXERCISE COACH MODE" + chr(10))
    legacy_tools = client.conversational_ai.tools.list(search=LEGACY_START_TOOL_NAME, page_size=100).tools
    legacy_ids = {
        tool.id
        for tool in legacy_tools
        if getattr(tool.tool_config, "name", None) == LEGACY_START_TOOL_NAME
    }
    retained_tool_ids = [tool_id for tool_id in (prompt_config.tool_ids or []) if tool_id not in legacy_ids]
    tool_ids = list(dict.fromkeys([*retained_tool_ids, exercise_tool.id, lesson_tool.id]))
    updated_prompt = prompt_config.model_copy(
        update={
            "prompt": f"{base_prompt}{CHECKIN_MARKER}{checkin_body}{PROMPT_MARKER}{exercise_body}",
            "tools": [],
            "tool_ids": tool_ids,
        }
    )
    updated_tts = agent.conversation_config.tts.model_copy(
        update={
            "voice_id": VOICE_ID,
            "stability": 0.42,
            "speed": 0.94,
            "similarity_boost": 0.82,
        }
    )
    client.conversational_ai.agents.update(
        agent_id,
        conversation_config=ConversationalConfig(
            agent=AgentConfig(
                first_message=(
                    "Good morning, {{athlete_name}}. Ask me to teach you any exercise for a visual guide, "
                    "or ask to practice a supported movement with camera coaching. Let's run today's readiness check-in — "
                    "how did you sleep, and how recovered do you feel?"
                ),
                prompt=updated_prompt,
            ),
            tts=updated_tts,
        ),
        version_description="Align Nova with the four-step GameDay check-in contract",
    )
    print(
        f"Configured {LESSON_TOOL_NAME}, {START_TOOL_NAME}, and voice {VOICE_ID} "
        f"on ElevenLabs agent {agent_id}."
    )


if __name__ == "__main__":
    main()
