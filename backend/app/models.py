"""Pydantic domain models — the source of truth for persistence and API payloads."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Band = Literal["LOW", "MODERATE", "HIGH"]
Recommendation = Literal["PUSH", "MAINTAIN", "RECOVER"]


class Athlete(BaseModel):
    id: str
    name: str
    sport: str
    coach_id: str | None = None
    baseline_daily_load: float = 300.0  # seed for provisional ACWR
    created_at: datetime | None = None


class TrainingLoad(BaseModel):
    session_rpe: int | None = None  # 1..10
    duration_min: int | None = None
    load: float | None = None  # session_rpe * duration_min

    @classmethod
    def from_rpe(cls, rpe: int | None, minutes: int | None) -> "TrainingLoad":
        load = float(rpe * minutes) if rpe is not None and minutes is not None else None
        return cls(session_rpe=rpe, duration_min=minutes, load=load)


class Soreness(BaseModel):
    areas: list[str] = Field(default_factory=list)  # e.g. ["right_hamstring"]


class Nutrition(BaseModel):
    fueled: bool | None = None
    notes: str | None = None


class CheckInMetrics(BaseModel):
    sleep_hours: float | None = None
    training: TrainingLoad = Field(default_factory=TrainingLoad)
    soreness: Soreness = Field(default_factory=Soreness)
    nutrition: Nutrition = Field(default_factory=Nutrition)
    mood: int | None = None  # 1..5
    unknown_fields: list[str] = Field(default_factory=list)


class ReadinessResult(BaseModel):
    score: int  # 0..100
    band: Band
    components: dict[str, float] = Field(default_factory=dict)
    acwr: float | None = None
    acwr_provisional: bool = False
    flags: list[str] = Field(default_factory=list)  # HIGH_INJURY_RISK, UNDERTRAINING
    recommendation: Recommendation


class CheckIn(BaseModel):
    id: str
    athlete_id: str
    date: date
    metrics: CheckInMetrics
    result: ReadinessResult
    coaching_text: str = ""
    transcript: list[dict] = Field(default_factory=list)  # [{"q":..., "answer":...}]
    created_at: datetime | None = None


class Streak(BaseModel):
    athlete_id: str
    current: int = 0
    last_check_in_date: date | None = None
