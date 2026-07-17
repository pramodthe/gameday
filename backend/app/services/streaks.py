"""Pure streak arithmetic (Req 9)."""
from __future__ import annotations

from datetime import date, timedelta

from ..models import Streak


def next_streak(athlete_id: str, prev: Streak | None, check_in_date: date) -> Streak:
    """Given the previous streak and a new completed check-in date, return the updated streak.

    - first check-in, or a gap of 2+ days -> 1 (today counts)
    - consecutive day -> increment
    - same day (re-check-in) -> unchanged
    """
    last = prev.last_check_in_date if prev else None
    current = prev.current if prev else 0

    if last is None:
        current = 1
    elif last == check_in_date:
        current = max(current, 1)
    elif last == check_in_date - timedelta(days=1):
        current = current + 1
    else:
        current = 1

    return Streak(athlete_id=athlete_id, current=current, last_check_in_date=check_in_date)
