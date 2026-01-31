from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def iso_now_utc() -> str:
    # You want Europe/Brussels in meta, but "now" as ISO is fine in UTC.
    return datetime.now(timezone.utc).isoformat()


def build_llm_request(
    *,
    schema_version: str,
    assistant_name: str,
    system_rules: str,
    timezone_name: str,
    user_description: str,
    recent_events: list[dict[str, str]],
    user_message: str,
) -> dict[str, Any]:
    return {
        "meta": {
            "schema_version": schema_version,
            "assistant_name": assistant_name,
            "system_rules": system_rules,
            "timezone": timezone_name,
            "now": iso_now_utc(),
        },
        "user_description": user_description or "",
        "recent_events": recent_events or [],
        "user_message": user_message or "",
    }
