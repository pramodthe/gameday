"""Coach team readiness board (Req 10)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from ..repositories.factory import get_repository

router = APIRouter(prefix="/api")


def _is_flagged(row: dict) -> bool:
    return row["recommendation"] == "RECOVER" or "HIGH_INJURY_RISK" in (row["flags"] or [])


@router.get("/coach/{coach_id}/board")
def get_board(coach_id: str) -> dict:
    repo = get_repository()
    today = date.today()
    rows: list[dict] = []

    for athlete in repo.list_athletes(coach_id):
        checkin = repo.get_latest_checkin(athlete.id)
        if checkin is None:
            rows.append({
                "athlete_id": athlete.id, "name": athlete.name, "sport": athlete.sport,
                "checked_in_today": False, "readiness": None, "band": None,
                "recommendation": None, "flags": [], "acwr": None,
            })
        else:
            rows.append({
                "athlete_id": athlete.id, "name": athlete.name, "sport": athlete.sport,
                "checked_in_today": checkin.date == today,
                "readiness": checkin.result.score, "band": checkin.result.band,
                "recommendation": checkin.result.recommendation,
                "flags": checkin.result.flags, "acwr": checkin.result.acwr,
            })

    # Surface at-risk athletes first, then worst readiness first; no-check-in last.
    rows.sort(key=lambda r: (
        0 if _is_flagged(r) else 1,
        r["readiness"] if r["readiness"] is not None else 10_000,
    ))
    return {"coach_id": coach_id, "date": today, "athletes": rows}
