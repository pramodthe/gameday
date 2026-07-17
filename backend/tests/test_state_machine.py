from datetime import date, timedelta

from app.models import (
    Athlete,
    CheckIn,
    CheckInMetrics,
    ReadinessResult,
    TrainingLoad,
)
from app.repositories.local import LocalRepository
from app.session.demo import DEMO_ANSWERS, DEMO_WORKLOAD
from app.session.state import Session


def _seed_loads(repo, aid, loads, end_date):
    for i, load in enumerate(loads):
        d = end_date - timedelta(days=len(loads) - i)
        repo.add_checkin(
            CheckIn(
                id=f"{aid}-{d.isoformat()}",
                athlete_id=aid,
                date=d,
                metrics=CheckInMetrics(training=TrainingLoad(session_rpe=6, duration_min=60, load=load)),
                result=ReadinessResult(score=70, band="MODERATE", recommendation="MAINTAIN"),
            )
        )


def test_full_demo_session_produces_stage_numbers():
    repo = LocalRepository()
    athlete = Athlete(id="a1", name="Alex", sport="soccer", baseline_daily_load=300)
    repo.upsert_athlete(athlete)
    _seed_loads(repo, "a1", DEMO_WORKLOAD, date(2026, 7, 17))

    s = Session("sess1", athlete, repo, use_llm=False)
    assert s.current_question()["index"] == 1
    for ans in DEMO_ANSWERS:
        s.submit_answer(ans)
    assert s.state == "READY_TO_COMPLETE"

    res = s.complete(today=date(2026, 7, 17))
    assert res["readiness"] == 47
    assert res["band"] == "LOW"
    assert res["recommendation"] == "RECOVER"
    assert "HIGH_INJURY_RISK" in res["flags"]
    assert res["acwr"] == 1.6
    assert res["streak"] == 1


def test_metrics_captured_from_answers():
    repo = LocalRepository()
    athlete = Athlete(id="a1", name="Alex", sport="soccer")
    repo.upsert_athlete(athlete)
    s = Session("s", athlete, repo, use_llm=False)
    for ans in DEMO_ANSWERS:
        s.submit_answer(ans)
    assert s.metrics.sleep_hours == 5
    assert s.metrics.training.session_rpe == 9
    assert s.metrics.training.duration_min == 120
    assert s.metrics.soreness.areas == ["right hamstring"]
    assert s.metrics.nutrition.fueled is False
    assert s.metrics.mood == 2


def test_reask_once_then_advances_with_unknown():
    repo = LocalRepository()
    athlete = Athlete(id="a2", name="Sam", sport="basketball")
    repo.upsert_athlete(athlete)
    s = Session("s2", athlete, repo, use_llm=False)

    ev = s.submit_answer("uhh I don't know")
    assert any(e["type"] == "coach.log" for e in ev)
    assert s.current_question()["field"] == "sleep"  # re-asked, still on Q1

    s.submit_answer("still not sure")
    assert s.current_question()["field"] == "load"  # advanced
    assert "sleep" in s.metrics.unknown_fields
