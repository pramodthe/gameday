# GameDay Mirror Technical Specification

Status: **Draft v0.1**

## Architecture Overview

GameDay Mirror is a realtime web experience with a React client, a LiveKit room, an ElevenLabs voice layer, an agent orchestrator, and sponsor-backed persistence and memory.

```text
React mirror UI
  ├── LiveKit camera, microphone, audio, transcript, AG-UI data events
  ├── InsForge realtime metric and plan subscription
  └── Local visual state and text fallback

LiveKit room
  └── Python LiveKit Agents worker
        └── ElevenLabs realtime speech session
              ├── Client tools → browser exercise experiences
              └── Agent orchestrator / Lyzr workflow
                    ├── OpenAI structured exercise lessons
                    ├── InsForge persistence
                    ├── Qdrant memory retrieval
                    └── Enkrypt output safety check
```

## Technology Responsibilities

### React and LiveKit Agents UI

- Render the local camera as the full-viewport mirror.
- Provide camera, microphone, disconnect, and audio-visualizer controls.
- Render the agent transcript and connection state.
- Consume structured data events for immediate card updates.
- Subscribe to InsForge realtime for persisted state reconciliation.

The UI should use LiveKit building blocks rather than a stock conferencing layout. The experience needs custom glass cards and a minimal control bar.

### LiveKit

- Transport realtime camera, microphone, and agent audio.
- Create one room per check-in session.
- Dispatch the voice worker through a server-issued token.
- Publish structured data events such as progress and metric updates.
- Carry AG-UI-compatible tool and state events over reliable data channels.
- Keep API secrets and room-token generation server-side.

### ElevenLabs

- Handle speech recognition, natural synthesized speech, interruptions, and turn-taking.
- Connect through the LiveKit worker so the room can contain both camera and agent audio.
- Use signed URLs or server-side credentials; never expose the API key to the browser.
- Emit finalized transcripts to the orchestrator.

### OpenAI Exercise Intelligence

- Use the Responses API with strict Structured Outputs to generate typed exercise lessons.
- Render generated lesson data through owned React and SVG components; never inject model-authored HTML.
- Use OpenAI Realtime vision only for selected camera frames and derived squat measurements.
- Fall back to curated bodyweight lessons and deterministic pose analysis when unavailable.

### Lyzr Agent Workflow

Lyzr is the multi-agent decision layer around the realtime execution loop:

```text
READINESS → PLAN → WORKOUT → VERIFIED_SET → ADAPTATION → MEMORY
```

The `GameDay Performance Director` Manager Agent dynamically routes readiness and workout requests. `GameDay Verified-Set Adaptation` is a deterministic SuperFlow that invokes the Movement Adaptation Coach after a camera-verified set and exposes its workflow task ID in application telemetry. Every specialist uses Cognis cross-session memory, shared Global Context, the `GameDay Athlete Safety` RAI policy, and strict Pydantic-derived JSON schemas. Stable `user_id` and role-scoped LiveKit `session_id` values preserve continuity without leaking one specialist's working context into another.

Provisioning is API-driven and idempotent:

- `scripts/configure_lyzr_agents.py` creates or updates the manager, specialists, Cognis, context, RAI, and schemas.
- `scripts/configure_lyzr_superflow.py` creates or updates the verified-set workflow.
- `scripts/configure_lyzr_tools.py` registers the optional InsForge OpenAPI context tool.
- `functions/gameday-agent-context.ts` exposes only scoped session and movement history behind a shared tool secret.

SRS reflection is intentionally excluded from the live workout and adaptation path because it materially increases latency. It can be enabled for offline readiness-plan quality review. If Manager routing fails, the requested specialist still runs directly; if SuperFlow fails, adaptation falls back to the direct specialist and then to deterministic rules.

The voice agent may call only defined UI tools:

- `get_recent_context`
- `record_answer`
- `update_metric`
- `advance_checkin`
- `generate_daily_plan`
- `complete_checkin`
- `teach_exercise(exercise_name)`
- `start_exercise(exercise)`

Tool results, typed Lyzr responses, and camera telemetry—not free-form model text—drive UI state. If Lyzr fails validation or times out, the existing OpenAI structured-output generator runs; if that fails, a curated Core-5 session is returned.

### InsForge

- Authenticate users.
- Store profiles, sessions, answers, metrics, plans, and streaks.
- Provide realtime updates for the active session.
- Store optional generated share cards; raw media remains disabled by default.

### Qdrant

- Store embeddings of completed reflections, plans, and camera-verified movement results.
- Retrieve a maximum of three relevant memories before the greeting and final plan.
- Filter retrieval by authenticated user ID.
- Store source session IDs and dates in payload metadata for explainability.

### Enkrypt

- Scan the final plan for unsupported medical, financial, or high-risk claims.
- Block or rewrite disallowed recommendations before `PLAN_READY`.
- Log only safety metadata, not raw camera or audio.

## Data Model

### `athlete_profiles`

- `id`
- `user_id`
- `display_name`
- `sport`
- `primary_goal`
- `timezone`
- `created_at`

### `checkin_sessions`

- `id`
- `athlete_profile_id`
- `livekit_room_name`
- `status`
- `started_at`
- `completed_at`
- `demo_mode`

### `checkin_answers`

- `id`
- `session_id`
- `category`
- `transcript`
- `normalized_value`
- `unit`
- `confidence`
- `created_at`

### `daily_metrics`

- `id`
- `session_id`
- `metric_key`
- `metric_value`
- `display_value`
- `status`
- `source_answer_id`

### `daily_plans`

- `id`
- `session_id`
- `actions_json`
- `memory_sources_json`
- `safety_status`
- `accepted_at`

### `streaks`

- `athlete_profile_id`
- `current_days`
- `longest_days`
- `last_completed_date`

## Realtime Event Contract

Every event includes `session_id`, `event_id`, and `timestamp`.

- `agent_state_changed`: listening, thinking, speaking, saving, or idle.
- `transcript_finalized`: speaker and final text.
- `metric_updated`: metric key, display value, status, and confidence.
- `checkin_progressed`: completed step and total steps.
- `memory_used`: short explanation and source date.
- `plan_ready`: validated actions and rationale.
- `checkin_completed`: streak and completion summary.
- `exercise_requested`: opens the squat coach and auto-starts after full-body lock.
- `exercise_lesson_requested`: asks the browser to generate and display a named exercise lesson.
- `recoverable_error`: user-facing message and retry action.

Exercise interactions use an AG-UI-compatible subset:

- `TOOL_CALL_START` → `TOOL_CALL_ARGS` → `TOOL_CALL_END` identifies one voice tool request.
- `STATE_SNAPSHOT` carries the complete exercise mode, status, request ID, lesson, metrics, and monotonic revision.
- Browser `CUSTOM` events named `gameday.exercise.telemetry` acknowledge loading, readiness, progress, completion, failure, or closure.
- `TOOL_CALL_RESULT` is emitted only after a matching browser acknowledgement; a six-second timeout returns an error to ElevenLabs.

The bridge rejects telemetry whose request ID does not match the active tool call and ignores idempotent
updates. Accepted lesson cues, body visibility, verified reps, and final scores become ElevenLabs
contextual updates. Nova answers from those trusted states without claiming direct access to raw video.

Events must be idempotent by `event_id`. The client applies LiveKit data events immediately and reconciles against InsForge realtime records.

## Session Sequence

1. Client creates a check-in session and requests a LiveKit token.
2. Token dispatches the named LiveKit worker into the room.
3. Worker opens an authenticated ElevenLabs session.
4. Orchestrator retrieves recent Qdrant memories and greets the athlete.
5. Each finalized answer triggers normalization, persistence, and a UI event.
6. After all six readiness dimensions are covered, Lyzr generates a plan and Core-5 workout using today's metrics and cited memories.
7. Enkrypt validates the plan.
8. Each completed set is analyzed, persisted, embedded in Qdrant, and sent through Lyzr SuperFlow for a next-set decision.
9. Plans, workouts, adaptations, and their provider provenance are visible in the UI.

## Reliability and Fallbacks

- If camera permission fails, continue with a neutral background.
- If voice fails, reveal a text field without resetting progress.
- If Qdrant fails, continue without prior memory and disclose that limitation.
- If Enkrypt is unavailable, use a conservative rules-based safety filter.
- If lesson generation fails, return a curated bodyweight lesson without blocking the voice session.
- If InsForge realtime disconnects, apply LiveKit events and retry persistence.
- Demo mode uses seeded memory and deterministic metric extraction fallbacks.

## Validation Plan

- Unit-test the check-in state machine and tool input schemas.
- Contract-test every realtime event payload.
- Verify that duplicate events do not duplicate answers or progress.
- Test camera-denied, microphone-denied, interruption, reconnect, and text fallback flows.
- Run one end-to-end seeded demo at least five times without manual recovery.
- Measure connection time, end-of-turn voice latency, metric update latency, and total completion time.

## Implementation Order

1. Camera-first static mirror and responsive overlays.
2. LiveKit room, token endpoint, and device controls.
3. ElevenLabs voice worker and transcript events.
4. Adaptive six-dimension readiness state machine.
5. InsForge persistence and realtime reconciliation.
6. Qdrant memory retrieval and visible memory moment.
7. Final-plan safety check and completion animation.
8. Demo mode, deployment, instrumentation, and rehearsal.
