"""
Configuration loading.

Import-safe:
- Loads .env
- Reads env vars
- Doesn't hard-exit at import time

Hard requirements validated only when starting bot.
"""

import os
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./data/messages.db")

    # LLM contract/meta
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Bianca")
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Brussels")
    SCHEMA_VERSION: str = os.getenv("SCHEMA_VERSION", "1.0")

    # Hard-coded system rules markdown (forces JSON output)
    SYSTEM_RULES_PATH: str = os.getenv("SYSTEM_RULES_PATH", "./data/core_behavior.md")

    # Optional
    DEBUG_TELEGRAM_UPDATES: bool = os.getenv("DEBUG_TELEGRAM_UPDATES", "0") == "1"
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "8"))


settings = Settings()


def require_bot_token() -> None:
    if not settings.BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env (or env vars).")


@lru_cache(maxsize=1)
def load_system_rules() -> str:
    """Load system rules markdown from disk (cached)."""
    path = Path(settings.SYSTEM_RULES_PATH)
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"SYSTEM_RULES_PATH not found: {path}")
