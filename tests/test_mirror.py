from apps.api.routers.mirror import _metric
from gameday_mirror.sponsors import DEFAULT_PLAN, validate_plan
from gameday_mirror.vision import fallback_analysis


def test_sleep_metric_extracts_hours() -> None:
    metric = _metric("sleep", "I slept about 7.5 hours")

    assert metric["display_value"] == "7.5 hrs"
    assert metric["status"] == "good"


def test_fuel_metric_flags_missed_meal() -> None:
    metric = _metric("fuel", "I skipped breakfast")

    assert metric["display_value"] == "Missed"
    assert metric["status"] == "risk"


def test_rules_rewrite_unsafe_plan(monkeypatch) -> None:
    monkeypatch.delenv("ENKRYPTAI_API_KEY", raising=False)
    monkeypatch.delenv("ENKRYPT_API_KEY", raising=False)
    actions = [{"id": "unsafe", "eyebrow": "Now", "title": "Push", "detail": "Play through injury."}]

    validated, status = validate_plan(actions)

    assert validated == DEFAULT_PLAN
    assert status == "rules_rewritten"


def test_pose_fallback_rewards_balanced_squat() -> None:
    analysis = fallback_analysis(
        {"reps": 3, "min_knee_angle": 94, "symmetry_gap": 3, "torso_lean": 16}
    )

    assert analysis["score"] >= 85
    assert analysis["source"] == "pose_fallback"
