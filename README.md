# GameDay Mirror

GameDay Mirror is a camera-first daily check-in for student athletes. A LiveKit room carries camera, microphone, agent audio, and structured UI events. An ElevenLabs voice agent asks four questions, while the interface updates recovery, training, fuel, mindset, and spending cards in real time.

The app works immediately in deterministic demo mode. Live voice mode activates when LiveKit and ElevenLabs credentials are configured.

## Structure

```text
apps/web/           React 19 + Vite mirror experience
apps/api/           FastAPI token and orchestration endpoints
apps/mirror_agent/  LiveKit ↔ ElevenLabs audio bridge
src/gameday_mirror/ InsForge, Qdrant, Lyzr, and Enkrypt adapters
migrations/         InsForge/Postgres schema
spec/               Product, technical, and demo specifications
```

## Run Locally

Prerequisites: Node.js 20+, Python 3.11+, and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
npm install
uv sync --extra dev
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API runs at `http://127.0.0.1:8001`.

## Live Voice

Set `LIVEKIT_*`, `ELEVENLABS_API_KEY`, and `ELEVENLABS_AGENT_ID` in `.env`, then run the worker separately:

```bash
npm run dev:agent
```

Configure the ElevenLabs agent to ask one question each for sleep, training, fuel, and spending. Its prompt may reference `{{athlete_name}}`, `{{recent_memory}}`, and `{{session_id}}` dynamic variables.

## Checks

```bash
npm run lint       # TypeScript type-check
npm run build      # Production web build
npm test           # Python tests
```

Sponsor integrations are optional. InsForge persists check-ins, Qdrant retrieves prior memories, Lyzr generates the final plan, and Enkrypt validates plan safety. Without credentials, each adapter falls back safely.
