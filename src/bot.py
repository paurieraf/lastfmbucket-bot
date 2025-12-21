import logging

import sentry_sdk
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

import commands
import config
from lastfm import LastfmClient
from services import LastfmService, ViewService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()


def main() -> None:
    """Starts the bot."""
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )

    # Initialize services
    lastfm_client = LastfmClient()
    lastfm_service = LastfmService(lastfm_client)
    view_service = ViewService(lastfm_service)

    # Add services to bot_data
    app.bot_data["lastfm_service"] = lastfm_service
    app.bot_data["view_service"] = view_service

    # Add command handlers
    app.add_handler(CommandHandler(commands.START_COMMAND, commands.start))
    app.add_handler(CommandHandler(commands.STATUS_COMMAND, commands.status))
    app.add_handler(CommandHandler(commands.NOW_PLAYING_COMMAND, commands.now_playing))
    app.add_handler(CommandHandler(commands.TOPS_COMMAND, commands.tops))
    app.add_handler(CommandHandler(commands.PREFERENCES_COMMAND, commands.preferences))
    app.add_handler(CommandHandler(commands.HELP_COMMAND, commands.help_command))
    app.add_handler(CommandHandler(commands.CHANGELOG_COMMAND, commands.changelog))
    app.add_handler(CommandHandler(commands.SET_COMMAND, commands.lastfm_username_set))
    app.add_handler(CommandHandler(commands.PRIVACY_COMMAND, commands.privacy))

    app.add_handler(CallbackQueryHandler(commands.button_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
