from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv


TOOLS_URL = "https://agent-prod.studio.lyzr.ai/v3/tools/"
TOOL_SET_NAME = "gameday-athlete-context"
FUNCTION_BASE_URL = "https://i87d4gcb.function2.insforge.app"


def tool_payload(tool_secret: str, default_user_id: str) -> dict[str, Any]:
    return {
        "tool_set_name": TOOL_SET_NAME,
        "openapi_schema": {
            "openapi": "3.0.3",
            "info": {
                "title": "GameDay Athlete Context",
                "version": "1.0.0",
                "description": "Read recent athlete sessions and camera-verified movement results from InsForge.",
            },
            "servers": [{"url": FUNCTION_BASE_URL}],
            "paths": {
                "/gameday-agent-context": {
                    "get": {
                        "operationId": "getAthleteContext",
                        "summary": "Get recent athlete context",
                        "description": (
                            "Use before personalizing a plan or workout when current prompt context is incomplete."
                        ),
                        "parameters": [
                            {
                                "name": "user_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string", "default": default_user_id},
                                "description": "GameDay athlete profile identifier.",
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Recent athlete context",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "additionalProperties": True,
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
        },
        "default_headers": {"X-GameDay-Tool-Key": tool_secret},
        "default_query_params": {"user_id": default_user_id},
        "default_body_params": {},
        "endpoint_defaults": {},
        "enhance_descriptions": False,
        "openai_api_key": None,
    }


def configure() -> str:
    load_dotenv(".env")
    api_key = (os.environ.get("LYZR_API_KEY") or "").strip()
    tool_secret = (os.environ.get("GAMEDAY_LYZR_TOOL_SECRET") or "").strip()
    configured_id = (os.environ.get("LYZR_CONTEXT_TOOL_ID") or "").strip()
    default_user_id = (os.environ.get("INSFORGE_PROFILE_ID") or "gameday-demo").strip()
    if not api_key or not tool_secret:
        raise RuntimeError("LYZR_API_KEY and GAMEDAY_LYZR_TOOL_SECRET are required in .env")

    headers = {"x-api-key": api_key, "content-type": "application/json"}
    with httpx.Client(headers=headers, timeout=30.0) as client:
        if configured_id:
            response = client.get(f"{TOOLS_URL}{configured_id}")
            if response.is_success:
                print(f"verified {TOOL_SET_NAME}: {configured_id}")
                return configured_id

        response = client.post(TOOLS_URL, json=tool_payload(tool_secret, default_user_id))
        response.raise_for_status()
        tool_ids = response.json().get("tool_ids", [])
        if not tool_ids:
            raise RuntimeError(f"Lyzr did not return a tool ID: {response.text}")
        created_tool = tool_ids[0]
        created_id = str(created_tool.get("name") if isinstance(created_tool, dict) else created_tool)
        print(f"created {TOOL_SET_NAME}: {created_id}")
        return created_id


if __name__ == "__main__":
    tool_id = configure()
    print(f'LYZR_CONTEXT_TOOL_ID="{tool_id}"')
