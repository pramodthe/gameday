"""Repository factory — selects the persistence backend from config (Req 11.2)."""
from __future__ import annotations

from ..config import settings
from .base import Repository
from .local import LocalRepository

_repo: Repository | None = None


def get_repository() -> Repository:
    global _repo
    if _repo is None:
        if settings.persistence == "insforge":
            # InsForge adapter lands in a later task; fall back to local until then.
            _repo = LocalRepository()
        else:
            _repo = LocalRepository()
    return _repo


def reset_repository() -> None:
    """Test helper — drop the singleton so each test gets a clean store."""
    global _repo
    _repo = None
