# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

GameDay Mirror is a full-stack multimodal athlete check-in app: a React/LiveKit mirror UI, a FastAPI orchestrator, and a Python LiveKit↔ElevenLabs voice worker, backed by InsForge (Postgres) and several sponsor AI providers. See `AGENTS.md` for coding-style conventions and the InsForge backend contract; see `spec/` for approved product/technical behavior.

## Commands

```bash
npm install            # install root + apps/web deps (npm workspace)
uv sync --extra dev    # create .venv with API, worker, and test deps
npm run dev            # web on :3000 + API on :8001 (concurrently)
npm run dev:web        # Vite only, :3000
npm run dev:api        # uvicorn only, :8001 (.venv/bin/uvicorn)
npm run dev:agent      # LiveKit/ElevenLabs voice worker (needs credentials)
npm run lint           # tsc type-check of apps/web (there is no ESLint step)
npm run build          # production web bundle
npm test               # pytest (.venv/bin/pytest)
```

Run a single test: `.venv/bin/pytest tests/test_mirror.py::test_name -q`. Tests set `pythonpath = [".", "src"]` (see `pyproject.toml`), so import bridge/router code as `gameday_mirror.*` and `apps.api.*`.

`scripts/configure_elevenlabs_agent.py` registers the exercise client tools and routing rules on the configured ElevenLabs agent — rerun it after changing tool names or the agent's tool contract.

## Architecture

Three runtime processes plus external services:

- **`apps/web/src/features/mirror/`** — the entire UI lives here. `useMirrorSession.ts` is the LiveKit client + state machine; `MirrorExperience.tsx` composes it. `MovementCoach.tsx` runs MediaPipe Pose in-browser and produces squat biomechanics. `demoScenario.ts` drives the credential-free demo path.
- **`apps/api/`** — FastAPI. `main.py` loads `.env` then `.env.local` (override) and mounts `routers/mirror.py`, which is the whole HTTP surface: `/api/mirror/{config,token,sessions/{room}/context,answers,movement/analyze,exercise/lesson}` plus `/api/health`. `/token` mints a LiveKit AccessToken and dispatches the agent into the room.
- **`apps/mirror_agent/bridge.py`** — LiveKit worker (`entrypoint`). Bridges room audio to an ElevenLabs conversational agent, injects `athlete_name`/`recent_memory`/`session_id` as dynamic variables, and translates between ElevenLabs tool calls and browser UI via AG-UI events.
- **`src/gameday_mirror/`** — provider adapters and domain logic, imported by both the API and the worker: `sponsors.py` (Lyzr plan, Qdrant memory, Enkrypt validation), `lessons.py` (OpenAI structured exercise lesson, Pydantic-validated), `vision.py` (OpenAI movement analysis + `fallback_analysis`), `persistence.py` (InsForge via REST *or* direct Postgres), `exercises.py` (intent detection + context strings), `agui.py` (event encoding + `ExerciseSharedState`).

### Two cross-cutting contracts — read these before touching realtime code

1. **AG-UI event protocol over LiveKit data channels** (`agui.py`). The worker emits `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` and monotonic `STATE_SNAPSHOT` events; the browser replies with `CUSTOM` telemetry carrying the **same `toolCallId`**. `ExerciseSharedState` is the source of truth for the active exercise request — stale/mismatched IDs are ignored, and ElevenLabs only receives a tool result after the browser acknowledges the requested UI. Never bypass this handshake by pushing UI state directly.

2. **Graceful fallback everywhere.** Every sponsor integration has a deterministic offline path (`DEFAULT_PLAN` in `sponsors.py`, `fallback_analysis` in `vision.py`, `demoScenario.ts`, deterministic hash embeddings). `persistence.enabled()` and the various `*_enabled` checks gate live calls on env presence. The app must stay fully demonstrable with **no** provider credentials — preserve this when adding features; don't make a provider a hard dependency of the happy path.

### Conventions that matter

- Realtime event fields cross the Python↔TypeScript JSON boundary, so keep them `snake_case` on both sides even though TS is otherwise camelCase.
- Check-in has exactly four categories: `("sleep", "training", "fuel", "spending")` — this tuple is duplicated in `mirror.py` and `bridge.py`; keep them in sync.
- Provider model IDs and endpoints are read from env (`OPENAI_LESSON_MODEL`, `OPENAI_REALTIME_MODEL`, etc.); don't hardcode them in the adapters.

## Persistence & deployment

`persistence.py` supports two InsForge modes: direct Postgres (`INSFORGE_DATABASE_URL`) or REST (`INSFORGE_URL` + `INSFORGE_API_KEY`), both requiring `INSFORGE_PROFILE_ID`. Schema changes go in `migrations/` as timestamped SQL applied in order.

Production runs three InsForge deployments; the root `Dockerfile` selects API vs. worker via `SERVICE_ROLE`. The frontend reads `VITE_API_BASE_URL`. Never expose provider secrets through `VITE_*` variables — only the public API base URL belongs there.
