"""Scripted Demo Mode answers (Req 13).

Feeding these through the same Session the live path uses reproduces the on-stage
result deterministically: readiness 47 (LOW), ACWR 1.6 (HIGH_INJURY_RISK), RECOVER
— provided the demo athlete is seeded with DEMO_WORKLOAD (see app.seed).
"""
from __future__ import annotations

DEMO_ANSWERS = [
    "About five hours, and pretty restless.",
    "Two hour match yesterday, absolutely cooked — a 9 out of 10.",
    "Yeah, my right hamstring's pretty tight.",
    "No, I skipped breakfast.",
    "Honestly feeling flat, like a two.",
]

# 21 steady days + a hard recent week; with the live session's 1080 load this
# yields acute 600 / chronic 375 = ACWR 1.60.
DEMO_WORKLOAD = [300.0] * 21 + [520.0] * 6
