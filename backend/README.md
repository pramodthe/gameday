# ReadyRoom — Backend (FastAPI)

Voice-first athlete readiness coach. FastAPI orchestrates the check-in state machine,
Deepgram STT/TTS, LLM extraction + coaching, and deterministic Readiness/ACWR scoring.

See `../specs/readyroom/` for requirements, design, and the task plan.

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run the tests (scoring core is fully unit-tested)
pytest

# run the API
uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health   http://127.0.0.1:8000/docs
```

## Layout

```
app/
  main.py            FastAPI app + health/config routes
  config.py          settings, feature flags, scoring weights (from env)
  models.py          Pydantic domain models
  services/
    scoring.py       readiness() + acwr()  — pure, deterministic
    coaching.py      recommend() rules + fallback coaching message
    (deepgram_client.py, extraction.py … land in later tasks)
  repositories/      persistence (local default / InsForge adapter)
tests/               scoring / acwr / coaching unit tests
```

## Status

**Backend check-in loop is complete and verified (39 tests passing).**

Implemented:
- Scaffold, config, Pydantic models
- Scoring core: readiness + ACWR + PUSH/MAINTAIN/RECOVER (deterministic, tested)
- Repository (in-memory local) + streaks
- Natural-language extraction (rule-based fallback, keyless; optional LLM)
- Session state machine (5-question flow, re-ask, completion)
- Deepgram client (prerecorded STT + TTS, graceful no-key degradation)
- WebSocket `/ws/checkin/{id}` (text / demo / audio paths) with live event stream
- REST: athletes, sessions, readiness, history, streak, coach board
- Seed demo athlete + roster; scripted Demo Mode reproduces the stage result

Runs keyless today (rule-based extraction + Demo Mode). Set `DEEPGRAM_API_KEY` for
live voice and `ANTHROPIC_API_KEY` for LLM-backed extraction/coaching.

Next: React mirror UI + coach board frontend; InsForge adapter (prize); Lyzr/Qdrant/Enkrypt stretches.

## Try the check-in loop

```bash
uvicorn app.main:app --port 8091            # (needs `websockets` installed for WS)
curl localhost:8091/api/coach/coach-1/board # seeded roster
# create a session, then connect a WS client to /ws/checkin/{id} and send
#   {"type":"demo_run"}  -> streams the full check-in and returns the result
```
