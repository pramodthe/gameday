"""Turn a natural-language answer into a typed value (Req 4).

Two paths behind one `extract()` call:
  * rule-based (default, keyless, deterministic) — robust enough for the demo script
    and used by every unit test.
  * LLM structured extraction (when ANTHROPIC_API_KEY is set) — more forgiving of
    phrasing; falls back to the rule-based path on any error.

Every result carries `_ok`: whether the primary value for that question was found.
"""
from __future__ import annotations

import re

from ..config import settings

# --- shared number parsing ---

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "couple": 2, "few": 3,
}


def _first_number(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if m:
        val = float(m.group(1))
        if re.search(re.escape(m.group(1)) + r"\s*(?:and\s*a\s*half|½)", text):
            val += 0.5
        return val
    for tok in re.findall(r"[a-z]+", text):
        if tok in WORD_NUMBERS:
            base = float(WORD_NUMBERS[tok])
            if "half" in text:
                base += 0.5
            return base
    return None


# --- per-question rule-based extractors (input is already lowercased) ---

def _extract_sleep(t: str) -> dict:
    hours = _first_number(t)
    return {"sleep_hours": hours, "_ok": hours is not None}


def _extract_load(t: str) -> dict:
    duration: int | None = None
    mh = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", t)
    mm = re.search(r"(\d+)\s*(?:minutes?|mins?|min)\b", t)
    if mh:
        duration = int(float(mh.group(1)) * 60)
    if mm:
        duration = (duration or 0) + int(mm.group(1))
    if duration is None:  # word hours, e.g. "two hour match"
        for w, n in WORD_NUMBERS.items():
            if re.search(rf"\b{w}\s*(?:hours?|hrs?|hour)\b", t):
                duration = n * 60
                break

    rpe: int | None = None
    mr = re.search(r"(\d+)\s*(?:out of\s*10|/\s*10)", t)
    mr2 = re.search(r"\brpe\s*(?:of\s*)?(\d+)", t)
    if mr:
        rpe = int(mr.group(1))
    elif mr2:
        rpe = int(mr2.group(1))
    else:
        for numstr in re.findall(r"\b(\d+)\b", t):  # a bare 1..10 intensity
            n = int(numstr)
            if 1 <= n <= 10 and n != duration and (duration is None or n != duration // 60):
                rpe = n
                break
    if rpe is None:  # qualitative intensity
        if any(w in t for w in ["max", "all out", "brutal", "cooked", "really hard", "very hard"]):
            rpe = 9
        elif "hard" in t:
            rpe = 8
        elif any(w in t for w in ["moderate", "medium", "tempo"]):
            rpe = 5
        elif any(w in t for w in ["easy", "light", "recovery", "chill"]):
            rpe = 3
    if rpe is not None:
        rpe = max(1, min(10, rpe))

    return {"session_rpe": rpe, "duration_min": duration, "_ok": duration is not None or rpe is not None}


_BODY_PARTS = [
    "hamstring", "calves", "calf", "quads", "quad", "knees", "knee", "shoulders",
    "shoulder", "back", "ankle", "achilles", "groin", "hips", "hip", "shins",
    "shin", "feet", "foot", "glutes", "glute", "neck", "elbow", "wrist",
]
_SINGULAR = {
    "calves": "calf", "quads": "quad", "knees": "knee", "shoulders": "shoulder",
    "hips": "hip", "shins": "shin", "feet": "foot", "glutes": "glute",
}
_NO_SORENESS = [
    "nothing", "none", "nope", "no sore", "not sore", "all good", "feeling good",
    "feel good", "i'm good", "im good", "nowhere", "no pain", "nada", "all fine",
]


def _extract_soreness(t: str) -> dict:
    areas: list[str] = []
    for part in _BODY_PARTS:
        if re.search(rf"\b{part}\b", t):
            canonical = _SINGULAR.get(part, part)
            side = "right " if "right" in t else ("left " if "left" in t else "")
            area = f"{side}{canonical}"
            if area not in areas and not any(canonical in a for a in areas):
                areas.append(area)
    if areas:
        return {"areas": areas, "_ok": True}
    if any(neg in t for neg in _NO_SORENESS):
        return {"areas": [], "_ok": True}
    return {"areas": [], "_ok": False}


def _extract_nutrition(t: str) -> dict:
    neg = any(w in t for w in [
        "skip", "skipped", "didn't eat", "did not eat", "haven't eaten",
        "havent eaten", "no breakfast", "nothing yet", "not yet", "empty stomach", "fasted",
    ])
    pos = any(w in t for w in [
        "ate", "had breakfast", "yes", "fueled", "fuelled", "eaten", "did eat",
        "good breakfast", "big breakfast", "protein", "oatmeal", "eggs", "smoothie",
    ])
    if neg and not pos:
        return {"fueled": False, "notes": None, "_ok": True}
    if pos and not neg:
        return {"fueled": True, "notes": None, "_ok": True}
    return {"fueled": None, "notes": None, "_ok": False}


def _extract_mood(t: str) -> dict:
    n = _first_number(t)
    if n is not None and 1 <= n <= 5:
        return {"mood": int(n), "_ok": True}
    buckets = [
        (5, ["amazing", "great", "fantastic", "excellent", "strong"]),
        (4, ["good", "solid", "fresh"]),
        (3, ["okay", "ok", "fine", "alright", "average"]),
        (2, ["flat", "tired", "low", "meh", "sluggish", "rough", "drained"]),
        (1, ["terrible", "awful", "exhausted", "wrecked", "horrible"]),
    ]
    for score, words in buckets:
        if any(w in t for w in words):
            return {"mood": score, "_ok": True}
    return {"mood": None, "_ok": False}


_RULE_EXTRACTORS = {
    "sleep": _extract_sleep,
    "load": _extract_load,
    "soreness": _extract_soreness,
    "nutrition": _extract_nutrition,
    "mood": _extract_mood,
}


def _rule_extract(field: str, text: str) -> dict:
    return _RULE_EXTRACTORS[field](text.lower())


# --- optional LLM path ---

_FIELD_TOOLS = {
    "sleep": {
        "name": "record_sleep",
        "description": "Record hours of sleep from the athlete's answer.",
        "input_schema": {
            "type": "object",
            "properties": {"sleep_hours": {"type": ["number", "null"]}},
            "required": ["sleep_hours"],
        },
    },
    "load": {
        "name": "record_load",
        "description": "Record yesterday's training as session RPE (1-10) and duration in minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_rpe": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
                "duration_min": {"type": ["integer", "null"]},
            },
            "required": ["session_rpe", "duration_min"],
        },
    },
    "soreness": {
        "name": "record_soreness",
        "description": "List sore/tight body areas (empty if none).",
        "input_schema": {
            "type": "object",
            "properties": {"areas": {"type": "array", "items": {"type": "string"}}},
            "required": ["areas"],
        },
    },
    "nutrition": {
        "name": "record_nutrition",
        "description": "Whether the athlete has fueled/eaten this morning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fueled": {"type": ["boolean", "null"]},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["fueled"],
        },
    },
    "mood": {
        "name": "record_mood",
        "description": "Mood on a 1-5 scale.",
        "input_schema": {
            "type": "object",
            "properties": {"mood": {"type": ["integer", "null"], "minimum": 1, "maximum": 5}},
            "required": ["mood"],
        },
    },
}


def _llm_extract(field: str, text: str) -> dict:
    import anthropic

    tool = _FIELD_TOOLS[field]
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{
            "role": "user",
            "content": f"Extract the requested value from this athlete check-in answer. "
                       f"Use null for anything not stated.\n\nAnswer: \"{text}\"",
        }],
    )
    for block in msg.content:
        if block.type == "tool_use":
            data = dict(block.input)
            data["_ok"] = any(v is not None for v in block.input.values())
            return data
    raise ValueError("no tool_use in LLM response")


def extract(field: str, text: str, use_llm: bool | None = None) -> dict:
    """Extract the typed value for `field` from `text`."""
    text = (text or "").strip()
    if not text:
        return {"_ok": False}
    if use_llm is None:
        use_llm = bool(settings.anthropic_api_key)
    if use_llm:
        try:
            return _llm_extract(field, text)
        except Exception:
            pass
    return _rule_extract(field, text)
