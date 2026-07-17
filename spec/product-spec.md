# GameDay Mirror Product Specification

Status: **Draft v0.1**
Primary track: **Athlete Performance & Coaching**

## Product Summary

GameDay Mirror is a 90-second conversational ritual that helps student athletes coordinate recovery, training, mindset, nutrition, and spending. The athlete sees a full-screen camera view with translucent cards around their reflection. A voice agent asks adaptive questions, updates the cards immediately, recalls relevant history, and generates a small, achievable plan for the day.

## Problem

Student athletes manage performance and everyday life across disconnected tools, conversations, and memory. Logging apps require manual entry and rarely connect yesterday's behavior to today's decisions. GameDay Mirror replaces the form with a short conversation and turns repeated check-ins into useful longitudinal context.

## Target User

The MVP targets a college or competitive student athlete who:

- Trains at least three times per week.
- Has limited access to dedicated support staff.
- Wants accountability without maintaining spreadsheets.
- Is comfortable completing a voice check-in from a laptop.

## Goals

- Complete a useful daily check-in in under two minutes.
- Make every spoken answer produce visible feedback.
- Demonstrate memory by referencing a previous check-in.
- Produce one realistic daily plan with clear reasoning.
- Create a camera-native experience that is compelling in a live demo.

## Non-Goals

- Medical diagnosis, injury clearance, or treatment advice.
- Continuous biometric monitoring or wearable integrations.
- Facial emotion recognition or identity detection.
- Financial transactions, investment advice, or bank connectivity.
- A comprehensive coaching or team-management platform.

## Core Experience

### 1. Start

The athlete grants camera and microphone access. The mirror displays their local camera feed, connection state, streak, and a single **Start Check-in** action.

### 2. Greeting and Recall

The agent greets the athlete by profile name and retrieves a concise memory from recent sessions. It may mention a previous commitment only when that memory directly affects today's check-in.

### 3. Four-Question Check-in

The default categories are:

1. **Recovery:** sleep duration and perceived recovery.
2. **Training:** completed or planned movement.
3. **Fuel:** nutrition quality or one relevant food choice.
4. **Mindset or Money:** confidence, stress, or spending relative to the athlete's current goal.

Questions may adapt, but the session must collect no more than four primary answers. Follow-up clarification is allowed when an answer cannot be converted into a metric.

### 4. Realtime Feedback

After each answer, the agent confirms what it understood and calls a structured update tool. The corresponding card changes value, status color, and progress. The transcript remains concise and secondary to the mirror.

### 5. Memory Moment

At least one response is compared with prior context. Example:

> “You planned a high-intensity workout, but this is your second short-sleep day. I’m changing today’s first priority to recovery.”

The UI identifies the prior observation and the resulting adjustment without presenting memory as certainty.

### 6. Daily Plan

The completed check-in produces up to three actions:

- One performance or recovery action.
- One personal accountability action.
- One optional stretch action.

The athlete can accept the plan or edit one item by voice. Completion updates the streak and stores the session.

## Functional Requirements

- Full-screen mirrored camera feed with responsive glass overlays.
- Natural turn-taking, interruption, mute, camera, and disconnect controls.
- Listening, thinking, speaking, saving, and complete states.
- Structured metric extraction from conversational answers.
- Four-step progress indicator.
- Realtime card updates without page refresh.
- Retrieval of relevant prior reflections.
- Persistent session, answer, metric, plan, and streak records.
- Graceful text fallback when voice is unavailable.
- Demo mode with deterministic seeded history.

## Visual Direction

- The user remains visually central at all times.
- Cards use high-contrast translucent surfaces and large numeric values.
- Green communicates completion, amber communicates attention, and red is reserved for connection or processing errors—not athlete judgment.
- Motion should reinforce state changes: card fill, progress advance, plan reveal, and streak completion.
- Avoid dense charts, side navigation, and conventional dashboard chrome during the check-in.

## Safety and Privacy

- Describe outputs as reflection and coaching support, not professional advice.
- Do not infer mood, health, or identity from facial appearance.
- Process the camera locally for display; do not store raw video by default.
- Store raw audio only when the athlete explicitly opts in.
- Show and allow correction of extracted metrics before final completion.
- Explain when a recommendation uses prior-session memory.
- Provide deletion controls for profile and check-in history after the MVP.

## Success Criteria

- A first-time user completes the session without instruction.
- The live demo completes in under 120 seconds.
- UI metric updates appear within 500 ms of a confirmed agent tool result.
- Agent speech begins within two seconds of normal end-of-turn conditions.
- One prior memory visibly changes the final plan.
- The experience remains usable if camera analysis is disabled.

## Open Decisions

- Final product name and visual identity.
- Whether spending is mandatory or an optional fifth card.
- Whether the agent uses a readiness score.
- Whether athletes can create custom check-in categories.
- Whether the final plan is shareable with a coach.
