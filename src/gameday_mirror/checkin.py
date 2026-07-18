"""Adaptive daily check-in: readiness categories and content-based routing.

The voice agent may cover readiness dimensions in any order (and skip ones a
recalled memory already answers), so answers are routed to a category by their
content rather than by arrival position. This module is the single source of
truth for the category set, shared by the API router and the LiveKit bridge.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Ordered readiness dimensions. Order is the tie-breaker for classification and
# the fallback sequence when an answer matches no keywords.
CATEGORIES: tuple[str, ...] = (
    "sleep",
    "recovery",
    "training",
    "fuel",
    "mindset",
    "spending",
)

CHECKIN_STEPS: tuple[tuple[str, ...], ...] = (
    ("sleep", "recovery"),
    ("training",),
    ("fuel",),
    ("mindset", "spending"),
)
CHECKIN_TOTAL_STEPS = len(CHECKIN_STEPS)

# Keyword cues per category. Kept deterministic so classification works with no
# provider key; an OpenAI classifier can later slot in behind classify_answer().
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep", "slept", "hours", "hrs", "bed", "nap", "woke", "awake", "night"),
    "recovery": ("recover", "recovery", "sore", "soreness", "ache", "achy", "fatigue",
                 "tired", "fresh", "stiff", "doms", "heavy legs"),
    "training": ("training", "practice", "workout", "gym", "session", "lift", "run",
                 "game", "load", "exercise", "conditioning", "drill"),
    "fuel": ("eat", "ate", "eaten", "food", "meal", "breakfast", "lunch", "dinner",
             "nutrition", "hydrate", "hydration", "water", "protein", "fuel", "snack"),
    "mindset": ("focus", "focused", "mindset", "confidence", "confident", "stress",
                "stressed", "motivation", "motivated", "mood", "mental", "nervous",
                "anxious", "calm", "discipline"),
    "spending": ("spend", "spent", "spending", "money", "dollar", "cost", "paid",
                 "buy", "bought", "dining", "budget", "$"),
}


def _cue_hits(cue: str, lowered: str, tokens: list[str]) -> bool:
    # Multi-word phrases and the "$" symbol match anywhere; single words match as
    # a token prefix so plurals/inflections count ("dollars"→"dollar") without
    # loose mid-word hits ("tonight" must not match "night").
    if " " in cue or cue == "$":
        return cue in lowered
    return any(token.startswith(cue) for token in tokens)


def classify_answer(transcript: str, already_captured: Iterable[str]) -> str:
    """Route a spoken answer to the best-fit readiness category.

    Prefers categories not yet captured this session; only re-uses a captured
    category once every dimension has been covered. Falls back to the next
    uncaptured category (in CATEGORIES order) when nothing matches.
    """
    captured = set(already_captured)
    candidates = [category for category in CATEGORIES if category not in captured]
    if not candidates:
        candidates = list(CATEGORIES)

    lowered = transcript.lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    best_category = candidates[0]
    best_score = -1
    for category in candidates:
        score = sum(1 for cue in _KEYWORDS[category] if _cue_hits(cue, lowered, tokens))
        if score > best_score:
            best_category = category
            best_score = score
    return best_category


def classify_answer_categories(
    transcript: str,
    already_captured: Iterable[str],
) -> tuple[str, ...]:
    """Map one primary check-in answer to every dimension it covers."""
    captured = set(already_captured)
    category = classify_answer(transcript, captured)
    step = next((group for group in CHECKIN_STEPS if category in group), (category,))
    remaining = tuple(item for item in step if item not in captured)
    return remaining or (category,)


def completed_steps(captured_categories: Iterable[str]) -> int:
    """Count completed primary questions from the six stored dimensions."""
    captured = set(captured_categories)
    return sum(set(step).issubset(captured) for step in CHECKIN_STEPS)


def checkin_complete(captured_categories: Iterable[str]) -> bool:
    """True once every readiness dimension has an answer."""
    return set(CATEGORIES).issubset(set(captured_categories))
