from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv


WORKFLOWS_URL = "https://agent-prod.studio.lyzr.ai/v3/workflows/"
FLOW_NAME = "GameDay Verified-Set Adaptation"


def workflow_id(workflow: dict[str, Any]) -> str:
    return str(
        workflow.get("_id")
        or workflow.get("id")
        or workflow.get("workflow_id")
        or workflow.get("flow_id")
        or ""
    )


def workflow_payload(api_key: str, adaptation_agent_id: str) -> dict[str, Any]:
    flow_data = {
        "tasks": [
            {
                "name": "adapt_verified_set",
                "tag": "GameDay Movement Adaptation Coach",
                "function": "call_lyzr_agent",
                "params": {
                    "config": {"input": "adaptation_agent_config"},
                    "user_message": {"input": "movement_context"},
                },
            }
        ],
        "default_inputs": {
            "adaptation_agent_config": {
                "user_id": "gameday-superflow",
                "session_id": "gameday-superflow",
                "agent_id": adaptation_agent_id,
                "api_key": api_key,
                "api_url": "https://agent-prod.studio.lyzr.ai/v3/inference/chat/",
                "agent_name": "GameDay Movement Adaptation Coach",
            },
            "movement_context": (
                "Choose the safest next action after this verified set. Return the configured JSON schema only."
            ),
        },
        "flow_name": FLOW_NAME,
        "run_name": "verified-set-adaptation",
        "edges": [],
    }
    return {"flow_name": FLOW_NAME, "flow_data": flow_data, "api_key": api_key}


def configure() -> str:
    load_dotenv(".env")
    api_key = (os.environ.get("LYZR_API_KEY") or "").strip()
    adaptation_agent_id = (os.environ.get("LYZR_ADAPTATION_AGENT_ID") or "").strip()
    if not api_key or not adaptation_agent_id:
        raise RuntimeError("LYZR_API_KEY and LYZR_ADAPTATION_AGENT_ID are required in .env")

    headers = {"x-api-key": api_key, "content-type": "application/json"}
    payload = workflow_payload(api_key, adaptation_agent_id)
    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(WORKFLOWS_URL)
        response.raise_for_status()
        workflows = response.json()
        existing = next(
            (
                item
                for item in workflows
                if isinstance(item, dict) and item.get("flow_name") == FLOW_NAME
            ),
            None,
        )
        existing_id = workflow_id(existing) if existing else ""
        if existing_id:
            response = client.put(f"{WORKFLOWS_URL}{existing_id}", json=payload)
            response.raise_for_status()
            print(f"updated {FLOW_NAME}: {existing_id}")
            return existing_id

        response = client.post(WORKFLOWS_URL, json=payload)
        response.raise_for_status()
        created_id = workflow_id(response.json())
        if not created_id:
            raise RuntimeError(f"Lyzr did not return a workflow ID: {response.text}")
        print(f"created {FLOW_NAME}: {created_id}")
        return created_id


if __name__ == "__main__":
    configured_id = configure()
    print(f'LYZR_SUPERFLOW_ID="{configured_id}"')
