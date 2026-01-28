"""Ollama HTTP client (minimal + robust).

Talks to your local Ollama server:
- GET /api/tags       (optional: list models)
- POST /api/generate  (non-streaming generation)
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from ai_chat_bot.core.config import settings

log = logging.getLogger(__name__)
_session = requests.Session()


def _list_models() -> list[str]:
    """Best-effort list of locally available models."""
    try:
        r = _session.get(f"{settings.OLLAMA_URL}/api/tags", timeout=15)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def chat(prompt: str) -> str:
    """Send a prompt to Ollama and return the response text."""
    payload = {
    "model": settings.OLLAMA_MODEL,
    "prompt": prompt,
    "stream": False,
    "options": {
        "temperature": 0.2,
        "num_predict": 300,
        "stop": [
            "\nUser:",
            "\nAssistant:",
            "\nSYSTEM:",
            "\nCONTEXT:",
            "\nHISTORY:",
            "\n###",   # if you still have markdown headings anywhere
        ],
    },
}

    try:
        r = _session.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120,
        )
    except requests.RequestException as e:
        return f"Ollama connection error: {e}"

    if r.status_code >= 400:
        # Try to parse JSON error
        try:
            err = r.json().get("error", r.text)
        except Exception:
            err = r.text

        err_s = str(err).lower()
        if "model" in err_s and "not found" in err_s:
            models = _list_models()
            if models:
                return f"Model '{settings.OLLAMA_MODEL}' not found. Available: {', '.join(models)}"
            return f"Model '{settings.OLLAMA_MODEL}' not found. (No model list available.)"

        return f"Ollama error {r.status_code}: {err}"

    try:
        data = r.json()
    except Exception:
        return f"Ollama returned non-JSON response: {r.text[:200]}"

    text = (data.get("response", "") or "").strip()
    return text or "(no response from model)"
