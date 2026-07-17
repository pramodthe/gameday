"""In-memory registry of active check-in sessions."""
from __future__ import annotations

import uuid

from ..models import Athlete
from ..repositories.base import Repository
from .state import Session

_sessions: dict[str, Session] = {}


def create_session(
    athlete: Athlete,
    repo: Repository,
    demo: bool = False,
    use_llm: bool | None = None,
) -> Session:
    session_id = uuid.uuid4().hex[:12]
    session = Session(session_id, athlete, repo, use_llm=use_llm, demo=demo)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def drop_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
