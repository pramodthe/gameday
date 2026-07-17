# Repository Guidelines

## Project Structure & Module Organization

GameDay Mirror is a small full-stack monorepo. The React interface lives in `apps/web/src/features/mirror/`; keep UI state, event types, and styles together there. `apps/api/` exposes FastAPI routes for LiveKit tokens and check-in orchestration. `apps/mirror_agent/bridge.py` carries audio and data events between LiveKit and ElevenLabs. Sponsor adapters live in `src/gameday_mirror/`, database changes in `migrations/`, and approved behavior in `spec/`.

## Build, Test, and Development Commands

- `npm install` installs root and web dependencies.
- `uv sync --extra dev` creates `.venv` with API, worker, and test dependencies.
- `npm run dev` starts the web app on `3000` and API on `8001`.
- `npm run dev:agent` starts the LiveKit/ElevenLabs worker; credentials are required.
- `npm run lint` runs TypeScript type-checking.
- `npm run build` creates the production web bundle.
- `npm test` runs Python tests with pytest.

## Coding Style & Naming Conventions

Use two-space indentation for TypeScript/CSS and four spaces for Python. React components use `PascalCase`, hooks use `useCamelCase`, and Python modules/functions use `snake_case`. Keep realtime event fields in `snake_case` because they cross the Python/TypeScript boundary as JSON. Prefer typed event contracts and small deterministic fallbacks over provider-specific logic in UI components.

## Testing Guidelines

Place Python tests in `tests/` with names such as `test_mirror_events.py`. Frontend changes must pass `npm run lint` and `npm run build`. Manually verify camera-denied behavior and complete the four-answer demo before merging realtime changes.

## Commit & Pull Request Guidelines

Use concise imperative commits, for example `Add Qdrant memory retrieval`. Keep pull requests focused, describe the user-visible flow, list required environment variables, and include screenshots or a short recording for UI changes. Never commit `.env`, raw audio/video, or provider API keys.

<!-- INSFORGE:START -->
## InsForge backend

This project uses [InsForge](https://insforge.dev): an all-in-one, open-source Postgres-based backend (BaaS) that gives this app a database, authentication, file storage, edge functions, realtime, an AI model gateway, and payments through one platform.

- **Project:** **sports_hack** (API base `https://i87d4gcb.us-east.insforge.app`)
- **Skills:** these InsForge skills are installed for supported coding agents. Reach for them before implementing any InsForge feature instead of guessing the API:
  - `insforge`: app code with the `@insforge/sdk` client (database CRUD, auth, storage, edge functions, realtime, AI, email, and Stripe payments).
  - `insforge-cli`: backend and infrastructure via the `insforge` CLI (projects, SQL, migrations, RLS policies, storage buckets, functions, secrets, payment setup, schedules, deploys).
  - `insforge-debug`: diagnosing failures (SDK/HTTP errors, RLS denials, auth and OAuth issues) and running security or performance audits.
  - `insforge-integrations`: wiring external auth providers (Clerk, Auth0, WorkOS, Better Auth, etc.) for JWT-based RLS, or the OKX x402 payment facilitator.
  - `find-skills`: discovering additional skills on demand.
- **Credentials:** app code reads keys from `.env.local`; the CLI reads `.insforge/project.json`. Never hardcode or commit keys.

Key patterns:

- Database inserts take an array: `insert([{ ... }])`.
- Reference users with `auth.users(id)`; use `auth.uid()` in RLS policies.
- For storage uploads, persist both the returned `url` and `key`.
<!-- INSFORGE:END -->
