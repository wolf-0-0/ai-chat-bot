"""SQLite persistence for chat messages.

MVP design:
- Single table `messages`
- Lazy schema evolution via ALTER TABLE (no migrations yet)
- Store both cleaned fields + raw JSON for later use
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from ai_chat_bot.core.config import settings


def _ensure_db_dir(path: str) -> None:
    """Create parent directory if SQLITE_PATH includes one."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Context-managed SQLite connection (always closes)."""
    _ensure_db_dir(settings.SQLITE_PATH)
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        # Better default behavior for a bot
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        yield conn
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, col: str, coltype: str) -> None:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def init_db() -> None:
    """Create base table and add missing columns."""
    with _conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                chat_id TEXT,
                user_name TEXT,
                user_text TEXT,
                assistant_text TEXT
            )
            """
        )
        conn.commit()

        # Match Telegram raw payload fields
        _ensure_column(conn, "messages", "update_id", "INTEGER")
        _ensure_column(conn, "messages", "message_id", "INTEGER")
        _ensure_column(conn, "messages", "date_unix", "INTEGER")

        _ensure_column(conn, "messages", "chat_type", "TEXT")
        _ensure_column(conn, "messages", "chat_first_name", "TEXT")
        _ensure_column(conn, "messages", "chat_last_name", "TEXT")

        _ensure_column(conn, "messages", "from_id", "INTEGER")
        _ensure_column(conn, "messages", "from_first_name", "TEXT")
        _ensure_column(conn, "messages", "from_last_name", "TEXT")
        _ensure_column(conn, "messages", "from_is_bot", "INTEGER")
        _ensure_column(conn, "messages", "from_language_code", "TEXT")

        # Useful extras
        _ensure_column(conn, "messages", "prompt_used", "TEXT")
        _ensure_column(conn, "messages", "raw_json", "TEXT")

        conn.commit()


def fetch_recent_turns(chat_id: str, limit: int = 10) -> list[tuple[str, str]]:
    """Return recent (user_text, assistant_text) turns, oldest -> newest."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_text, assistant_text
            FROM messages
            WHERE chat_id = ?
              AND user_text IS NOT NULL
              AND assistant_text IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        rows = cur.fetchall()

    rows.reverse()
    return rows


def log_message(
    chat_id: str,
    user_name: str,
    user_text: str,
    assistant_text: str,
    *,
    update_id: int | None = None,
    message_id: int | None = None,
    date_unix: int | None = None,
    chat_type: str | None = None,
    chat_first_name: str | None = None,
    chat_last_name: str | None = None,
    from_id: int | None = None,
    from_first_name: str | None = None,
    from_last_name: str | None = None,
    from_is_bot: bool | int | None = None,
    from_language_code: str | None = None,
    prompt_used: str | None = None,
    raw_json: Any | None = None,
) -> None:
    """Persist one message exchange."""
    if isinstance(from_is_bot, bool):
        from_is_bot = int(from_is_bot)

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO messages(
                chat_id, user_name, user_text, assistant_text,
                update_id, message_id, date_unix,
                chat_type, chat_first_name, chat_last_name,
                from_id, from_first_name, from_last_name, from_is_bot, from_language_code,
                prompt_used, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id, user_name, user_text, assistant_text,
                update_id, message_id, date_unix,
                chat_type, chat_first_name, chat_last_name,
                from_id, from_first_name, from_last_name, from_is_bot, from_language_code,
                prompt_used,
                json.dumps(raw_json, ensure_ascii=False) if raw_json is not None else None,
            ),
        )
        conn.commit()
