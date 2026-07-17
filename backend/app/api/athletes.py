"""Athlete REST endpoints (Req 6.4, 9.2, 11.4)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import Athlete
from ..repositories.factory import get_repository

router = APIRouter(prefix="/api")


class CreateAthleteReq(BaseModel):
    id: str | None = None
    name: str
    sport: str
    coach_id: str | None = None
    baseline_daily_load: float = 300.0


@router.post("/athletes")
def create_athlete(req: CreateAthleteReq) -> Athlete:
    repo = get_repository()
    athlete = Athlete(
        id=req.id or uuid.uuid4().hex[:10],
        name=req.name,
        sport=req.sport,
        coach_id=req.coach_id,
        baseline_daily_load=req.baseline_daily_load,
        created_at=datetime.now(),
    )
    return repo.upsert_athlete(athlete)


@router.get("/athletes/{athlete_id}/readiness")
def get_readiness(athlete_id: str) -> dict:
    repo = get_repository()
    checkin = repo.get_latest_checkin(athlete_id)
    if checkin is None:
        raise HTTPException(status_code=404, detail="no check-in yet")
    return {
        "athlete_id": athlete_id,
        "date": checkin.date,
        "result": checkin.result,
        "coaching_text": checkin.coaching_text,
    }


@router.get("/athletes/{athlete_id}/history")
def get_history(athlete_id: str, days: int = 28) -> dict:
    repo = get_repository()
    checkins = repo.get_checkins(athlete_id, days)
    return {
        "athlete_id": athlete_id,
        "checkins": [
            {
                "date": c.date,
                "readiness": c.result.score,
                "band": c.result.band,
                "recommendation": c.result.recommendation,
                "acwr": c.result.acwr,
                "load": c.metrics.training.load,
            }
            for c in checkins
        ],
    }


@router.get("/athletes/{athlete_id}/streak")
def get_streak(athlete_id: str) -> dict:
    repo = get_repository()
    streak = repo.get_streak(athlete_id)
    return {
        "athlete_id": athlete_id,
        "current": streak.current if streak else 0,
        "last_check_in_date": streak.last_check_in_date if streak else None,
    }
