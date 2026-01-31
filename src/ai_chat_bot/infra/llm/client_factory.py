from __future__ import annotations

import json
from typing import Any

from ai_chat_bot.core.config import settings


def generate_contract(request_obj: dict[str, Any]) -> tuple[dict[str, Any], str]:
    backend = (settings.LLM_BACKEND or "").strip().lower()

    if backend == "ollama":
        from ai_chat_bot.infra.llm.ollama_client import generate_contract as impl
        return impl(request_obj)

    if backend == "openai_compat":
        from ai_chat_bot.infra.llm.openai_compat_client import generate_contract as impl
        return impl(request_obj)

    prompt_used = json.dumps(request_obj, ensure_ascii=False, indent=2)
    return (
        {
            "assistant_text": f"Unknown LLM_BACKEND='{settings.LLM_BACKEND}'. Use 'ollama' or 'openai_compat'.",
            "updated_user_description": "",
        },
        prompt_used,
    )
