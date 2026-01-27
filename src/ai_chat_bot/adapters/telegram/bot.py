import json
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

from ai_chat_bot.core.config import BOT_TOKEN
from ai_chat_bot.infra.db.sqlite import log_message
from ai_chat_bot.app.graph import build_graph

_app_graph = build_graph()

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user or not msg.text:
        return

    # --- RAW TELEGRAM UPDATE (for debugging/learning) ---
    raw = update.to_dict()
    raw_msg = raw.get("message") or {}
    raw_chat = raw_msg.get("chat") or {}
    raw_from = raw_msg.get("from") or {}

    print("=== TELEGRAM RAW UPDATE ===")
    print(json.dumps(raw, ensure_ascii=False, indent=2))

    state = {
        "chat_id": str(chat.id),
        "user_name": user.username or user.first_name or "unknown",
        "user_text": msg.text,
        "assistant_text": "",
    }
    print("=== STATE ===")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    out = _app_graph.invoke(state)
    print("=== OUT ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("=== END ===")
    reply = out.get("assistant_text", "") or "(no response)"

    log_message(
    chat_id=str(raw_chat.get("id")),
    user_name=(raw_from.get("first_name") or "unknown"),
    user_text=raw_msg.get("text") or "",
    assistant_text=reply,

    update_id=raw.get("update_id"),
    message_id=raw_msg.get("message_id"),
    date_unix=raw_msg.get("date"),

    chat_type=raw_chat.get("type"),
    chat_first_name=raw_chat.get("first_name"),
    chat_last_name=raw_chat.get("last_name"),

    from_id=raw_from.get("id"),
    from_first_name=raw_from.get("first_name"),
    from_last_name=raw_from.get("last_name"),
    from_is_bot=raw_from.get("is_bot"),
    from_language_code=raw_from.get("language_code"),

    raw_json=raw,
)
    await msg.reply_text(reply)

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(close_loop=False)
