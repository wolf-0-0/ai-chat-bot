"""Ollama HTTP client (JSON contract).

We send a JSON request object as the prompt.
We force the model to output ONLY valid JSON with:
{
  "assistant_text": "...",
  "updated_user_description": "..."
}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from ai_chat_bot.core.config import settings, load_system_rules

log = logging.getLogger(__name__)
_session = requests.Session()


def _list_models() -> list[str]:
    try:
        r = _session.get(f"{settings.OLLAMA_URL}/api/tags", timeout=15)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _extract_json_object(s: str) -> dict[str, Any] | None:
    """Best-effort extraction if the model wraps JSON in extra garbage."""
    s = (s or "").strip()
    if not s:
        return None

    # Fast path
    try:
        return json.loads(s)
    except Exception:
        pass

    # Try to find first {...} block
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def generate_contract(request_obj: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Returns (parsed_json, prompt_used_as_string)."""
    prompt_used = json.dumps(request_obj, ensure_ascii=False, indent=2)

    payload = {
  "model": settings.OLLAMA_MODEL,
  "system": load_system_rules(),       # <- THIS is what gives it teeth
  "prompt": prompt_used,
  "stream": False,
  "format": "json",
  "options": {"temperature": 0.2, "num_predict": 400},
}

    try:
        r = _session.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120,
        )
    except requests.RequestException as e:
        return (
            {
                "assistant_text": f"Ollama connection error: {e}",
                "updated_user_description": "",
            },
            prompt_used,
        )

    if r.status_code >= 400:
        try:
            err = r.json().get("error", r.text)
        except Exception:
            err = r.text

        err_s = str(err).lower()
        if "model" in err_s and "not found" in err_s:
            models = _list_models()
            if models:
                msg = f"Model '{settings.OLLAMA_MODEL}' not found. Available: {', '.join(models)}"
            else:
                msg = f"Model '{settings.OLLAMA_MODEL}' not found. (No model list available.)"
            return ({"assistant_text": msg, "updated_user_description": ""}, prompt_used)

        return ({"assistant_text": f"Ollama error {r.status_code}: {err}", "updated_user_description": ""}, prompt_used)

    try:
        data = r.json()
    except Exception:
        return (
            {"assistant_text": f"Ollama returned non-JSON response: {r.text[:200]}", "updated_user_description": ""},
            prompt_used,
        )

    text = (data.get("response", "") or "").strip()
    parsed = _extract_json_object(text)

    if not isinstance(parsed, dict):
        return ({"assistant_text": text or "(no response from model)", "updated_user_description": ""}, prompt_used)

    # Normalize keys
    assistant_text = (parsed.get("assistant_text") or "").strip()
    updated_user_description = (parsed.get("updated_user_description") or "").strip()

    return (
        {
            "assistant_text": assistant_text or "(no response from model)",
            "updated_user_description": updated_user_description,
        },
        prompt_used,
    )
