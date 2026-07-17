from apps.api.routers.mirror import _memory_summary, _metric
from gameday_mirror.agui import ExerciseSharedState
from gameday_mirror.checkin import CATEGORIES, checkin_complete, classify_answer
from gameday_mirror.exercises import exercise_context_update, exercise_is_active, is_exercise_request
from gameday_mirror.lessons import fallback_lesson
from gameday_mirror.sponsors import DEFAULT_PLAN, EMBED_DIM, _embedding, validate_plan
from gameday_mirror.vision import fallback_analysis


def test_sleep_metric_extracts_hours() -> None:
    metric = _metric("sleep", "I slept about 7.5 hours")

    assert metric["display_value"] == "7.5 hrs"
    assert metric["status"] == "good"


def test_fuel_metric_flags_missed_meal() -> None:
    metric = _metric("fuel", "I skipped breakfast")

    assert metric["display_value"] == "Missed"
    assert metric["status"] == "risk"


def test_metric_covers_all_six_categories() -> None:
    for category in CATEGORIES:
        metric = _metric(category, "generic answer with 5 units")
        assert metric["key"] == category
        assert metric["display_value"]
        assert metric["status"] in {"neutral", "good", "attention", "risk"}

    assert _metric("recovery", "legs are really sore and tired")["status"] == "attention"
    assert _metric("mindset", "I feel stressed and nervous")["display_value"] == "Strained"


def test_embedding_falls_back_to_hash_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    vector = _embedding("five hours of sleep and a hard practice")

    assert len(vector) == EMBED_DIM
    assert abs(sum(value * value for value in vector) - 1.0) < 1e-6


def test_classify_routes_by_content_not_order() -> None:
    assert classify_answer("I slept about five hours last night", []) == "sleep"
    assert classify_answer("my legs feel sore and I'm fatigued", []) == "recovery"
    assert classify_answer("I ate out and spent forty dollars", []) == "spending"
    assert classify_answer("hard team practice at six tonight", []) == "training"


def test_classify_skips_already_captured_until_full() -> None:
    captured: list[str] = []
    for _ in CATEGORIES:
        chosen = classify_answer("nonspecific answer", captured)
        assert chosen not in captured
        captured.append(chosen)
    assert set(captured) == set(CATEGORIES)


def test_checkin_complete_requires_full_coverage() -> None:
    assert not checkin_complete({"sleep", "fuel"})
    assert not checkin_complete(CATEGORIES[:-1])
    assert checkin_complete(CATEGORIES)


def test_memory_summary_varies_with_answers() -> None:
    plan = [{"id": "fuel", "eyebrow": "AM", "title": "Refuel on purpose", "detail": "Eat."}]
    tired = _memory_summary(
        [
            {"category": "sleep", "transcript": "only four hours"},
            {"category": "fuel", "transcript": "skipped breakfast"},
        ],
        plan,
    )
    rested = _memory_summary(
        [
            {"category": "sleep", "transcript": "a full nine hours"},
            {"category": "fuel", "transcript": "ate three solid meals"},
        ],
        plan,
    )

    assert tired != rested
    assert "Refuel on purpose" in tired
    assert "attention" in tired  # four hours flags the sleep metric


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


def test_exercise_request_is_not_recorded_as_checkin_answer() -> None:
    assert is_exercise_request("Nova, can you check my squat form?")
    assert is_exercise_request("Teach me how to do a reverse lunge")
    assert not is_exercise_request("I did squats at practice this morning")


def test_exercise_progress_becomes_agent_context() -> None:
    context = exercise_context_update(
        {
            "type": "exercise_progress",
            "reps": 3,
            "target_reps": 5,
            "cue": "Keep pressure even through both feet.",
        }
    )

    assert context == (
        "Exercise sensor verified squat rep 3 of 5. "
        "Keep pressure even through both feet."
    )


def test_lesson_ready_becomes_agent_context() -> None:
    context = exercise_context_update(
        {
            "type": "exercise_lesson_ready",
            "exercise_name": "reverse lunge",
            "summary": "Build single-leg strength with a controlled backward step.",
            "form_cues": ["Stay tall", "Keep the front heel planted", "Move with control"],
        }
    )

    assert context is not None
    assert "reverse lunge visual guide is ready" in context
    assert "Stay tall" in context
    assert exercise_is_active("exercise_lesson_ready") is True
    assert exercise_is_active("exercise_lesson_closed") is False


def test_lesson_fallback_matches_requested_pattern() -> None:
    lesson = fallback_lesson("reverse lunge")

    assert lesson["exercise_name"] == "Reverse Lunge"
    assert lesson["motion_pattern"] == "lunge"
    assert lesson["source"] == "curated_fallback"


def test_shared_state_rejects_stale_exercise_payloads() -> None:
    state = ExerciseSharedState("room-1")
    state.begin_lesson("tool-a", "reverse lunge")
    first_snapshot = state.apply_telemetry(
        {
            "type": "exercise_lesson_ready",
            "request_id": "tool-a",
            "exercise_name": "reverse lunge",
            "lesson": {"exercise_name": "Reverse Lunge"},
        }
    )
    duplicate_snapshot = state.apply_telemetry(
        {
            "type": "exercise_lesson_ready",
            "request_id": "tool-a",
            "exercise_name": "reverse lunge",
            "lesson": {"exercise_name": "Reverse Lunge"},
        }
    )
    state.begin_lesson("tool-b", "push-up")

    stale_snapshot = state.apply_telemetry(
        {
            "type": "exercise_lesson_closed",
            "request_id": "tool-a",
            "exercise_name": "reverse lunge",
        }
    )

    assert first_snapshot is not None
    assert duplicate_snapshot is None
    assert stale_snapshot is None
    assert state.request_id == "tool-b"
    assert state.exercise["name"] == "push-up"
    assert state.exercise["status"] == "requested"


def test_shared_state_emits_agui_tool_and_snapshot_events() -> None:
    state = ExerciseSharedState("room-1")

    events = state.begin_squat("tool-squat")

    assert [event["type"] for event in events] == [
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "STATE_SNAPSHOT",
    ]
    assert events[-1]["snapshot"]["revision"] == 1
