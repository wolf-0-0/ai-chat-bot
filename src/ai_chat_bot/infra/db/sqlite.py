"""SQLite persistence (new schema).

Tables (from dbdiagram):
- chat
- telegram_user
- message (raw event log, role=user|assistant)
- user_state (1 row per telegram user, holds minimal memory string)

Notes:
- We keep things migration-light: CREATE IF NOT EXISTS + indexes
- We store timestamps as SQLite TEXT defaults (CURRENT_TIMESTAMP)
- We enable foreign_keys pragma
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from ai_chat_bot.core.config import settings


def _ensure_db_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    _ensure_db_dir(settings.SQLITE_PATH)
    conn = sqlite3.connect(settings.SQLITE_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables + indexes if missing."""
    schema = """
    CREATE TABLE IF NOT EXISTS chat (
      id INTEGER PRIMARY KEY,
      telegram_chat_id INTEGER NOT NULL UNIQUE,
      type TEXT,
      title TEXT,
      modified_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS telegram_user (
      id INTEGER PRIMARY KEY,
      telegram_user_id INTEGER NOT NULL UNIQUE,
      is_bot INTEGER,
      first_name TEXT,
      last_name TEXT,
      language_code TEXT,
      modified_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS message (
      id INTEGER PRIMARY KEY,
      update_id INTEGER,
      telegram_message_id INTEGER,
      chat_telegram_id INTEGER NOT NULL,
      from_telegram_user_id INTEGER,
      role TEXT NOT NULL,
      text TEXT,
      telegram_date INTEGER,
      modified_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,

      FOREIGN KEY(chat_telegram_id) REFERENCES chat(telegram_chat_id),
      FOREIGN KEY(from_telegram_user_id) REFERENCES telegram_user(telegram_user_id)
    );

    CREATE TABLE IF NOT EXISTS user_state (
      id INTEGER PRIMARY KEY,
      telegram_user_id INTEGER NOT NULL UNIQUE,
      user_description TEXT NOT NULL,
      modified_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,

      FOREIGN KEY(telegram_user_id) REFERENCES telegram_user(telegram_user_id)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_message_update_id_unique ON message(update_id);
    CREATE INDEX IF NOT EXISTS idx_message_chat_created ON message(chat_telegram_id, created_at);
    """
    with _conn() as conn:
        conn.executescript(schema)
        conn.commit()


def upsert_chat(*, telegram_chat_id: int, chat_type: str | None, title: str | None) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO chat(telegram_chat_id, type, title, modified_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_chat_id) DO UPDATE SET
              type=excluded.type,
              title=excluded.title,
              modified_at=CURRENT_TIMESTAMP
            """,
            (telegram_chat_id, chat_type, title),
        )
        conn.commit()


def upsert_telegram_user(
    *,
    telegram_user_id: int,
    is_bot: bool | int | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None,
) -> None:
    is_bot_i: int | None
    if is_bot is None:
        is_bot_i = None
    else:
        is_bot_i = int(is_bot)

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO telegram_user(
              telegram_user_id, is_bot, first_name, last_name, language_code, modified_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
              is_bot=excluded.is_bot,
              first_name=excluded.first_name,
              last_name=excluded.last_name,
              language_code=excluded.language_code,
              modified_at=CURRENT_TIMESTAMP
            """,
            (telegram_user_id, is_bot_i, first_name, last_name, language_code),
        )
        conn.commit()


def get_user_description(telegram_user_id: int) -> str:
    """Return user_description; create empty state row if missing."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_description FROM user_state WHERE telegram_user_id = ?",
            (telegram_user_id,),
        )
        row = cur.fetchone()
        if row and row[0] is not None:
            return str(row[0])

        # create default empty description (NOT NULL)
        conn.execute(
            """
            INSERT INTO user_state(telegram_user_id, user_description, modified_at)
            VALUES (?, '', CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO NOTHING
            """,
            (telegram_user_id,),
        )
        conn.commit()
        return ""


def update_user_description(telegram_user_id: int, user_description: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO user_state(telegram_user_id, user_description, modified_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
              user_description=excluded.user_description,
              modified_at=CURRENT_TIMESTAMP
            """,
            (telegram_user_id, user_description or ""),
        )
        conn.commit()


def insert_message(
    *,
    update_id: int | None,
    telegram_message_id: int | None,
    chat_telegram_id: int,
    from_telegram_user_id: int | None,
    role: str,
    text: str | None,
    telegram_date: int | None,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO message(
              update_id, telegram_message_id, chat_telegram_id, from_telegram_user_id,
              role, text, telegram_date, modified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                update_id,
                telegram_message_id,
                chat_telegram_id,
                from_telegram_user_id,
                role,
                text,
                telegram_date,
            ),
        )
        conn.commit()


def fetch_recent_events(chat_telegram_id: int, limit_turns: int = 10) -> list[dict[str, str]]:
    """Return recent paired turns: [{"timestamp": iso, "user": u, "assistant": a}, ...] oldest->newest.

    We reconstruct turns from the event log:
    - Take last ~4*limit events
    - Pair user -> next assistant
    """
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, text, created_at, telegram_date
            FROM message
            WHERE chat_telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_telegram_id, max(20, limit_turns * 4)),
        )
        rows = cur.fetchall()

    rows.reverse()

    turns: list[dict[str, str]] = []
    pending_user_text: str | None = None
    pending_ts: str | None = None

    for role, text, created_at, telegram_date in rows:
        role = (role or "").strip()
        text = (text or "").strip()
        ts = created_at  # already ISO-ish "YYYY-MM-DD HH:MM:SS"
        if telegram_date:
            # Keep created_at for readability; telegram_date exists if you ever want exact unix.
            pass

        if role == "user":
            pending_user_text = text
            pending_ts = ts
        elif role == "assistant":
            if pending_user_text is None:
                continue
            turns.append(
                {
                    "timestamp": pending_ts or ts or "",
                    "user": pending_user_text,
                    "assistant": text,
                }
            )
            pending_user_text = None
            pending_ts = None

    # Keep only last limit_turns
    if len(turns) > limit_turns:
        turns = turns[-limit_turns:]

    return turns
