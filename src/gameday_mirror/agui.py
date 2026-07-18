from __future__ import annotations

import json
from copy import deepcopy
from time import time
from typing import Any, Mapping
from uuid import uuid4


def _timestamp() -> int:
    return int(time() * 1000)


def tool_call_events(tool_call_id: str, tool_name: str, arguments: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {
            "type": "TOOL_CALL_START",
            "timestamp": _timestamp(),
            "toolCallId": tool_call_id,
            "toolCallName": tool_name,
        },
        {
            "type": "TOOL_CALL_ARGS",
            "timestamp": _timestamp(),
            "toolCallId": tool_call_id,
            "delta": json.dumps(arguments),
        },
        {
            "type": "TOOL_CALL_END",
            "timestamp": _timestamp(),
            "toolCallId": tool_call_id,
        },
    ]


def tool_result_event(tool_call_id: str, content: Mapping[str, object]) -> dict[str, object]:
    return {
        "type": "TOOL_CALL_RESULT",
        "timestamp": _timestamp(),
        "messageId": f"tool-result-{uuid4()}",
        "toolCallId": tool_call_id,
        "content": json.dumps(content),
        "role": "tool",
    }


class ExerciseSharedState:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.revision = 0
        self.exercise: dict[str, Any] = self._idle_exercise()

    @staticmethod
    def _idle_exercise() -> dict[str, object]:
        return {
            "mode": "idle",
            "status": "idle",
            "requestId": None,
            "name": None,
            "targetReps": None,
            "reps": 0,
            "bodyVisible": None,
            "cue": None,
            "lesson": None,
            "analysis": None,
            "adaptation": None,
            "error": None,
        }

    @property
    def request_id(self) -> str | None:
        value = self.exercise.get("requestId")
        return str(value) if value else None

    @property
    def is_active(self) -> bool:
        return self.exercise.get("status") in {
            "requested",
            "loading",
            "waiting",
            "ready",
            "active",
        }

    def snapshot_event(self) -> dict[str, object]:
        return {
            "type": "STATE_SNAPSHOT",
            "timestamp": _timestamp(),
            "snapshot": {
                "version": 1,
                "revision": self.revision,
                "sessionId": self.session_id,
                "exercise": deepcopy(self.exercise),
            },
        }

    def _commit(self) -> dict[str, object]:
        self.revision += 1
        return self.snapshot_event()

    def begin_lesson(self, request_id: str, exercise_name: str) -> list[dict[str, object]]:
        self.exercise = {
            **self._idle_exercise(),
            "mode": "lesson",
            "status": "requested",
            "requestId": request_id,
            "name": exercise_name,
        }
        return [
            *tool_call_events(request_id, "teach_exercise", {"exercise_name": exercise_name}),
            self._commit(),
        ]

    def begin_exercise(
        self,
        request_id: str,
        exercise: str,
        target_reps: int,
    ) -> list[dict[str, object]]:
        self.exercise = {
            **self._idle_exercise(),
            "mode": "camera",
            "status": "requested",
            "requestId": request_id,
            "name": exercise,
            "targetReps": target_reps,
        }
        return [
            *tool_call_events(request_id, "start_exercise", {"exercise": exercise}),
            self._commit(),
        ]

    def begin_squat(self, request_id: str, target_reps: int = 5) -> list[dict[str, object]]:
        return self.begin_exercise(request_id, "squat", target_reps)

    def fail_request(self, request_id: str, message: str) -> dict[str, object] | None:
        if request_id != self.request_id:
            return None

        self.exercise["status"] = "failed"
        self.exercise["error"] = message
        return self._commit()

    def apply_telemetry(self, event: Mapping[str, object]) -> dict[str, object] | None:
        event_type = str(event.get("type") or "")
        request_id = str(event.get("request_id") or "")
        if not request_id:
            return None

        if event_type == "exercise_opened" and (
            self.exercise.get("status") in {"idle", "closed", "failed", "completed"}
            or event.get("trigger") == "manual"
        ):
            self.exercise = {
                **self._idle_exercise(),
                "mode": "camera",
                "status": "requested",
                "requestId": request_id,
                "name": str(event.get("exercise") or "squat"),
                "targetReps": int(event.get("target_reps") or 5),
            }

        if request_id != self.request_id:
            return None

        previous_exercise = deepcopy(self.exercise)

        lesson_statuses = {
            "exercise_lesson_loading": "loading",
            "exercise_lesson_ready": "ready",
            "exercise_lesson_failed": "failed",
            "exercise_lesson_closed": "closed",
        }
        camera_statuses = {
            "exercise_opened": "waiting",
            "exercise_waiting": "waiting",
            "exercise_ready": "ready",
            "exercise_started": "active",
            "exercise_progress": "active",
            "exercise_reset": "waiting",
            "exercise_completed": "completed",
            "exercise_closed": "closed",
        }
        if event_type in lesson_statuses and self.exercise.get("mode") == "lesson":
            self.exercise["status"] = lesson_statuses[event_type]
            self.exercise["lesson"] = event.get("lesson") or self.exercise.get("lesson")
            self.exercise["error"] = event.get("message") if event_type == "exercise_lesson_failed" else None
        elif event_type in camera_statuses and self.exercise.get("mode") == "camera":
            self.exercise["status"] = camera_statuses[event_type]
            self.exercise["reps"] = int(event.get("reps") or 0)
            self.exercise["bodyVisible"] = event.get("body_visible")
            self.exercise["cue"] = event.get("cue")
            self.exercise["analysis"] = event.get("analysis") or self.exercise.get("analysis")
            self.exercise["adaptation"] = event.get("adaptation") or self.exercise.get("adaptation")
        else:
            return None
        if self.exercise == previous_exercise:
            return None
        return self._commit()
