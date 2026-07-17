"""Session bootstrap endpoint (Req 1.2)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..repositories.factory import get_repository
from ..session.registry import create_session

router = APIRouter(prefix="/api")


class CreateSessionReq(BaseModel):
    athlete_id: str
    demo: bool = False


@router.post("/sessions")
def create_session_endpoint(req: CreateSessionReq) -> dict:
    repo = get_repository()
    athlete = repo.get_athlete(req.athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    session = create_session(athlete, repo, demo=req.demo)
    return {
        "session_id": session.id,
        "ws": f"/ws/checkin/{session.id}",
        "demo": req.demo,
        "athlete": {"id": athlete.id, "name": athlete.name, "sport": athlete.sport},
    }
