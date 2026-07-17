# Requirements Document

## Introduction

**ReadyRoom** is a voice-first athlete readiness coach. Each morning an athlete talks to a browser "mirror" (their webcam feed with glassmorphic overlays) for ~60 seconds. An AI coach ("Nova") asks a short, scripted set of questions about sleep, training load, soreness, fueling, and mood. The system transcribes the answers, extracts structured metrics, computes a **Readiness Score (0–100)** and an **ACWR injury-risk indicator** (acute:chronic workload ratio), and speaks back a recommendation — **PUSH / MAINTAIN / RECOVER**. Coaches see a team-wide readiness board that flags at-risk athletes for the day.

The goal is to deliver the daily-monitoring value of elite sports-science teams (readiness, load management, injury-risk flagging) through a 60-second conversation, for athletes and coaches who don't have that infrastructure.

### Personas
- **Athlete** — completes the daily voice check-in; sees their readiness, recommendation, and streak.
- **Coach** — views the aggregated readiness board for their roster and today's flagged athletes.

### Platform constraints
- **Backend:** FastAPI (Python), exposing REST + WebSocket APIs.
- **Frontend:** Browser SPA ("mirror" UI) using `getUserMedia` for the camera and microphone.
- **Voice:** Deepgram for speech-to-text (STT) and text-to-speech (TTS).
- **Persistence:** Repository abstraction with a local default (SQLite/in-memory) and an InsForge adapter.
- **Reliability:** A scripted **Demo Mode** must reproduce the full flow without live speech, for presenting.

### Glossary
- **Readiness Score** — composite 0–100 index of how prepared the athlete is to train today.
- **Training Load** — session RPE × duration (minutes), a standard internal-load proxy.
- **ACWR** — Acute:Chronic Workload Ratio = mean daily load over the last 7 days ÷ mean daily load over the last 28 days. Elevated injury risk when ACWR > 1.5 (or under-training when < 0.8).
- **Check-In** — one completed daily session producing one persisted record.

---

## Requirements

### Requirement 1 — Start a daily check-in session

**User Story:** As an athlete, I want to start a guided voice check-in, so that I can log my morning status hands-free in under a minute.

#### Acceptance Criteria
1. WHEN an athlete opens the mirror view THEN the system SHALL request camera and microphone permission and display the live camera feed.
2. WHEN the athlete starts a session THEN the system SHALL create a check-in session bound to the athlete and set its state to `LIVE`.
3. WHILE a session is active THE SYSTEM SHALL display a visible status indicator reflecting one of: `CONNECTING`, `LIVE`, `LISTENING`, `SAVING`.
4. IF the athlete has already completed a check-in for the current calendar day THEN the system SHALL still allow a new session but SHALL overwrite that day's record on completion.
5. WHERE microphone permission is denied THE SYSTEM SHALL fall back to Demo Mode and surface an explanatory message.

### Requirement 2 — Conduct the scripted question flow

**User Story:** As an athlete, I want the coach to ask me a fixed short set of questions, so that the check-in is fast, predictable, and complete.

#### Acceptance Criteria
1. WHEN a session becomes `LIVE` THEN the system SHALL ask an opening prompt and then ask exactly five questions in order: sleep, training load, soreness, fueling, mood.
2. WHILE asking a question THE SYSTEM SHALL display the current question index as `N/5`.
3. WHEN the athlete finishes answering a question THEN the system SHALL advance to the next question only after that answer has been transcribed and processed.
4. WHEN all five questions are answered THEN the system SHALL present a `Complete Check-in` action.
5. IF an answer cannot be interpreted for a question THEN the system SHALL re-ask that question once before recording it as `unknown`.

### Requirement 3 — Transcribe speech to text

**User Story:** As an athlete, I want my spoken answers converted to text accurately, so that the system can understand what I said.

#### Acceptance Criteria
1. WHEN the athlete speaks during a question THEN the system SHALL stream audio to the backend over the session WebSocket.
2. THE SYSTEM SHALL transcribe streamed audio via Deepgram STT and return interim and final transcripts.
3. WHEN a final transcript is produced for the active question THEN the system SHALL associate it with that question and proceed to extraction.
4. IF the Deepgram STT connection fails THEN the system SHALL retry once and, on repeated failure, degrade to a text-input fallback for that answer.

### Requirement 4 — Extract structured metrics from answers

**User Story:** As an athlete, I want to answer naturally in plain language, so that I don't have to fill in forms.

#### Acceptance Criteria
1. WHEN a final transcript is available for a question THEN the system SHALL extract a typed value using an LLM structured-extraction call constrained to a defined schema.
2. THE SYSTEM SHALL extract: `sleep_hours` (number), `training_load` (session RPE 1–10 and duration in minutes), `soreness` (list of body-area flags), `nutrition` (fueled boolean and notes), and `mood` (1–5 with optional label).
3. WHEN a numeric value is stated indirectly (e.g., "about five", "a couple hours") THEN the system SHALL normalize it to a number.
4. IF a required field is absent from the answer THEN the system SHALL set that field to `null` and mark it `unknown` rather than guessing.
5. WHEN extraction completes for a question THEN the system SHALL emit a live UI update reflecting the new value.

### Requirement 5 — Update the live readiness dashboard

**User Story:** As an athlete, I want to see my metrics fill in as I talk, so that the check-in feels responsive and trustworthy.

#### Acceptance Criteria
1. WHEN a metric is extracted THEN the system SHALL update the corresponding dashboard panel within the same session in real time.
2. WHERE a metric crosses a defined caution threshold (e.g., sleep < 6h, soreness present, skipped meal) THE SYSTEM SHALL render that metric with a caution (amber) state.
3. WHERE a metric crosses a defined risk threshold THE SYSTEM SHALL render that metric with a risk (red) state.
4. THE SYSTEM SHALL show a running transcript log of the coach's confirmations (e.g., "20 minutes of movement logged").

### Requirement 6 — Compute the Readiness Score

**User Story:** As an athlete, I want a single readiness number, so that I instantly know how prepared I am to train today.

#### Acceptance Criteria
1. WHEN all available metrics for a session are collected THEN the system SHALL compute a Readiness Score between 0 and 100 using a documented weighted formula over sleep, load/fatigue, soreness, nutrition, and mood.
2. WHERE one or more inputs are `unknown` THE SYSTEM SHALL compute the score from available inputs and record which inputs were missing.
3. THE SYSTEM SHALL classify the score into a band: `LOW` (0–49), `MODERATE` (50–74), `HIGH` (75–100).
4. WHEN the score is computed THEN the system SHALL persist the score and its component breakdown with the check-in.

### Requirement 7 — Flag injury risk via ACWR

**User Story:** As an athlete and coach, I want an injury-risk indicator based on my workload trend, so that we can prevent overtraining injuries.

#### Acceptance Criteria
1. WHEN a check-in is completed THEN the system SHALL append the session's training load to the athlete's daily workload history.
2. THE SYSTEM SHALL compute ACWR as the ratio of mean daily load over the last 7 days to mean daily load over the last 28 days.
3. WHERE fewer than 7 days of history exist THE SYSTEM SHALL use the athlete's seeded baseline load and label the ACWR result as `provisional`.
4. WHERE ACWR > 1.5 THE SYSTEM SHALL raise a `HIGH_INJURY_RISK` flag; WHERE ACWR < 0.8 THE SYSTEM SHALL raise an `UNDERTRAINING` flag.
5. WHEN an injury-risk flag is raised THEN the system SHALL include it in the coaching recommendation and the coach board.

### Requirement 8 — Generate and speak a coaching recommendation

**User Story:** As an athlete, I want the coach to tell me what to do today, so that the readiness data becomes an actionable decision.

#### Acceptance Criteria
1. WHEN readiness and ACWR are computed THEN the system SHALL derive a recommendation of `PUSH`, `MAINTAIN`, or `RECOVER` using documented rules.
2. THE SYSTEM SHALL produce recommendation `RECOVER` WHEN readiness band is `LOW` OR a `HIGH_INJURY_RISK` flag is present.
3. THE SYSTEM SHALL produce recommendation `PUSH` WHEN readiness band is `HIGH` AND ACWR is within 0.8–1.3.
4. WHEN a recommendation is derived THEN the system SHALL generate a short spoken coaching message that states the recommendation and its primary reason, and SHALL play it back via Deepgram TTS.
5. THE SYSTEM SHALL render the recommendation text alongside the audio for accessibility.

### Requirement 9 — Track check-in streaks

**User Story:** As an athlete, I want credit for consistent check-ins, so that I stay motivated to do them daily.

#### Acceptance Criteria
1. WHEN an athlete completes a check-in on a calendar day THEN the system SHALL increment the streak if the previous check-in was the prior calendar day, otherwise reset the streak to 1.
2. THE SYSTEM SHALL display the current streak count on the mirror view.
3. IF a day is missed THEN the system SHALL reset the streak to 0 until the next completed check-in.

### Requirement 10 — Coach team readiness board

**User Story:** As a coach, I want a roster-wide readiness view, so that I can adjust today's session for at-risk athletes.

#### Acceptance Criteria
1. WHEN a coach opens the board THEN the system SHALL list every athlete on the roster with their latest readiness score, band, recommendation, and any injury-risk flag.
2. THE SYSTEM SHALL sort or visually surface athletes with `RECOVER` recommendations or `HIGH_INJURY_RISK` flags first.
3. WHERE an athlete has not checked in today THE SYSTEM SHALL show a `no check-in` state rather than stale data.
4. THE SYSTEM SHALL reflect a newly completed athlete check-in on the board without requiring a full page reload.

### Requirement 11 — Persist athletes, check-ins, and history

**User Story:** As a returning user, I want my data to persist, so that trends, streaks, and ACWR are meaningful over time.

#### Acceptance Criteria
1. THE SYSTEM SHALL persist athletes, completed check-ins, workload history, and streaks through a repository interface.
2. THE SYSTEM SHALL provide a local default persistence implementation and an InsForge-backed implementation selectable by configuration.
3. WHEN persistence to the configured backend fails THEN the system SHALL surface a `SAVING` failure state and retain the completed check-in in memory for retry.
4. THE SYSTEM SHALL expose read APIs for an athlete's latest readiness, check-in history, and streak.

### Requirement 12 — Guard health advice (stretch)

**User Story:** As a user, I want the coaching advice to stay within safe bounds, so that I'm not given unsafe or fabricated medical claims.

#### Acceptance Criteria
1. WHEN a coaching message is generated THEN the system SHALL screen it through a safety guardrail before playback.
2. WHERE the guardrail flags disallowed content (diagnosis, medication, fabricated injury claims) THE SYSTEM SHALL replace it with a safe, generic recovery message.
3. THE SYSTEM SHALL never present the recommendation as a medical diagnosis and SHALL include a brief non-medical disclaimer in the athlete view.

### Requirement 13 — Demo Mode (presentation reliability)

**User Story:** As a presenter, I want a scripted mode that reproduces the full flow without live audio, so that the demo cannot fail on stage.

#### Acceptance Criteria
1. WHERE Demo Mode is enabled THE SYSTEM SHALL play a predetermined sequence of answers, metric updates, score, ACWR flag, and coaching message that mirrors the live flow.
2. WHEN Demo Mode runs THEN the system SHALL NOT depend on live microphone input or external STT.
3. THE SYSTEM SHALL allow toggling between Live and Demo Mode from the mirror view.
