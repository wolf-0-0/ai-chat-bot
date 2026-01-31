"""Telegram adapter (event-log DB + JSON contract LLM)."""

from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

from ai_chat_bot.core.config import settings, require_bot_token
from ai_chat_bot.app.graph import build_graph
from ai_chat_bot.infra.db.sqlite import (
    upsert_chat,
    upsert_telegram_user,
    insert_message,
    update_user_description,
)

log = logging.getLogger(__name__)
_app_graph = build_graph()


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or not msg.text:
        return

    raw = update.to_dict()
    if settings.DEBUG_TELEGRAM_UPDATES:
        log.debug("TELEGRAM RAW UPDATE: %s", json.dumps(raw, ensure_ascii=False))

    chat_id = int(chat.id)
    user_id = int(user.id)
    chat_type = getattr(chat, "type", None) or "unknown"
    title = getattr(chat, "title", None)

    # 0) Upsert chat + user (best effort, but should not crash bot)
    try:
        upsert_chat(telegram_chat_id=chat_id, chat_type=chat_type, title=title)
        upsert_telegram_user(
            telegram_user_id=user_id,
            is_bot=user.is_bot,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=getattr(user, "language_code", None),
        )
    except Exception:
        log.exception("DB upsert failed (ignored).")

    # 1) Insert incoming user event
    try:
        insert_message(
            update_id=raw.get("update_id"),
            telegram_message_id=msg.message_id,
            chat_telegram_id=chat_id,
            from_telegram_user_id=user_id,
            role="user",
            text=msg.text,
            telegram_date=getattr(msg, "date", None).timestamp() if getattr(msg, "date", None) else raw.get("message", {}).get("date"),
        )
    except Exception:
        log.exception("DB insert user message failed (ignored).")

    # 2) Invoke graph
    try:
        out = _app_graph.invoke(
            {
                "telegram_chat_id": chat_id,
                "telegram_user_id": user_id,
                "user_text": msg.text,
            }
        )
        
        log.debug(json.dumps(out, ensure_ascii=False, indent=2))

        reply = (out.get("assistant_text") or "").strip() or "(no response)"
        new_desc = (out.get("updated_user_description") or "").strip()
    except Exception:
        log.exception("Graph invoke failed")
        reply = "Sorry, internal error."
        new_desc = ""

    # 3) Reply (critical path)
    sent = await msg.reply_text(reply)

    # 4) Insert assistant event
    try:
        insert_message(
            update_id=None,
            telegram_message_id=getattr(sent, "message_id", None),
            chat_telegram_id=chat_id,
            from_telegram_user_id=None,
            role="assistant",
            text=reply,
            telegram_date=getattr(sent, "date", None).timestamp() if getattr(sent, "date", None) else None,
        )
    except Exception:
        log.exception("DB insert assistant message failed (ignored).")

    # 5) Replace user_description in DB (AI decides)
    if new_desc is not None:
        try:
            update_user_description(user_id, new_desc)
        except Exception:
            log.exception("DB update user_description failed (ignored).")


def run_bot() -> None:
    require_bot_token()

    app = Application.builder().token(settings.BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(timeout=50, poll_interval=0.0, close_loop=False)

