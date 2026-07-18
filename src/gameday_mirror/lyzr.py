from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


LYZR_INFERENCE_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"

ROLE_ALIASES = {
    "plan": "plan",
    "readiness": "plan",
    "workout": "workout",
    "training": "workout",
    "adaptation": "adaptation",
    "movement": "adaptation",
}
ROLE_AGENTS = {
    "plan": ("GameDay Readiness Analyst", "Daily readiness check-ins and three-action plans."),
    "workout": ("GameDay Workout Architect", "Recovery-aware Core-5 workout programming."),
    "adaptation": ("GameDay Movement Adaptation Coach", "Post-set movement adaptation."),
}


def _flag(name: str, default: bool) -> bool:
    value = (os.environ.get(name) or "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "no", "off"}


def _agent_id(role: str) -> str:
    role_key = f"LYZR_{role.upper()}_AGENT_ID"
    return (os.environ.get(role_key) or os.environ.get("LYZR_AGENT_ID") or "").strip()


def _manager_id() -> str:
    return (os.environ.get("LYZR_MANAGER_AGENT_ID") or "").strip()


def _managed_agents() -> list[dict[str, str]]:
    agents = []
    for role, (name, usage_description) in ROLE_AGENTS.items():
        specialist_id = (os.environ.get(f"LYZR_{role.upper()}_AGENT_ID") or "").strip()
        if specialist_id:
            agents.append(
                {
                    "id": specialist_id,
                    "name": name,
                    "usage_description": usage_description,
                }
            )
    return agents


def _manager_enabled() -> bool:
    return _flag("LYZR_MANAGER_ROUTING_ENABLED", bool(_manager_id())) and bool(
        (os.environ.get("LYZR_API_KEY") or "").strip() and _manager_id() and _managed_agents()
    )


def _scoped_session_id(session_id: str, scope: str, user_id: str) -> str:
    base_session_id = session_id or f"gameday-{user_id}"
    return f"{base_session_id}--lyzr-{scope}"


def enabled(role: str) -> bool:
    configured = bool((os.environ.get("LYZR_API_KEY") or "").strip() and _agent_id(role))
    return _flag("LYZR_ORCHESTRATION_ENABLED", configured) and configured


def shadow_mode() -> bool:
    return _flag("LYZR_SHADOW_MODE", False)


def _extract_json(body: Any) -> Any:
    if not isinstance(body, dict):
        return body
    raw = body.get("response") or body.get("message") or body.get("content") or body
    if not isinstance(raw, str):
        return raw
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        array_start = text.find("[")
        object_start = text.find("{")
        starts = [index for index in (array_start, object_start) if index >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(text.rfind("]"), text.rfind("}"))
        if end < start:
            raise
        return json.loads(text[start:end + 1])


def _request(
    agent_id: str,
    message: str,
    session_id: str,
    user_id: str,
    *,
    managed_agents: list[dict[str, str]] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    headers = {
        "x-api-key": (os.environ.get("LYZR_API_KEY") or "").strip(),
        "Content-Type": "application/json",
    }
    payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "session_id": session_id or f"gameday-{user_id}",
        "message": message,
    }
    if managed_agents:
        payload["managed_agents"] = managed_agents
    return headers, payload


def _meta(
    role: str,
    status: str,
    session_id: str,
    *,
    memory_used: bool = False,
    manager_status: str = "disabled",
    manager_route: str | None = None,
    specialist_id: str = "",
    specialist_session_id: str = "",
) -> dict[str, Any]:
    metadata = {
        "provider": "lyzr",
        "role": role,
        "status": status,
        "session_id": session_id,
        "memory_used": memory_used,
        "specialist_agent_id": specialist_id,
        "specialist_session_id": specialist_session_id,
    }
    if _manager_id():
        metadata["manager"] = {
            "agent_id": _manager_id(),
            "status": manager_status,
            "route": manager_route or role,
            "session_id": _scoped_session_id(session_id, "director", "anonymous"),
        }
    return metadata


def _routing_prompt(role: str) -> str:
    return (
        f"Task role: {role}. Select the one managed agent that should handle this request. "
        "Do not solve the task. Return only JSON with route and status, for example "
        '{"route":"workout","status":"delegated"}.'
    )


def _route(role: str, parsed: Any) -> str:
    if not isinstance(parsed, dict):
        return role
    route = str(parsed.get("route") or "").strip().lower().replace(" ", "_")
    return ROLE_ALIASES.get(route, role)


def _manager_route_sync(role: str, session_id: str, user_id: str, timeout: float) -> tuple[str, str]:
    if not _manager_enabled():
        return role, "disabled"
    headers, payload = _request(
        _manager_id(),
        _routing_prompt(role),
        _scoped_session_id(session_id, "director", user_id),
        user_id,
        managed_agents=_managed_agents(),
    )
    try:
        with httpx.Client(timeout=min(timeout, 12.0)) as client:
            response = client.post(LYZR_INFERENCE_URL, headers=headers, json=payload)
            response.raise_for_status()
            return _route(role, _extract_json(response.json())), "completed"
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return role, "failed"


async def _manager_route_async(role: str, session_id: str, user_id: str, timeout: float) -> tuple[str, str]:
    if not _manager_enabled():
        return role, "disabled"
    headers, payload = _request(
        _manager_id(),
        _routing_prompt(role),
        _scoped_session_id(session_id, "director", user_id),
        user_id,
        managed_agents=_managed_agents(),
    )
    try:
        async with httpx.AsyncClient(timeout=min(timeout, 12.0)) as client:
            response = await client.post(LYZR_INFERENCE_URL, headers=headers, json=payload)
            response.raise_for_status()
            return _route(role, _extract_json(response.json())), "completed"
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return role, "failed"


def invoke_json(
    role: str,
    message: str,
    *,
    session_id: str,
    user_id: str,
    memory_used: bool = False,
    timeout: float = 20.0,
) -> tuple[Any | None, dict[str, Any]]:
    if not enabled(role):
        return None, _meta(role, "disabled", session_id, memory_used=memory_used)
    selected_role, manager_status = _manager_route_sync(role, session_id, user_id, timeout)
    specialist_id = _agent_id(selected_role)
    specialist_session_id = _scoped_session_id(session_id, selected_role, user_id)
    headers, payload = _request(specialist_id, message, specialist_session_id, user_id)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(LYZR_INFERENCE_URL, headers=headers, json=payload)
            response.raise_for_status()
            parsed = _extract_json(response.json())
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return None, _meta(
            role,
            "failed",
            session_id,
            memory_used=memory_used,
            manager_status=manager_status,
            manager_route=selected_role,
            specialist_id=specialist_id,
            specialist_session_id=specialist_session_id,
        )
    status = "shadow" if shadow_mode() else "completed"
    return (None if shadow_mode() else parsed), _meta(
        role,
        status,
        session_id,
        memory_used=memory_used,
        manager_status=manager_status,
        manager_route=selected_role,
        specialist_id=specialist_id,
        specialist_session_id=specialist_session_id,
    )


async def invoke_json_async(
    role: str,
    message: str,
    *,
    session_id: str,
    user_id: str,
    memory_used: bool = False,
    timeout: float = 25.0,
) -> tuple[Any | None, dict[str, Any]]:
    if not enabled(role):
        return None, _meta(role, "disabled", session_id, memory_used=memory_used)
    selected_role, manager_status = await _manager_route_async(role, session_id, user_id, timeout)
    specialist_id = _agent_id(selected_role)
    specialist_session_id = _scoped_session_id(session_id, selected_role, user_id)
    headers, payload = _request(specialist_id, message, specialist_session_id, user_id)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(LYZR_INFERENCE_URL, headers=headers, json=payload)
            response.raise_for_status()
            parsed = _extract_json(response.json())
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return None, _meta(
            role,
            "failed",
            session_id,
            memory_used=memory_used,
            manager_status=manager_status,
            manager_route=selected_role,
            specialist_id=specialist_id,
            specialist_session_id=specialist_session_id,
        )
    status = "shadow" if shadow_mode() else "completed"
    return (None if shadow_mode() else parsed), _meta(
        role,
        status,
        session_id,
        memory_used=memory_used,
        manager_status=manager_status,
        manager_route=selected_role,
        specialist_id=specialist_id,
        specialist_session_id=specialist_session_id,
    )
