from apps.api.routers.mirror import _memory_summary, _metric
from gameday_mirror.agui import ExerciseSharedState
from gameday_mirror.checkin import (
    CATEGORIES,
    CHECKIN_TOTAL_STEPS,
    checkin_complete,
    classify_answer,
    classify_answer_categories,
    completed_steps,
)
from gameday_mirror.exercises import checkin_resume_context, exercise_context_update, exercise_is_active, is_exercise_request
from gameday_mirror.lessons import fallback_lesson
from gameday_mirror.lyzr import _extract_json, _managed_agents, _route, _scoped_session_id
from gameday_mirror import sponsors
from gameday_mirror.sponsors import (
    DEFAULT_PLAN,
    EMBED_DIM,
    _embedding,
    recall_voice_context,
    store_workout_memory,
    validate_plan,
    workout_memory_summary,
)
from gameday_mirror.superflow import _parse_result, enabled as superflow_enabled
from gameday_mirror.vision import fallback_analysis
from gameday_mirror.workouts import WorkoutAdaptation, WorkoutSession, fallback_adaptation, fallback_workout


def test_sleep_metric_extracts_hours() -> None:
    metric = _metric("sleep", "I slept about 7.5 hours")

    assert metric["display_value"] == "7.5 hrs"
    assert metric["status"] == "good"


def test_fuel_metric_flags_missed_meal() -> None:
    metric = _metric("fuel", "I skipped breakfast")

    assert metric["display_value"] == "Missed"
    assert metric["status"] == "risk"


def test_sleep_metric_parses_spoken_number_words() -> None:
    assert _metric("sleep", "I got about eight hours")["display_value"] == "8 hrs"
    assert _metric("sleep", "seven and a half hours")["display_value"] == "7.5 hrs"
    assert _metric("sleep", "eight hours")["status"] == "good"
    # Spending spoken as words parses too
    assert _metric("spending", "I spent about thirty five dollars")["display_value"] == "$35"


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


def test_four_primary_answers_cover_all_six_dimensions() -> None:
    captured: list[str] = []
    transcripts = (
        "I slept six hours and feel pretty tired.",
        "I have a hard team practice at six.",
        "I skipped breakfast but drank water.",
        "I need discipline with spending; I spent thirty dollars.",
    )

    for transcript in transcripts:
        captured.extend(classify_answer_categories(transcript, captured))

    assert set(captured) == set(CATEGORIES)
    assert completed_steps(captured) == CHECKIN_TOTAL_STEPS == 4
    assert checkin_complete(captured)


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


def test_pose_fallback_scores_every_tracked_movement() -> None:
    good = {
        "squat": {"reps": 3, "min_primary_angle": 94, "symmetry_gap": 3, "alignment_deviation": 16},
        "pushup": {"reps": 4, "min_primary_angle": 90, "symmetry_gap": 4, "alignment_deviation": 8},
        "lunge": {"reps": 3, "min_primary_angle": 96, "symmetry_gap": 6, "alignment_deviation": 15},
        "glute_bridge": {"reps": 5, "max_primary_angle": 172, "symmetry_gap": 5, "alignment_deviation": 12},
        "plank": {"hold_seconds": 32, "alignment_deviation": 7},
    }
    for movement, metrics in good.items():
        result = fallback_analysis(metrics, movement)
        assert result["score"] >= 80, movement
        assert result["source"] == "pose_fallback"
        assert result["cues"]

    # A shallow, sagging push-up loses points and gets a depth cue.
    bad = fallback_analysis(
        {"reps": 2, "min_primary_angle": 125, "symmetry_gap": 4, "alignment_deviation": 22}, "pushup"
    )
    assert bad["score"] < 85
    assert any("elbow" in cue.lower() or "line" in cue.lower() for cue in bad["cues"])


def test_workout_fallback_tailors_to_recovery() -> None:
    recovery = fallback_workout("attention")
    hard = fallback_workout("high")
    moderate = fallback_workout("good")

    assert recovery["intensity"] == "recovery"
    assert hard["intensity"] == "hard"
    assert moderate["intensity"] == "moderate"
    # A low-recovery session is lighter than a well-recovered one.
    assert len(recovery["exercises"]) < len(hard["exercises"])

    # Every programmed movement is one the camera can actually track (Core 5).
    tracked = {"squat", "pushup", "lunge", "plank", "glute_bridge"}
    for session in (recovery, hard, moderate):
        runtime_fields = {"source", "decision_trace", "orchestration"}
        WorkoutSession.model_validate({k: v for k, v in session.items() if k not in runtime_fields})
        assert all(ex["motion_pattern"] in tracked for ex in session["exercises"])


def test_workout_memory_records_exact_exercise_doses(monkeypatch) -> None:
    workout = fallback_workout("good")
    summary = workout_memory_summary(workout)

    assert 'Workout "Full-body base"' in summary
    assert "Bodyweight Squat: 3 sets x 10 reps" in summary
    assert "Forearm Plank: 3 sets x 30-second holds" in summary

    captured: dict[str, object] = {}

    def fake_store(user_id, room_name, stored_summary, payload):
        captured.update(user_id=user_id, room_name=room_name, summary=stored_summary, payload=payload)
        return True

    monkeypatch.setattr(sponsors, "_store_memory_payload", fake_store)
    assert store_workout_memory("athlete-1", "room-1", workout) is True
    assert captured["payload"]["kind"] == "workout"


def test_voice_context_prioritizes_saved_routine(monkeypatch) -> None:
    memories = {
        "workout": [
            {
                "kind": "workout",
                "session_id": "room-2",
                "created_at": "2026-07-18T02:00:00+00:00",
                "summary": "Workout Full-body base: squats and push-ups.",
            }
        ],
        "movement": [
            {
                "kind": "movement",
                "session_id": "room-1",
                "created_at": "2026-07-17T02:00:00+00:00",
                "summary": "Push-up set: 8 verified reps.",
            }
        ],
        "checkin": [],
    }

    def fake_retrieve(user_id, query, *, limit=3, kinds=None):
        assert user_id == "athlete-1"
        return memories[(kinds or ("",))[0]]

    monkeypatch.setattr(sponsors, "retrieve_memories", fake_retrieve)
    context, recalled = recall_voice_context("athlete-1")

    assert context.startswith("WORKOUT: Workout Full-body base")
    assert "MOVEMENT: Push-up set" in context
    assert [item["kind"] for item in recalled] == ["workout", "movement"]


def test_lyzr_json_parser_accepts_fenced_output() -> None:
    parsed = _extract_json({"response": "```json\n{\"action\": \"continue\"}\n```"})

    assert parsed == {"action": "continue"}


def test_lyzr_manager_normalizes_readiness_route() -> None:
    assert _route("plan", {"route": "readiness", "status": "delegated"}) == "plan"
    assert _route("workout", {"route": "workout", "status": "delegated"}) == "workout"
    assert _route("adaptation", {"route": "unknown", "status": "delegated"}) == "adaptation"


def test_lyzr_manager_payload_lists_configured_specialists(monkeypatch) -> None:
    monkeypatch.setenv("LYZR_PLAN_AGENT_ID", "plan-id")
    monkeypatch.setenv("LYZR_WORKOUT_AGENT_ID", "workout-id")
    monkeypatch.setenv("LYZR_ADAPTATION_AGENT_ID", "adaptation-id")

    agents = _managed_agents()

    assert [agent["id"] for agent in agents] == ["plan-id", "workout-id", "adaptation-id"]
    assert [agent["name"] for agent in agents] == [
        "GameDay Readiness Analyst",
        "GameDay Workout Architect",
        "GameDay Movement Adaptation Coach",
    ]


def test_lyzr_sessions_are_stable_and_isolated_by_agent() -> None:
    assert _scoped_session_id("room-7", "director", "athlete") == "room-7--lyzr-director"
    assert _scoped_session_id("room-7", "workout", "athlete") == "room-7--lyzr-workout"
    assert _scoped_session_id("", "plan", "athlete") == "gameday-athlete--lyzr-plan"


def test_plan_generation_reuses_stable_lyzr_session(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_invoke(role, message, *, session_id, user_id, memory_used):
        captured.update(role=role, session_id=session_id, user_id=user_id)
        return [
            {"id": "one", "eyebrow": "Now", "title": "First", "detail": "Do one."},
            {"id": "two", "eyebrow": "Later", "title": "Second", "detail": "Do two."},
            {"id": "three", "eyebrow": "Tonight", "title": "Third", "detail": "Do three."},
        ], {"status": "completed"}

    monkeypatch.setattr(sponsors, "invoke_json", fake_invoke)
    _, source = sponsors.generate_plan(
        [{"category": "sleep", "transcript": "eight hours"}],
        [{"summary": "Previous session"}],
        session_id="room-stable",
        user_id="athlete-stable",
    )

    assert source == "lyzr"
    assert captured == {"role": "plan", "session_id": "room-stable", "user_id": "athlete-stable"}


def test_adaptation_fallback_reduces_dose_for_low_score() -> None:
    adaptation = fallback_adaptation("pushup", {"reps": 8}, {"score": 42})

    assert adaptation["action"] == "reduce_reps"
    assert adaptation["next_reps"] == 6
    assert adaptation["source"] == "deterministic"


def test_adaptation_schema_requires_nullable_output_fields() -> None:
    schema = WorkoutAdaptation.model_json_schema()

    assert set(schema["required"]) == {
        "action",
        "message",
        "reason",
        "next_reps",
        "next_hold_seconds",
        "next_rest_seconds",
        "replacement_movement",
    }
    WorkoutAdaptation.model_validate(
        {
            "action": "continue",
            "message": "Keep going.",
            "reason": "Movement quality is stable.",
            "next_reps": 8,
            "next_hold_seconds": None,
            "next_rest_seconds": 45,
            "replacement_movement": None,
        }
    )


def test_superflow_result_parser_accepts_agent_json() -> None:
    assert _parse_result('{"action":"continue"}') == {"action": "continue"}
    assert _parse_result(None) is None


def test_superflow_requires_all_runtime_ids(monkeypatch) -> None:
    monkeypatch.setenv("LYZR_API_KEY", "key")
    monkeypatch.setenv("LYZR_SUPERFLOW_ID", "flow")
    monkeypatch.delenv("LYZR_ADAPTATION_AGENT_ID", raising=False)

    assert superflow_enabled() is False


def test_exercise_request_is_not_recorded_as_checkin_answer() -> None:
    assert is_exercise_request("Nova, can you check my squat form?")
    assert is_exercise_request("Start push-ups with the camera")
    assert is_exercise_request("Teach me how to do a reverse lunge")
    assert not is_exercise_request("I did squats at practice this morning")


def test_exercise_resume_context_never_restarts_completed_checkin() -> None:
    assert "Do not restart readiness questions" in checkin_resume_context(4, 4)
    assert "next unanswered question only" in checkin_resume_context(2, 4)


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
    assert events[0]["toolCallName"] == "start_exercise"
    assert events[-1]["snapshot"]["revision"] == 1


def test_shared_state_tracks_manual_core_five_exercise() -> None:
    state = ExerciseSharedState("room-1")

    snapshot = state.apply_telemetry(
        {
            "type": "exercise_opened",
            "request_id": "manual-pushup",
            "trigger": "manual",
            "exercise": "pushup",
            "target_reps": 8,
        }
    )

    assert snapshot is not None
    assert state.exercise["name"] == "pushup"
    assert state.exercise["targetReps"] == 8
