from datetime import date, timedelta

from app.models import Streak
from app.services.streaks import next_streak

D = date(2026, 7, 17)


def test_first_checkin_is_one():
    assert next_streak("a1", None, D).current == 1


def test_consecutive_day_increments():
    prev = Streak(athlete_id="a1", current=4, last_check_in_date=D - timedelta(days=1))
    assert next_streak("a1", prev, D).current == 5


def test_same_day_recheckin_no_increment():
    prev = Streak(athlete_id="a1", current=4, last_check_in_date=D)
    assert next_streak("a1", prev, D).current == 4


def test_gap_resets_to_one():
    prev = Streak(athlete_id="a1", current=9, last_check_in_date=D - timedelta(days=3))
    s = next_streak("a1", prev, D)
    assert s.current == 1
    assert s.last_check_in_date == D
