from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from uuid import uuid4

import httpx


WORKFLOWS_URL = "https://agent-prod.studio.lyzr.ai/v3/workflows/"
RUN_DAG_URL = "https://lao.studio.lyzr.ai/run-dag/"
TASK_STATUS_URL = "https://lao.studio.lyzr.ai/task-status/"
ADAPTATION_TASK = "adapt_verified_set"


def enabled() -> bool:
    configured = bool(
        (os.environ.get("LYZR_API_KEY") or "").strip()
        and (os.environ.get("LYZR_SUPERFLOW_ID") or "").strip()
        and (os.environ.get("LYZR_ADAPTATION_AGENT_ID") or "").strip()
    )
    value = (os.environ.get("LYZR_SUPERFLOW_ENABLED") or "").strip().lower()
    return configured and (value not in {"0", "false", "no", "off"})


def _meta(
    status: str,
    session_id: str,
    *,
    task_id: str = "",
    elapsed_ms: int = 0,
    memory_used: bool = False,
) -> dict[str, Any]:
    return {
        "provider": "lyzr",
        "role": "adaptation",
        "status": status,
        "session_id": session_id,
        "memory_used": memory_used,
        "specialist_agent_id": (os.environ.get("LYZR_ADAPTATION_AGENT_ID") or "").strip(),
        "specialist_session_id": f"{session_id}--lyzr-superflow-adaptation",
        "workflow": {
            "type": "superflow",
            "workflow_id": (os.environ.get("LYZR_SUPERFLOW_ID") or "").strip(),
            "task_id": task_id,
            "status": status,
            "elapsed_ms": elapsed_ms,
        },
    }


def _parse_result(result: Any) -> Any | None:
    if isinstance(result, (dict, list)):
        return result
    if not isinstance(result, str):
        return None
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None


async def invoke_adaptation(
    message: str,
    *,
    session_id: str,
    user_id: str,
    memory_used: bool = False,
    timeout: float = 25.0,
) -> tuple[Any | None, dict[str, Any]]:
    if not enabled():
        return None, _meta("disabled", session_id, memory_used=memory_used)

    api_key = (os.environ.get("LYZR_API_KEY") or "").strip()
    workflow_id = (os.environ.get("LYZR_SUPERFLOW_ID") or "").strip()
    adaptation_agent_id = (os.environ.get("LYZR_ADAPTATION_AGENT_ID") or "").strip()
    headers = {"x-api-key": api_key, "content-type": "application/json"}
    started = time.monotonic()
    task_id = ""
    try:
        async with httpx.AsyncClient(timeout=min(timeout, 30.0)) as client:
            workflow_response = await client.get(f"{WORKFLOWS_URL}{workflow_id}", headers=headers)
            workflow_response.raise_for_status()
            workflow = workflow_response.json()
            flow_data = dict(workflow.get("flow_data") or workflow)
            default_inputs = dict(flow_data.get("default_inputs") or {})
            default_inputs.update(
                {
                    "movement_context": message,
                    "adaptation_agent_config": {
                        "user_id": user_id,
                        "session_id": f"{session_id}--lyzr-superflow-adaptation",
                        "agent_id": adaptation_agent_id,
                        "api_key": api_key,
                        "api_url": "https://agent-prod.studio.lyzr.ai/v3/inference/chat/",
                        "agent_name": "GameDay Movement Adaptation Coach",
                    },
                }
            )
            flow_data["default_inputs"] = default_inputs
            flow_data["run_name"] = f"verified-set-{uuid4().hex[:12]}"
            run_response = await client.post(RUN_DAG_URL, json=flow_data)
            run_response.raise_for_status()
            task_id = str(run_response.json().get("task_id") or "")
            if not task_id:
                raise ValueError("Lyzr SuperFlow did not return a task ID")

            deadline = started + timeout
            while time.monotonic() < deadline:
                status_response = await client.get(f"{TASK_STATUS_URL}{task_id}")
                status_response.raise_for_status()
                status_body = status_response.json()
                status = str(status_body.get("status") or "processing")
                if status == "completed":
                    parsed = _parse_result((status_body.get("results") or {}).get(ADAPTATION_TASK))
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    if parsed is not None:
                        return parsed, _meta(
                            "completed",
                            session_id,
                            task_id=task_id,
                            elapsed_ms=elapsed_ms,
                            memory_used=memory_used,
                        )
                    break
                if status in {"failed", "error"}:
                    break
                await asyncio.sleep(0.75)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        pass

    return None, _meta(
        "failed",
        session_id,
        task_id=task_id,
        elapsed_ms=int((time.monotonic() - started) * 1000),
        memory_used=memory_used,
    )
