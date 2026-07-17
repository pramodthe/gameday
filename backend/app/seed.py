"""Seed a demo athlete + coach roster at startup (Req 10.2, 18).

The primary demo athlete (Alex) gets a realistic 27-day workload so the live
check-in produces a real, non-provisional ACWR of 1.60. Three roster athletes get
today's check-ins spanning PUSH / MAINTAIN / RECOVER so the coach board is populated.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import (
    Athlete,
    CheckIn,
    CheckInMetrics,
    Nutrition,
    ReadinessResult,
    Soreness,
    TrainingLoad,
)
from .repositories.factory import get_repository
from .services import coaching, scoring
from .services.streaks import next_streak
from .session.demo import DEMO_WORKLOAD

COACH_ID = "coach-1"
DEMO_ATHLETE_ID = "a-alex"


def _seed_history(repo, athlete_id: str, loads: list[float], end_date: date) -> None:
    for i, load in enumerate(loads):
        d = end_date - timedelta(days=len(loads) - i)
        repo.add_checkin(
            CheckIn(
                id=f"{athlete_id}-{d.isoformat()}",
                athlete_id=athlete_id,
                date=d,
                metrics=CheckInMetrics(training=TrainingLoad(session_rpe=6, duration_min=60, load=load)),
                result=ReadinessResult(score=70, band="MODERATE", recommendation="MAINTAIN"),
            )
        )


def _seed_today(repo, athlete: Athlete, *, sleep, rpe, mins, soreness, fueled, mood, today: date) -> None:
    load = float(rpe * mins)
    history = repo.get_workload_history(athlete.id, 28) + [load]
    acwr_res = scoring.acwr(history, athlete.baseline_daily_load)
    breakdown = scoring.readiness(
        sleep_hours=sleep, session_rpe=rpe, soreness_areas=soreness, fueled=fueled, mood=mood
    )
    rec = coaching.recommend(breakdown.band, acwr_res.acwr, acwr_res.flags)
    result = ReadinessResult(
        score=breakdown.score, band=breakdown.band, components=breakdown.components,
        acwr=acwr_res.acwr, acwr_provisional=acwr_res.provisional, flags=acwr_res.flags,
        recommendation=rec,
    )
    repo.add_checkin(
        CheckIn(
            id=f"{athlete.id}-{today.isoformat()}",
            athlete_id=athlete.id,
            date=today,
            metrics=CheckInMetrics(
                sleep_hours=sleep,
                training=TrainingLoad.from_rpe(rpe, mins),
                soreness=Soreness(areas=soreness),
                nutrition=Nutrition(fueled=fueled),
                mood=mood,
            ),
            result=result,
            coaching_text=coaching.fallback_message(rec, breakdown.score, acwr_res.acwr, acwr_res.flags),
            created_at=datetime.now(),
        )
    )
    repo.set_streak(next_streak(athlete.id, repo.get_streak(athlete.id), today))


def seed_demo_data() -> None:
    repo = get_repository()
    today = date.today()

    # Primary demo athlete: seeded workload history, no check-in today (the live demo fills it).
    alex = Athlete(
        id=DEMO_ATHLETE_ID, name="Alex Rivera", sport="soccer",
        coach_id=COACH_ID, baseline_daily_load=300.0, created_at=datetime.now(),
    )
    repo.upsert_athlete(alex)
    _seed_history(repo, alex.id, DEMO_WORKLOAD, today)

    # Roster with today's check-ins -> variety on the coach board.
    roster = [
        dict(id="a-sam", name="Sam Chen", sport="basketball",
             sleep=8, rpe=6, mins=60, soreness=[], fueled=True, mood=5),       # ~PUSH
        dict(id="a-jordan", name="Jordan Lee", sport="running",
             sleep=6, rpe=8, mins=50, soreness=[], fueled=True, mood=3),       # ~MAINTAIN
        dict(id="a-maria", name="Maria Gomez", sport="soccer",
             sleep=3, rpe=5, mins=40, soreness=["left calf"], fueled=False, mood=1),  # ~RECOVER
    ]
    for r in roster:
        athlete = Athlete(
            id=r["id"], name=r["name"], sport=r["sport"],
            coach_id=COACH_ID, baseline_daily_load=300.0, created_at=datetime.now(),
        )
        repo.upsert_athlete(athlete)
        _seed_today(
            repo, athlete,
            sleep=r["sleep"], rpe=r["rpe"], mins=r["mins"],
            soreness=r["soreness"], fueled=r["fueled"], mood=r["mood"], today=today,
        )
