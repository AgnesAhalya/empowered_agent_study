import json
import re
from typing import Dict, Optional

import requests
from fastapi import HTTPException

from app.config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from app.core.logger import canonical_option
from app.core.prompts import (
    EMPOWERED_SELECTOR_PROMPT,
    NORMAL_PROMPT,
    NORMAL_SELECTOR_PROMPT,
    SOFT_EMPOWER_PROMPT,
)


VALID_SELECTED_OPTIONS = [
    "concept_suggestion",
    "code_suggestion",
    "direct_code",
]


METHOD_CONFIG = {
    "normal_selector": {
        "prompt": NORMAL_SELECTOR_PROMPT,
        "max_tokens": 900,
    },
    "empowered_selector": {
        "prompt": EMPOWERED_SELECTOR_PROMPT,
        "max_tokens": 900,
    },
    # Old method names kept so older frontend choices still work.
    "normal_openrouter": {
        "prompt": NORMAL_PROMPT,
        "max_tokens": 900,
    },
    "soft_empower_openrouter": {
        "prompt": SOFT_EMPOWER_PROMPT,
        "max_tokens": 900,
    },
}


def clean_helper_response(text: object) -> str:
    if text is None:
        return ""

    cleaned = str(text).strip()
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned).strip()
    cleaned = re.sub(
        r"^\s*model\s+chose\s+.*?(\n\n|\n|$)",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    if cleaned.lower() in {"none", "null", "undefined"}:
        return ""

    return cleaned


def normalize_selected_option(value: object) -> Optional[str]:
    option = canonical_option(str(value)) if value is not None else None
    return option if option in VALID_SELECTED_OPTIONS else None


def _try_json(text: str) -> Optional[dict]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def extract_json_object(text: str) -> Optional[dict]:
    cleaned = clean_helper_response(text)

    parsed = _try_json(cleaned)
    if parsed:
        return parsed

    start = cleaned.find("{")

    while start != -1:
        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(cleaned)):
            char = cleaned[index]

            if escape:
                escape = False
                continue

            if char == "\\":
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    parsed = _try_json(cleaned[start : index + 1])
                    if parsed:
                        return parsed
                    break

        start = cleaned.find("{", start + 1)

    return None


def extract_loose_fields(text: str) -> dict:
    cleaned = clean_helper_response(text)

    option_match = re.search(
        r"(?:selected_option|option|help_type|choice)\s*[:=]\s*[\"']?([^\"'\n,}]+)",
        cleaned,
        flags=re.IGNORECASE,
    )

    selected_option = option_match.group(1).strip() if option_match else None

    content = cleaned
    content_match = re.search(
        r"(?:content|response|suggestion|code)\s*[:=]\s*(.*)$",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if content_match:
        content = content_match.group(1).strip()

    if len(content) >= 2 and content[0] in {"'", '"'} and content[-1] == content[0]:
        content = content[1:-1]

    return {
        "selected_option": selected_option,
        "content": clean_helper_response(content),
    }


def looks_like_full_python_function(content: str) -> bool:
    stripped = content.lstrip()
    return stripped.startswith("def ") or "\ndef " in stripped


def parse_model_choice(raw_text: str) -> Dict[str, str]:
    parsed = extract_json_object(raw_text)

    if parsed:
        selected_option = normalize_selected_option(
            parsed.get("selected_option")
            or parsed.get("option")
            or parsed.get("help_type")
            or parsed.get("choice")
        )

        content_value = None
        for key in ["content", "response", "suggestion", "code"]:
            if key in parsed:
                content_value = parsed.get(key)
                break

        content = clean_helper_response(content_value)
    else:
        loose = extract_loose_fields(raw_text)
        selected_option = normalize_selected_option(loose.get("selected_option"))
        content = clean_helper_response(loose.get("content"))

    if selected_option not in VALID_SELECTED_OPTIONS:
        if looks_like_full_python_function(content):
            selected_option = "direct_code"
        else:
            selected_option = "code_suggestion"

    return {
        "selected_option": selected_option,
        "suggestion": content,
        "raw_response": clean_helper_response(raw_text),
    }


def call_openrouter(
    prefix: str,
    method: str,
    problem_description: str = "",
) -> Dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY is missing in .env",
        )

    if method not in METHOD_CONFIG:
        valid = ", ".join(METHOD_CONFIG.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown method: {method}. Valid methods: {valid}",
        )

    config = METHOD_CONFIG[method]
    system_prompt = config["prompt"]
    max_tokens = config["max_tokens"]

    user_message = f"""
Problem:
{problem_description}

Current code in the editor:
{prefix}

Choose exactly one help type and return only the required JSON object.
Remember: content must not be None, null, undefined, or empty.
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-OpenRouter-Title": "Soft Empower Coding Study",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"OpenRouter error: {response.status_code} {response.text}",
        )

    data = response.json()

    try:
        raw = data["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected OpenRouter response: {data}",
        )

    return parse_model_choice(raw)
