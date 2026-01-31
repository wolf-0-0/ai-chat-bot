"""
OpenAI-compatible Chat Completions client (JSON contract).

Works with providers like:
- Groq (https://api.groq.com/openai/v1)
- OpenRouter (https://openrouter.ai/api/v1)
- Any OpenAI-compatible endpoint

Contract we expect back (ONLY JSON):
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


def _chat_completions_url() -> str:
    base = (settings.OPENAI_COMPAT_BASE_URL or "").rstrip("/")
    return f"{base}/chat/completions"


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


def _response_format_schema() -> dict[str, Any]:
    """
    Prefer strict schema output when provider supports it.
    Some providers reject json_schema; we fallback in generate_contract.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "assistant_contract",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "assistant_text": {"type": "string"},
                    "updated_user_description": {"type": "string"},
                },
                "required": ["assistant_text", "updated_user_description"],
            },
        },
    }


def _headers() -> dict[str, str]:
    key = (settings.OPENAI_COMPAT_API_KEY or "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _build_payload(prompt_used: str, response_format: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": settings.OPENAI_COMPAT_MODEL,
        "messages": [
            {"role": "system", "content": load_system_rules()},
            {"role": "user", "content": prompt_used},
        ],
        "temperature": 0.2,
        # Different providers call this differently; OpenAI supports max_completion_tokens,
        # others sometimes accept max_tokens. We'll send both to be tolerant.
        "max_completion_tokens": 400,
        "max_tokens": 400,
        "response_format": response_format,
        "stream": False,
    }


def _parse_choice_content(data: dict[str, Any]) -> str:
    """
    Standard OpenAI-compatible shape:
      data["choices"][0]["message"]["content"]
    Some providers might return content in other places. We handle a few common variants.
    """
    choices = data.get("choices") or []
    if not choices:
        return ""

    c0 = choices[0] or {}

    # Normal:
    msg = c0.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()

    # Some providers might return already-parsed object (rare but possible):
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)

    # Fallback:
    text = c0.get("text")
    if isinstance(text, str):
        return text.strip()

    return ""


def generate_contract(request_obj: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Returns (parsed_json, prompt_used_as_string).

    On errors, returns:
      {"assistant_text": "...error...", "updated_user_description": ""}
    """
    prompt_used = json.dumps(request_obj, ensure_ascii=False, indent=2)

    if not (settings.OPENAI_COMPAT_API_KEY or "").strip():
        return (
            {
                "assistant_text": (
                    "Missing OPENAI_COMPAT_API_KEY (or GROQ_API_KEY). "
                    "Set it in .env or env vars."
                ),
                "updated_user_description": "",
            },
            prompt_used,
        )

    url = _chat_completions_url()
    headers = _headers()

    # 1) Try strict schema
    payload = _build_payload(prompt_used, _response_format_schema())

    try:
        r = _session.post(
            url,
            headers=headers,
            json=payload,
            timeout=settings.OPENAI_COMPAT_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return (
            {"assistant_text": f"Remote LLM connection error: {e}", "updated_user_description": ""},
            prompt_used,
        )

    # If schema format rejected, retry with json_object mode
    if r.status_code >= 400:
        err_text = ""
        try:
            err_json = r.json()
            err_text = json.dumps(err_json, ensure_ascii=False)
        except Exception:
            err_text = r.text or ""

        err_l = err_text.lower()
        schema_rejected = any(k in err_l for k in ["json_schema", "response_format", "schema", "strict"])

        if schema_rejected:
            payload = _build_payload(prompt_used, {"type": "json_object"})
            try:
                r = _session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=settings.OPENAI_COMPAT_TIMEOUT_S,
                )
            except requests.RequestException as e:
                return (
                    {"assistant_text": f"Remote LLM connection error (retry): {e}", "updated_user_description": ""},
                    prompt_used,
                )

    if r.status_code >= 400:
        # Still failing
        try:
            err = r.json()
        except Exception:
            err = r.text
        return (
            {"assistant_text": f"Remote LLM error {r.status_code}: {err}", "updated_user_description": ""},
            prompt_used,
        )

    try:
        data = r.json()
    except Exception:
        return (
            {"assistant_text": f"Remote LLM returned non-JSON HTTP body: {r.text[:200]}", "updated_user_description": ""},
            prompt_used,
        )

    content = _parse_choice_content(data)
    parsed = _extract_json_object(content)

    if not isinstance(parsed, dict):
        # If provider returned plain text, at least show it.
        return (
            {"assistant_text": content or "(no response from model)", "updated_user_description": ""},
            prompt_used,
        )

    assistant_text = (parsed.get("assistant_text") or "").strip()
    updated_user_description = (parsed.get("updated_user_description") or "").strip()

    return (
        {
            "assistant_text": assistant_text or "(no response from model)",
            "updated_user_description": updated_user_description,
        },
        prompt_used,
    )
