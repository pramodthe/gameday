"""In-memory repository — the default local persistence.

Fast and dependency-free for the demo. Data resets on restart, so the app seeds
a demo athlete + roster at startup (see app.seed).
"""
from __future__ import annotations

from ..models import Athlete, CheckIn, Streak


class LocalRepository:
    def __init__(self) -> None:
        self._athletes: dict[str, Athlete] = {}
        self._checkins: dict[str, list[CheckIn]] = {}  # athlete_id -> chronological list
        self._streaks: dict[str, Streak] = {}

    # --- athletes ---
    def upsert_athlete(self, athlete: Athlete) -> Athlete:
        self._athletes[athlete.id] = athlete
        self._checkins.setdefault(athlete.id, [])
        return athlete

    def get_athlete(self, athlete_id: str) -> Athlete | None:
        return self._athletes.get(athlete_id)

    def list_athletes(self, coach_id: str | None = None) -> list[Athlete]:
        athletes = list(self._athletes.values())
        if coach_id is not None:
            athletes = [a for a in athletes if a.coach_id == coach_id]
        return athletes

    # --- check-ins ---
    def add_checkin(self, checkin: CheckIn) -> CheckIn:
        bucket = self._checkins.setdefault(checkin.athlete_id, [])
        # one record per calendar day: replace any existing same-day check-in
        bucket = [c for c in bucket if c.date != checkin.date]
        bucket.append(checkin)
        bucket.sort(key=lambda c: c.date)
        self._checkins[checkin.athlete_id] = bucket
        return checkin

    def get_latest_checkin(self, athlete_id: str) -> CheckIn | None:
        bucket = self._checkins.get(athlete_id, [])
        return bucket[-1] if bucket else None

    def get_checkins(self, athlete_id: str, days: int = 28) -> list[CheckIn]:
        return list(self._checkins.get(athlete_id, []))[-days:]

    def get_workload_history(self, athlete_id: str, days: int = 28) -> list[float]:
        return [
            (c.metrics.training.load or 0.0)
            for c in self._checkins.get(athlete_id, [])[-days:]
        ]

    # --- streaks ---
    def get_streak(self, athlete_id: str) -> Streak | None:
        return self._streaks.get(athlete_id)

    def set_streak(self, streak: Streak) -> Streak:
        self._streaks[streak.athlete_id] = streak
        return streak
