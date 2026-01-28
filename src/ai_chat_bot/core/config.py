"""
Configuration loading.

Keep this module import-safe:
- Load .env
- Read env vars
- Don't hard-exit at import time

Validate required settings (like TELEGRAM_BOT_TOKEN) when starting the bot.
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

    # Prompt / behavior
    CORE_BEHAVIOR_PATH: str = os.getenv("CORE_BEHAVIOR_PATH", "./db/core_behavior.md")


    # Optional
    DEBUG_TELEGRAM_UPDATES: bool = os.getenv("DEBUG_TELEGRAM_UPDATES", "0") == "1"
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "16"))


settings = Settings()


def require_bot_token() -> None:
    """Fail fast only when we actually start Telegram polling."""
    if not settings.BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env (or env vars).")

@lru_cache(maxsize=1)
def load_core_behavior() -> str:
    """Load the core behavior prompt from disk (cached).

    Keeps config import-safe: this only reads the file when called.
    """
    path = Path(settings.CORE_BEHAVIOR_PATH)
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"CORE_BEHAVIOR_PATH not found: {path}")