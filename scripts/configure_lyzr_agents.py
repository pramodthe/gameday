from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from lyzr import PIIAction, PIIType, SecretsAction, Studio
from lyzr.cognis.config import CognisConfig
from pydantic import BaseModel, ConfigDict

from gameday_mirror.sponsors import ReadinessPlan
from gameday_mirror.workouts import WorkoutAdaptation, WorkoutSession


AGENTS_URL = "https://agent-prod.studio.lyzr.ai/v3/agents/"
MODEL_CONFIG = {
    "provider_id": "OpenAI",
    "model": "gpt-4o-mini",
    "llm_credential_id": "lyzr_openai",
    "temperature": 0.2,
    "top_p": 0.9,
}
CONTEXT_NAME = "gameday_agent_policy"
POLICY_NAME = "GameDay Athlete Safety"
CONTEXT_VALUE = """GameDay is a camera-first training companion, not a medical provider.
The browser can verify exactly five movements: squat, pushup, lunge, plank, and glute_bridge.
Prefer current camera evidence over recalled history. Use memory to personalize, never to diagnose.
Remember stable goals, preferred session duration, equipment constraints, baseline scores, and recurring form cues.
Do not treat transient soreness as a diagnosis and never store raw camera frames, audio, secrets, or payment data.
If pain, injury, dizziness, chest pain, or severe symptoms are reported, stop exercise guidance and recommend qualified human help.
All application-facing responses must follow the requested JSON schema without markdown or commentary."""


class DirectorRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["plan", "workout", "adaptation"]
    status: Literal["delegated"]


RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "manager": DirectorRoute,
    "plan": ReadinessPlan,
    "workout": WorkoutSession,
    "adaptation": WorkoutAdaptation,
}


def strict_response_schema(model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "strict": True,
            "schema": model.model_json_schema(),
        },
    }


def base_agent(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        **MODEL_CONFIG,
        "features": [CognisConfig(max_messages_context_count=20, cross_session=True).to_feature_format()],
        "tools": [],
        "tool_configs": [],
        "tool_usage_description": "",
        "managed_agents": [],
        "response_format": {},
        "store_messages": True,
        "file_output": False,
        "max_iterations": 8,
        "examples": "",
    }
    payload.update(overrides)
    return payload


SPECIALISTS = {
    "plan": base_agent(
        name="GameDay Readiness Analyst",
        description="Turns daily athlete readiness signals and remembered context into three safe actions.",
        agent_role="Readiness analyst for student athletes",
        agent_goal="Convert check-in evidence and relevant memory into exactly three useful actions for today.",
        agent_context=(
            "The athlete completes a camera-first readiness check-in covering sleep, energy, soreness, "
            "hydration, stress, and training intent."
        ),
        agent_instructions=(
            "Use only evidence supplied in the request and memory recalled for the same user. Prioritize recovery "
            "when readiness is low. Never diagnose, prescribe treatment, clear an injury, or provide investment "
            "advice. Return a JSON object with one actions field containing exactly three objects with string fields "
            "id, eyebrow, title, and detail. Keep every action achievable today and every detail under 24 words."
        ),
        agent_output=(
            '{"actions":[{"id":"recover","eyebrow":"Before practice","title":"Protect recovery",'
            '"detail":"Take a 20-minute reset before deciding on extra training volume."}]}'
        ),
    ),
    "workout": base_agent(
        name="GameDay Workout Architect",
        description="Builds recovery-aware Core-5 workouts that the browser camera can verify.",
        agent_role="Bodyweight workout architect for the GameDay camera coach",
        agent_goal="Create a safe, trackable 3-to-5 exercise session matched to readiness and athlete goals.",
        agent_context=(
            "The camera supports exactly five motion patterns: squat, pushup, lunge, plank, and glute_bridge."
        ),
        agent_instructions=(
            "Use only squat, pushup, lunge, plank, or glute_bridge as motion_pattern. Use 3 to 5 exercises. "
            "For plank set reps to 0 and hold_seconds from 10 to 60. For every other movement set reps from 5 "
            "to 15 and hold_seconds to 0. Match volume to recovery and relevant memories. Never diagnose or tell "
            "an athlete to train through pain. Return only one JSON object matching the schema supplied in the request."
        ),
        agent_output=(
            '{"title":"Recovery reset","focus":"Movement quality","intensity":"recovery",'
            '"estimated_minutes":12,"summary":"A light trackable session.","exercises":[]}'
        ),
    ),
    "adaptation": base_agent(
        name="GameDay Movement Adaptation Coach",
        description="Uses verified pose results and athlete memory to choose the safest next set.",
        agent_role="Post-set movement adaptation coach",
        agent_goal="Turn camera-verified set quality into one safe and explainable next action.",
        agent_context=(
            "Each request contains the tracked movement, rep or hold metrics, a visual-analysis score, and relevant "
            "performance memories."
        ),
        agent_instructions=(
            "Choose exactly one action: continue, reduce_reps, increase_rest, replace_exercise, or finish. Base the "
            "decision on current verified metrics first and memory second. Never diagnose, prescribe rehabilitation, "
            "or claim injury clearance. Return only one JSON object matching the schema supplied in the request."
        ),
        agent_output=(
            '{"action":"increase_rest","message":"Take a longer reset before repeating.",'
            '"reason":"Movement quality declined late in the set.","next_reps":8,'
            '"next_hold_seconds":null,"next_rest_seconds":75,"replacement_movement":null}'
        ),
    ),
}


def manager_agent(managed_agents: list[dict[str, str]]) -> dict[str, Any]:
    return base_agent(
        name="GameDay Performance Director",
        description="Routes readiness, workout, and post-set decisions to specialized Lyzr agents.",
        agent_role="Performance director coordinating a multi-agent athlete coaching system",
        agent_goal="Route each request to the correct specialist and preserve a safe, coherent athlete experience.",
        agent_context=(
            "GameDay combines a voice coach, browser pose tracking, readiness check-ins, and persistent athlete memory."
        ),
        agent_instructions=(
            "Read the Task role in every request. Delegate plan tasks to the Readiness Analyst, workout tasks to the "
            "Workout Architect, and adaptation tasks to the Movement Adaptation Coach. Preserve the specialist's JSON "
            "shape exactly and return JSON only. Never diagnose, prescribe treatment, or encourage training through pain."
        ),
        agent_output='{"route":"workout","status":"delegated"}',
        managed_agents=managed_agents,
        max_iterations=12,
    )


def agent_id(agent: dict[str, Any]) -> str:
    return str(agent.get("_id") or agent.get("id") or agent.get("agent_id") or "")


def upsert_context(studio: Studio):
    contexts = studio.list_contexts().contexts
    context = next((item for item in contexts if item.name == CONTEXT_NAME), None)
    if context is None:
        context = studio.create_context(name=CONTEXT_NAME, value=CONTEXT_VALUE)
        print(f"created global context: {context.id}")
    else:
        context = context.update(CONTEXT_VALUE)
        print(f"updated global context: {context.id}")
    return context


def upsert_safety_policy(studio: Studio):
    policies = studio.list_rai_policies().policies
    policy = next((item for item in policies if item.name == POLICY_NAME), None)
    pii_detection = {
        PIIType.CREDIT_CARD: PIIAction.BLOCK,
        PIIType.SSN: PIIAction.BLOCK,
        PIIType.EMAIL: PIIAction.REDACT,
        PIIType.PHONE: PIIAction.REDACT,
    }
    if policy is None:
        policy = studio.create_rai_policy(
            name=POLICY_NAME,
            description="Protects athlete conversations from unsafe content, prompt injection, secrets, and sensitive PII.",
            toxicity_threshold=0.35,
            prompt_injection=True,
            secrets_detection=SecretsAction.MASK,
            pii_detection=pii_detection,
        )
        print(f"created RAI policy: {policy.id}")
    else:
        policy = policy.update(
            name=POLICY_NAME,
            description="Protects athlete conversations from unsafe content, prompt injection, secrets, and sensitive PII.",
            toxicity_check={"enabled": True, "threshold": 0.35},
            prompt_injection={"enabled": True, "threshold": 0.3},
            secrets_detection={"enabled": True, "action": "mask"},
            pii_detection={
                "enabled": True,
                "types": {item.value: action.value for item, action in pii_detection.items()},
                "custom_pii": [],
            },
        )
        print(f"updated RAI policy: {policy.id}")
    return policy


AGENT_UPDATE_FIELDS = {
    "name",
    "description",
    "agent_role",
    "agent_instructions",
    "agent_goal",
    "agent_context",
    "agent_output",
    "examples",
    "features",
    "tools",
    "tool_usage_description",
    "llm_credential_id",
    "response_format",
    "provider_id",
    "model",
    "top_p",
    "temperature",
    "managed_agents",
    "tool_configs",
    "store_messages",
    "file_output",
    "a2a_tools",
    "voice_config",
    "additional_model_params",
    "image_output_config",
    "max_iterations",
    "git_agent",
    "proxy_config",
}


def configure_agent_features(
    client: httpx.Client,
    configured_ids: dict[str, str],
    context,
    policy,
) -> None:
    context_tool_id = (os.environ.get("LYZR_CONTEXT_TOOL_ID") or "").strip()
    context_tool_enabled = os.environ.get("LYZR_CONTEXT_TOOL_ENABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    for role, configured_id in configured_ids.items():
        response = client.get(f"{AGENTS_URL}{configured_id}")
        response.raise_for_status()
        agent = response.json()
        preserved_features = [
            feature
            for feature in agent.get("features", [])
            if feature.get("type")
            not in {"MEMORY", "SHORT_TERM_MEMORY", "LONG_TERM_MEMORY", "CONTEXT", "RAI", "SRS"}
        ]
        features = [
            *preserved_features,
            CognisConfig(max_messages_context_count=20, cross_session=True).to_feature_format(),
            context.to_feature_format(),
            policy.to_feature_format("https://srs-prod.studio.lyzr.ai/v1/rai/inference"),
        ]
        if role == "plan" and os.environ.get("LYZR_REFLECTION_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            features.append(
                {
                    "type": "SRS",
                    "config": {"max_tries": 1, "modules": {"reflection": True, "bias": False}},
                    "priority": 0,
                }
            )

        payload = {key: value for key, value in agent.items() if key in AGENT_UPDATE_FIELDS}
        payload["features"] = features
        payload["response_format"] = strict_response_schema(RESPONSE_MODELS[role])
        current_tools = [tool for tool in agent.get("tools", []) if tool != context_tool_id]
        if role != "manager" and context_tool_id and context_tool_enabled:
            payload["tools"] = list(dict.fromkeys([*current_tools, context_tool_id]))
            payload["tool_usage_description"] = (
                "Use getAthleteContext when the current request lacks recent session or camera-verified movement "
                "history. Treat returned data as supporting context; current camera evidence always wins."
            )
        else:
            payload["tools"] = current_tools
        update_response = client.put(f"{AGENTS_URL}{configured_id}", json=payload)
        update_response.raise_for_status()
        print(f"configured Cognis, context, RAI, and structured output for {agent['name']}")


def upsert_agent(
    client: httpx.Client,
    existing_agents: dict[str, str],
    payload: dict[str, Any],
) -> str:
    name = str(payload["name"])
    existing_id = existing_agents.get(name)
    if existing_id:
        response = client.put(f"{AGENTS_URL}{existing_id}", json=payload)
        response.raise_for_status()
        print(f"updated {name}: {existing_id}")
        return existing_id

    response = client.post(AGENTS_URL, json=payload)
    response.raise_for_status()
    created_id = agent_id(response.json())
    if not created_id:
        raise RuntimeError(f"Lyzr did not return an ID for {name}: {response.text}")
    print(f"created {name}: {created_id}")
    return created_id


def configure() -> dict[str, str]:
    load_dotenv()
    api_key = (os.environ.get("LYZR_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("LYZR_API_KEY is required in .env")

    headers = {
        "x-api-key": api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }
    studio = Studio(api_key=api_key)
    context = upsert_context(studio)
    policy = upsert_safety_policy(studio)

    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(AGENTS_URL)
        response.raise_for_status()
        agents = response.json()
        existing_agents = {
            str(agent.get("name")): agent_id(agent)
            for agent in agents
            if isinstance(agent, dict) and agent.get("name") and agent_id(agent)
        }

        specialist_ids = {
            role: upsert_agent(client, existing_agents, payload)
            for role, payload in SPECIALISTS.items()
        }
        managed_agents = [
            {
                "id": specialist_ids["plan"],
                "name": "GameDay Readiness Analyst",
                "usage_description": "Use for daily readiness check-ins and three-action plans.",
            },
            {
                "id": specialist_ids["workout"],
                "name": "GameDay Workout Architect",
                "usage_description": "Use for recovery-aware Core-5 workout programming.",
            },
            {
                "id": specialist_ids["adaptation"],
                "name": "GameDay Movement Adaptation Coach",
                "usage_description": "Use after a camera-verified set to choose the next action.",
            },
        ]
        manager_id = upsert_agent(client, existing_agents, manager_agent(managed_agents))

        configured_ids = {"manager": manager_id, **specialist_ids}
        configure_agent_features(client, configured_ids, context, policy)

    return {
        **configured_ids,
        "context": context.id,
        "rai_policy": policy.id,
    }


if __name__ == "__main__":
    configured_ids = configure()
    print("\nAdd these values to .env:")
    print(f'LYZR_AGENT_ID="{configured_ids["manager"]}"')
    print(f'LYZR_MANAGER_AGENT_ID="{configured_ids["manager"]}"')
    print(f'LYZR_PLAN_AGENT_ID="{configured_ids["plan"]}"')
    print(f'LYZR_WORKOUT_AGENT_ID="{configured_ids["workout"]}"')
    print(f'LYZR_ADAPTATION_AGENT_ID="{configured_ids["adaptation"]}"')
    print(f'LYZR_CONTEXT_ID="{configured_ids["context"]}"')
    print(f'LYZR_RAI_POLICY_ID="{configured_ids["rai_policy"]}"')
