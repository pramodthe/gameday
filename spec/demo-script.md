# GameDay Mirror Demo Script

Status: **Draft v0.1**
Target duration: **90–120 seconds**

## Demo Objective

Make a judge experience the product rather than watch a feature tour. The demo must prove camera-native interaction, natural voice, realtime tool-driven UI, persistent memory, sponsor integrations, and a useful final outcome.

## Seeded Athlete

- Name: Jordan Lee
- Sport: Soccer
- Goal: Improve consistency before Saturday's match
- Current streak: 5 days
- Previous check-in: 4.5 hours of sleep, planned high-intensity training, exceeded dining target
- Today's planned session: Evening team practice

## Stage Setup

- Open directly on the mirror start screen.
- Confirm camera, microphone, LiveKit, ElevenLabs, and backend health before presenting.
- Keep demo mode available but visually labeled.
- Preload the seeded athlete and prior memory.
- Hide browser chrome if practical and use a large display.

## Live Flow

### 0:00–0:12 — Hook

Presenter:

> “Athletes have coaches for competition, but nobody coordinates recovery, mindset, and everyday accountability. GameDay Mirror does it in 90 seconds.”

The judge or presenter selects **Start Check-in**.

### 0:12–0:25 — Greeting

Agent:

> “Good morning, Jordan. You have team practice tonight. Let’s build today’s game plan.”

The camera remains central. The four-step progress indicator activates.

### 0:25–0:42 — Recovery

Agent:

> “How many hours did you sleep, and how recovered do you feel?”

Demo answer:

> “About five hours. I’m pretty tired.”

Expected UI: Sleep updates to **5 hrs**, recovery becomes **Low**, progress advances to 1/4.

### 0:42–0:57 — Training

Agent:

> “What training have you already completed or planned today?”

Demo answer:

> “No training yet. We have hard team practice at six.”

Expected UI: Training updates to **Practice · 6 PM**, progress advances to 2/4.

### 0:57–1:10 — Fuel

Agent:

> “How has your nutrition been so far?”

Demo answer:

> “Mostly good, but I skipped breakfast.”

Expected UI: Fuel updates to **Breakfast missed**, progress advances to 3/4.

### 1:10–1:24 — Mindset or Money

Agent:

> “What needs the most discipline today: confidence, focus, or spending?”

Demo answer:

> “Spending. I ate out again yesterday.”

Expected UI: Spending updates to **Attention**, progress advances to 4/4.

### 1:24–1:42 — Memory Moment

Agent:

> “That is two short-sleep days, and yesterday you planned another intense session. I’m adjusting today’s priorities instead of simply repeating the plan.”

Expected UI: A small **Based on yesterday** memory card appears with its source date.

### 1:42–1:58 — Plan Reveal

The cards transition into a three-item plan:

1. Eat a balanced meal before noon.
2. Take a 20-minute recovery break before practice.
3. Keep dining spending below the selected daily target.

Agent:

> “Want to lock this in?”

Demo answer:

> “Lock it in.”

Expected UI: streak advances to 6 days and completion animation plays.

## Sponsor Proof

Mention sponsors only after the experience:

> “LiveKit carries the realtime camera and voice session. ElevenLabs powers the conversation. Lyzr controls the check-in workflow and tool calls. InsForge persists and streams the cards, Qdrant recalls relevant history, and Enkrypt validates the final plan.”

Do not interrupt the live flow with architecture explanations.

## Fallback Demo

If voice fails:

1. Switch to the visible text fallback.
2. Submit the same four seeded answers.
3. Continue realtime card updates, memory retrieval, and plan generation.
4. State that the transport failed while the agent workflow remained operational.

If the network is unstable, use labeled demo mode with prerecorded agent audio and deterministic events. Never pretend the fallback is live.

## Rehearsal Checklist

- Complete five uninterrupted runs.
- Verify the selected microphone and camera.
- Confirm secrets are server-side and production URLs are configured.
- Check that prior memory belongs to the seeded athlete.
- Reset the demo session and streak between runs.
- Confirm card text is readable from the judging distance.
- Keep the full presentation under two minutes.
- Prepare one sentence each for privacy, market, and differentiation questions.
