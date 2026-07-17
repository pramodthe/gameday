from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def enabled() -> bool:
    return bool(_profile_id() and (_database_url() or (_base_url() and _api_key())))


def _database_url() -> str:
    return (os.environ.get("INSFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()


def _base_url() -> str:
    return (os.environ.get("INSFORGE_URL") or "").rstrip("/")


def _api_key() -> str:
    return (os.environ.get("INSFORGE_API_KEY") or "").strip()


def _profile_id() -> str:
    return (os.environ.get("INSFORGE_PROFILE_ID") or "").strip()


def _headers(*, representation: bool = False) -> dict[str, str]:
    key = _api_key()
    headers = {"Authorization": f"Bearer {key}", "apikey": key}
    if representation:
        headers["Prefer"] = "return=representation"
    return headers


def _records(table: str) -> str:
    return f"{_base_url()}/api/database/records/{table}"


def _fetchone(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with psycopg.connect(_database_url(), row_factory=dict_row, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None


def ensure_session(room_name: str, *, demo_mode: bool = False) -> dict[str, Any] | None:
    if not enabled():
        return None
    if _database_url():
        return _fetchone(
            """
            WITH athlete AS (
              INSERT INTO public.athlete_profiles (user_id, display_name, sport, primary_goal)
              VALUES (%s, %s, %s, %s)
              ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name
              RETURNING id
            )
            INSERT INTO public.checkin_sessions (athlete_profile_id, livekit_room_name, demo_mode)
            SELECT id, %s, %s FROM athlete
            ON CONFLICT (livekit_room_name) DO UPDATE SET livekit_room_name = EXCLUDED.livekit_room_name
            RETURNING id, livekit_room_name, status
            """,
            (
                _profile_id(),
                os.environ.get("MIRROR_ATHLETE_NAME", "Jordan Lee"),
                os.environ.get("MIRROR_ATHLETE_SPORT", "Basketball"),
                os.environ.get("MIRROR_ATHLETE_GOAL", "Protect recovery while staying consistent"),
                room_name,
                demo_mode,
            ),
        )

    with httpx.Client(timeout=30.0) as client:
        athlete_response = client.get(
            _records("athlete_profiles"),
            headers=_headers(),
            params={"user_id": f"eq.{_profile_id()}", "select": "id", "limit": "1"},
        )
        athlete_response.raise_for_status()
        athletes = athlete_response.json()
        if athletes:
            athlete_id = athletes[0]["id"]
        else:
            created = client.post(
                _records("athlete_profiles"),
                headers=_headers(representation=True),
                json=[
                    {
                        "user_id": _profile_id(),
                        "display_name": os.environ.get("MIRROR_ATHLETE_NAME", "Jordan Lee"),
                        "sport": os.environ.get("MIRROR_ATHLETE_SPORT", "Basketball"),
                        "primary_goal": os.environ.get(
                            "MIRROR_ATHLETE_GOAL",
                            "Protect recovery while staying consistent",
                        ),
                    }
                ],
            )
            created.raise_for_status()
            athlete_id = created.json()[0]["id"]

        existing = client.get(
            _records("checkin_sessions"),
            headers=_headers(),
            params={"livekit_room_name": f"eq.{room_name}", "select": "id,livekit_room_name,status", "limit": "1"},
        )
        existing.raise_for_status()
        rows = existing.json()
        if rows:
            return rows[0]
        created = client.post(
            _records("checkin_sessions"),
            headers=_headers(representation=True),
            json=[{"athlete_profile_id": athlete_id, "livekit_room_name": room_name, "demo_mode": demo_mode}],
        )
        created.raise_for_status()
        return created.json()[0]


def record_answer(
    room_name: str,
    *,
    category: str,
    transcript: str,
    metric: dict[str, Any],
) -> dict[str, Any] | None:
    if not enabled():
        return None
    session = ensure_session(room_name)
    if not session:
        return None
    session_id = str(session["id"])
    if _database_url():
        return _fetchone(
            """
            WITH answer AS (
              INSERT INTO public.checkin_answers
                (session_id, category, transcript, normalized_value, unit, confidence)
              VALUES (%s, %s, %s, %s, %s, %s)
              ON CONFLICT (session_id, category) DO UPDATE SET
                transcript = EXCLUDED.transcript,
                normalized_value = EXCLUDED.normalized_value,
                unit = EXCLUDED.unit,
                confidence = EXCLUDED.confidence
              RETURNING id
            )
            INSERT INTO public.daily_metrics
              (session_id, metric_key, metric_value, display_value, status, source_answer_id)
            SELECT %s, %s, %s, %s, %s, id FROM answer
            ON CONFLICT (session_id, metric_key) DO UPDATE SET
              metric_value = EXCLUDED.metric_value,
              display_value = EXCLUDED.display_value,
              status = EXCLUDED.status,
              source_answer_id = EXCLUDED.source_answer_id
            RETURNING id, metric_key, display_value, status
            """,
            (
                session_id,
                category,
                transcript,
                metric.get("numeric_value"),
                metric.get("unit"),
                metric.get("confidence", 0.8),
                session_id,
                metric["key"],
                metric.get("numeric_value"),
                metric["display_value"],
                metric["status"],
            ),
        )

    with httpx.Client(timeout=30.0) as client:
        answer_rows = client.get(
            _records("checkin_answers"),
            headers=_headers(),
            params={"session_id": f"eq.{session_id}", "category": f"eq.{category}", "select": "id", "limit": "1"},
        )
        answer_rows.raise_for_status()
        existing_answers = answer_rows.json()
        answer_body = {
            "session_id": session_id,
            "category": category,
            "transcript": transcript,
            "normalized_value": metric.get("numeric_value"),
            "unit": metric.get("unit"),
            "confidence": metric.get("confidence", 0.8),
        }
        if existing_answers:
            answer_id = existing_answers[0]["id"]
            updated = client.patch(
                f"{_records('checkin_answers')}?id=eq.{answer_id}",
                headers=_headers(),
                json=answer_body,
            )
            updated.raise_for_status()
        else:
            created = client.post(
                _records("checkin_answers"),
                headers=_headers(representation=True),
                json=[answer_body],
            )
            created.raise_for_status()
            answer_id = created.json()[0]["id"]

        metric_rows = client.get(
            _records("daily_metrics"),
            headers=_headers(),
            params={"session_id": f"eq.{session_id}", "metric_key": f"eq.{metric['key']}", "select": "id", "limit": "1"},
        )
        metric_rows.raise_for_status()
        metric_body = {
            "session_id": session_id,
            "metric_key": metric["key"],
            "metric_value": metric.get("numeric_value"),
            "display_value": metric["display_value"],
            "status": metric["status"],
            "source_answer_id": answer_id,
        }
        existing_metrics = metric_rows.json()
        if existing_metrics:
            metric_id = existing_metrics[0]["id"]
            updated = client.patch(
                f"{_records('daily_metrics')}?id=eq.{metric_id}",
                headers=_headers(representation=True),
                json=metric_body,
            )
        else:
            updated = client.post(
                _records("daily_metrics"),
                headers=_headers(representation=True),
                json=[metric_body],
            )
        updated.raise_for_status()
        payload = updated.json()
        return payload[0] if isinstance(payload, list) and payload else metric_body


def record_movement_analysis(
    room_name: str,
    *,
    movement: str,
    pose_metrics: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any] | None:
    if not enabled():
        return None
    session = ensure_session(room_name, demo_mode=True)
    if not session:
        return None
    session_id = str(session["id"])
    if _database_url():
        return _fetchone(
            """
            INSERT INTO public.movement_analyses
              (session_id, athlete_profile_id, movement, reps, score, confidence, pose_metrics, feedback, source)
            SELECT %s, athlete_profile_id, %s, %s, %s, %s, %s, %s, %s
            FROM public.checkin_sessions
            WHERE id = %s
            RETURNING id, movement, reps, score, confidence, source, created_at
            """,
            (
                session_id,
                movement,
                int(pose_metrics.get("reps") or 0),
                int(analysis["score"]),
                analysis.get("confidence"),
                Jsonb(pose_metrics),
                Jsonb(analysis),
                analysis.get("source", "pose_fallback"),
                session_id,
            ),
        )

    with httpx.Client(timeout=30.0) as client:
        session_response = client.get(
            _records("checkin_sessions"),
            headers=_headers(),
            params={"id": f"eq.{session_id}", "select": "athlete_profile_id", "limit": "1"},
        )
        session_response.raise_for_status()
        athlete_id = session_response.json()[0]["athlete_profile_id"]
        created = client.post(
            _records("movement_analyses"),
            headers=_headers(representation=True),
            json=[
                {
                    "session_id": session_id,
                    "athlete_profile_id": athlete_id,
                    "movement": movement,
                    "reps": int(pose_metrics.get("reps") or 0),
                    "score": int(analysis["score"]),
                    "confidence": analysis.get("confidence"),
                    "pose_metrics": pose_metrics,
                    "feedback": analysis,
                    "source": analysis.get("source", "pose_fallback"),
                }
            ],
        )
        created.raise_for_status()
        rows = created.json()
        return rows[0] if rows else None


def complete_session(
    room_name: str,
    *,
    actions: list[dict[str, Any]],
    memory_sources: list[dict[str, Any]],
    safety_status: str,
) -> int:
    if not enabled():
        return 6
    session = ensure_session(room_name)
    if not session:
        return 6
    session_id = str(session["id"])
    if _database_url():
        row = _fetchone(
            """
            WITH finished AS (
              UPDATE public.checkin_sessions
              SET status = 'complete', completed_at = now()
              WHERE id = %s
              RETURNING athlete_profile_id
            ), plan AS (
              INSERT INTO public.daily_plans
                (session_id, actions_json, memory_sources_json, safety_status, accepted_at)
              VALUES (%s, %s, %s, %s, now())
              ON CONFLICT (session_id) DO UPDATE SET
                actions_json = EXCLUDED.actions_json,
                memory_sources_json = EXCLUDED.memory_sources_json,
                safety_status = EXCLUDED.safety_status,
                accepted_at = now()
            )
            INSERT INTO public.streaks
              (athlete_profile_id, current_days, longest_days, last_completed_date)
            SELECT athlete_profile_id, 1, 1, current_date FROM finished
            ON CONFLICT (athlete_profile_id) DO UPDATE SET
              current_days = CASE
                WHEN public.streaks.last_completed_date = current_date THEN public.streaks.current_days
                WHEN public.streaks.last_completed_date = current_date - 1 THEN public.streaks.current_days + 1
                ELSE 1
              END,
              longest_days = GREATEST(
                public.streaks.longest_days,
                CASE
                  WHEN public.streaks.last_completed_date = current_date THEN public.streaks.current_days
                  WHEN public.streaks.last_completed_date = current_date - 1 THEN public.streaks.current_days + 1
                  ELSE 1
                END
              ),
              last_completed_date = current_date
            RETURNING current_days
            """,
            (session_id, session_id, Jsonb(actions), Jsonb(memory_sources), safety_status),
        )
        return int(row["current_days"]) if row else 1

    with httpx.Client(timeout=30.0) as client:
        session_rows = client.get(
            _records("checkin_sessions"),
            headers=_headers(),
            params={"id": f"eq.{session_id}", "select": "athlete_profile_id", "limit": "1"},
        )
        session_rows.raise_for_status()
        athlete_id = session_rows.json()[0]["athlete_profile_id"]
        client.patch(
            f"{_records('checkin_sessions')}?id=eq.{session_id}",
            headers=_headers(),
            json={"status": "complete", "completed_at": date.today().isoformat()},
        ).raise_for_status()
        plans = client.get(
            _records("daily_plans"),
            headers=_headers(),
            params={"session_id": f"eq.{session_id}", "select": "id", "limit": "1"},
        )
        plans.raise_for_status()
        plan_body = {
            "session_id": session_id,
            "actions_json": actions,
            "memory_sources_json": memory_sources,
            "safety_status": safety_status,
            "accepted_at": date.today().isoformat(),
        }
        if plans.json():
            client.patch(
                f"{_records('daily_plans')}?id=eq.{plans.json()[0]['id']}",
                headers=_headers(),
                json=plan_body,
            ).raise_for_status()
        else:
            client.post(_records("daily_plans"), headers=_headers(), json=[plan_body]).raise_for_status()

        streak_response = client.get(
            _records("streaks"),
            headers=_headers(),
            params={"athlete_profile_id": f"eq.{athlete_id}", "select": "current_days,longest_days,last_completed_date", "limit": "1"},
        )
        streak_response.raise_for_status()
        rows = streak_response.json()
        today = date.today()
        current = 1
        longest = 1
        if rows:
            previous_date = date.fromisoformat(rows[0]["last_completed_date"]) if rows[0].get("last_completed_date") else None
            previous_current = int(rows[0].get("current_days") or 0)
            current = previous_current if previous_date == today else previous_current + 1 if previous_date == today.fromordinal(today.toordinal() - 1) else 1
            longest = max(int(rows[0].get("longest_days") or 0), current)
            client.patch(
                f"{_records('streaks')}?athlete_profile_id=eq.{athlete_id}",
                headers=_headers(),
                json={"current_days": current, "longest_days": longest, "last_completed_date": today.isoformat()},
            ).raise_for_status()
        else:
            client.post(
                _records("streaks"),
                headers=_headers(),
                json=[{"athlete_profile_id": athlete_id, "current_days": 1, "longest_days": 1, "last_completed_date": today.isoformat()}],
            ).raise_for_status()
        return current
