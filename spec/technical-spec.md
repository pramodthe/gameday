# GameDay Mirror Technical Specification

Status: **Draft v0.1**

## Architecture Overview

GameDay Mirror is a realtime web experience with a React client, a LiveKit room, an ElevenLabs voice layer, an agent orchestrator, and sponsor-backed persistence and memory.

```text
React mirror UI
  ├── LiveKit camera, microphone, audio, transcript, data events
  ├── InsForge realtime metric and plan subscription
  └── Local visual state and text fallback

LiveKit room
  └── Python LiveKit Agents worker
        └── ElevenLabs realtime speech session
              └── Agent orchestrator / Lyzr workflow
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
- Keep API secrets and room-token generation server-side.

### ElevenLabs

- Handle speech recognition, natural synthesized speech, interruptions, and turn-taking.
- Connect through the LiveKit worker so the room can contain both camera and agent audio.
- Use signed URLs or server-side credentials; never expose the API key to the browser.
- Emit finalized transcripts to the orchestrator.

### Lyzr Agent Workflow

The orchestration layer owns a constrained state machine:

```text
CONNECTING → GREETING → QUESTION_1..4 → SUMMARIZING → PLAN_READY → COMPLETE
```

The agent may call only defined tools:

- `get_recent_context`
- `record_answer`
- `update_metric`
- `advance_checkin`
- `generate_daily_plan`
- `complete_checkin`

Tool results, not free-form model text, drive UI state.

### InsForge

- Authenticate users.
- Store profiles, sessions, answers, metrics, plans, and streaks.
- Provide realtime updates for the active session.
- Store optional generated share cards; raw media remains disabled by default.

### Qdrant

- Store embeddings of completed reflections and plans.
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
- `recoverable_error`: user-facing message and retry action.

Events must be idempotent by `event_id`. The client applies LiveKit data events immediately and reconciles against InsForge realtime records.

## Session Sequence

1. Client creates a check-in session and requests a LiveKit token.
2. Token dispatches the named LiveKit worker into the room.
3. Worker opens an authenticated ElevenLabs session.
4. Orchestrator retrieves recent Qdrant memories and greets the athlete.
5. Each finalized answer triggers normalization, persistence, and a UI event.
6. After question four, the orchestrator generates a plan using today's metrics and cited memories.
7. Enkrypt validates the plan.
8. The plan is published, accepted, persisted, embedded, and added to the streak.

## Reliability and Fallbacks

- If camera permission fails, continue with a neutral background.
- If voice fails, reveal a text field without resetting progress.
- If Qdrant fails, continue without prior memory and disclose that limitation.
- If Enkrypt is unavailable, use a conservative rules-based safety filter.
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
4. Constrained four-question state machine.
5. InsForge persistence and realtime reconciliation.
6. Qdrant memory retrieval and visible memory moment.
7. Final-plan safety check and completion animation.
8. Demo mode, deployment, instrumentation, and rehearsal.
