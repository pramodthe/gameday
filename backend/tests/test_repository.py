from datetime import date

from app.models import (
    Athlete,
    CheckIn,
    CheckInMetrics,
    ReadinessResult,
    TrainingLoad,
)
from app.repositories.local import LocalRepository


def _checkin(aid: str, d: date, load: float, score: int = 70) -> CheckIn:
    return CheckIn(
        id=f"{aid}-{d.isoformat()}",
        athlete_id=aid,
        date=d,
        metrics=CheckInMetrics(training=TrainingLoad(session_rpe=6, duration_min=60, load=load)),
        result=ReadinessResult(score=score, band="MODERATE", recommendation="MAINTAIN"),
    )


def test_upsert_and_get_athlete():
    repo = LocalRepository()
    repo.upsert_athlete(Athlete(id="a1", name="Alex", sport="soccer"))
    assert repo.get_athlete("a1").name == "Alex"
    assert repo.get_athlete("missing") is None


def test_workload_history_and_latest():
    repo = LocalRepository()
    repo.upsert_athlete(Athlete(id="a1", name="Alex", sport="soccer"))
    repo.add_checkin(_checkin("a1", date(2026, 7, 15), 300))
    repo.add_checkin(_checkin("a1", date(2026, 7, 16), 600))
    assert repo.get_workload_history("a1") == [300, 600]
    assert repo.get_latest_checkin("a1").date == date(2026, 7, 16)


def test_same_day_checkin_is_replaced():
    repo = LocalRepository()
    repo.upsert_athlete(Athlete(id="a1", name="Alex", sport="soccer"))
    repo.add_checkin(_checkin("a1", date(2026, 7, 16), 300))
    repo.add_checkin(_checkin("a1", date(2026, 7, 16), 900))
    assert repo.get_workload_history("a1") == [900]


def test_list_athletes_by_coach():
    repo = LocalRepository()
    repo.upsert_athlete(Athlete(id="a1", name="A", sport="soccer", coach_id="c1"))
    repo.upsert_athlete(Athlete(id="a2", name="B", sport="soccer", coach_id="c2"))
    assert [a.id for a in repo.list_athletes("c1")] == ["a1"]
