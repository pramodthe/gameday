# Implementation Plan

Tasks are ordered to reach a working, demoable path first (scoring core → voice loop → mirror UI), then persistence and the coach board, then sponsor-tool stretches. Each task is incremental and references the requirements it satisfies. Check off as you go.

> **Progress (backend + frontend complete, 43 tests passing, verified in-browser):**
> Tasks 1–3, 5–10 done; Task 4 via prerecorded STT + TTS (graceful no-key). Demo Mode (13)
> server + UI. Frontend (11–12): Vite + React mirror + coach board wired to the WebSocket,
> LiveKit Agents UI *aesthetic* (their components need a LiveKit room, so the visuals were
> adapted to our transport). Lyzr (16) wired as the coaching brain with deterministic fallback.
> **Remaining: 14 InsForge adapter (prize category), 15 Enkrypt guardrail, 17 Qdrant; plug in
> Deepgram/Lyzr keys for live voice; rehearse the demo + record a backup.**

- [ ] 1. Scaffold the FastAPI backend
  - Create `backend/app/main.py` with a FastAPI app, CORS for the frontend origin, and health route.
  - Add `config.py` with settings, feature flags, and scoring weights loaded from env.
  - Define all Pydantic models from the design in `models.py`.
  - Add `requirements.txt` / `pyproject.toml` (fastapi, uvicorn, pydantic, websockets, deepgram-sdk, anthropic, httpx, pytest).
  - _Requirements: platform constraints, Data models_

- [ ] 2. Implement the scoring core (test-driven — the credibility layer)
  - [ ] 2.1 Write `services/scoring.py::readiness(components)` returning score, band, and per-input breakdown with renormalization when inputs are missing.
    - _Requirements: 6.1, 6.2, 6.3_
  - [ ] 2.2 Write `services/scoring.py::acwr(load_history, baseline)` returning ratio, `provisional` flag, and injury/undertraining flags.
    - _Requirements: 7.2, 7.3, 7.4_
  - [ ] 2.3 Write `services/coaching.py::recommend(band, acwr, flags)` implementing the PUSH/MAINTAIN/RECOVER rules.
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 2.4 Add `tests/test_scoring.py` and `tests/test_acwr.py` with table-driven cases (including the demo case: 5h sleep + load spike → LOW + HIGH_INJURY_RISK → RECOVER).
    - _Requirements: 6.1, 7.4, 8.2_

- [ ] 3. Build the persistence layer
  - [ ] 3.1 Define the `Repository` protocol in `repositories/base.py` (athletes, check-ins, workload history, streaks; read + write).
    - _Requirements: 11.1, 11.4_
  - [ ] 3.2 Implement `repositories/local.py` (SQLite or in-memory) as the default.
    - _Requirements: 11.2_
  - [ ] 3.3 Implement streak update logic (increment/reset by calendar-day rules) used on check-in completion.
    - _Requirements: 9.1, 9.3_

- [ ] 4. Integrate Deepgram voice I/O
  - [ ] 4.1 Implement `services/deepgram_client.py` streaming STT (audio chunks → interim/final transcripts).
    - _Requirements: 3.2, 3.3_
  - [ ] 4.2 Implement TTS (text → audio) for questions and the coaching message.
    - _Requirements: 8.4_
  - [ ] 4.3 Add retry + degradation handling for STT connection failure.
    - _Requirements: 3.4_

- [ ] 5. Implement structured extraction
  - Define per-question JSON schemas in `schemas/` (sleep, load, soreness, nutrition, mood).
  - Implement `services/extraction.py` calling the LLM constrained to each schema; normalize fuzzy quantities ("about five" → 5); set absent fields to `null` and record `unknown`.
  - Add `tests/test_extraction.py` with sample transcripts.
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 6. Build the session state machine
  - Implement `session/state.py` with states (`CONNECTING/LIVE/LISTENING/SAVING/COMPLETE`), the fixed 5-question script, and per-answer flow (STT → extraction → emit metric update → advance).
  - Re-ask a question once when its answer is uninterpretable, else record `unknown`.
  - On completion, compute readiness + ACWR, append workload, update streak.
  - Add `tests/test_state_machine.py` driving a full mocked session.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 7.1_

- [ ] 7. Wire the check-in WebSocket
  - Implement `ws/checkin.py` at `/ws/checkin/{session_id}` handling binary audio in and the JSON control/event protocol from the design.
  - Emit `state`, `question`, `transcript`, `metric.update` (with ok/caution/risk status), `coach.log`, and final `result` events.
  - Support `text_answer` fallback and `demo_mode` toggle messages.
  - _Requirements: 1.2, 1.3, 3.1, 5.1, 5.2, 5.3, 5.4_

- [ ] 8. Generate and speak coaching
  - Implement `services/coaching.py::message(...)` producing a one-line spoken message stating recommendation + primary reason; fall back to a deterministic sentence if the LLM fails.
  - Route the message through TTS and return `coaching_audio_url` + `coaching_text` in the `result` event.
  - _Requirements: 8.4, 8.5_

- [ ] 9. Expose REST read APIs
  - Implement `POST /api/athletes`, `POST /api/sessions`, `GET /api/athletes/{id}/readiness`, `GET /api/athletes/{id}/history`, `GET /api/athletes/{id}/streak`.
  - _Requirements: 1.2, 6.4, 9.2, 11.4_

- [ ] 10. Coach board API
  - Implement `GET /api/coach/{coach_id}/board` returning each athlete's latest readiness, band, recommendation, flags, and `checked_in_today`; surface RECOVER / HIGH_INJURY_RISK first; show `no check-in` where absent.
  - _Requirements: 10.1, 10.2, 10.3_

- [ ] 11. Build the mirror frontend (athlete)
  - [ ] 11.1 Camera feed via `getUserMedia` + glassmorphic overlay panels (HEALTH TODAY / readiness, status pill, streak bar, Nova Check-in log).
    - _Requirements: 1.1, 1.3, 5.4, 9.2_
  - [ ] 11.2 WebSocket client: stream mic audio, render `metric.update` with ok/caution/risk colors, play question + coaching audio, show final result.
    - _Requirements: 3.1, 5.1, 5.2, 5.3, 8.5_
  - [ ] 11.3 Question progress `N/5`, `Complete Check-in` action, and mic-denied → Demo Mode fallback with banner.
    - _Requirements: 1.5, 2.2, 2.4_

- [ ] 12. Build the coach board frontend
  - Render the roster board from `/api/coach/{id}/board`; auto-refresh (poll or WS) so a new check-in appears without a full reload; highlight flagged athletes.
  - _Requirements: 10.1, 10.2, 10.4_

- [ ] 13. Implement Demo Mode
  - Server-side scripted sequence (answers → metric updates → result → coaching) that runs without mic/STT; frontend toggle between Live and Demo.
  - Snapshot test the golden on-stage path.
  - _Requirements: 13.1, 13.2, 13.3_

- [ ] 14. InsForge persistence adapter (prize category)
  - Implement `repositories/insforge.py` mapping the repository interface to InsForge; select via `PERSISTENCE=insforge`.
  - Handle save failure → `SAVING` failure state with in-memory retention and retry.
  - _Requirements: 11.2, 11.3_

- [ ] 15. Enkrypt AI guardrail (stretch)
  - Implement `services/guardrail.py` screening coaching messages; replace disallowed content with a safe generic recovery message; add the non-medical disclaimer to the athlete view.
  - _Requirements: 12.1, 12.2, 12.3_

- [ ] 16. Lyzr multi-agent coaching (stretch)
  - Behind `ENABLE_LYZR`, route coaching generation through Recovery / Nutrition / Physio agents and merge into the single spoken message.
  - _Requirements: 8.4_

- [ ] 17. Qdrant baseline recall (stretch)
  - Behind `ENABLE_QDRANT`, vector each completed check-in and retrieve similar past days to contextualize the readiness/ACWR explanation.
  - _Requirements: 7.2, 8.4_

- [ ] 18. Demo readiness pass
  - Seed a demo athlete with 28 days of workload history (so ACWR is real, not provisional) and a demo roster with a few flagged athletes for the coach board.
  - Rehearse the 90-second script end-to-end against live Deepgram; record a backup demo video.
  - _Requirements: 7.3, 10.2, 13.1_
