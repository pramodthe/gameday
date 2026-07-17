"""Deterministic readiness + ACWR scoring.

Pure functions, no I/O — this is the sports-science credibility core and is
fully unit-tested. See specs/readyroom/design.md for the documented formulas.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

DEFAULT_WEIGHTS: dict[str, float] = {
    "sleep": 0.30,
    "fatigue": 0.25,
    "soreness": 0.20,
    "nutrition": 0.15,
    "mood": 0.10,
}

# Injury-risk thresholds for the acute:chronic workload ratio.
ACWR_HIGH_RISK = 1.5
ACWR_UNDERTRAINING = 0.8


@dataclass
class ReadinessBreakdown:
    score: int
    band: str
    components: dict[str, float]  # per-input 0..100 sub-scores that were used
    missing: list[str]  # inputs that were unknown and dropped


@dataclass
class AcwrResult:
    acwr: float | None
    provisional: bool
    flags: list[str]


# --- sub-score functions (each returns 0..100, or None when the input is unknown) ---

_SLEEP_ANCHORS = [(4, 35), (5, 50), (6, 70), (7, 90), (8, 100)]


def _interp(x: float, anchors: list[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation across sorted (x, y) anchors, clamped at the ends."""
    if x <= anchors[0][0]:
        return float(anchors[0][1])
    if x >= anchors[-1][0]:
        return float(anchors[-1][1])
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return float(anchors[-1][1])


def sleep_sub(hours: float | None) -> float | None:
    if hours is None:
        return None
    if hours < 4:
        return 20.0
    return float(_interp(hours, _SLEEP_ANCHORS))


def fatigue_sub(session_rpe: int | None) -> float | None:
    """Yesterday's session RPE (1=easy..10=maximal). Harder session -> more fatigue -> lower readiness."""
    if session_rpe is None:
        return None
    r = max(1, min(10, session_rpe))
    return 100.0 - (r - 1) / 9 * 80.0  # rpe 1 -> 100, rpe 10 -> 20


def soreness_sub(areas: list[str] | None) -> float | None:
    if areas is None:
        return None
    return float(max(0.0, 100.0 - 25.0 * len(areas)))


def nutrition_sub(fueled: bool | None) -> float:
    """Always contributes: unknown maps to a neutral 70 rather than being dropped."""
    if fueled is True:
        return 100.0
    if fueled is False:
        return 40.0
    return 70.0


def mood_sub(mood: int | None) -> float | None:
    if mood is None:
        return None
    m = max(1, min(5, mood))
    return (m - 1) / 4 * 80.0 + 20.0  # mood 1 -> 20, mood 5 -> 100


def band_for(score: float) -> str:
    if score < 50:
        return "LOW"
    if score < 75:
        return "MODERATE"
    return "HIGH"


def readiness(
    *,
    sleep_hours: float | None = None,
    session_rpe: int | None = None,
    soreness_areas: list[str] | None = None,
    fueled: bool | None = None,
    mood: int | None = None,
    weights: dict[str, float] | None = None,
) -> ReadinessBreakdown:
    """Composite readiness 0..100. Unknown inputs are dropped and remaining weights renormalized."""
    w = weights or DEFAULT_WEIGHTS
    subs: dict[str, float | None] = {
        "sleep": sleep_sub(sleep_hours),
        "fatigue": fatigue_sub(session_rpe),
        "soreness": soreness_sub(soreness_areas),
        "nutrition": nutrition_sub(fueled),  # never None
        "mood": mood_sub(mood),
    }
    present = {k: v for k, v in subs.items() if v is not None}
    missing = [k for k, v in subs.items() if v is None]

    total_w = sum(w[k] for k in present) or 1.0
    score_f = sum(w[k] * present[k] for k in present) / total_w
    score = round(score_f)

    return ReadinessBreakdown(
        score=score,
        band=band_for(score),
        components={k: round(v, 1) for k, v in present.items()},
        missing=missing,
    )


def acwr(daily_loads: list[float], baseline: float) -> AcwrResult:
    """Acute:Chronic Workload Ratio.

    daily_loads: one load value per day, chronological (most recent last).
    Windows shorter than 7/28 days are padded with the athlete's seeded baseline,
    and the result is marked provisional when fewer than 7 real days exist.
    """
    real_days = len(daily_loads)

    def window(n: int) -> list[float]:
        w = list(daily_loads[-n:])
        if len(w) < n:
            w = [baseline] * (n - len(w)) + w
        return w

    acute = mean(window(7))
    chronic = mean(window(28))
    ratio = (acute / chronic) if chronic else None

    flags: list[str] = []
    if ratio is not None:
        if ratio > ACWR_HIGH_RISK:
            flags.append("HIGH_INJURY_RISK")
        elif ratio < ACWR_UNDERTRAINING:
            flags.append("UNDERTRAINING")

    return AcwrResult(
        acwr=round(ratio, 2) if ratio is not None else None,
        provisional=real_days < 7,
        flags=flags,
    )
