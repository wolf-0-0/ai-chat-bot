import os
import sqlite3
import json
from ai_chat_bot.core.config import SQLITE_PATH

def _conn():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    return sqlite3.connect(SQLITE_PATH)

def _ensure_column(conn, table: str, col: str, coltype: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

def init_db():
    conn = _conn()
    cur = conn.cursor()

    # Original table (keep it)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        chat_id TEXT,
        user_name TEXT,
        user_text TEXT,
        assistant_text TEXT
    )
    """)
    conn.commit()

    # Add columns that match your RAW payload paths
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
    conn.close()
    
def fetch_recent_turns(chat_id: str, limit: int = 10):
    """
    Returns the most recent conversation turns for a chat_id.
    Each row includes user_text + assistant_text.
    """
    conn = _conn()
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
    conn.close()

    # rows are newest-first; reverse to chronological
    rows.reverse()
    return rows

def log_message(
    chat_id: str,
    user_name: str,
    user_text: str,
    assistant_text: str,
    *,
    update_id=None,
    message_id=None,
    date_unix=None,
    chat_type=None,
    chat_first_name=None,
    chat_last_name=None,
    from_id=None,
    from_first_name=None,
    from_last_name=None,
    from_is_bot=None,
    from_language_code=None,
    prompt_used=None,
    raw_json=None,
):
    conn = _conn()
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
    conn.close()
