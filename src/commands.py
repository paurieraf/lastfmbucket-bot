import logging
from typing import Optional

import telegram.constants
from dotenv import load_dotenv
from emoji import emojize
from telegram import LinkPreviewOptions, Update
from telegram.ext import ContextTypes

import lastfm
from services import ViewService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Command constants
START_COMMAND = "start"
STATUS_COMMAND = "status"
NOW_PLAYING_COMMAND = "np"
TOPS_COMMAND = "tops"
PREFERENCES_COMMAND = "preferences"
HELP_COMMAND = "help"
CHANGELOG_COMMAND = "changelog"
SET_COMMAND = "set"
PRIVACY_COMMAND = "privacy"


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()

    view_service: ViewService = context.bot_data["view_service"]

    if query.data == view_service.NOW_PLAYING_LESS_INFO:
        await now_playing(update, context)
    elif query.data == view_service.NOW_PLAYING_LESS_INFO_SHOW_COVER:
        await now_playing(update, context, show_cover=True)
    elif query.data == view_service.NOW_PLAYING_MORE_INFO:
        await status(update, context, show_cover=True)
    elif query.data == view_service.PREFERENCES_UNLINK_ACCOUNT:
        await unlink_account(update, context)
    elif query.data.startswith(view_service.TOPS_PREFIX):
        await tops(update, context)
    else:
        logger.error(f"No button handler found for data: {query.data}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message to the user."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- id: {update.message.from_user.id} started a private chat with the bot"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_start_response(update.message.from_user)
    await update.message.reply_text(response)


async def now_playing(
    update: Update, context: ContextTypes.DEFAULT_TYPE, show_cover: bool = False
) -> None:
    """Fetches and displays the user's currently playing track."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.message
    from_user = (
        update.callback_query.from_user if from_button else update.message.from_user
    )

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_np_response(
        from_user, show_cover
    )

    if from_button and show_cover and cover_url:
        await message.edit_media(
            telegram.InputMediaPhoto(
                media=cover_url,
                caption=response,
                parse_mode=telegram.constants.ParseMode.HTML,
            ),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


async def lastfm_username_set(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sets the user's Last.fm username."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    if not context.args:
        await update.message.reply_text("Please provide a Last.fm username.")
        return

    lastfm_username = context.args[0]
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_lastfm_username_set_response(
        telegram_user=update.message.from_user, lastfm_username=lastfm_username
    )
    await update.message.reply_text(response)


async def status(
    update: Update, context: ContextTypes.DEFAULT_TYPE, show_cover: bool = False
) -> None:
    """Fetches and displays the user's recent tracks."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.message
    from_user = (
        update.callback_query.from_user if from_button else update.message.from_user
    )

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_status_response(
        from_user, show_cover
    )

    if from_button and show_cover:
        await message.edit_media(
            telegram.InputMediaPhoto(
                media=cover_url,
                caption=response,
                parse_mode=telegram.constants.ParseMode.HTML,
            ),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


async def tops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user's top artists, albums or tracks."""
    entity_type = None
    period = None

    if update.callback_query:
        logger.info(
            f"username: {update.callback_query.from_user.username} "
            f"- pressed button: {update.callback_query.data}"
        )
        message = update.callback_query.message
        from_user = update.callback_query.from_user
        is_callback = True

        data_parts = update.callback_query.data.split("_")
        if len(data_parts) > 1:
            entity_type = lastfm.EntityType(data_parts[1])
        if len(data_parts) > 2:
            period = lastfm.Period(data_parts[2])
    else:
        logger.info(
            f"username: {update.message.from_user.username} "
            f"- issued command: {update.message.text}"
        )
        message = update.message
        from_user = update.message.from_user
        is_callback = False

        if context.args:
            try:
                arg0 = context.args[0].lower()
                if arg0 in ["artists", "artist"]:
                    entity_type = lastfm.EntityType.ARTIST
                elif arg0 in ["albums", "album"]:
                    entity_type = lastfm.EntityType.ALBUM
                elif arg0 in ["tracks", "track"]:
                    entity_type = lastfm.EntityType.TRACK
            except (IndexError, ValueError):
                pass

        if len(context.args) > 1:
            try:
                arg1 = context.args[1].lower()
                if arg1 in ["1week", "week"]:
                    period = lastfm.Period.WEEK
                elif arg1 in ["1month", "month"]:
                    period = lastfm.Period.ONE_MONTH
                elif arg1 in ["3months", "3month"]:
                    period = lastfm.Period.THREE_MONTHS
                elif arg1 in ["6months", "6month"]:
                    period = lastfm.Period.SIX_MONTHS
                elif arg1 in ["12months", "12month", "year"]:
                    period = lastfm.Period.YEAR
                elif arg1 in ["overall", "alltime"]:
                    period = lastfm.Period.OVERALL
            except (IndexError, ValueError):
                pass

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_tops_response(
        from_user.id, entity_type, period
    )

    if is_callback:
        await message.edit_text(
            response,
            reply_markup=reply_markup,
            parse_mode=telegram.constants.ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user preferences options."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_preferences_response()
    await update.message.reply_html(response, reply_markup=reply_markup)


async def unlink_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unlinks a user's Last.fm account."""
    query = update.callback_query
    view_service: ViewService = context.bot_data["view_service"]
    response = view_service.build_preferences_unlink_account_response(
        query.from_user.id
    )
    await query.edit_message_text(text=response)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the bot's description as help text."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    bot_description = (await context.bot.get_my_description()).description
    await update.message.reply_text(emojize(bot_description))


async def changelog(update: Update, context: ContextTypes.DEFAULT_TPE) -> None:
    """TODO: Implement changelog command."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    await update.message.reply_text("Hello!")


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the privacy policy."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    message = await view_service.build_privacy_response()
    await update.message.reply_html(message)
