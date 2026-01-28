"""Telegram adapter.

Responsibilities:
- Receive Telegram messages
- Build state for the app graph
- Invoke the graph (LLM)
- Reply to the user
- Best-effort logging to SQLite (never break the bot if DB fails)

Tip:
    DEBUG_TELEGRAM_UPDATES=1 will log the raw update JSON.
"""

from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

from ai_chat_bot.core.config import settings, require_bot_token
from ai_chat_bot.app.graph import build_graph
from ai_chat_bot.infra.db.sqlite import log_message

log = logging.getLogger(__name__)

# Build once (fast) — if you prefer, we can lazy-build inside run_bot().
_app_graph = build_graph()


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a normal text message (non-command)."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # Ignore non-text messages safely.
    if not msg or not chat or not user or not msg.text:
        return

    log.info("Incoming message chat_id=%s user=%s text=%r", chat.id, user.username or user.first_name, msg.text)

    raw = update.to_dict()

    if settings.DEBUG_TELEGRAM_UPDATES:
        log.debug("TELEGRAM RAW UPDATE: %s", json.dumps(raw, ensure_ascii=False))

    # Minimal state the graph needs.
    state = {
        "chat_id": str(chat.id),
        "user_name": user.username or user.first_name or "unknown",
        "user_text": msg.text,
        "chat_type": getattr(chat, "type", None) or "unknown",
    }

    # 1) Invoke the app graph (LLM pipeline)
    try:
        out = _app_graph.invoke(state)
        reply = (out.get("assistant_text") or "").strip() or "(no response)"
        prompt_used = out.get("prompt_used")
    except Exception:
        log.exception("Graph invoke failed")
        reply = "Sorry — internal error."
        prompt_used = None

    # 2) Reply to the user (this is the critical path)
    await msg.reply_text(reply)

    # 3) Best-effort: log to DB (never crash the bot if DB has issues)
    try:
        raw_msg = raw.get("message") or {}
        raw_chat = raw_msg.get("chat") or {}
        raw_from = raw_msg.get("from") or {}

        log_message(
            chat_id=str(chat.id),
            user_name=(raw_from.get("first_name") or state["user_name"] or "unknown"),
            user_text=raw_msg.get("text") or msg.text or "",
            assistant_text=reply,
            update_id=raw.get("update_id"),
            message_id=raw_msg.get("message_id"),
            date_unix=raw_msg.get("date"),
            chat_type=raw_chat.get("type") or state.get("chat_type"),
            chat_first_name=raw_chat.get("first_name"),
            chat_last_name=raw_chat.get("last_name"),
            from_id=raw_from.get("id"),
            from_first_name=raw_from.get("first_name"),
            from_last_name=raw_from.get("last_name"),
            from_is_bot=raw_from.get("is_bot"),
            from_language_code=raw_from.get("language_code"),
            prompt_used=prompt_used,
            raw_json=raw,
        )
    except Exception:
        log.exception("DB logging failed (ignored).")


def run_bot() -> None:
    """Start Telegram long-polling."""
    require_bot_token()

    app = Application.builder().token(settings.BOT_TOKEN).build()

    # Only handle normal text; commands can be added later (/start, /help).
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # close_loop=False helps when running in some environments; we can tweak later if needed.
    app.run_polling(close_loop=False)
