# GameDay Mirror Specification

Status: **Implemented MVP v0.1**
Product: **GameDay Mirror**
Audience: Hackathon team, product reviewers, designers, and engineers

GameDay Mirror is a camera-first, voice-driven daily check-in for student athletes. In roughly 90 seconds, an athlete reports recovery, training, nutrition, mindset, and spending. Floating cards update around their live reflection, and the agent produces a personalized plan informed by previous check-ins.

## Specification Map

- [`product-spec.md`](./product-spec.md) — problem, users, experience, requirements, safety, and success criteria.
- [`technical-spec.md`](./technical-spec.md) — system architecture, service responsibilities, data model, events, and validation.
- [`demo-script.md`](./demo-script.md) — two-minute judging flow, seeded scenario, fallback path, and presentation checklist.

## Current Product Decisions

- The live camera is the primary interface; there is no traditional dashboard during check-in.
- The initial user is a student athlete balancing performance and personal finances.
- The agent asks four adaptive questions rather than displaying a static form.
- Prior-session memory must visibly change at least one recommendation.
- Voice, cards, progress, and the final plan must update in realtime.
- Raw camera and microphone media is not stored by default.
- The repository is now dedicated to GameDay Mirror; the previous application has been removed.

## Review Questions

1. Is the student-athlete audience specific enough, or should the MVP target all athletes?
2. Should spending remain a core metric or move to a later release?
3. Should the mirror provide coaching recommendations or only reflection and accountability?
4. Is a four-question session short enough for the live demo?
5. Which visual identity should we pursue: premium sports, playful game, or futuristic HUD?
6. Should the final output be a daily plan, a readiness score, or both?

Record requested changes directly in these documents or send a list of updates. Keep implementation changes aligned with the approved four-question journey.
