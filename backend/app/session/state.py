"""Check-in session state machine (Req 2, 5, 6, 7, 8, 9).

Synchronous and I/O-free except for the injected repository — audio/LLM I/O lives
in the WebSocket layer and the services. This makes the whole conversation flow
unit-testable by feeding answer strings to `submit_answer()`.
"""
from __future__ import annotations

from datetime import date, datetime

from ..models import (
    Athlete,
    CheckIn,
    CheckInMetrics,
    Nutrition,
    ReadinessResult,
    Soreness,
    TrainingLoad,
)
from ..repositories.base import Repository
from ..services import coaching, extraction, scoring
from ..services.streaks import next_streak

# (field, spoken prompt) in order.
QUESTIONS: list[tuple[str, str]] = [
    ("sleep", "Good morning. Quick check-in. How did you sleep — hours and quality?"),
    ("load", "What did you train yesterday, and how hard was it, one to ten?"),
    ("soreness", "Anything sore or tight today?"),
    ("nutrition", "Have you fueled yet — did you eat this morning?"),
    ("mood", "Last one — how are you feeling, one to five?"),
]
TOTAL = len(QUESTIONS)


def _fmt(x: float | None) -> str:
    if x is None:
        return "—"
    return str(int(x)) if float(x).is_integer() else str(x)


class Session:
    def __init__(
        self,
        session_id: str,
        athlete: Athlete,
        repo: Repository,
        use_llm: bool | None = None,
        demo: bool = False,
    ) -> None:
        self.id = session_id
        self.athlete = athlete
        self.repo = repo
        self.use_llm = False if demo else use_llm
        self.demo = demo
        self.index = 0
        self.state = "LIVE"
        self.metrics = CheckInMetrics()
        self.transcript: list[dict] = []
        self._reasked: set[str] = set()
        self.result: ReadinessResult | None = None

    # --- flow ---

    def current_question(self) -> dict | None:
        if self.index >= TOTAL:
            return None
        field, text = QUESTIONS[self.index]
        return {"type": "question", "index": self.index + 1, "total": TOTAL, "field": field, "text": text}

    def submit_answer(self, text: str) -> list[dict]:
        """Process the answer to the current question; return events to emit."""
        events: list[dict] = []
        if self.index >= TOTAL:
            return events

        field, _ = QUESTIONS[self.index]
        events.append({"type": "transcript", "final": True, "text": text})

        value = extraction.extract(field, text, use_llm=self.use_llm)
        if not value.get("_ok", False) and field not in self._reasked:
            self._reasked.add(field)
            events.append({"type": "coach.log", "text": "Didn't catch that — let's try once more."})
            events.append(self.current_question())
            return events

        if not value.get("_ok", False):
            self.metrics.unknown_fields.append(field)
        self._apply(field, value)
        self.transcript.append({"q": field, "answer": text})
        events.extend(self._metric_events(field))

        self.index += 1
        nxt = self.current_question()
        if nxt is None:
            self.state = "READY_TO_COMPLETE"
            events.append({"type": "state", "value": "READY_TO_COMPLETE"})
        else:
            events.append(nxt)
        return events

    def _apply(self, field: str, value: dict) -> None:
        if field == "sleep":
            self.metrics.sleep_hours = value.get("sleep_hours")
        elif field == "load":
            self.metrics.training = TrainingLoad.from_rpe(
                value.get("session_rpe"), value.get("duration_min")
            )
        elif field == "soreness":
            self.metrics.soreness = Soreness(areas=value.get("areas", []) or [])
        elif field == "nutrition":
            self.metrics.nutrition = Nutrition(fueled=value.get("fueled"), notes=value.get("notes"))
        elif field == "mood":
            self.metrics.mood = value.get("mood")

    def _metric_events(self, field: str) -> list[dict]:
        m = self.metrics
        if field == "sleep":
            h = m.sleep_hours
            status = "risk" if (h is not None and h < 4) else ("caution" if (h is not None and h < 7) else "ok")
            log = f"{_fmt(h)} hours of sleep logged." if h is not None else "Sleep noted."
            return [
                {"type": "metric.update", "field": "sleep_hours", "value": h, "status": status},
                {"type": "coach.log", "text": log},
            ]
        if field == "load":
            tr = m.training
            log = f"{tr.duration_min} minutes of training logged." if tr.duration_min else "Training logged."
            return [
                {"type": "metric.update", "field": "training",
                 "value": {"rpe": tr.session_rpe, "minutes": tr.duration_min, "load": tr.load},
                 "status": "ok"},
                {"type": "coach.log", "text": log},
            ]
        if field == "soreness":
            areas = m.soreness.areas
            status = "risk" if len(areas) >= 2 else ("caution" if areas else "ok")
            log = ("Soreness noted: " + ", ".join(areas) + ".") if areas else "No soreness — good."
            return [
                {"type": "metric.update", "field": "soreness", "value": areas, "status": status},
                {"type": "coach.log", "text": log},
            ]
        if field == "nutrition":
            fueled = m.nutrition.fueled
            status = "caution" if fueled is False else "ok"
            log = "Fueled — nice." if fueled else ("Skipped meal flagged." if fueled is False else "Nutrition noted.")
            return [
                {"type": "metric.update", "field": "nutrition", "value": fueled, "status": status},
                {"type": "coach.log", "text": log},
            ]
        if field == "mood":
            mood = m.mood
            status = "caution" if (mood is not None and mood <= 2) else "ok"
            log = f"Mood {mood} out of 5 logged." if mood is not None else "Mood noted."
            return [
                {"type": "metric.update", "field": "mood", "value": mood, "status": status},
                {"type": "coach.log", "text": log},
            ]
        return []

    # --- completion ---

    def complete(self, today: date | None = None) -> dict:
        today = today or date.today()
        self.state = "SAVING"

        tr = self.metrics.training
        history = self.repo.get_workload_history(self.athlete.id, 28)
        if tr.load is not None:
            history = history + [tr.load]
        acwr_res = scoring.acwr(history, self.athlete.baseline_daily_load)

        breakdown = scoring.readiness(
            sleep_hours=self.metrics.sleep_hours,
            session_rpe=tr.session_rpe,
            soreness_areas=self.metrics.soreness.areas,
            fueled=self.metrics.nutrition.fueled,
            mood=self.metrics.mood,
        )
        rec = coaching.recommend(breakdown.band, acwr_res.acwr, acwr_res.flags)
        coaching_text = coaching.generate_message(
            rec, breakdown.score, acwr_res.acwr, acwr_res.flags, sport=self.athlete.sport
        )

        result = ReadinessResult(
            score=breakdown.score,
            band=breakdown.band,
            components=breakdown.components,
            acwr=acwr_res.acwr,
            acwr_provisional=acwr_res.provisional,
            flags=acwr_res.flags,
            recommendation=rec,
        )
        checkin = CheckIn(
            id=f"{self.athlete.id}-{today.isoformat()}",
            athlete_id=self.athlete.id,
            date=today,
            metrics=self.metrics,
            result=result,
            coaching_text=coaching_text,
            transcript=self.transcript,
            created_at=datetime.now(),
        )
        self.repo.add_checkin(checkin)
        streak = next_streak(self.athlete.id, self.repo.get_streak(self.athlete.id), today)
        self.repo.set_streak(streak)

        self.result = result
        self.state = "COMPLETE"
        return {
            "type": "result",
            "readiness": result.score,
            "band": result.band,
            "recommendation": result.recommendation,
            "acwr": result.acwr,
            "acwr_provisional": result.acwr_provisional,
            "flags": result.flags,
            "components": result.components,
            "coaching_text": coaching_text,
            "streak": streak.current,
        }
