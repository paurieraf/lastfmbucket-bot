import logging

import sentry_sdk
from dotenv import load_dotenv
from telegram import LinkPreviewOptions, Update, constants
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
)

import commands
import config
from lastfm import LastfmClient
from services import CollageService, LastfmService, ViewService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()


async def post_init(application: Application) -> None:
    """Post-initialization callback to register bot commands."""
    await application.bot.set_my_commands(commands.BOT_COMMANDS)
    logger.info("Bot commands successfully registered with Telegram API.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a user-friendly error message."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    if config.SENTRY_DSN:
        sentry_sdk.capture_exception(context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ An unexpected error occurred while processing your request. Please try again later.",
            )
        except Exception as e:
            logger.error(f"Failed to send error notification message: {e}")


def main() -> None:
    """Starts the bot."""
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        send_default_pii=True,
    )

    defaults = Defaults(
        parse_mode=constants.ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .build()
    )

    # Initialize services
    lastfm_client = LastfmClient()
    lastfm_service = LastfmService(lastfm_client)
    view_service = ViewService(lastfm_service)
    collage_service = CollageService(config.LASTFM_API_KEY, config.LASTFM_API_SECRET)

    # Add services to bot_data
    app.bot_data["lastfm_service"] = lastfm_service
    app.bot_data["view_service"] = view_service
    app.bot_data["collage_service"] = collage_service

    # Add command handlers
    app.add_handler(CommandHandler(commands.START_COMMAND, commands.start))
    app.add_handler(CommandHandler(commands.STATUS_COMMAND, commands.status))
    app.add_handler(CommandHandler(commands.NOW_PLAYING_COMMAND, commands.now_playing))
    app.add_handler(CommandHandler(commands.TOPS_COMMAND, commands.tops))
    app.add_handler(CommandHandler(commands.COLLAGE_COMMAND, commands.collage))
    app.add_handler(CommandHandler(commands.PREFERENCES_COMMAND, commands.preferences))
    app.add_handler(CommandHandler(commands.HELP_COMMAND, commands.help_command))
    app.add_handler(CommandHandler(commands.CHANGELOG_COMMAND, commands.changelog))
    app.add_handler(CommandHandler(commands.SET_COMMAND, commands.lastfm_username_set))
    app.add_handler(CommandHandler(commands.PRIVACY_COMMAND, commands.privacy))
    app.add_handler(CommandHandler(commands.COMPARE_COMMAND, commands.compare))
    app.add_handler(CommandHandler(commands.VIBE_COMMAND, commands.vibe))
    app.add_handler(CommandHandler(commands.ROAST_COMMAND, commands.roast))
    app.add_handler(CommandHandler(commands.RECOMMEND_COMMAND, commands.recommend))

    app.add_handler(CallbackQueryHandler(commands.button_handler))

    # Add global error handler
    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
