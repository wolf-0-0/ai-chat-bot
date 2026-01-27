# import os

# from ai_chat_bot.infra.logging.setup import setup_logging
from ai_chat_bot.infra.db.sqlite import init_db
from ai_chat_bot.adapters.telegram.bot import run_bot


def main():
    # setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    init_db()
    run_bot()


if __name__ == "__main__":
    main()
