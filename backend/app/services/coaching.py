"""Recommendation rules + coaching message generation.

`recommend()` is the deterministic rule layer. `generate_message()` produces the
spoken one-liner: it uses the LLM when a key is configured and always falls back
to `fallback_message()` (no-LLM, deterministic) on any error or missing key.
"""
from __future__ import annotations

from ..config import settings
from . import lyzr_client

ACWR_PUSH_MIN = 0.8
ACWR_PUSH_MAX = 1.3


def recommend(band: str, acwr: float | None, flags: list[str] | None) -> str:
    """Map (readiness band, ACWR, flags) -> PUSH | MAINTAIN | RECOVER."""
    flags = flags or []
    if band == "LOW" or "HIGH_INJURY_RISK" in flags:
        return "RECOVER"
    if band == "HIGH" and acwr is not None and ACWR_PUSH_MIN <= acwr <= ACWR_PUSH_MAX:
        return "PUSH"
    return "MAINTAIN"


def fallback_message(
    recommendation: str,
    readiness_score: int,
    acwr: float | None = None,
    flags: list[str] | None = None,
) -> str:
    """Deterministic one-line coaching message (no LLM)."""
    flags = flags or []
    reasons: list[str] = []
    if "HIGH_INJURY_RISK" in flags:
        ratio = f"{acwr}" if acwr is not None else "elevated"
        reasons.append(f"your workload ratio is {ratio}, a spike past the 1.5 injury-risk line")
    if readiness_score < 50:
        reasons.append("your readiness is low")
    if "UNDERTRAINING" in flags:
        reasons.append("your recent load has dropped off")
    reason = "; ".join(reasons) if reasons else "your inputs look balanced"

    verb = {
        "RECOVER": "Take a recovery day",
        "MAINTAIN": "Keep today steady",
        "PUSH": "You're clear to push today",
    }.get(recommendation, "Keep today steady")

    return f"Readiness {readiness_score}. {verb} — {reason}."


def _coaching_prompt(recommendation, readiness_score, acwr, flags, sport) -> str:
    return (
        f"You are Nova, a concise athletic readiness coach for a {sport or 'athlete'}. "
        f"Readiness is {readiness_score}/100, recommendation is {recommendation}, "
        f"ACWR is {acwr}, flags: {flags or []}. Reply with ONE short spoken sentence "
        f"(max 30 words) starting with 'Readiness {readiness_score}.' that states the "
        "recommendation and its single most important reason. No medical diagnosis, no emojis."
    )


def generate_message(
    recommendation: str,
    readiness_score: int,
    acwr: float | None = None,
    flags: list[str] | None = None,
    *,
    sport: str | None = None,
    metrics: dict | None = None,
) -> str:
    # Lyzr (sponsor) is the preferred conversational brain when configured.
    if lyzr_client.available():
        reply = lyzr_client.chat(_coaching_prompt(recommendation, readiness_score, acwr, flags, sport))
        if reply:
            return reply
    if settings.anthropic_api_key:
        try:
            return _llm_message(recommendation, readiness_score, acwr, flags, sport, metrics)
        except Exception:
            pass
    return fallback_message(recommendation, readiness_score, acwr, flags)


def _llm_message(
    recommendation: str,
    readiness_score: int,
    acwr: float | None,
    flags: list[str] | None,
    sport: str | None,
    metrics: dict | None,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    context = {
        "recommendation": recommendation,
        "readiness_score": readiness_score,
        "acwr": acwr,
        "flags": flags or [],
        "sport": sport,
        "metrics": metrics or {},
    }
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=120,
        system=(
            "You are Nova, a concise athletic readiness coach. Given the readiness data, "
            "speak ONE short sentence (max 30 words) that states the recommendation "
            "(PUSH/MAINTAIN/RECOVER) and its single most important reason. No medical "
            "diagnosis, no emojis. Start with 'Readiness <score>.'"
        ),
        messages=[{"role": "user", "content": f"Data: {context}"}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    text = " ".join(parts).strip()
    if not text:
        raise ValueError("empty LLM message")
    return text
