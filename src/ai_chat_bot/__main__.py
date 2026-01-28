"""
ai_chat_bot entrypoint.

Run:
    python -m ai_chat_bot

Does:
- setup logging
- init sqlite schema
- start telegram polling
"""

import os
import logging

from ai_chat_bot.infra.logging.setup import setup_logging
from ai_chat_bot.infra.db.sqlite import init_db
from ai_chat_bot.adapters.telegram.bot import run_bot


def main() -> None:
    setup_logging(os.getenv("LOG_LEVEL", "DEBUG"))
    log = logging.getLogger(__name__)

    try:
        init_db()
        run_bot()
    except KeyboardInterrupt:
        log.info("Shutting down (KeyboardInterrupt).")
    except Exception:
        log.exception("Fatal error in main()")
        raise


if __name__ == "__main__":
    main()
